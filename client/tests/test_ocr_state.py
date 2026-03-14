import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from client.hunt.ocr_state import OCRState, OCRStateTracker
from client.core.constants import (
    EVENT_PLAYER_STATUS_UPDATE, EVENT_PLAYER_STATUS_LOST,
    EVENT_TARGET_LOCK_UPDATE, EVENT_TARGET_LOCK_LOST,
    EVENT_RADAR_COORDINATES, EVENT_RADAR_LOST,
    EVENT_ACTIVE_TOOL_CHANGED,
)


class _MockEventBus:
    """Minimal event bus for testing — stores callbacks by event type."""

    def __init__(self):
        self._subs: dict[str, list] = {}

    def subscribe(self, event_type, callback):
        self._subs.setdefault(event_type, []).append(callback)

    def publish(self, event_type, data=None):
        for cb in self._subs.get(event_type, []):
            cb(data)


class TestOCRStateTracker(unittest.TestCase):

    def setUp(self):
        self.bus = _MockEventBus()
        self.tracker = OCRStateTracker(self.bus)

    def test_initial_state_all_none(self):
        s = self.tracker.state
        self.assertIsNone(s.health_pct)
        self.assertIsNone(s.reload_pct)
        self.assertIsNone(s.target_hp_pct)
        self.assertIsNone(s.lon)

    def test_player_status_update(self):
        self.bus.publish(EVENT_PLAYER_STATUS_UPDATE, {
            "health_pct": 0.85,
            "reload_pct": 50.0,
            "tool_equipped": True,
        })
        s = self.tracker.state
        self.assertAlmostEqual(s.health_pct, 0.85)
        self.assertAlmostEqual(s.reload_pct, 50.0)
        self.assertTrue(s.tool_equipped)

    def test_reload_completion_detection(self):
        # First update: reload at 50%
        self.bus.publish(EVENT_PLAYER_STATUS_UPDATE, {"reload_pct": 50.0})
        self.assertIsNone(self.tracker.state.reload_completed_at)

        # Second update: reload at 100% → completion detected
        self.bus.publish(EVENT_PLAYER_STATUS_UPDATE, {"reload_pct": 100.0})
        self.assertIsNotNone(self.tracker.state.reload_completed_at)

    def test_reload_completion_not_triggered_on_steady_100(self):
        # Both updates at 100% → no completion event
        self.bus.publish(EVENT_PLAYER_STATUS_UPDATE, {"reload_pct": 100.0})
        self.bus.publish(EVENT_PLAYER_STATUS_UPDATE, {"reload_pct": 100.0})
        self.assertIsNone(self.tracker.state.reload_completed_at)

    def test_player_status_lost(self):
        self.bus.publish(EVENT_PLAYER_STATUS_UPDATE, {
            "health_pct": 0.85, "reload_pct": 50.0,
        })
        self.bus.publish(EVENT_PLAYER_STATUS_LOST, {})
        s = self.tracker.state
        self.assertIsNone(s.health_pct)
        self.assertIsNone(s.reload_pct)

    def test_target_lock_update(self):
        self.bus.publish(EVENT_TARGET_LOCK_UPDATE, {
            "hp_pct": 0.6,
            "is_shared": True,
            "raw_name": "Atrox Young",
        })
        s = self.tracker.state
        self.assertAlmostEqual(s.target_hp_pct, 0.6)
        self.assertTrue(s.target_is_shared)
        self.assertEqual(s.target_raw_name, "Atrox Young")

    def test_target_lock_lost(self):
        self.bus.publish(EVENT_TARGET_LOCK_UPDATE, {"hp_pct": 0.6})
        self.bus.publish(EVENT_TARGET_LOCK_LOST, {})
        self.assertIsNone(self.tracker.state.target_hp_pct)

    def test_radar_update(self):
        self.bus.publish(EVENT_RADAR_COORDINATES, {
            "lon": 61234.5,
            "lat": 72345.6,
            "confidence": 0.95,
        })
        s = self.tracker.state
        self.assertAlmostEqual(s.lon, 61234.5)
        self.assertAlmostEqual(s.lat, 72345.6)
        self.assertAlmostEqual(s.location_confidence, 0.95)

    def test_radar_lost(self):
        self.bus.publish(EVENT_RADAR_COORDINATES, {"lon": 100, "lat": 200})
        self.bus.publish(EVENT_RADAR_LOST, {})
        self.assertIsNone(self.tracker.state.lon)

    def test_tool_update(self):
        self.bus.publish(EVENT_ACTIVE_TOOL_CHANGED, {"tool_name": "Armatrix LR-35 (L)"})
        self.assertEqual(self.tracker.state.ocr_tool_name, "Armatrix LR-35 (L)")

    def test_staleness_no_data(self):
        self.assertTrue(self.tracker.is_stale("target"))
        self.assertTrue(self.tracker.is_stale("location"))

    def test_staleness_fresh_data(self):
        self.bus.publish(EVENT_TARGET_LOCK_UPDATE, {"hp_pct": 0.5})
        self.assertFalse(self.tracker.is_stale("target"))

    def test_staleness_old_data(self):
        self.bus.publish(EVENT_TARGET_LOCK_UPDATE, {"hp_pct": 0.5})
        # Manually backdate
        self.tracker._state.target_last_seen = (
            datetime.utcnow() - timedelta(seconds=20)
        )
        self.assertTrue(self.tracker.is_stale("target"))


if __name__ == "__main__":
    unittest.main()
