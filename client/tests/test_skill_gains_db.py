"""Tests for compact skill_gains table: migration, insert, and query methods."""

import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from client.core.database import Database


class TestSkillGainsCompact(unittest.TestCase):
    """Test the new compact skill_gains schema on a fresh database."""

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.db = Database(self._tmp.name)

    def tearDown(self):
        self.db.close()
        Path(self._tmp.name).unlink(missing_ok=True)

    def test_fresh_schema_has_compact_columns(self):
        conn = sqlite3.connect(self._tmp.name)
        cur = conn.execute("PRAGMA table_info(skill_gains)")
        cols = {row[1] for row in cur.fetchall()}
        conn.close()
        self.assertIn("ts", cols)
        self.assertIn("skill_id", cols)
        self.assertIn("amount", cols)
        self.assertNotIn("skill_name", cols)
        self.assertNotIn("is_attribute", cols)
        self.assertNotIn("session_id", cols)

    def test_insert_and_query(self):
        ts = int(datetime(2026, 3, 1, 12, 0, 0).timestamp())
        self.db.insert_skill_gain(ts=ts, skill_id=10, amount=0.5)
        self.db.insert_skill_gain(ts=ts + 1, skill_id=10, amount=0.3)
        self.db.insert_skill_gain(ts=ts + 2, skill_id=20, amount=1.0)

        gains = self.db.get_skill_gains_since(ts)
        self.assertAlmostEqual(gains[10], 0.8)
        self.assertAlmostEqual(gains[20], 1.0)

    def test_query_since_filters_old(self):
        old_ts = 1000
        new_ts = 2000
        self.db.insert_skill_gain(ts=old_ts, skill_id=10, amount=5.0)
        self.db.insert_skill_gain(ts=new_ts, skill_id=10, amount=1.0)

        gains = self.db.get_skill_gains_since(new_ts)
        self.assertAlmostEqual(gains.get(10, 0), 1.0)

    def test_last_scan_timestamp_none_when_empty(self):
        self.assertIsNone(self.db.get_last_scan_timestamp())

    def test_last_scan_timestamp(self):
        self.db.insert_skill_snapshot(
            scan_timestamp="2026-03-01T12:00:00",
            skill_name="Aim", rank="Expert",
            current_points=3500.0, progress_percent=50.0,
            category="Combat",
        )
        ts = self.db.get_last_scan_timestamp()
        self.assertIsNotNone(ts)
        self.assertIsInstance(ts, int)
        self.assertGreater(ts, 0)

    def test_latest_skill_values_merges_local_state_and_snapshots(self):
        self.db.insert_skill_snapshot(
            scan_timestamp="2026-03-01T12:00:00",
            skill_name="Aim", rank="Expert",
            current_points=100.0, progress_percent=50.0,
            category="Combat",
        )
        self.db.upsert_local_skill_values(
            {"Evade": 200.0, "Aim": 150.0},
            source="test",
            dirty=False,
        )

        values = self.db.get_latest_skill_values()
        self.assertAlmostEqual(values["Aim"], 150.0)   # local overrides snapshot
        self.assertAlmostEqual(values["Evade"], 200.0)


class TestSkillGainsMigration(unittest.TestCase):
    """Test migration from old TEXT-based schema to compact format."""

    def test_migration_converts_data(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        try:
            # Create old-format DB manually
            conn = sqlite3.connect(tmp.name)
            conn.execute("""
                CREATE TABLE skill_gains (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    skill_name TEXT NOT NULL,
                    amount REAL NOT NULL,
                    is_attribute INTEGER NOT NULL,
                    session_id TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS skill_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_timestamp TEXT NOT NULL,
                    skill_name TEXT NOT NULL,
                    rank TEXT NOT NULL,
                    current_points REAL NOT NULL,
                    progress_percent REAL NOT NULL,
                    category TEXT NOT NULL
                )
            """)
            # Insert old-format rows ("Aim" has id=1 in skill_reference.json — check dynamically)
            from client.skills.skill_ids import name_to_id_map
            known = name_to_id_map()
            test_skill = next(iter(known))  # Pick any known skill
            test_id = known[test_skill]

            conn.execute(
                "INSERT INTO skill_gains (timestamp, skill_name, amount, is_attribute) "
                "VALUES (?, ?, ?, ?)",
                ("2026-03-01T12:00:00", test_skill, 0.1234, 0),
            )
            conn.execute(
                "INSERT INTO skill_gains (timestamp, skill_name, amount, is_attribute) "
                "VALUES (?, ?, ?, ?)",
                ("2026-03-01T12:01:00", "UnknownFakeSkill", 0.5, 0),
            )
            conn.commit()
            conn.close()

            # Open with Database — triggers migration
            db = Database(tmp.name)

            # Verify new schema
            conn2 = sqlite3.connect(tmp.name)
            cur = conn2.execute("PRAGMA table_info(skill_gains)")
            cols = {row[1] for row in cur.fetchall()}
            self.assertIn("ts", cols)
            self.assertIn("skill_id", cols)
            self.assertNotIn("skill_name", cols)

            # Verify migrated data
            cur = conn2.execute("SELECT skill_id, amount FROM skill_gains")
            rows = cur.fetchall()
            conn2.close()

            # Only the known skill should have been migrated
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][0], test_id)
            self.assertAlmostEqual(rows[0][1], 0.1234)

            db.close()
        finally:
            Path(tmp.name).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
