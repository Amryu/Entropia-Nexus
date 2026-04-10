import os
import json
import tempfile
import unittest
from datetime import datetime

from client.core.database import Database


class TestEnhancerTimelineDB(unittest.TestCase):

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db = Database(self.path)
        self.session_id = "s1"
        self.db.insert_hunt_session(
            self.session_id, datetime(2026, 1, 1).isoformat(),
        )

    def tearDown(self):
        try:
            self.db.close()
        except Exception:
            pass
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def test_anchored_event_round_trip(self):
        delta = json.dumps({"Economy": 2})
        event_id = self.db.insert_anchored_loadout_event(
            self.session_id,
            timestamp=datetime.utcnow().isoformat(),
            event_type="enhancer_adjust",
            anchor_kind="session_start",
            enhancer_delta=delta,
            description="test note",
        )
        self.assertIsNotNone(event_id)
        rows = self.db.get_anchored_loadout_events(self.session_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["anchor_kind"], "session_start")
        self.assertEqual(rows[0]["description"], "test note")

    def test_anchored_filter_excludes_legacy(self):
        self.db.insert_loadout_event(
            self.session_id,
            timestamp=datetime.utcnow().isoformat(),
            event_type="loadout_snapshot",
        )
        self.db.insert_anchored_loadout_event(
            self.session_id,
            timestamp=datetime.utcnow().isoformat(),
            event_type="enhancer_adjust",
            anchor_kind="hunt_start",
        )
        anchored = self.db.get_anchored_loadout_events(self.session_id)
        self.assertEqual(len(anchored), 1)

        all_events = self.db.get_session_loadout_events(self.session_id)
        self.assertEqual(len(all_events), 2)


if __name__ == "__main__":
    unittest.main()
