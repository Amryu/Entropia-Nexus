import os
import sqlite3
import tempfile
import unittest

from client.core.database import Database
from client.hunt.tool_inference import ToolInferenceEngine


class TestGearOverridesDB(unittest.TestCase):

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

    def test_set_get_round_trip(self):
        self.db.set_gear_override(
            "Opalo",
            decay_pec_per_use=6.5,
            ammo_use_per_shot=9.1,
            custom_markup=115.0,
            custom_markup_type="percentage",
            note="test",
        )
        row = self.db.get_gear_override("Opalo")
        self.assertIsNotNone(row)
        self.assertAlmostEqual(row["decay_pec_per_use"], 6.5)
        self.assertAlmostEqual(row["ammo_use_per_shot"], 9.1)
        self.assertAlmostEqual(row["custom_markup"], 115.0)
        self.assertEqual(row["custom_markup_type"], "percentage")
        self.assertEqual(row["note"], "test")

    def test_case_insensitive_lookup(self):
        self.db.set_gear_override("Jester D-1 (L)", decay_pec_per_use=2.0)
        self.assertIsNotNone(self.db.get_gear_override("jester d-1 (l)"))
        self.assertIsNotNone(self.db.get_gear_override("JESTER D-1 (L)"))

    def test_get_all(self):
        self.db.set_gear_override("A", decay_pec_per_use=1.0)
        self.db.set_gear_override("B", ammo_use_per_shot=2.0)
        all_overrides = self.db.get_all_gear_overrides()
        self.assertIn("a", all_overrides)
        self.assertIn("b", all_overrides)

    def test_delete(self):
        self.db.set_gear_override("Gone", decay_pec_per_use=1.0)
        self.db.delete_gear_override("Gone")
        self.assertIsNone(self.db.get_gear_override("Gone"))


class TestToolInferenceOverridePrecedence(unittest.TestCase):

    def _engine(self) -> ToolInferenceEngine:
        ti = ToolInferenceEngine()
        ti.load_signature(
            "Opalo", damage_min=10, damage_max=30,
            total_damage=1000, cost_per_shot=20.0,
            decay_pec=8.0, ammo_pec=12.0,
        )
        return ti

    def test_no_override_returns_base(self):
        ti = self._engine()
        self.assertEqual(ti.get_cost_per_shot("Opalo"), 20.0)

    def test_decay_only_override(self):
        ti = self._engine()
        ti.set_override_provider(lambda: {
            "opalo": {"decay_pec_per_use": 5.0, "ammo_use_per_shot": None},
        })
        # 5 (override) + 12 (signature ammo) = 17
        self.assertAlmostEqual(ti.get_cost_per_shot("Opalo"), 17.0)

    def test_ammo_only_override(self):
        ti = self._engine()
        ti.set_override_provider(lambda: {
            "opalo": {"decay_pec_per_use": None, "ammo_use_per_shot": 20.0},
        })
        # 8 (signature decay) + 20 (override ammo) = 28
        self.assertAlmostEqual(ti.get_cost_per_shot("Opalo"), 28.0)

    def test_full_override(self):
        ti = self._engine()
        ti.set_override_provider(lambda: {
            "opalo": {"decay_pec_per_use": 5.0, "ammo_use_per_shot": 9.0},
        })
        self.assertAlmostEqual(ti.get_cost_per_shot("Opalo"), 14.0)

    def test_unknown_tool_without_signature_but_full_override(self):
        ti = ToolInferenceEngine()
        ti.set_override_provider(lambda: {
            "mystery tool": {"decay_pec_per_use": 1.5, "ammo_use_per_shot": 2.5},
        })
        self.assertAlmostEqual(ti.get_cost_per_shot("Mystery Tool"), 4.0)

    def test_custom_markup_readback(self):
        ti = self._engine()
        ti.set_override_provider(lambda: {
            "opalo": {"custom_markup": 115.0, "custom_markup_type": "percentage"},
        })
        value, typ = ti.get_custom_markup("Opalo")
        self.assertAlmostEqual(value, 115.0)
        self.assertEqual(typ, "percentage")


if __name__ == "__main__":
    unittest.main()
