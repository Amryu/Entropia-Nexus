import unittest
from datetime import datetime
from unittest.mock import MagicMock

from client.hunt.combat_action_log import CombatAction
from client.hunt.tool_inference import ToolInferenceEngine


class TestToolInferenceEngine(unittest.TestCase):
    def setUp(self):
        self.engine = ToolInferenceEngine()

    # --- Signature loading ---

    def test_no_signatures_returns_none(self):
        name, conf, cost = self.engine.infer_tool(50.0)
        self.assertIsNone(name)
        self.assertAlmostEqual(conf, 0.0)
        self.assertAlmostEqual(cost, 0.0)

    def test_load_signature_and_match(self):
        self.engine.load_signature("WeaponA", 30.0, 60.0, 50.0, 0.15)
        name, conf, cost = self.engine.infer_tool(45.0)
        self.assertEqual(name, "WeaponA")
        self.assertGreater(conf, 0.7)
        self.assertAlmostEqual(cost, 0.15)

    def test_damage_outside_range_no_match(self):
        self.engine.load_signature("WeaponA", 30.0, 60.0, 50.0, 0.15)
        name, conf, cost = self.engine.infer_tool(100.0)
        self.assertIsNone(name)
        self.assertAlmostEqual(conf, 0.0)

    def test_zero_damage_no_match(self):
        self.engine.load_signature("WeaponA", 30.0, 60.0, 50.0, 0.15)
        name, conf, cost = self.engine.infer_tool(0.0)
        self.assertIsNone(name)

    def test_load_from_loadout_stats(self):
        stats = MagicMock()
        stats.damage_interval_min = 30.0
        stats.damage_interval_max = 60.0
        stats.total_damage = 50.0
        stats.cost = 0.15
        self.engine.load_from_loadout_stats("Gun", stats)
        self.assertTrue(self.engine.has_signatures)
        name, conf, cost = self.engine.infer_tool(45.0)
        self.assertEqual(name, "Gun")

    def test_load_from_loadout_stats_no_name(self):
        stats = MagicMock()
        stats.damage_interval_min = 30.0
        self.engine.load_from_loadout_stats("", stats)
        self.assertFalse(self.engine.has_signatures)

    def test_load_from_loadout_stats_zero_damage(self):
        stats = MagicMock()
        stats.damage_interval_min = 0
        stats.damage_interval_max = 60.0
        stats.total_damage = 50.0
        stats.cost = 0.15
        self.engine.load_from_loadout_stats("Gun", stats)
        self.assertFalse(self.engine.has_signatures)

    def test_duplicate_signature_replaced(self):
        self.engine.load_signature("Gun", 30.0, 60.0, 50.0, 0.15)
        self.engine.load_signature("Gun", 80.0, 120.0, 100.0, 0.25)
        # Old range should not match
        name, _, _ = self.engine.infer_tool(45.0)
        self.assertIsNone(name)
        # New range should match
        name, _, cost = self.engine.infer_tool(100.0)
        self.assertEqual(name, "Gun")
        self.assertAlmostEqual(cost, 0.25)

    # --- Cost lookup ---

    def test_get_cost_per_shot(self):
        self.engine.load_signature("WeaponA", 30.0, 60.0, 50.0, 0.15)
        self.assertAlmostEqual(self.engine.get_cost_per_shot("WeaponA"), 0.15)

    def test_get_cost_per_shot_unknown(self):
        self.assertAlmostEqual(self.engine.get_cost_per_shot("NoSuchGun"), 0.0)

    # --- Confidence ---

    def test_confidence_narrower_interval_higher(self):
        self.engine.load_signature("Narrow", 48.0, 52.0, 50.0, 0.10)
        _, conf_narrow, _ = self.engine.infer_tool(50.0)

        self.engine.clear()
        self.engine.load_signature("Wide", 20.0, 80.0, 50.0, 0.10)
        _, conf_wide, _ = self.engine.infer_tool(50.0)

        self.assertGreater(conf_narrow, conf_wide)

    # --- Timeline enrichment (using CombatAction objects) ---

    def _action(self, action_id, timestamp, amount=50.0, event_type="damage_dealt",
                tool_name=None, tool_source=None):
        return CombatAction(
            id=action_id,
            encounter_id="enc-1",
            timestamp=timestamp,
            event_type=event_type,
            amount=amount,
            tool_name=tool_name,
            tool_source=tool_source,
        )

    def test_enrich_via_timeline(self):
        now = datetime(2026, 1, 1, 12, 0, 0)
        actions = [self._action("e1", now)]

        self.engine.on_tool_detected("Gun", now)
        enriched = self.engine.enrich_actions(actions)
        self.assertEqual(len(enriched), 1)
        self.assertEqual(enriched[0][1], "Gun")  # tool_name
        self.assertEqual(enriched[0][2], "ocr_timeline")  # source
        self.assertAlmostEqual(enriched[0][3], 0.85)  # confidence

    def test_enrich_multi_weapon_timeline(self):
        """Events before/between/after tool changes are correctly attributed."""
        t1 = datetime(2026, 1, 1, 12, 0, 0)
        t2 = datetime(2026, 1, 1, 12, 0, 5)
        t3 = datetime(2026, 1, 1, 12, 0, 10)

        actions = [
            self._action("e1", t1),
            self._action("e2", t2),
            self._action("e3", t3),
        ]

        self.engine.on_tool_detected("GunA", t1)
        self.engine.on_tool_detected("GunB", t2)

        enriched = self.engine.enrich_actions(actions)
        enriched_map = {eid: tool for eid, tool, _, _ in enriched}

        self.assertEqual(enriched_map["e1"], "GunA")   # before switch
        self.assertEqual(enriched_map["e2"], "GunB")   # at switch time
        self.assertEqual(enriched_map["e3"], "GunB")   # after switch

    def test_enrich_skips_already_attributed(self):
        now = datetime(2026, 1, 1, 12, 0, 0)
        actions = [self._action("e1", now, tool_name="Gun", tool_source="ocr")]
        self.engine.on_tool_detected("OtherGun", now)

        enriched = self.engine.enrich_actions(actions)
        self.assertEqual(len(enriched), 0)  # ocr has higher priority than ocr_timeline

    def test_enrich_skips_non_damage_events(self):
        now = datetime(2026, 1, 1, 12, 0, 0)
        actions = [self._action("e1", now, event_type="player_evade")]
        self.engine.on_tool_detected("Gun", now)

        enriched = self.engine.enrich_actions(actions)
        self.assertEqual(len(enriched), 0)

    def test_enrich_upgrades_inferred(self):
        """Events with 'inferred' source can be upgraded to 'ocr_timeline'."""
        now = datetime(2026, 1, 1, 12, 0, 0)
        actions = [self._action("e1", now, tool_name="InferredGun", tool_source="inferred")]
        self.engine.on_tool_detected("ActualGun", now)

        enriched = self.engine.enrich_actions(actions)
        self.assertEqual(len(enriched), 1)
        self.assertEqual(enriched[0][1], "ActualGun")

    def test_clear_resets_all_state(self):
        self.engine.load_signature("Gun", 30.0, 60.0, 50.0, 0.15)
        now = datetime(2026, 1, 1, 12, 0, 0)
        self.engine.on_tool_detected("Gun", now)

        self.engine.clear()
        self.assertFalse(self.engine.has_signatures)

    def test_timeline_dedup(self):
        """Same tool detected repeatedly doesn't duplicate timeline entries."""
        now = datetime(2026, 1, 1, 12, 0, 0)
        self.engine.on_tool_detected("Gun", now)
        self.engine.on_tool_detected("Gun", now)
        self.assertEqual(len(self.engine._tool_timeline), 1)

    def test_enrich_no_timeline_returns_empty(self):
        now = datetime(2026, 1, 1, 12, 0, 0)
        actions = [self._action("e1", now)]
        enriched = self.engine.enrich_actions(actions)
        self.assertEqual(len(enriched), 0)


if __name__ == "__main__":
    unittest.main()
