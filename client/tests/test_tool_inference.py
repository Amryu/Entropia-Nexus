import unittest
from datetime import datetime
from unittest.mock import MagicMock

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

    # --- Per-encounter buffering and enrichment ---

    def test_buffer_and_enrich_via_timeline(self):
        now = datetime(2026, 1, 1, 12, 0, 0)
        event = self.engine.create_event(
            encounter_id="enc-1", timestamp=now,
            event_type="damage_dealt", amount=50.0,
        )
        self.assertIsNone(event.tool_name)
        self.engine.buffer_event("enc-1", event.id, now, 50.0, False)

        # Record tool on timeline and enrich
        self.engine.on_tool_detected("Gun", now)
        enriched = self.engine.enrich_encounter("enc-1")
        self.assertEqual(len(enriched), 1)
        self.assertEqual(enriched[0][1], "Gun")  # tool_name
        self.assertEqual(enriched[0][2], "ocr_timeline")  # source
        self.assertAlmostEqual(enriched[0][3], 0.85)  # confidence

    def test_enrich_with_tool_timeline_multi_weapon(self):
        """Events before/between/after tool changes are correctly attributed."""
        t1 = datetime(2026, 1, 1, 12, 0, 0)
        t2 = datetime(2026, 1, 1, 12, 0, 5)
        t3 = datetime(2026, 1, 1, 12, 0, 10)

        # Buffer 3 events at different times
        self.engine.buffer_event("enc-1", "e1", t1, 50.0, False)
        self.engine.buffer_event("enc-1", "e2", t2, 60.0, False)
        self.engine.buffer_event("enc-1", "e3", t3, 70.0, False)

        # Tool change at t2: switched from GunA to GunB
        self.engine.on_tool_detected("GunA", t1)
        self.engine.on_tool_detected("GunB", t2)

        enriched = self.engine.enrich_encounter("enc-1")
        enriched_map = {eid: tool for eid, tool, _, _ in enriched}

        self.assertEqual(enriched_map["e1"], "GunA")   # before switch
        self.assertEqual(enriched_map["e2"], "GunB")   # at switch time → new tool
        self.assertEqual(enriched_map["e3"], "GunB")   # after switch

    def test_enrich_skips_already_attributed(self):
        now = datetime(2026, 1, 1, 12, 0, 0)
        # Buffer event that already has a tool
        self.engine.buffer_event("enc-1", "e1", now, 50.0, False, "Gun", "ocr")
        self.engine.on_tool_detected("OtherGun", now)

        enriched = self.engine.enrich_encounter("enc-1")
        self.assertEqual(len(enriched), 0)  # Already attributed, not enriched

    def test_clear_encounter(self):
        now = datetime(2026, 1, 1, 12, 0, 0)
        self.engine.buffer_event("enc-1", "e1", now, 50.0, False)
        self.engine.clear_encounter("enc-1")
        self.assertEqual(len(self.engine.get_encounter_events("enc-1")), 0)

    def test_clear_resets_all_state(self):
        self.engine.load_signature("Gun", 30.0, 60.0, 50.0, 0.15)
        now = datetime(2026, 1, 1, 12, 0, 0)
        self.engine.buffer_event("enc-1", "e1", now, 50.0, False)
        self.engine.on_tool_detected("Gun", now)

        self.engine.clear()
        self.assertFalse(self.engine.has_signatures)
        self.assertEqual(len(self.engine.get_encounter_events("enc-1")), 0)

    def test_timeline_dedup(self):
        """Same tool detected repeatedly doesn't duplicate timeline entries."""
        now = datetime(2026, 1, 1, 12, 0, 0)
        self.engine.on_tool_detected("Gun", now)
        self.engine.on_tool_detected("Gun", now)
        self.assertEqual(len(self.engine._tool_timeline), 1)

    def test_enrich_no_timeline_returns_empty(self):
        now = datetime(2026, 1, 1, 12, 0, 0)
        self.engine.buffer_event("enc-1", "e1", now, 50.0, False)
        enriched = self.engine.enrich_encounter("enc-1")
        self.assertEqual(len(enriched), 0)


if __name__ == "__main__":
    unittest.main()
