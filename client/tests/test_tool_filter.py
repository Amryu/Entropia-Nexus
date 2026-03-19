import unittest
from unittest.mock import MagicMock

from client.hunt.tool_filter import ToolFilter


class TestToolFilter(unittest.TestCase):
    def _config(self, mode="blacklist", tools=None):
        config = MagicMock()
        config.tool_cost_filter_mode = mode
        config.tool_cost_filter_list = tools or []
        return config

    # --- Blacklist mode ---

    def test_blacklist_empty_includes_all(self):
        f = ToolFilter(self._config("blacklist", []))
        self.assertTrue(f.should_include_cost("WeaponA"))
        self.assertTrue(f.should_include_cost("HealingFAP"))

    def test_blacklist_excludes_listed(self):
        f = ToolFilter(self._config("blacklist", ["HealingFAP", "MiningDrill"]))
        self.assertTrue(f.should_include_cost("WeaponA"))
        self.assertFalse(f.should_include_cost("HealingFAP"))
        self.assertFalse(f.should_include_cost("MiningDrill"))

    def test_blacklist_case_insensitive(self):
        f = ToolFilter(self._config("blacklist", ["healingfap"]))
        self.assertFalse(f.should_include_cost("HealingFAP"))
        self.assertFalse(f.should_include_cost("HEALINGFAP"))

    def test_blacklist_unknown_included(self):
        f = ToolFilter(self._config("blacklist", []))
        self.assertTrue(f.should_include_cost("Unknown"))

    def test_blacklist_none_included(self):
        f = ToolFilter(self._config("blacklist", []))
        self.assertTrue(f.should_include_cost(None))

    # --- Whitelist mode ---

    def test_whitelist_empty_excludes_all(self):
        f = ToolFilter(self._config("whitelist", []))
        self.assertFalse(f.should_include_cost("WeaponA"))

    def test_whitelist_includes_listed(self):
        f = ToolFilter(self._config("whitelist", ["WeaponA", "WeaponB"]))
        self.assertTrue(f.should_include_cost("WeaponA"))
        self.assertTrue(f.should_include_cost("WeaponB"))
        self.assertFalse(f.should_include_cost("HealingFAP"))

    def test_whitelist_case_insensitive(self):
        f = ToolFilter(self._config("whitelist", ["WeaponA"]))
        self.assertTrue(f.should_include_cost("weapona"))

    def test_whitelist_unknown_excluded(self):
        f = ToolFilter(self._config("whitelist", ["WeaponA"]))
        self.assertFalse(f.should_include_cost("Unknown"))
        self.assertFalse(f.should_include_cost(None))

    # --- Config reload ---

    def test_on_config_changed_reloads(self):
        config = self._config("blacklist", [])
        f = ToolFilter(config)
        self.assertTrue(f.should_include_cost("Gun"))

        config.tool_cost_filter_list = ["Gun"]
        f.on_config_changed()
        self.assertFalse(f.should_include_cost("Gun"))


if __name__ == "__main__":
    unittest.main()
