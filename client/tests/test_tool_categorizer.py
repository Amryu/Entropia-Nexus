import unittest
from unittest.mock import MagicMock

from client.hunt.tool_categorizer import ToolCategorizer


def _stub_client(**buckets):
    client = MagicMock()
    for name in (
        "get_weapons", "get_amplifiers", "get_scopes_and_sights",
        "get_armors", "get_armor_sets", "get_armor_platings",
        "get_medical_tools", "get_medical_chips", "get_stimulants",
        "get_effect_chips", "get_teleportation_chips", "get_misc_tools",
        "get_absorbers", "get_scanners", "get_implants",
        "get_finders", "get_finder_amplifiers", "get_refiners",
        "get_excavators",
    ):
        getattr(client, name).return_value = buckets.get(name, [])
    return client


class TestToolCategorizer(unittest.TestCase):

    def test_weapon_offense(self):
        tc = ToolCategorizer(_stub_client(
            get_weapons=[{"Name": "Jester D-1 (L)", "Type": "Handgun"}],
        ))
        self.assertEqual(tc.category_for("Jester D-1 (L)"), "offense")
        self.assertEqual(tc.item_type_for("Jester D-1 (L)"), "Handgun")

    def test_armor_defense(self):
        tc = ToolCategorizer(_stub_client(
            get_armors=[{"Name": "Shogun Arm Guards (M)", "Type": "Armor"}],
        ))
        self.assertEqual(tc.category_for("Shogun Arm Guards (M)"), "defense")

    def test_fap_defense(self):
        tc = ToolCategorizer(_stub_client(
            get_medical_tools=[{"Name": "ML-35", "Type": "Medical Tool"}],
        ))
        self.assertEqual(tc.category_for("ML-35"), "defense")

    def test_effect_chip_utility(self):
        tc = ToolCategorizer(_stub_client(
            get_effect_chips=[{"Name": "Firework Chip", "Type": "Effect Chip"}],
        ))
        self.assertEqual(tc.category_for("Firework Chip"), "utility")

    def test_mining_tool_excluded(self):
        tc = ToolCategorizer(_stub_client(
            get_finders=[{"Name": "IFN Z120", "Type": "Finder"}],
            get_excavators=[{"Name": "Excavator Mk. II", "Type": "Excavator"}],
        ))
        self.assertIsNone(tc.category_for("IFN Z120"))
        self.assertIsNone(tc.category_for("Excavator Mk. II"))

    def test_unknown_defaults_to_utility(self):
        tc = ToolCategorizer(_stub_client())
        self.assertEqual(tc.category_for("Widgetron X"), "utility")

    def test_empty_and_none(self):
        tc = ToolCategorizer(_stub_client())
        self.assertIsNone(tc.category_for(None))
        self.assertIsNone(tc.category_for(""))

    def test_case_insensitive(self):
        tc = ToolCategorizer(_stub_client(
            get_weapons=[{"Name": "Opalo", "Type": "Handgun"}],
        ))
        self.assertEqual(tc.category_for("opalo"), "offense")
        self.assertEqual(tc.category_for("OPALO"), "offense")

    def test_is_in_loadout(self):
        tc = ToolCategorizer(_stub_client())
        loadout = {"Gear": {"Weapon": {"Name": "Opalo"},
                             "Healing": {"Name": "ML-35"}}}
        self.assertTrue(tc.is_in_loadout("Opalo", loadout))
        self.assertTrue(tc.is_in_loadout("ml-35", loadout))
        self.assertFalse(tc.is_in_loadout("Jester D-1", loadout))
        self.assertFalse(tc.is_in_loadout("Opalo", None))


if __name__ == "__main__":
    unittest.main()
