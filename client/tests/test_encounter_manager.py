import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from client.hunt.encounter_manager import EncounterManager, EncounterState
from client.hunt.session import HuntSession, MobEncounter, EncounterToolStats


def _make_config(**overrides):
    config = MagicMock()
    config.encounter_close_timeout_ms = overrides.get("encounter_close_timeout_ms", 15000)
    config.attribution_window_ms = overrides.get("attribution_window_ms", 3000)
    return config


def _make_session(primary_mob=None):
    return HuntSession(
        id="session-1",
        start_time=datetime(2026, 1, 1),
        primary_mob=primary_mob,
    )


class TestEncounterManagerInitialState(unittest.TestCase):

    def test_initial_state_idle(self):
        em = EncounterManager(_make_config(), _make_session())
        self.assertEqual(em.state, EncounterState.IDLE)
        self.assertIsNone(em.current_encounter)


class TestEncounterCreation(unittest.TestCase):

    def setUp(self):
        self.config = _make_config()
        self.session = _make_session()
        self.em = EncounterManager(self.config, self.session)

    def test_damage_creates_encounter(self):
        self.em.on_damage_dealt(50.0)
        self.assertEqual(self.em.state, EncounterState.ACTIVE)
        self.assertIsNotNone(self.em.current_encounter)
        self.assertEqual(self.em.current_encounter.mob_name, "Unknown")

    def test_damage_with_session_primary_mob(self):
        session = _make_session(primary_mob="Atrox")
        em = EncounterManager(self.config, session)
        em.on_damage_dealt(50.0)
        self.assertEqual(em.current_encounter.mob_name, "Atrox")
        self.assertEqual(em.current_encounter.mob_name_source, "user")

    def test_mob_detected_creates_encounter(self):
        self.em.on_mob_name_detected("Atrox", confidence=0.95, source="ocr")
        self.assertEqual(self.em.state, EncounterState.ACTIVE)
        self.assertEqual(self.em.current_encounter.mob_name, "Atrox")
        self.assertAlmostEqual(self.em.current_encounter.confidence, 0.95)


class TestCombatEvents(unittest.TestCase):

    def setUp(self):
        self.config = _make_config()
        self.session = _make_session(primary_mob="Atrox")
        self.em = EncounterManager(self.config, self.session)
        self.em.on_mob_name_detected("Atrox")

    def test_damage_accumulates(self):
        self.em.on_damage_dealt(30.0)
        self.em.on_damage_dealt(20.0)
        enc = self.em.current_encounter
        self.assertAlmostEqual(enc.damage_dealt, 50.0)
        self.assertEqual(enc.shots_fired, 2)

    def test_critical_hit_tracked(self):
        self.em.on_damage_dealt(50.0, is_crit=True)
        self.assertEqual(self.em.current_encounter.critical_hits, 1)

    def test_damage_received(self):
        self.em.on_damage_received(15.0)
        self.em.on_damage_received(10.0)
        self.assertAlmostEqual(self.em.current_encounter.damage_taken, 25.0)

    def test_heal(self):
        self.em.on_heal(20.0)
        self.assertAlmostEqual(self.em.current_encounter.heals_received, 20.0)

    def test_player_avoid(self):
        self.em.on_player_avoid()
        self.assertEqual(self.em.current_encounter.player_avoids, 1)

    def test_target_avoid(self):
        self.em.on_target_avoid()
        self.assertEqual(self.em.current_encounter.target_avoids, 1)

    def test_mob_miss(self):
        self.em.on_mob_miss()
        self.assertEqual(self.em.current_encounter.mob_misses, 1)

    def test_deflect(self):
        self.em.on_deflect()
        self.assertEqual(self.em.current_encounter.deflects, 1)

    def test_block(self):
        self.em.on_block()
        self.assertEqual(self.em.current_encounter.blocks, 1)

    def test_defensive_noop_without_encounter(self):
        em = EncounterManager(self.config, _make_session())
        # These should not raise or create encounters
        em.on_heal(10.0)
        em.on_player_avoid()
        em.on_mob_miss()
        em.on_deflect()
        em.on_block()
        self.assertIsNone(em.current_encounter)


class TestToolStats(unittest.TestCase):

    def setUp(self):
        self.em = EncounterManager(_make_config(), _make_session(primary_mob="Atrox"))
        self.em.on_mob_name_detected("Atrox")

    def test_tool_stats_tracked(self):
        self.em.set_current_tool("Armatrix LR-35 (L)")
        self.em.on_damage_dealt(50.0, is_crit=True)
        self.em.on_damage_dealt(30.0)
        ts = self.em.current_encounter.tool_stats["Armatrix LR-35 (L)"]
        self.assertEqual(ts.shots_fired, 2)
        self.assertAlmostEqual(ts.damage_dealt, 80.0)
        self.assertEqual(ts.critical_hits, 1)

    def test_tool_stats_unknown_default(self):
        self.em.on_damage_dealt(50.0)
        self.assertIn("Unknown", self.em.current_encounter.tool_stats)


class TestLootHandling(unittest.TestCase):

    def setUp(self):
        self.em = EncounterManager(_make_config(), _make_session(primary_mob="Atrox"))
        self.em.on_mob_name_detected("Atrox")
        self.em.on_damage_dealt(50.0)

    def test_loot_sets_closing(self):
        self.em.on_loot_group(12.5)
        self.assertEqual(self.em.state, EncounterState.CLOSING)
        self.assertAlmostEqual(self.em.current_encounter.loot_total_ped, 12.5)

    def test_loot_extends_items(self):
        items = [MagicMock(), MagicMock()]
        self.em.on_loot_group(10.0, loot_items=items)
        self.assertEqual(len(self.em.current_encounter.loot_items), 2)

    def test_loot_accumulates_across_groups(self):
        self.em.on_loot_group(10.0)
        self.em.on_loot_group(5.0)
        self.assertAlmostEqual(self.em.current_encounter.loot_total_ped, 15.0)


class TestMobChange(unittest.TestCase):

    def setUp(self):
        self.em = EncounterManager(_make_config(), _make_session())
        self.em.on_mob_name_detected("Atrox")
        self.em.on_damage_dealt(50.0)

    def test_mob_change_closes_encounter(self):
        ended = self.em.on_mob_name_detected("Foul")
        self.assertIsNotNone(ended)
        self.assertEqual(ended.mob_name, "Atrox")
        self.assertIsNotNone(ended.end_time)  # Close sets end_time
        self.assertEqual(self.em.current_encounter.mob_name, "Foul")

    def test_same_mob_updates_confidence(self):
        # Create a fresh encounter manager (setUp already created one at confidence=1.0)
        em = EncounterManager(_make_config(), _make_session())
        em.on_mob_name_detected("Atrox", confidence=0.5)
        self.assertAlmostEqual(em.current_encounter.confidence, 0.5)
        em.on_mob_name_detected("Atrox", confidence=0.99)
        self.assertAlmostEqual(em.current_encounter.confidence, 0.99)


class TestTimeoutAndClose(unittest.TestCase):

    def setUp(self):
        self.config = _make_config(encounter_close_timeout_ms=1000)
        self.session = _make_session(primary_mob="Atrox")
        self.em = EncounterManager(self.config, self.session)

    def test_check_timeout_no_close_when_active(self):
        self.em.on_mob_name_detected("Atrox")
        self.em.on_damage_dealt(50.0)
        self.assertEqual(self.em.state, EncounterState.ACTIVE)
        result = self.em.check_timeout()
        self.assertIsNone(result)

    def test_check_timeout_closes_after_delay(self):
        self.em.on_mob_name_detected("Atrox")
        self.em.on_damage_dealt(50.0)
        self.em.on_loot_group(10.0)
        self.assertEqual(self.em.state, EncounterState.CLOSING)
        # Simulate time passing beyond timeout
        self.em._last_event_time = datetime.utcnow() - timedelta(seconds=5)
        result = self.em.check_timeout()
        self.assertIsNotNone(result)
        self.assertEqual(result.mob_name, "Atrox")
        self.assertIsNotNone(result.end_time)
        self.assertEqual(self.em.state, EncounterState.IDLE)

    def test_force_close(self):
        self.em.on_mob_name_detected("Atrox")
        self.em.on_damage_dealt(50.0)
        result = self.em.force_close()
        self.assertIsNotNone(result)
        self.assertEqual(result.mob_name, "Atrox")
        self.assertIsNotNone(result.end_time)  # Close sets end_time
        self.assertEqual(self.em.state, EncounterState.IDLE)
        self.assertIsNone(self.em.current_encounter)

    def test_force_close_no_encounter(self):
        result = self.em.force_close()
        self.assertIsNone(result)

    def test_closed_encounter_in_session(self):
        self.em.on_mob_name_detected("Atrox")
        self.em.on_damage_dealt(50.0)
        self.em.force_close()
        self.assertEqual(len(self.session.encounters), 1)
        self.assertEqual(self.session.encounters[0].mob_name, "Atrox")


class TestDeathHandling(unittest.TestCase):

    def setUp(self):
        self.config = _make_config()
        self.session = _make_session(primary_mob="Atrox")
        self.em = EncounterManager(self.config, self.session)
        self.em.on_mob_name_detected("Atrox")
        self.em.on_damage_dealt(50.0)

    def test_death_closes_encounter_immediately(self):
        result = self.em.on_death("Atrox Young")
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.end_time)
        self.assertEqual(self.em.state, EncounterState.IDLE)
        self.assertIsNone(self.em.current_encounter)

    def test_death_sets_outcome(self):
        result = self.em.on_death("Atrox Young")
        self.assertEqual(result.outcome, "death")

    def test_death_increments_death_count(self):
        result = self.em.on_death("Atrox Young")
        self.assertEqual(result.death_count, 1)

    def test_death_sets_killed_by_mob(self):
        result = self.em.on_death("Atrox Young")
        self.assertEqual(result.killed_by_mob, "Atrox Young")

    def test_death_marks_open_ended(self):
        result = self.em.on_death("Atrox Young")
        self.assertTrue(result.is_open_ended)

    def test_death_updates_unknown_mob_name(self):
        em = EncounterManager(self.config, _make_session())
        em.on_damage_dealt(50.0)  # Creates encounter with "Unknown"
        self.assertEqual(em.current_encounter.mob_name, "Unknown")
        result = em.on_death("Atrox Young")
        self.assertEqual(result.mob_name, "Atrox Young")
        self.assertEqual(result.mob_name_source, "death_message")

    def test_death_preserves_known_mob_name(self):
        result = self.em.on_death("Atrox Young")
        # The encounter already had "Atrox" from OCR — keep it
        self.assertEqual(result.mob_name, "Atrox")

    def test_death_no_encounter_returns_none(self):
        em = EncounterManager(self.config, _make_session())
        result = em.on_death("Atrox Young")
        self.assertIsNone(result)

    def test_death_encounter_in_session(self):
        self.em.on_death("Atrox Young")
        self.assertEqual(len(self.session.encounters), 1)
        self.assertEqual(self.session.encounters[0].outcome, "death")


class TestOutcomeTracking(unittest.TestCase):

    def setUp(self):
        self.config = _make_config(encounter_close_timeout_ms=1000)
        self.session = _make_session(primary_mob="Atrox")
        self.em = EncounterManager(self.config, self.session)

    def test_loot_sets_kill_outcome(self):
        self.em.on_mob_name_detected("Atrox")
        self.em.on_damage_dealt(50.0)
        self.em.on_loot_group(10.0)
        self.assertEqual(self.em.current_encounter.outcome, "kill")

    def test_force_close_outcome(self):
        self.em.on_mob_name_detected("Atrox")
        self.em.on_damage_dealt(50.0)
        result = self.em.force_close()
        self.assertEqual(result.outcome, "force_closed")

    def test_timeout_from_closing_is_kill(self):
        self.em.on_mob_name_detected("Atrox")
        self.em.on_damage_dealt(50.0)
        self.em.on_loot_group(10.0)
        self.em._last_event_time = datetime.utcnow() - timedelta(seconds=5)
        result = self.em.check_timeout()
        self.assertEqual(result.outcome, "kill")

    def test_timeout_from_active_is_timeout(self):
        self.em.on_mob_name_detected("Atrox")
        self.em.on_damage_dealt(50.0)
        self.em._last_event_time = datetime.utcnow() - timedelta(seconds=5)
        result = self.em.check_timeout()
        self.assertEqual(result.outcome, "timeout")

    def test_mob_change_with_loot_is_kill(self):
        self.em.on_mob_name_detected("Atrox")
        self.em.on_damage_dealt(50.0)
        self.em.on_loot_group(10.0)
        ended = self.em.on_mob_name_detected("Foul")
        self.assertEqual(ended.outcome, "kill")

    def test_mob_change_without_loot_is_timeout(self):
        self.em.on_mob_name_detected("Atrox")
        self.em.on_damage_dealt(50.0)
        ended = self.em.on_mob_name_detected("Foul")
        self.assertEqual(ended.outcome, "timeout")


if __name__ == "__main__":
    unittest.main()
