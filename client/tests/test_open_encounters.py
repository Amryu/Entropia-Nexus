"""Tests for open-ended encounter management: merge, abandon, split, reopen."""

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from client.hunt.encounter_manager import EncounterManager, EncounterState
from client.hunt.session import HuntSession, MobEncounter, EncounterToolStats
from client.hunt.tracker import HuntTracker
from client.core.constants import (
    EVENT_PLAYER_DEATH, EVENT_PLAYER_REVIVED,
    EVENT_OPEN_ENCOUNTER_UPDATED, EVENT_HUNT_SESSION_UPDATED,
    EVENT_HUNT_ENCOUNTER_ENDED,
)


def _make_config(**overrides):
    config = MagicMock()
    config.encounter_close_timeout_ms = overrides.get("encounter_close_timeout_ms", 15000)
    config.loot_close_timeout_ms = overrides.get("loot_close_timeout_ms", 3000)
    config.max_encounter_duration_ms = overrides.get("max_encounter_duration_ms", 600000)
    config.attribution_window_ms = overrides.get("attribution_window_ms", 3000)
    config.session_auto_timeout_ms = overrides.get("session_auto_timeout_ms", 3600000)
    config.hunt_split_mob_threshold = overrides.get("hunt_split_mob_threshold", 10)
    config.hunt_split_min_remote_kills = overrides.get("hunt_split_min_remote_kills", 5)
    config.hunt_markup_pct = overrides.get("hunt_markup_pct", 100.0)
    config.loot_blacklist = overrides.get("loot_blacklist", [])
    config.loot_blacklist_per_mob = overrides.get("loot_blacklist_per_mob", {})
    config.auto_merge_deaths = overrides.get("auto_merge_deaths", False)
    return config


def _make_encounter(mob_name="Atrox", outcome="kill", cost=5.0, damage=50.0,
                    death_count=0, is_open_ended=False, session_id="session-1"):
    import uuid
    enc = MobEncounter(
        id=str(uuid.uuid4()),
        session_id=session_id,
        mob_name=mob_name,
        mob_name_source="ocr",
        start_time=datetime(2026, 1, 1),
        end_time=datetime(2026, 1, 1, 0, 1),
        damage_dealt=damage,
        cost=cost,
        shots_fired=5,
        outcome=outcome,
        death_count=death_count,
        is_open_ended=is_open_ended,
    )
    return enc


def _make_tracker(config=None):
    """Create a HuntTracker with mocked dependencies, session active."""
    config = config or _make_config()
    event_bus = MagicMock()
    db = MagicMock()
    db.get_incomplete_session.return_value = None

    tracker = HuntTracker(config, event_bus, db)
    tracker._live = True

    # Manually set up a session
    session = HuntSession(
        id="session-1",
        start_time=datetime(2026, 1, 1),
    )
    tracker._session = session
    tracker._manager = EncounterManager(config, session)
    tracker._active = True
    tracker._last_activity_time = datetime.utcnow()

    return tracker, event_bus, db


# ---------------------------------------------------------------------------
# EncounterManager.on_death tests
# ---------------------------------------------------------------------------

class TestEncounterManagerOnDeath(unittest.TestCase):

    def test_death_closes_active_encounter(self):
        config = _make_config()
        session = HuntSession(id="s1", start_time=datetime(2026, 1, 1))
        em = EncounterManager(config, session)
        em.on_mob_name_detected("Atrox")
        em.on_damage_dealt(50.0)
        result = em.on_death("Atrox Young")
        self.assertIsNotNone(result)
        self.assertEqual(em.state, EncounterState.IDLE)
        self.assertEqual(result.outcome, "death")
        self.assertEqual(result.death_count, 1)
        self.assertTrue(result.is_open_ended)

    def test_death_no_encounter_noop(self):
        config = _make_config()
        session = HuntSession(id="s1", start_time=datetime(2026, 1, 1))
        em = EncounterManager(config, session)
        result = em.on_death("Atrox")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Merge tests
# ---------------------------------------------------------------------------

class TestMergeOpenEncounter(unittest.TestCase):

    def setUp(self):
        self.tracker, self.bus, self.db = _make_tracker()

    def test_merge_into_completed_encounter(self):
        # Create a completed kill encounter
        kill_enc = _make_encounter("Atrox", outcome="kill", cost=5.0, damage=50.0)
        self.tracker._session.encounters.append(kill_enc)

        # Create an open death encounter
        death_enc = _make_encounter("Atrox", outcome="death", cost=3.0, damage=30.0,
                                    death_count=1, is_open_ended=True)
        self.tracker._session.encounters.append(death_enc)
        self.tracker._open_encounters.append(death_enc)

        result = self.tracker.merge_open_encounter(death_enc.id, kill_enc.id)
        self.assertTrue(result)

        # Stats merged
        self.assertAlmostEqual(kill_enc.damage_dealt, 80.0)
        self.assertAlmostEqual(kill_enc.cost, 8.0)
        self.assertEqual(kill_enc.death_count, 1)
        self.assertIn(death_enc.id, kill_enc.merged_from)

        # Source marked as merged
        self.assertEqual(death_enc.outcome, "merged")
        self.assertFalse(death_enc.is_open_ended)
        self.assertEqual(death_enc.merged_into, kill_enc.id)

        # Removed from open list
        self.assertNotIn(death_enc, self.tracker._open_encounters)

    def test_merge_unknown_mob_into_known(self):
        kill_enc = _make_encounter("Atrox", outcome="kill")
        unknown_enc = _make_encounter("Unknown", outcome="death", is_open_ended=True,
                                      death_count=1)
        self.tracker._session.encounters.extend([kill_enc, unknown_enc])
        self.tracker._open_encounters.append(unknown_enc)

        result = self.tracker.merge_open_encounter(unknown_enc.id, kill_enc.id)
        self.assertTrue(result)

    def test_merge_incompatible_mobs_fails(self):
        kill_enc = _make_encounter("Atrox", outcome="kill")
        foul_enc = _make_encounter("Foul", outcome="death", is_open_ended=True,
                                    death_count=1)
        self.tracker._session.encounters.extend([kill_enc, foul_enc])
        self.tracker._open_encounters.append(foul_enc)

        result = self.tracker.merge_open_encounter(foul_enc.id, kill_enc.id)
        self.assertFalse(result)

    def test_merge_nonexistent_open_fails(self):
        kill_enc = _make_encounter("Atrox", outcome="kill")
        self.tracker._session.encounters.append(kill_enc)

        result = self.tracker.merge_open_encounter("nonexistent-id", kill_enc.id)
        self.assertFalse(result)

    def test_merge_tool_stats(self):
        kill_enc = _make_encounter("Atrox", outcome="kill")
        kill_enc.tool_stats["Gun A"] = EncounterToolStats("Gun A", shots_fired=3,
                                                           damage_dealt=30.0, critical_hits=1)

        death_enc = _make_encounter("Atrox", outcome="death", is_open_ended=True,
                                    death_count=1)
        death_enc.tool_stats["Gun A"] = EncounterToolStats("Gun A", shots_fired=2,
                                                            damage_dealt=20.0, critical_hits=0)

        self.tracker._session.encounters.extend([kill_enc, death_enc])
        self.tracker._open_encounters.append(death_enc)

        self.tracker.merge_open_encounter(death_enc.id, kill_enc.id)

        ts = kill_enc.tool_stats["Gun A"]
        self.assertEqual(ts.shots_fired, 5)
        self.assertAlmostEqual(ts.damage_dealt, 50.0)
        self.assertEqual(ts.critical_hits, 1)

    def test_merge_adopts_mob_name_when_target_unknown(self):
        target_enc = _make_encounter("Unknown", outcome="kill")
        source_enc = _make_encounter("Atrox", outcome="death", is_open_ended=True,
                                      death_count=1)
        self.tracker._session.encounters.extend([target_enc, source_enc])
        self.tracker._open_encounters.append(source_enc)

        self.tracker.merge_open_encounter(source_enc.id, target_enc.id)
        self.assertEqual(target_enc.mob_name, "Atrox")


# ---------------------------------------------------------------------------
# Abandon tests
# ---------------------------------------------------------------------------

class TestAbandonOpenEncounter(unittest.TestCase):

    def setUp(self):
        self.tracker, self.bus, self.db = _make_tracker()

    def test_abandon_sets_outcome(self):
        enc = _make_encounter("Atrox", outcome="death", is_open_ended=True,
                              death_count=1)
        self.tracker._session.encounters.append(enc)
        self.tracker._open_encounters.append(enc)

        result = self.tracker.abandon_open_encounter(enc.id)
        self.assertTrue(result)
        self.assertEqual(enc.outcome, "abandoned")
        self.assertFalse(enc.is_open_ended)
        self.assertNotIn(enc, self.tracker._open_encounters)

    def test_abandon_nonexistent_fails(self):
        result = self.tracker.abandon_open_encounter("nonexistent-id")
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# Reopen tests
# ---------------------------------------------------------------------------

class TestReopenEncounter(unittest.TestCase):

    def setUp(self):
        self.tracker, self.bus, self.db = _make_tracker()

    def test_reopen_abandoned_encounter(self):
        enc = _make_encounter("Atrox", outcome="abandoned", death_count=1)
        self.tracker._session.encounters.append(enc)

        result = self.tracker.reopen_encounter(enc.id)
        self.assertTrue(result)
        self.assertEqual(enc.outcome, "death")
        self.assertTrue(enc.is_open_ended)
        self.assertIn(enc, self.tracker._open_encounters)

    def test_reopen_timeout_encounter(self):
        enc = _make_encounter("Atrox", outcome="abandoned", death_count=0)
        self.tracker._session.encounters.append(enc)

        result = self.tracker.reopen_encounter(enc.id)
        self.assertTrue(result)
        self.assertEqual(enc.outcome, "timeout")

    def test_reopen_non_abandoned_fails(self):
        enc = _make_encounter("Atrox", outcome="kill")
        self.tracker._session.encounters.append(enc)

        result = self.tracker.reopen_encounter(enc.id)
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# Split tests
# ---------------------------------------------------------------------------

class TestSplitMergedEncounter(unittest.TestCase):

    def setUp(self):
        self.tracker, self.bus, self.db = _make_tracker()

    def test_split_reverses_merge(self):
        kill_enc = _make_encounter("Atrox", outcome="kill", cost=5.0, damage=50.0)
        death_enc = _make_encounter("Atrox", outcome="death", cost=3.0, damage=30.0,
                                    death_count=1, is_open_ended=True)
        self.tracker._session.encounters.extend([kill_enc, death_enc])
        self.tracker._open_encounters.append(death_enc)

        # Merge first
        self.tracker.merge_open_encounter(death_enc.id, kill_enc.id)
        self.assertAlmostEqual(kill_enc.cost, 8.0)
        self.assertEqual(kill_enc.death_count, 1)

        # Split
        result = self.tracker.split_merged_encounter(kill_enc.id, death_enc.id)
        self.assertTrue(result)
        self.assertAlmostEqual(kill_enc.cost, 5.0)
        self.assertAlmostEqual(kill_enc.damage_dealt, 50.0)
        self.assertEqual(kill_enc.death_count, 0)
        self.assertNotIn(death_enc.id, kill_enc.merged_from)

        # Source restored
        self.assertTrue(death_enc.is_open_ended)
        self.assertIsNone(death_enc.merged_into)
        self.assertIn(death_enc, self.tracker._open_encounters)

    def test_split_nonexistent_fails(self):
        enc = _make_encounter("Atrox", outcome="kill")
        self.tracker._session.encounters.append(enc)

        result = self.tracker.split_merged_encounter(enc.id, "nonexistent-id")
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# Auto-merge tests
# ---------------------------------------------------------------------------

class TestAutoMergeDeaths(unittest.TestCase):

    def test_auto_merge_same_mob(self):
        tracker, bus, db = _make_tracker(_make_config(auto_merge_deaths=True))

        # Start an encounter
        tracker._manager.on_mob_name_detected("Atrox")
        tracker._manager.on_damage_dealt(50.0)
        tracker._manager.on_damage_received(10.0)

        # First death
        death_event_1 = MagicMock()
        death_event_1.mob_name = "Atrox"
        death_event_1.timestamp = datetime(2026, 1, 1, 12, 0, 5)
        tracker._on_player_death(death_event_1)

        # Should have one open encounter
        self.assertEqual(len(tracker._open_encounters), 1)

        # Start new encounter, second death
        tracker._manager.on_mob_name_detected("Atrox")
        tracker._manager.on_damage_dealt(30.0)

        death_event_2 = MagicMock()
        death_event_2.mob_name = "Atrox"
        death_event_2.timestamp = datetime(2026, 1, 1, 12, 1, 0)
        tracker._on_player_death(death_event_2)

        # Auto-merged: still one open encounter, but with accumulated stats
        self.assertEqual(len(tracker._open_encounters), 1)
        open_enc = tracker._open_encounters[0]
        self.assertAlmostEqual(open_enc.damage_dealt, 80.0)
        self.assertEqual(open_enc.death_count, 2)

    def test_no_auto_merge_when_disabled(self):
        tracker, bus, db = _make_tracker(_make_config(auto_merge_deaths=False))

        # Start encounter, die
        tracker._manager.on_mob_name_detected("Atrox")
        tracker._manager.on_damage_dealt(50.0)

        death_event_1 = MagicMock()
        death_event_1.mob_name = "Atrox"
        death_event_1.timestamp = datetime(2026, 1, 1, 12, 0, 5)
        tracker._on_player_death(death_event_1)

        # Start new encounter, die again
        tracker._manager.on_mob_name_detected("Atrox")
        tracker._manager.on_damage_dealt(30.0)

        death_event_2 = MagicMock()
        death_event_2.mob_name = "Atrox"
        death_event_2.timestamp = datetime(2026, 1, 1, 12, 1, 0)
        tracker._on_player_death(death_event_2)

        # Two separate open encounters
        self.assertEqual(len(tracker._open_encounters), 2)

    def test_auto_merge_different_mob_not_merged(self):
        tracker, bus, db = _make_tracker(_make_config(auto_merge_deaths=True))

        # Die to Atrox
        tracker._manager.on_mob_name_detected("Atrox")
        tracker._manager.on_damage_dealt(50.0)
        death_event_1 = MagicMock()
        death_event_1.mob_name = "Atrox"
        death_event_1.timestamp = datetime(2026, 1, 1, 12, 0, 5)
        tracker._on_player_death(death_event_1)

        # Die to Foul
        tracker._manager.on_mob_name_detected("Foul")
        tracker._manager.on_damage_dealt(30.0)
        death_event_2 = MagicMock()
        death_event_2.mob_name = "Foul"
        death_event_2.timestamp = datetime(2026, 1, 1, 12, 1, 0)
        tracker._on_player_death(death_event_2)

        # Two separate open encounters (different mobs)
        self.assertEqual(len(tracker._open_encounters), 2)


# ---------------------------------------------------------------------------
# Session end auto-abandon tests
# ---------------------------------------------------------------------------

class TestSessionEndAutoAbandon(unittest.TestCase):

    def test_session_stop_abandons_open_encounters(self):
        tracker, bus, db = _make_tracker()

        enc = _make_encounter("Atrox", outcome="death", is_open_ended=True,
                              death_count=1)
        tracker._session.encounters.append(enc)
        tracker._open_encounters.append(enc)

        tracker._on_session_stop({"session_id": tracker._session.id})

        self.assertEqual(enc.outcome, "abandoned")
        self.assertFalse(enc.is_open_ended)
        self.assertEqual(len(tracker._open_encounters), 0)


if __name__ == "__main__":
    unittest.main()
