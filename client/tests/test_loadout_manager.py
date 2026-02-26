import json
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from client.core.database import Database
from client.hunt.session import HuntSession, SessionLoadoutEntry
from client.hunt.tool_inference import ToolInferenceEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**overrides):
    """Create a mock config with sensible defaults."""
    config = MagicMock()
    config.active_loadout_id = overrides.get("active_loadout_id", "loadout-1")
    config.js_utils_path = overrides.get("js_utils_path", "")
    config.encounter_close_timeout_ms = 15000
    config.attribution_window_ms = 3000
    config.session_auto_timeout_ms = 3600000
    config.hunt_split_mob_threshold = 10
    config.hunt_split_min_remote_kills = 5
    return config


def _make_loadout(weapon_name="Armatrix LR-35 (L)", loadout_id="loadout-1"):
    """Create a minimal loadout dict matching the website format."""
    return {
        "Id": loadout_id,
        "Gear": {"Weapon": {"Name": weapon_name}},
    }


def _make_stats(cost=0.15, damage_min=30.0, damage_max=60.0, total_damage=50.0):
    """Create a mock LoadoutStats object."""
    stats = MagicMock()
    stats.cost = cost
    stats.damage_interval_min = damage_min
    stats.damage_interval_max = damage_max
    stats.total_damage = total_damage
    return stats


def _make_session(session_id="session-1"):
    """Create a HuntSession for testing."""
    return HuntSession(id=session_id, start_time=datetime(2026, 2, 26, 12, 0, 0))


# ---------------------------------------------------------------------------
# SessionLoadoutEntry dataclass tests
# ---------------------------------------------------------------------------

class TestSessionLoadoutEntry(unittest.TestCase):
    def test_defaults(self):
        entry = SessionLoadoutEntry()
        self.assertIsNone(entry.id)
        self.assertEqual(entry.session_id, "")
        self.assertIsNone(entry.weapon_name)
        self.assertAlmostEqual(entry.cost_per_shot, 0.0)
        self.assertAlmostEqual(entry.damage_min, 0.0)
        self.assertAlmostEqual(entry.damage_max, 0.0)
        self.assertEqual(entry.source, "snapshot")
        self.assertEqual(entry.loadout_data, {})

    def test_custom_values(self):
        entry = SessionLoadoutEntry(
            id=42, session_id="s1", weapon_name="Gun",
            cost_per_shot=0.15, damage_min=30.0, damage_max=60.0,
            source="user_edit",
        )
        self.assertEqual(entry.id, 42)
        self.assertEqual(entry.session_id, "s1")
        self.assertEqual(entry.weapon_name, "Gun")
        self.assertAlmostEqual(entry.cost_per_shot, 0.15)
        self.assertEqual(entry.source, "user_edit")


# ---------------------------------------------------------------------------
# SessionLoadoutManager tests
# ---------------------------------------------------------------------------

class TestSessionLoadoutManager(unittest.TestCase):
    """Tests for SessionLoadoutManager core snapshot logic.

    Uses mocked calculator (patched _evaluate) to avoid needing the JS bridge.
    """

    def setUp(self):
        self.config = _make_config()
        self.db = MagicMock()
        self.db.insert_session_loadout.return_value = 1
        self.data_client = MagicMock()
        self.tool_inference = ToolInferenceEngine()
        self.session = _make_session()
        self.stats = _make_stats()
        self.loadout = _make_loadout()

        # Import and create manager with mocked _evaluate to avoid JS bridge
        from client.hunt.loadout_manager import SessionLoadoutManager
        self.mgr = SessionLoadoutManager(
            self.config, self.db, self.data_client, self.tool_inference
        )
        # Pre-load active loadout so start_session doesn't try file I/O
        self.mgr._active_loadout = self.loadout
        self.mgr._active_stats = self.stats

    def _patch_evaluate(self):
        """Patch _evaluate to return known weapon + stats without JS bridge."""
        return patch.object(
            self.mgr, '_evaluate',
            return_value=("Armatrix LR-35 (L)", self.stats)
        )

    def test_start_session_creates_snapshot(self):
        with self._patch_evaluate():
            self.mgr.start_session(self.session)
        self.db.insert_session_loadout.assert_called_once()
        self.assertEqual(len(self.session.loadout_entries), 1)
        entry = self.session.loadout_entries[0]
        self.assertEqual(entry.weapon_name, "Armatrix LR-35 (L)")
        self.assertEqual(entry.source, "snapshot")

    def test_start_session_no_loadout_no_crash(self):
        self.mgr._active_loadout = None
        # Mock load_active_loadout to also not find anything
        with patch.object(self.mgr, 'load_active_loadout'):
            self.mgr.start_session(self.session)
        self.db.insert_session_loadout.assert_not_called()
        self.assertEqual(len(self.session.loadout_entries), 0)

    def test_on_combat_sets_flag(self):
        self.mgr.on_combat()
        self.assertTrue(self.mgr._combat_since_last_snapshot)

    def test_on_loot_sets_flag(self):
        self.mgr.on_loot()
        self.assertTrue(self.mgr._loot_since_last_snapshot)

    def test_loadout_change_after_combat_creates_snapshot(self):
        with self._patch_evaluate():
            self.mgr.start_session(self.session)
            self.mgr.on_combat()
            new_stats = _make_stats(cost=0.25, damage_min=40.0, damage_max=80.0)
            self.mgr.on_active_loadout_changed(
                _make_loadout("New Weapon"), "New Weapon", new_stats
            )
        # Initial snapshot + new snapshot after combat
        self.assertEqual(self.db.insert_session_loadout.call_count, 2)
        self.assertEqual(len(self.session.loadout_entries), 2)

    def test_loadout_change_without_combat_no_duplicate(self):
        with self._patch_evaluate():
            self.mgr.start_session(self.session)
            # Change loadout without any combat
            self.mgr.on_active_loadout_changed(
                _make_loadout("New Weapon"), "New Weapon", _make_stats()
            )
        # Only initial snapshot — no new one since no combat
        self.assertEqual(self.db.insert_session_loadout.call_count, 1)
        self.assertEqual(len(self.session.loadout_entries), 1)

    def test_loot_seals_snapshot(self):
        with self._patch_evaluate():
            self.mgr.start_session(self.session)
            self.mgr.on_combat()
            self.mgr.on_loot()  # Seals current snapshot
            self.mgr.on_active_loadout_changed(
                _make_loadout("New Weapon"), "New Weapon", _make_stats()
            )
        # Initial + post-loot change = 2
        self.assertEqual(self.db.insert_session_loadout.call_count, 2)

    def test_end_session_clears_state(self):
        with self._patch_evaluate():
            self.mgr.start_session(self.session)
            self.mgr.on_combat()
        self.mgr.end_session()
        self.assertIsNone(self.mgr._session)
        self.assertFalse(self.mgr._combat_since_last_snapshot)
        self.assertFalse(self.mgr._loot_since_last_snapshot)

    def test_snapshot_stores_correct_fields(self):
        with self._patch_evaluate():
            self.mgr.start_session(self.session)
        call_args = self.db.insert_session_loadout.call_args
        args = call_args[0]
        self.assertEqual(args[0], "session-1")         # session_id
        self.assertIn("loadout-1", args[2])             # loadout_data JSON contains Id
        self.assertEqual(args[3], "Armatrix LR-35 (L)") # weapon_name
        self.assertAlmostEqual(args[4], 0.15)           # cost_per_shot
        self.assertAlmostEqual(args[5], 30.0)           # damage_min
        self.assertAlmostEqual(args[6], 60.0)           # damage_max
        self.assertEqual(args[7], "snapshot")            # source

    def test_snapshot_loads_signature_into_inference(self):
        with self._patch_evaluate():
            self.mgr.start_session(self.session)
        # After session start, tool inference should have the weapon signature
        self.assertTrue(self.tool_inference.has_signatures)
        name, conf, cost = self.tool_inference.infer_tool(45.0)
        self.assertEqual(name, "Armatrix LR-35 (L)")

    def test_auto_detect_after_threshold(self):
        with self._patch_evaluate():
            self.mgr.start_session(self.session)
        # Simulate 3 unmatched damage values (threshold)
        self.mgr.on_unmatched_damage(100.0)
        self.mgr.on_unmatched_damage(120.0)
        self.mgr.on_unmatched_damage(110.0)
        # Should have created an auto-detected entry (initial + auto)
        self.assertEqual(self.db.insert_session_loadout.call_count, 2)
        auto_entry = self.session.loadout_entries[-1]
        self.assertEqual(auto_entry.source, "auto_detected")
        self.assertEqual(auto_entry.weapon_name, "Unknown weapon")
        self.assertAlmostEqual(auto_entry.damage_min, 100.0)
        self.assertAlmostEqual(auto_entry.damage_max, 120.0)

    def test_auto_detect_clears_after_creation(self):
        with self._patch_evaluate():
            self.mgr.start_session(self.session)
        for _ in range(3):
            self.mgr.on_unmatched_damage(50.0)
        # After auto-detect, further single values don't trigger
        self.mgr.on_unmatched_damage(55.0)
        # Still just 2 inserts (initial + 1 auto-detect)
        self.assertEqual(self.db.insert_session_loadout.call_count, 2)

    def test_auto_detect_no_session_ignored(self):
        # No session active — should not crash
        self.mgr.on_unmatched_damage(100.0)
        self.mgr.on_unmatched_damage(120.0)
        self.mgr.on_unmatched_damage(110.0)
        self.db.insert_session_loadout.assert_not_called()


# ---------------------------------------------------------------------------
# Database CRUD tests (real in-memory SQLite)
# ---------------------------------------------------------------------------

class TestDatabaseSessionLoadouts(unittest.TestCase):
    """Integration tests for session_loadouts table using in-memory SQLite."""

    def setUp(self):
        self.db = Database(":memory:")
        # Insert a parent session for FK integrity
        self.db.insert_hunt_session("session-1", "2026-02-26T12:00:00")

    def tearDown(self):
        self.db.close()

    def test_insert_session_loadout(self):
        row_id = self.db.insert_session_loadout(
            "session-1", "2026-02-26T12:00:00", '{"Id": "lo-1"}',
            "WeaponA", 0.15, 30.0, 60.0, "snapshot",
        )
        self.assertIsInstance(row_id, int)
        self.assertGreater(row_id, 0)

    def test_get_session_loadouts(self):
        self.db.insert_session_loadout(
            "session-1", "2026-02-26T12:00:00", '{}',
            "Gun1", 0.10, 20.0, 40.0, "snapshot",
        )
        self.db.insert_session_loadout(
            "session-1", "2026-02-26T12:05:00", '{}',
            "Gun2", 0.20, 30.0, 50.0, "external_update",
        )
        rows = self.db.get_session_loadouts("session-1")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["weapon_name"], "Gun1")
        self.assertEqual(rows[1]["weapon_name"], "Gun2")

    def test_get_latest_session_loadout(self):
        self.db.insert_session_loadout(
            "session-1", "2026-02-26T12:00:00", '{}',
            "OldGun", 0.10, 20.0, 40.0, "snapshot",
        )
        self.db.insert_session_loadout(
            "session-1", "2026-02-26T12:05:00", '{}',
            "NewGun", 0.20, 30.0, 50.0, "external_update",
        )
        latest = self.db.get_latest_session_loadout("session-1")
        self.assertIsNotNone(latest)
        self.assertEqual(latest["weapon_name"], "NewGun")

    def test_update_session_loadout(self):
        row_id = self.db.insert_session_loadout(
            "session-1", "2026-02-26T12:00:00", '{}',
            "OldName", 0.10, 20.0, 40.0, "snapshot",
        )
        self.db.update_session_loadout(row_id, weapon_name="NewName", cost_per_shot=0.25)
        rows = self.db.get_session_loadouts("session-1")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["weapon_name"], "NewName")
        self.assertAlmostEqual(rows[0]["cost_per_shot"], 0.25)

    def test_delete_hunt_session_cascades(self):
        self.db.insert_session_loadout(
            "session-1", "2026-02-26T12:00:00", '{}',
            "Gun", 0.10, 20.0, 40.0, "snapshot",
        )
        self.db.insert_session_loadout(
            "session-1", "2026-02-26T12:05:00", '{}',
            "Gun2", 0.20, 30.0, 50.0, "external_update",
        )
        self.db.delete_hunt_session("session-1")
        rows = self.db.get_session_loadouts("session-1")
        self.assertEqual(len(rows), 0)

    def test_get_session_loadouts_empty(self):
        rows = self.db.get_session_loadouts("nonexistent")
        self.assertEqual(rows, [])

    def test_get_latest_session_loadout_none(self):
        result = self.db.get_latest_session_loadout("nonexistent")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Tracker cost accumulation integration tests
# ---------------------------------------------------------------------------

class TestTrackerCostAccumulation(unittest.TestCase):
    """Integration test: damage events should accumulate cost via tool inference."""

    def setUp(self):
        self.config = _make_config()
        self.db = MagicMock()
        self.db.insert_session_loadout.return_value = 1
        self.event_bus = MagicMock()
        self.data_client = MagicMock()

    def _make_tracker(self):
        from client.hunt.tracker import HuntTracker
        tracker = HuntTracker(self.config, self.event_bus, self.db, self.data_client)
        # Mark as live (past catchup)
        tracker._live = True
        return tracker

    def _fire_damage(self, tracker, amount, event_type="damage_dealt"):
        """Simulate a combat event with the given damage amount."""
        event = MagicMock()
        event.event_type = MagicMock()
        event.event_type.value = event_type
        event.amount = amount
        event.timestamp = "2026-02-26T12:01:00"
        tracker._on_combat(event)

    def test_damage_accumulates_cost(self):
        tracker = self._make_tracker()
        # Load a weapon signature directly
        tracker._tool_inference.load_signature("Gun", 30.0, 60.0, 50.0, 0.15)
        # Fire 3 damage events within range
        self._fire_damage(tracker, 45.0)
        self._fire_damage(tracker, 50.0)
        self._fire_damage(tracker, 35.0)
        enc = tracker._manager.current_encounter
        self.assertIsNotNone(enc)
        self.assertAlmostEqual(enc.cost, 0.45)

    def test_no_signature_zero_cost(self):
        tracker = self._make_tracker()
        self._fire_damage(tracker, 45.0)
        self._fire_damage(tracker, 50.0)
        enc = tracker._manager.current_encounter
        self.assertIsNotNone(enc)
        self.assertAlmostEqual(enc.cost, 0.0)

    def test_inferred_tool_recorded_on_event(self):
        tracker = self._make_tracker()
        tracker._tool_inference.load_signature("Gun", 30.0, 60.0, 50.0, 0.15)
        self._fire_damage(tracker, 45.0)
        # Check that insert_combat_event_detail was called with the inferred tool
        call_args = self.db.insert_combat_event_detail.call_args
        args = call_args[0]
        tool_name = args[5]
        tool_source = args[6]
        self.assertEqual(tool_name, "Gun")
        self.assertEqual(tool_source, "inferred")


# ---------------------------------------------------------------------------
# Database: get_incomplete_session tests
# ---------------------------------------------------------------------------

class TestDatabaseIncompleteSession(unittest.TestCase):
    """Tests for get_incomplete_session() query."""

    def setUp(self):
        self.db = Database(":memory:")

    def tearDown(self):
        self.db.close()

    def test_get_incomplete_session_returns_open(self):
        self.db.insert_hunt_session("s1", "2026-02-26T12:00:00")
        result = self.db.get_incomplete_session()
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "s1")
        self.assertIsNone(result["end_time"])

    def test_get_incomplete_session_none_when_all_closed(self):
        self.db.insert_hunt_session("s1", "2026-02-26T12:00:00")
        self.db.end_hunt_session("s1", "2026-02-26T13:00:00")
        result = self.db.get_incomplete_session()
        self.assertIsNone(result)

    def test_get_incomplete_session_returns_latest(self):
        self.db.insert_hunt_session("s1", "2026-02-26T10:00:00")
        self.db.insert_hunt_session("s2", "2026-02-26T12:00:00")
        result = self.db.get_incomplete_session()
        self.assertEqual(result["id"], "s2")

    def test_get_incomplete_session_empty_db(self):
        result = self.db.get_incomplete_session()
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Session restore tests
# ---------------------------------------------------------------------------

class TestSessionRestore(unittest.TestCase):
    """Tests for _try_restore_session on HuntTracker."""

    def setUp(self):
        self.config = _make_config()
        self.db = Database(":memory:")
        self.event_bus = MagicMock()
        self.data_client = MagicMock()

    def tearDown(self):
        self.db.close()

    def _make_tracker(self):
        from client.hunt.tracker import HuntTracker
        tracker = HuntTracker(self.config, self.event_bus, self.db, self.data_client)
        tracker._live = True
        return tracker

    def _insert_full_session(self):
        """Insert a session with encounters, hunts, and loadout for restore testing."""
        self.db.insert_hunt_session("s1", "2026-02-26T12:00:00")

        # Insert a hunt
        self.db.insert_hunt("h1", "s1", "2026-02-26T12:00:00", "Atrox")

        # Insert completed encounters
        self.db.insert_mob_encounter("e1", "s1", "Atrox", "ocr", "2026-02-26T12:01:00", "h1")
        self.db.update_mob_encounter(
            "e1", end_time="2026-02-26T12:02:00",
            damage_dealt=100.0, damage_taken=50.0,
            loot_total_ped=5.0, cost=0.45, shots_fired=3,
        )
        self.db.insert_mob_encounter("e2", "s1", "Atrox", "ocr", "2026-02-26T12:03:00", "h1")
        self.db.update_mob_encounter(
            "e2", end_time="2026-02-26T12:04:00",
            damage_dealt=120.0, damage_taken=60.0,
            loot_total_ped=3.0, cost=0.45, shots_fired=3,
        )

        # Insert loadout snapshot
        self.db.insert_session_loadout(
            "s1", "2026-02-26T12:00:00", '{"Id": "lo-1"}',
            "TestGun", 0.15, 30.0, 60.0, "snapshot",
        )

    def test_restore_incomplete_session(self):
        self._insert_full_session()
        tracker = self._make_tracker()
        tracker._try_restore_session()

        self.assertIsNotNone(tracker._session)
        self.assertEqual(tracker._session.id, "s1")
        self.assertEqual(len(tracker._session.encounters), 2)
        self.assertEqual(len(tracker._session.hunts), 1)
        self.assertEqual(tracker._session.hunts[0].primary_mob, "Atrox")
        self.assertTrue(tracker._active)

    def test_restore_no_incomplete_session(self):
        tracker = self._make_tracker()
        tracker._try_restore_session()
        self.assertIsNone(tracker._session)
        self.assertFalse(tracker._active)

    def test_restore_skips_partial_encounters(self):
        self.db.insert_hunt_session("s1", "2026-02-26T12:00:00")
        self.db.insert_mob_encounter("e1", "s1", "Atrox", "ocr", "2026-02-26T12:01:00")
        # e1 has no end_time — partial encounter

        self.db.insert_mob_encounter("e2", "s1", "Atrox", "ocr", "2026-02-26T12:03:00")
        self.db.update_mob_encounter("e2", end_time="2026-02-26T12:04:00",
                                     damage_dealt=100.0, cost=0.45)

        tracker = self._make_tracker()
        tracker._try_restore_session()

        self.assertEqual(len(tracker._session.encounters), 1)
        self.assertEqual(tracker._session.encounters[0].id, "e2")
        # Partial encounter ID should still be tracked as persisted
        self.assertIn("e1", tracker._persisted_encounter_ids)

    def test_restore_loads_weapon_signatures(self):
        self._insert_full_session()
        tracker = self._make_tracker()
        tracker._try_restore_session()

        self.assertTrue(tracker._tool_inference.has_signatures)
        name, _conf, cost = tracker._tool_inference.infer_tool(45.0)
        self.assertEqual(name, "TestGun")
        self.assertAlmostEqual(cost, 0.15)

    def test_restore_publishes_events(self):
        self._insert_full_session()
        tracker = self._make_tracker()
        tracker._try_restore_session()

        # Check that session started was published
        calls = [c[0][0] for c in self.event_bus.publish.call_args_list]
        self.assertIn("hunt_session_started", calls)
        self.assertIn("hunt_session_updated", calls)
        # 2 encounters should be published
        encounter_ended_calls = [c for c in calls if c == "hunt_encounter_ended"]
        self.assertEqual(len(encounter_ended_calls), 2)

    def test_restore_seeds_hunt_detector(self):
        self._insert_full_session()
        tracker = self._make_tracker()
        tracker._try_restore_session()

        self.assertIsNotNone(tracker._hunt_detector)
        self.assertIsNotNone(tracker._hunt_detector.current_hunt)
        self.assertEqual(tracker._hunt_detector.current_hunt.id, "h1")
        self.assertEqual(len(tracker._hunt_detector.current_hunt.encounters), 2)

    def test_restore_loads_loot_items(self):
        self.db.insert_hunt_session("s1", "2026-02-26T12:00:00")
        self.db.insert_mob_encounter("e1", "s1", "Atrox", "ocr", "2026-02-26T12:01:00")
        self.db.update_mob_encounter("e1", end_time="2026-02-26T12:02:00",
                                     loot_total_ped=10.0)
        # Insert loot items using raw SQL since insert_encounter_loot_items expects objects
        from client.hunt.session import EncounterLootItem
        items = [EncounterLootItem("Shrapnel", 50, 5.0),
                 EncounterLootItem("Animal Oil Residue", 10, 3.0)]
        self.db.insert_encounter_loot_items("e1", items)

        tracker = self._make_tracker()
        tracker._try_restore_session()

        enc = tracker._session.encounters[0]
        self.assertEqual(len(enc.loot_items), 2)
        self.assertEqual(enc.loot_items[0].item_name, "Shrapnel")

    def test_restore_closed_session_not_restored(self):
        self.db.insert_hunt_session("s1", "2026-02-26T12:00:00")
        self.db.end_hunt_session("s1", "2026-02-26T13:00:00")

        tracker = self._make_tracker()
        tracker._try_restore_session()
        self.assertIsNone(tracker._session)
        self.assertFalse(tracker._active)


# ---------------------------------------------------------------------------
# Loadout manager restore tests
# ---------------------------------------------------------------------------

class TestLoadoutManagerRestore(unittest.TestCase):
    """Tests for SessionLoadoutManager.restore_session()."""

    def setUp(self):
        self.config = _make_config()
        self.db = MagicMock()
        self.data_client = MagicMock()
        self.tool_inference = ToolInferenceEngine()

        from client.hunt.loadout_manager import SessionLoadoutManager
        self.mgr = SessionLoadoutManager(
            self.config, self.db, self.data_client, self.tool_inference
        )

    def test_restore_loads_weapon_signature(self):
        session = _make_session()
        session.loadout_entries.append(SessionLoadoutEntry(
            id=1, session_id="session-1",
            weapon_name="TestGun", cost_per_shot=0.15,
            damage_min=30.0, damage_max=60.0,
            loadout_data={"Id": "lo-1"},
            source="snapshot",
        ))
        self.mgr.restore_session(session)

        self.assertTrue(self.tool_inference.has_signatures)
        name, _conf, cost = self.tool_inference.infer_tool(45.0)
        self.assertEqual(name, "TestGun")
        self.assertAlmostEqual(cost, 0.15)
        self.assertEqual(self.mgr._active_loadout, {"Id": "lo-1"})

    def test_restore_no_loadout_entries(self):
        session = _make_session()
        self.mgr.restore_session(session)
        self.assertFalse(self.tool_inference.has_signatures)
        self.assertIsNone(self.mgr._active_loadout)

    def test_restore_clears_unmatched_damage(self):
        self.mgr._unmatched_damage_values = [100.0, 120.0]
        session = _make_session()
        self.mgr.restore_session(session)
        self.assertEqual(len(self.mgr._unmatched_damage_values), 0)


if __name__ == "__main__":
    unittest.main()
