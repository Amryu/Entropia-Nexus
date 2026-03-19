import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, call

from client.hunt.combat_action_log import CombatAction, CombatActionLog
from client.hunt.reload_correlator import ReloadCorrelator


class TestReloadCorrelator(unittest.TestCase):
    def setUp(self):
        self.config = MagicMock()
        self.config.reload_correlation_window_ms = 500
        self.config.reload_correlation_enabled = True
        self.combat_log = CombatActionLog()
        self.db = MagicMock()
        self.correlator = ReloadCorrelator(self.config, self.combat_log, self.db)
        self.t0 = datetime(2026, 3, 19, 12, 0, 0)

    def _add_damage(self, offset_ms, enc_id="enc1", tool_name=None, tool_source=None):
        action = CombatAction(
            id=f"ev-{offset_ms}",
            encounter_id=enc_id,
            timestamp=self.t0 + timedelta(milliseconds=offset_ms),
            event_type="damage_dealt",
            amount=100.0,
            tool_name=tool_name,
            tool_source=tool_source,
        )
        self.combat_log.append(action)
        return action

    def test_single_shot_retroactive_attribution(self):
        """Damage event at t=50ms, reload drop at t=200ms → attribute to tool."""
        self._add_damage(50)

        attributed = self.correlator.on_reload_drop(
            "WeaponA", self.t0 + timedelta(milliseconds=200)
        )
        self.assertEqual(attributed, 1)
        action = self.combat_log.get_by_id("ev-50")
        self.assertEqual(action.tool_name, "WeaponA")
        self.assertEqual(action.tool_source, "ocr_reload")
        self.assertAlmostEqual(action.confidence, 0.95)

        # DB should be updated too
        self.db.update_combat_event_tool.assert_called_once_with(
            "ev-50", "WeaponA", "ocr_reload", 0.95
        )

    def test_rapid_fire_multiple_events(self):
        """Multiple damage events between OCR frames → all attributed to same tool."""
        self._add_damage(50)
        self._add_damage(150)
        self._add_damage(250)

        attributed = self.correlator.on_reload_drop(
            "WeaponA", self.t0 + timedelta(milliseconds=300)
        )
        self.assertEqual(attributed, 3)
        for offset in [50, 150, 250]:
            a = self.combat_log.get_by_id(f"ev-{offset}")
            self.assertEqual(a.tool_name, "WeaponA")

    def test_events_outside_window_not_attributed(self):
        """Events older than correlation window are not attributed."""
        self._add_damage(0)  # 1000ms before reload drop — outside 500ms window

        attributed = self.correlator.on_reload_drop(
            "WeaponA", self.t0 + timedelta(milliseconds=1000)
        )
        self.assertEqual(attributed, 0)

    def test_already_attributed_not_overwritten(self):
        """Events already attributed via higher-priority source are preserved."""
        self._add_damage(50, tool_name="Gun", tool_source="ocr_reload")

        attributed = self.correlator.on_reload_drop(
            "OtherGun", self.t0 + timedelta(milliseconds=200)
        )
        self.assertEqual(attributed, 0)
        action = self.combat_log.get_by_id("ev-50")
        self.assertEqual(action.tool_name, "Gun")

    def test_inferred_can_be_upgraded(self):
        """Events with 'inferred' source can be upgraded to 'ocr_reload'."""
        self._add_damage(50, tool_name="Inferred", tool_source="inferred")

        attributed = self.correlator.on_reload_drop(
            "ActualGun", self.t0 + timedelta(milliseconds=200)
        )
        self.assertEqual(attributed, 1)
        action = self.combat_log.get_by_id("ev-50")
        self.assertEqual(action.tool_name, "ActualGun")
        self.assertEqual(action.tool_source, "ocr_reload")

    def test_no_tool_name_skips(self):
        """Reload drop with no tool name does nothing."""
        self._add_damage(50)

        attributed = self.correlator.on_reload_drop(
            None, self.t0 + timedelta(milliseconds=200)
        )
        self.assertEqual(attributed, 0)

    def test_disabled_skips(self):
        """Disabled correlator does nothing."""
        self.config.reload_correlation_enabled = False
        correlator = ReloadCorrelator(self.config, self.combat_log, self.db)

        self._add_damage(50)
        attributed = correlator.on_reload_drop(
            "WeaponA", self.t0 + timedelta(milliseconds=200)
        )
        self.assertEqual(attributed, 0)

    def test_tool_switch_mid_fight(self):
        """Tool switch: events attributed to correct tool per reload drop."""
        self._add_damage(50)
        self.correlator.on_reload_drop("WeaponA", self.t0 + timedelta(milliseconds=200))

        self._add_damage(400)
        self.correlator.on_reload_drop("WeaponB", self.t0 + timedelta(milliseconds=600))

        a1 = self.combat_log.get_by_id("ev-50")
        a2 = self.combat_log.get_by_id("ev-400")
        self.assertEqual(a1.tool_name, "WeaponA")
        self.assertEqual(a2.tool_name, "WeaponB")


class TestReloadCorrelatorProperties(unittest.TestCase):
    def test_last_drop_state(self):
        config = MagicMock()
        config.reload_correlation_window_ms = 500
        config.reload_correlation_enabled = True
        combat_log = CombatActionLog()
        db = MagicMock()
        correlator = ReloadCorrelator(config, combat_log, db)

        self.assertIsNone(correlator.last_drop_tool)
        self.assertIsNone(correlator.last_drop_time)

        t = datetime(2026, 3, 19, 12, 0, 0)
        correlator.on_reload_drop("Gun", t)
        self.assertEqual(correlator.last_drop_tool, "Gun")
        self.assertEqual(correlator.last_drop_time, t)


if __name__ == "__main__":
    unittest.main()
