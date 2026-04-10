import os
import tempfile
import unittest
from datetime import datetime

from client.core.database import Database
from client.hunt.markup_resolver import MarkupResolver


class _StubNexus:
    def is_authenticated(self):
        return False


class TestSessionMarkupResolver(unittest.TestCase):

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db = Database(self.path)
        self.resolver = MarkupResolver(self.db, nexus_client=None, data_client=None)
        # Seed a hunt session row so the session_item_markups blob can
        # be persisted against it.
        self.session_id = "sess-1"
        self.db.insert_hunt_session(
            self.session_id, datetime(2026, 1, 1).isoformat(),
            loadout_id=None, primary_mob=None,
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

    def test_session_override_wins_over_default(self):
        self.db.set_session_item_markup(self.session_id, "Foo", 150.0, "percentage")
        result = self.resolver.resolve("Foo", session_id=self.session_id)
        self.assertEqual(result.source, "session")
        self.assertAlmostEqual(result.markup_value, 150.0)

    def test_session_override_wins_over_custom(self):
        # Custom global markup first.
        self.db.set_custom_markup("Bar", 120.0, "percentage",
                                  updated_at=datetime.utcnow().isoformat())
        # Then a session-scoped override that should take precedence.
        self.db.set_session_item_markup(self.session_id, "Bar", 180.0, "percentage")
        result = self.resolver.resolve("Bar", session_id=self.session_id)
        self.assertEqual(result.source, "session")
        self.assertAlmostEqual(result.markup_value, 180.0)

    def test_no_session_id_falls_through(self):
        self.db.set_session_item_markup(self.session_id, "Baz", 150.0, "percentage")
        result = self.resolver.resolve("Baz")
        self.assertNotEqual(result.source, "session")

    def test_clearing_entry(self):
        self.db.set_session_item_markup(self.session_id, "Qux", 200.0, "percentage")
        self.db.set_session_item_markup(self.session_id, "Qux", None)
        blob = self.db.get_session_item_markups(self.session_id)
        self.assertNotIn("qux", blob)


if __name__ == "__main__":
    unittest.main()
