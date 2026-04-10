import os
import tempfile
import unittest
from datetime import datetime

from client.core.database import Database
from client.hunt.session import EncounterLootItem


class TestLootEditorDB(unittest.TestCase):

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db = Database(self.path)
        self.session_id = "s1"
        self.db.insert_hunt_session(
            self.session_id, datetime(2026, 1, 1).isoformat(),
        )
        self.enc_id = "e1"
        self.db.insert_mob_encounter(
            self.enc_id, self.session_id, "Atrox", "ocr",
            datetime(2026, 1, 1, 12, 0, 0).isoformat(),
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

    def test_replace_loot_items(self):
        initial = [
            EncounterLootItem(item_name="Shrapnel", quantity=100, value_ped=1.0),
            EncounterLootItem(item_name="Lyst", quantity=5, value_ped=2.5),
        ]
        self.db.insert_encounter_loot_items(self.enc_id, initial)
        loaded = self.db.get_encounter_loot_items(self.enc_id)
        self.assertEqual(len(loaded), 2)

        # Replace with a different set.
        replacement = [
            EncounterLootItem(item_name="Shrapnel", quantity=50, value_ped=0.5),
        ]
        self.db.replace_encounter_loot_items(self.enc_id, replacement)

        loaded2 = self.db.get_encounter_loot_items(self.enc_id)
        self.assertEqual(len(loaded2), 1)
        self.assertEqual(loaded2[0]["item_name"], "Shrapnel")
        self.assertAlmostEqual(loaded2[0]["value_ped"], 0.5)

    def test_replace_with_empty_clears_rows(self):
        self.db.insert_encounter_loot_items(self.enc_id, [
            EncounterLootItem(item_name="Shrapnel", quantity=1, value_ped=0.1),
        ])
        self.db.replace_encounter_loot_items(self.enc_id, [])
        self.assertEqual(self.db.get_encounter_loot_items(self.enc_id), [])

    def test_update_mob_encounter_loot_total(self):
        self.db.update_mob_encounter(self.enc_id, loot_total_ped=42.5)
        row = self.db.get_hunt_session(self.session_id)
        self.assertIsNotNone(row)
        # Re-query the encounter row directly.
        rows = self.db.get_session_encounters(self.session_id)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["loot_total_ped"], 42.5)


class TestListHuntSessions(unittest.TestCase):

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db = Database(self.path)

    def tearDown(self):
        try:
            self.db.close()
        except Exception:
            pass
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def test_list_sessions_in_descending_order(self):
        self.db.insert_hunt_session("a", datetime(2026, 1, 1).isoformat())
        self.db.insert_hunt_session("b", datetime(2026, 2, 1).isoformat())
        self.db.insert_hunt_session("c", datetime(2026, 3, 1).isoformat())
        rows = self.db.list_hunt_sessions(limit=10)
        self.assertEqual([r["id"] for r in rows], ["c", "b", "a"])


if __name__ == "__main__":
    unittest.main()
