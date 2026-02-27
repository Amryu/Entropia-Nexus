"""Tests for the MarkupResolver: priority chain, CRUD, and computation."""

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock

from client.core.database import Database
from client.hunt.markup_resolver import (
    ExchangeItemData, MarkupResolver, MarkupResult,
)


def _make_db():
    """Create a fresh in-memory database."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return Database(path), path


class TestMarkupResult(unittest.TestCase):

    def test_percentage_compute(self):
        r = MarkupResult(markup_value=115.0, markup_type="percentage", source="custom")
        self.assertAlmostEqual(r.compute(10.0), 11.5)

    def test_absolute_compute(self):
        r = MarkupResult(markup_value=5.0, markup_type="absolute", source="custom")
        self.assertAlmostEqual(r.compute(10.0), 15.0)

    def test_default_percentage_compute(self):
        r = MarkupResult(markup_value=100.0, markup_type="percentage", source="default")
        self.assertAlmostEqual(r.compute(10.0), 10.0)

    def test_default_absolute_compute(self):
        r = MarkupResult(markup_value=0.0, markup_type="absolute", source="default")
        self.assertAlmostEqual(r.compute(10.0), 10.0)


class TestCustomMarkupCRUD(unittest.TestCase):

    def setUp(self):
        self.db, self.db_path = _make_db()
        self.resolver = MarkupResolver(self.db)

    def tearDown(self):
        self.db.close()
        os.unlink(self.db_path)

    def test_set_and_get_custom_markup(self):
        self.resolver.set_custom_markup("Animal Hide", 135.0, "percentage")
        result = self.resolver.resolve("Animal Hide")
        self.assertEqual(result.source, "custom")
        self.assertAlmostEqual(result.markup_value, 135.0)
        self.assertEqual(result.markup_type, "percentage")

    def test_set_absolute_custom_markup(self):
        self.resolver.set_custom_markup("Armatrix LR-35 (L)", 12.5, "absolute")
        result = self.resolver.resolve("Armatrix LR-35 (L)")
        self.assertEqual(result.source, "custom")
        self.assertAlmostEqual(result.markup_value, 12.5)
        self.assertEqual(result.markup_type, "absolute")

    def test_remove_custom_markup(self):
        self.resolver.set_custom_markup("Animal Hide", 135.0)
        self.resolver.remove_custom_markup("Animal Hide")
        result = self.resolver.resolve("Animal Hide")
        self.assertEqual(result.source, "default")

    def test_update_custom_markup(self):
        self.resolver.set_custom_markup("Animal Hide", 135.0)
        self.resolver.set_custom_markup("Animal Hide", 150.0)
        result = self.resolver.resolve("Animal Hide")
        self.assertAlmostEqual(result.markup_value, 150.0)

    def test_get_all_custom_markups(self):
        self.resolver.set_custom_markup("Animal Hide", 135.0)
        self.resolver.set_custom_markup("Soft Hide", 120.0)
        all_markups = self.resolver.get_all_custom_markups()
        self.assertEqual(len(all_markups), 2)
        names = {m["item_name"] for m in all_markups}
        self.assertEqual(names, {"Animal Hide", "Soft Hide"})

    def test_percentage_minimum_enforced(self):
        """Percentage markup cannot be below 100%."""
        self.resolver.set_custom_markup("Animal Hide", 50.0, "percentage")
        result = self.resolver.resolve("Animal Hide")
        self.assertAlmostEqual(result.markup_value, 100.0)

    def test_absolute_minimum_enforced(self):
        """Absolute markup cannot be below 0."""
        self.resolver.set_custom_markup("Weapon (L)", -5.0, "absolute")
        result = self.resolver.resolve("Weapon (L)")
        self.assertAlmostEqual(result.markup_value, 0.0)


class TestPriorityChain(unittest.TestCase):

    def setUp(self):
        self.db, self.db_path = _make_db()
        self.resolver = MarkupResolver(self.db)

    def tearDown(self):
        self.db.close()
        os.unlink(self.db_path)

    def test_default_when_no_sources(self):
        """With no caches loaded, should return default (100% / +0)."""
        result = self.resolver.resolve("Animal Hide")
        self.assertEqual(result.source, "default")
        self.assertAlmostEqual(result.markup_value, 100.0)
        self.assertEqual(result.markup_type, "percentage")

    def test_market_overrides_default(self):
        """Exchange cache should override default."""
        self.resolver._exchange_cache = {
            "animal hide": ExchangeItemData(
                item_id=1, name="Animal Hide", item_type="Material",
                sub_type=None, value=0.01, wap=115.0, median=112.0, p10=108.0,
            )
        }
        self.resolver._item_name_to_type = {"animal hide": "Material"}
        self.resolver._item_name_to_sub_type = {"animal hide": None}
        result = self.resolver.resolve("Animal Hide")
        self.assertEqual(result.source, "market")
        self.assertAlmostEqual(result.markup_value, 115.0)

    def test_inventory_overrides_market(self):
        """Inventory markup should override exchange."""
        self.resolver._exchange_cache = {
            "animal hide": ExchangeItemData(
                item_id=1, name="Animal Hide", item_type="Material",
                sub_type=None, value=0.01, wap=115.0, median=112.0, p10=108.0,
            )
        }
        self.resolver._item_name_to_type = {"animal hide": "Material"}
        self.resolver._item_name_to_sub_type = {"animal hide": None}
        self.resolver._inventory_markups = {"animal hide": 130.0}

        result = self.resolver.resolve("Animal Hide")
        self.assertEqual(result.source, "inventory")
        self.assertAlmostEqual(result.markup_value, 130.0)

    def test_custom_overrides_all(self):
        """Custom local markup should override everything else."""
        self.resolver._exchange_cache = {
            "animal hide": ExchangeItemData(
                item_id=1, name="Animal Hide", item_type="Material",
                sub_type=None, value=0.01, wap=115.0, median=112.0, p10=108.0,
            )
        }
        self.resolver._item_name_to_type = {"animal hide": "Material"}
        self.resolver._item_name_to_sub_type = {"animal hide": None}
        self.resolver._inventory_markups = {"animal hide": 130.0}
        self.resolver.set_custom_markup("Animal Hide", 150.0)

        result = self.resolver.resolve("Animal Hide")
        self.assertEqual(result.source, "custom")
        self.assertAlmostEqual(result.markup_value, 150.0)

    def test_exchange_without_wap_falls_through(self):
        """Exchange item with no WAP should fall through to default."""
        self.resolver._exchange_cache = {
            "rare item": ExchangeItemData(
                item_id=2, name="Rare Item", item_type="Material",
                sub_type=None, value=0.01, wap=None, median=None, p10=None,
            )
        }
        result = self.resolver.resolve("Rare Item")
        self.assertEqual(result.source, "default")

    def test_inventory_empty_falls_through_to_market(self):
        """If inventory markups loaded but item not in it, fall through to market."""
        self.resolver._exchange_cache = {
            "animal hide": ExchangeItemData(
                item_id=1, name="Animal Hide", item_type="Material",
                sub_type=None, value=0.01, wap=115.0, median=112.0, p10=108.0,
            )
        }
        self.resolver._item_name_to_type = {"animal hide": "Material"}
        self.resolver._item_name_to_sub_type = {"animal hide": None}
        self.resolver._inventory_markups = {}  # loaded but empty

        result = self.resolver.resolve("Animal Hide")
        self.assertEqual(result.source, "market")


class TestComputeMuValue(unittest.TestCase):

    def setUp(self):
        self.db, self.db_path = _make_db()
        self.resolver = MarkupResolver(self.db)

    def tearDown(self):
        self.db.close()
        os.unlink(self.db_path)

    def test_default_mu_equals_tt(self):
        mu, source = self.resolver.compute_mu_value("Unknown Item", 10.0)
        self.assertAlmostEqual(mu, 10.0)
        self.assertEqual(source, "default")

    def test_custom_mu_computation(self):
        self.resolver.set_custom_markup("Animal Hide", 135.0, "percentage")
        mu, source = self.resolver.compute_mu_value("Animal Hide", 10.0)
        self.assertAlmostEqual(mu, 13.5)
        self.assertEqual(source, "custom")

    def test_market_mu_computation(self):
        self.resolver._exchange_cache = {
            "soft hide": ExchangeItemData(
                item_id=3, name="Soft Hide", item_type="Material",
                sub_type=None, value=0.01, wap=120.0, median=118.0, p10=115.0,
            )
        }
        self.resolver._item_name_to_type = {"soft hide": "Material"}
        self.resolver._item_name_to_sub_type = {"soft hide": None}
        mu, source = self.resolver.compute_mu_value("Soft Hide", 5.0)
        self.assertAlmostEqual(mu, 6.0)  # 5.0 * 120/100 = 6.0
        self.assertEqual(source, "market")


class TestRefreshExchangeCache(unittest.TestCase):

    def setUp(self):
        self.db, self.db_path = _make_db()
        self.nexus_client = MagicMock()
        self.resolver = MarkupResolver(self.db, nexus_client=self.nexus_client)

    def tearDown(self):
        self.db.close()
        os.unlink(self.db_path)

    def test_refresh_success(self):
        self.nexus_client.get_exchange_items.return_value = [
            {"i": 1, "n": "Animal Hide", "t": "Material", "v": 0.01,
             "w": 115.0, "m": 112.0, "p": 108.0, "st": None},
            {"i": 2, "n": "Opalo (L)", "t": "Weapon", "v": 2.0,
             "w": 3.5, "m": 3.0, "p": 2.5, "st": None},
        ]
        ok = self.resolver.refresh_exchange_cache()
        self.assertTrue(ok)
        self.assertEqual(len(self.resolver._exchange_cache), 2)
        self.assertIn("animal hide", self.resolver._exchange_cache)

    def test_refresh_failure(self):
        self.nexus_client.get_exchange_items.return_value = None
        ok = self.resolver.refresh_exchange_cache()
        self.assertFalse(ok)

    def test_refresh_no_nexus_client(self):
        resolver = MarkupResolver(self.db)
        ok = resolver.refresh_exchange_cache()
        self.assertFalse(ok)


class TestRefreshInventoryMarkups(unittest.TestCase):

    def setUp(self):
        self.db, self.db_path = _make_db()
        self.nexus_client = MagicMock()
        self.nexus_client.is_authenticated.return_value = True
        self.data_client = MagicMock()
        self.resolver = MarkupResolver(
            self.db, nexus_client=self.nexus_client, data_client=self.data_client
        )
        # Pre-populate exchange cache for ID→name mapping
        self.resolver._item_id_to_name = {1: "Animal Hide", 2: "Soft Hide"}

    def tearDown(self):
        self.db.close()
        os.unlink(self.db_path)

    def test_refresh_success(self):
        self.nexus_client.get_inventory_markups.return_value = [
            {"item_id": 1, "markup": 135.0},
            {"item_id": 2, "markup": 120.0},
        ]
        ok = self.resolver.refresh_inventory_markups()
        self.assertTrue(ok)
        self.assertEqual(len(self.resolver._inventory_markups), 2)
        self.assertAlmostEqual(self.resolver._inventory_markups["animal hide"], 135.0)

    def test_refresh_not_authenticated(self):
        self.nexus_client.is_authenticated.return_value = False
        ok = self.resolver.refresh_inventory_markups()
        self.assertFalse(ok)

    def test_refresh_failure(self):
        self.nexus_client.get_inventory_markups.return_value = None
        ok = self.resolver.refresh_inventory_markups()
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
