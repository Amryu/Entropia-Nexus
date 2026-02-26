import unittest
from unittest.mock import MagicMock

from client.hunt.loot_filter import LootFilter, DEFAULT_BLACKLIST


def _make_config(**overrides):
    config = MagicMock()
    config.loot_blacklist = overrides.get("loot_blacklist", [])
    config.loot_blacklist_per_mob = overrides.get("loot_blacklist_per_mob", {})
    return config


def _make_data_client(refining_products=None, mob_loots=None):
    client = MagicMock()

    if refining_products is not None:
        client.get_refining_recipes.return_value = [
            {"Product": {"Name": name}} for name in refining_products
        ]
    else:
        client.get_refining_recipes.return_value = []

    if mob_loots is not None:
        client.get_mob_loots.return_value = [
            {"Item": {"Name": name}} for name in mob_loots
        ]
    else:
        client.get_mob_loots.return_value = []

    return client


class TestBlacklist(unittest.TestCase):

    def test_default_blacklist_universal_ammo(self):
        lf = LootFilter(_make_config())
        result = lf.classify("Universal Ammo")
        self.assertTrue(result["is_blacklisted"])
        self.assertFalse(result["should_count"])

    def test_case_insensitive(self):
        lf = LootFilter(_make_config())
        result = lf.classify("UNIVERSAL AMMO")
        self.assertTrue(result["is_blacklisted"])

    def test_user_blacklist_item(self):
        config = _make_config(loot_blacklist=["Shrapnel"])
        lf = LootFilter(config)
        result = lf.classify("Shrapnel")
        self.assertTrue(result["is_blacklisted"])
        self.assertFalse(result["should_count"])

    def test_per_mob_blacklist(self):
        config = _make_config(loot_blacklist_per_mob={"atrox": ["Nova Fragment"]})
        lf = LootFilter(config)
        result = lf.classify("Nova Fragment", mob_name="Atrox")
        self.assertTrue(result["is_blacklisted"])

    def test_per_mob_blacklist_wrong_mob(self):
        config = _make_config(loot_blacklist_per_mob={"atrox": ["Nova Fragment"]})
        lf = LootFilter(config)
        result = lf.classify("Nova Fragment", mob_name="Foul")
        self.assertFalse(result["is_blacklisted"])


class TestNormalLoot(unittest.TestCase):

    def test_normal_loot_counted(self):
        lf = LootFilter(_make_config())
        result = lf.classify("Animal Muscle Oil", mob_name="Atrox")
        self.assertFalse(result["is_blacklisted"])
        self.assertTrue(result["should_count"])


class TestRefiningOutput(unittest.TestCase):

    def test_refining_output_excluded(self):
        data_client = _make_data_client(
            refining_products=["Lysterium Ingot"],
            mob_loots=["Animal Muscle Oil"],  # Lysterium Ingot not in loot table
        )
        lf = LootFilter(_make_config(), data_client)
        result = lf.classify("Lysterium Ingot", mob_name="Atrox")
        self.assertTrue(result["is_refining_output"])
        self.assertFalse(result["should_count"])

    def test_refining_in_loot_table_counted(self):
        data_client = _make_data_client(
            refining_products=["Lysterium Ingot"],
            mob_loots=["Lysterium Ingot", "Animal Muscle Oil"],
        )
        lf = LootFilter(_make_config(), data_client)
        result = lf.classify("Lysterium Ingot", mob_name="Atrox")
        # Refining output overridden because mob actually drops it
        self.assertFalse(result["is_refining_output"])
        self.assertTrue(result["should_count"])


class TestGracefulDegradation(unittest.TestCase):

    def test_unknown_mob_assumes_valid(self):
        lf = LootFilter(_make_config())
        result = lf.classify("Animal Muscle Oil", mob_name=None)
        self.assertTrue(result["is_in_loot_table"])
        self.assertTrue(result["should_count"])

    def test_no_data_client_only_blacklist(self):
        lf = LootFilter(_make_config(), data_client=None)
        result = lf.classify("Animal Muscle Oil", mob_name="Atrox")
        self.assertTrue(result["should_count"])
        # Universal Ammo still blacklisted
        result2 = lf.classify("Universal Ammo")
        self.assertTrue(result2["is_blacklisted"])

    def test_api_failure_graceful(self):
        client = MagicMock()
        client.get_refining_recipes.side_effect = ConnectionError("timeout")
        client.get_mob_loots.side_effect = ConnectionError("timeout")
        lf = LootFilter(_make_config(), client)
        result = lf.classify("Animal Muscle Oil", mob_name="Atrox")
        # Both API calls fail, but item is still counted (graceful degradation)
        self.assertTrue(result["should_count"])
        self.assertTrue(result["is_in_loot_table"])  # Assumed valid when API fails


class TestMobLootCache(unittest.TestCase):

    def test_mob_loot_cache_hit(self):
        data_client = _make_data_client(mob_loots=["Animal Muscle Oil"])
        lf = LootFilter(_make_config(), data_client)
        lf.classify("Animal Muscle Oil", mob_name="Atrox")
        lf.classify("Animal Muscle Oil", mob_name="Atrox")
        # get_mob_loots called only once (cached)
        data_client.get_mob_loots.assert_called_once()

    def test_invalidate_mob_cache(self):
        data_client = _make_data_client(mob_loots=["Animal Muscle Oil"])
        lf = LootFilter(_make_config(), data_client)
        lf.classify("Animal Muscle Oil", mob_name="Atrox")
        lf.invalidate_mob_cache("Atrox")
        lf.classify("Animal Muscle Oil", mob_name="Atrox")
        self.assertEqual(data_client.get_mob_loots.call_count, 2)

    def test_invalidate_all_cache(self):
        data_client = _make_data_client(mob_loots=["Animal Muscle Oil"])
        lf = LootFilter(_make_config(), data_client)
        lf.classify("Animal Muscle Oil", mob_name="Atrox")
        lf.invalidate_mob_cache()  # clear all
        lf.classify("Animal Muscle Oil", mob_name="Atrox")
        self.assertEqual(data_client.get_mob_loots.call_count, 2)


if __name__ == "__main__":
    unittest.main()
