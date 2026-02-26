import unittest
from datetime import datetime
from unittest.mock import MagicMock

from client.hunt.hunt_detector import MobTypeTracker, HuntDetector, HuntBoundaryEvent
from client.hunt.session import Hunt, MobEncounter


def _make_encounter(mob_name="Atrox", session_id="session-1"):
    return MobEncounter(
        id="enc-1",
        session_id=session_id,
        mob_name=mob_name,
        mob_name_source="ocr",
        start_time=datetime(2026, 1, 1),
        end_time=datetime(2026, 1, 1, 0, 1),
    )


def _make_config(**overrides):
    config = MagicMock()
    config.hunt_split_mob_threshold = overrides.get("hunt_split_mob_threshold", 5)
    config.hunt_split_min_remote_kills = overrides.get("hunt_split_min_remote_kills", 5)
    return config


# ---------------------------------------------------------------------------
# MobTypeTracker
# ---------------------------------------------------------------------------

class TestMobTypeTrackerNoSplit(unittest.TestCase):

    def test_no_split_before_window_full(self):
        tracker = MobTypeTracker(window_size=5)
        tracker.set_dominant("Atrox")
        for _ in range(4):
            result = tracker.observe("Foul")
        self.assertIsNone(result)

    def test_no_split_dominant_still_present(self):
        tracker = MobTypeTracker(window_size=5)
        tracker.set_dominant("Atrox")
        for _ in range(4):
            tracker.observe("Foul")
        # Add dominant mob back in window
        result = tracker.observe("Atrox")
        self.assertIsNone(result)

    def test_no_split_mixed_spawn(self):
        tracker = MobTypeTracker(window_size=5)
        tracker.set_dominant("Atrox")
        # Fill window with mixed mobs (none >= 60%)
        mobs = ["Foul", "Merp", "Foul", "Merp", "Snablesnot"]
        result = None
        for m in mobs:
            result = tracker.observe(m)
        self.assertIsNone(result)


class TestMobTypeTrackerSplit(unittest.TestCase):

    def test_split_on_single_new_mob(self):
        tracker = MobTypeTracker(window_size=5)
        tracker.set_dominant("Atrox")
        result = None
        for _ in range(5):
            result = tracker.observe("Foul")
        self.assertIsNotNone(result)
        self.assertEqual(result.split_reason, "mob_type_change")
        self.assertEqual(result.new_hunt_mob, "Foul")

    def test_split_on_60pct_threshold(self):
        tracker = MobTypeTracker(window_size=5)
        tracker.set_dominant("Atrox")
        # 3/5 = 60% Foul, plus 2 others
        mobs = ["Foul", "Foul", "Foul", "Merp", "Snablesnot"]
        result = None
        for m in mobs:
            result = tracker.observe(m)
        self.assertIsNotNone(result)
        self.assertEqual(result.new_hunt_mob, "Foul")


class TestMobTypeTrackerReset(unittest.TestCase):

    def test_set_dominant_clears_window(self):
        tracker = MobTypeTracker(window_size=5)
        tracker.set_dominant("Atrox")
        for _ in range(4):
            tracker.observe("Foul")
        tracker.set_dominant("Foul")
        # Window cleared, need full window again before split
        result = tracker.observe("Merp")
        self.assertIsNone(result)

    def test_reset_clears_state(self):
        tracker = MobTypeTracker(window_size=5)
        tracker.set_dominant("Atrox")
        tracker.observe("Foul")
        tracker.reset()
        self.assertIsNone(tracker.dominant_mob)


# ---------------------------------------------------------------------------
# HuntDetector
# ---------------------------------------------------------------------------

class TestHuntDetectorStartHunt(unittest.TestCase):

    def test_start_hunt_creates_hunt(self):
        config = _make_config()
        detector = HuntDetector(config)
        enc = _make_encounter("Atrox")
        hunt = detector.start_hunt("session-1", enc)
        self.assertIsNotNone(hunt)
        self.assertEqual(hunt.session_id, "session-1")
        self.assertEqual(hunt.primary_mob, "Atrox")
        self.assertEqual(len(hunt.encounters), 1)

    def test_start_hunt_sets_encounter_hunt_id(self):
        detector = HuntDetector(_make_config())
        enc = _make_encounter("Atrox")
        hunt = detector.start_hunt("session-1", enc)
        self.assertEqual(enc.hunt_id, hunt.id)


class TestHuntDetectorEncounters(unittest.TestCase):

    def setUp(self):
        self.config = _make_config(hunt_split_mob_threshold=5)
        self.detector = HuntDetector(self.config)
        first_enc = _make_encounter("Atrox")
        self.hunt = self.detector.start_hunt("session-1", first_enc)

    def test_encounter_added_to_hunt(self):
        enc = _make_encounter("Atrox")
        result = self.detector.on_encounter_ended(enc)
        self.assertIsNone(result)
        self.assertEqual(len(self.hunt.encounters), 2)
        self.assertEqual(enc.hunt_id, self.hunt.id)

    def test_no_split_within_threshold(self):
        # Only 3 kills of Foul (window_size=5, not full yet)
        for _ in range(3):
            enc = _make_encounter("Foul")
            result = self.detector.on_encounter_ended(enc)
        self.assertIsNone(result)

    def test_split_returns_boundary_event(self):
        # Fill window with new mob (5 kills of Foul, dominant was Atrox)
        result = None
        for _ in range(5):
            enc = _make_encounter("Foul")
            result = self.detector.on_encounter_ended(enc)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, HuntBoundaryEvent)
        self.assertEqual(result.new_hunt_mob, "Foul")
        # Triggering encounter should NOT be added to old hunt
        # Old hunt has: 1 initial (Atrox) + 4 non-split (Foul) = 5
        self.assertEqual(len(self.hunt.encounters), 5)
        self.assertIsNone(enc.hunt_id)  # Not assigned to old hunt


class TestHuntDetectorEndAndReset(unittest.TestCase):

    def setUp(self):
        self.detector = HuntDetector(_make_config())

    def test_end_current_hunt(self):
        enc = _make_encounter("Atrox")
        self.detector.start_hunt("session-1", enc)
        hunt = self.detector.end_current_hunt()
        self.assertIsNotNone(hunt)
        self.assertIsNotNone(hunt.end_time)
        self.assertIsNone(self.detector.current_hunt)

    def test_end_hunt_no_current(self):
        result = self.detector.end_current_hunt()
        self.assertIsNone(result)

    def test_reset_clears_all(self):
        enc = _make_encounter("Atrox")
        self.detector.start_hunt("session-1", enc)
        self.detector.reset()
        self.assertIsNone(self.detector.current_hunt)


if __name__ == "__main__":
    unittest.main()
