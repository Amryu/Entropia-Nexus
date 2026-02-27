"""Tests for loot aggregation across encounters."""

import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import MagicMock

from client.core.database import Database
from client.hunt.markup_resolver import MarkupResolver
from client.hunt.session import (
    EncounterLootItem, Hunt, HuntSession, MobEncounter,
)
from client.hunt.stats import (
    aggregate_loot, aggregate_loot_for_hunt, aggregate_loot_for_session,
)


def _make_db():
    """Create a fresh in-memory database."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return Database(path), path


def _enc(enc_id, loot_items=None, mob="Atrox"):
    """Create a minimal MobEncounter with loot items."""
    return MobEncounter(
        id=enc_id,
        session_id="sess-1",
        mob_name=mob,
        mob_name_source="user",
        start_time=datetime(2026, 1, 1, 12, 0),
        end_time=datetime(2026, 1, 1, 12, 1),
        loot_items=loot_items or [],
        loot_total_ped=sum(li.value_ped for li in (loot_items or [])
                          if not li.is_blacklisted and not li.is_refining_output),
    )


def _loot(name, qty, value, *, blacklisted=False, refining=False):
    """Create a loot item."""
    return EncounterLootItem(
        item_name=name,
        quantity=qty,
        value_ped=value,
        is_blacklisted=blacklisted,
        is_refining_output=refining,
    )


class TestAggregateLoot(unittest.TestCase):

    def test_empty_encounters(self):
        result = aggregate_loot([])
        self.assertEqual(result, [])

    def test_single_encounter_single_item(self):
        encs = [_enc("e1", [_loot("Animal Hide", 100, 1.0)])]
        result = aggregate_loot(encs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["item_name"], "Animal Hide")
        self.assertEqual(result[0]["total_quantity"], 100)
        self.assertAlmostEqual(result[0]["tt_value"], 1.0)

    def test_deduplication_across_encounters(self):
        """Same item across multiple encounters should be merged."""
        encs = [
            _enc("e1", [_loot("Animal Hide", 100, 1.0)]),
            _enc("e2", [_loot("Animal Hide", 200, 2.0)]),
            _enc("e3", [_loot("Animal Hide", 50, 0.5)]),
        ]
        result = aggregate_loot(encs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["total_quantity"], 350)
        self.assertAlmostEqual(result[0]["tt_value"], 3.5)

    def test_multiple_items_sorted_by_tt_descending(self):
        encs = [_enc("e1", [
            _loot("Animal Hide", 100, 1.0),
            _loot("Blazar Fragment", 1, 12.0),
            _loot("Animal Oil Residue", 50, 0.5),
        ])]
        result = aggregate_loot(encs)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["item_name"], "Blazar Fragment")
        self.assertEqual(result[1]["item_name"], "Animal Hide")
        self.assertEqual(result[2]["item_name"], "Animal Oil Residue")

    def test_blacklisted_items_excluded(self):
        encs = [_enc("e1", [
            _loot("Animal Hide", 100, 1.0),
            _loot("Shrapnel", 500, 5.0, blacklisted=True),
        ])]
        result = aggregate_loot(encs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["item_name"], "Animal Hide")

    def test_refining_output_excluded(self):
        encs = [_enc("e1", [
            _loot("Animal Hide", 100, 1.0),
            _loot("Refined Hide", 10, 0.8, refining=True),
        ])]
        result = aggregate_loot(encs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["item_name"], "Animal Hide")

    def test_all_items_filtered_gives_empty(self):
        encs = [_enc("e1", [
            _loot("Shrapnel", 500, 5.0, blacklisted=True),
            _loot("Refined Hide", 10, 0.8, refining=True),
        ])]
        result = aggregate_loot(encs)
        self.assertEqual(result, [])

    def test_encounter_with_no_loot(self):
        encs = [_enc("e1", [])]
        result = aggregate_loot(encs)
        self.assertEqual(result, [])

    def test_default_mu_equals_tt_without_resolver(self):
        """Without markup resolver, MU should equal TT."""
        encs = [_enc("e1", [_loot("Animal Hide", 100, 1.0)])]
        result = aggregate_loot(encs, markup_resolver=None)
        self.assertAlmostEqual(result[0]["mu_value"], 1.0)
        self.assertEqual(result[0]["markup_source"], "default")
        self.assertFalse(result[0]["is_custom"])


class TestAggregateLootWithMarkup(unittest.TestCase):

    def setUp(self):
        self.db, self.db_path = _make_db()
        self.resolver = MarkupResolver(self.db)

    def tearDown(self):
        self.db.close()
        os.unlink(self.db_path)

    def test_default_markup_100pct(self):
        """Default markup (100%) should give MU == TT."""
        encs = [_enc("e1", [_loot("Unknown Item", 50, 10.0)])]
        result = aggregate_loot(encs, markup_resolver=self.resolver)
        self.assertAlmostEqual(result[0]["mu_value"], 10.0)
        self.assertEqual(result[0]["markup_source"], "default")

    def test_custom_markup_applied(self):
        """Custom percentage markup should apply correctly."""
        self.resolver.set_custom_markup("Animal Hide", 135.0, "percentage")
        encs = [_enc("e1", [_loot("Animal Hide", 100, 10.0)])]
        result = aggregate_loot(encs, markup_resolver=self.resolver)
        self.assertAlmostEqual(result[0]["mu_value"], 13.5)
        self.assertEqual(result[0]["markup_source"], "custom")
        self.assertTrue(result[0]["is_custom"])

    def test_custom_absolute_markup_applied(self):
        """Custom absolute markup should apply correctly."""
        self.resolver.set_custom_markup("Opalo (L)", 5.0, "absolute")
        encs = [_enc("e1", [_loot("Opalo (L)", 1, 2.0)])]
        result = aggregate_loot(encs, markup_resolver=self.resolver)
        self.assertAlmostEqual(result[0]["mu_value"], 7.0)
        self.assertEqual(result[0]["markup_source"], "custom")

    def test_is_custom_flag_only_for_custom(self):
        """is_custom should be False for non-custom sources."""
        encs = [_enc("e1", [_loot("Animal Hide", 100, 1.0)])]
        result = aggregate_loot(encs, markup_resolver=self.resolver)
        self.assertFalse(result[0]["is_custom"])

    def test_mixed_items_different_markups(self):
        """Different items can have different markup sources."""
        self.resolver.set_custom_markup("Animal Hide", 130.0, "percentage")
        encs = [_enc("e1", [
            _loot("Animal Hide", 100, 10.0),
            _loot("Some Other Item", 50, 5.0),
        ])]
        result = aggregate_loot(encs, markup_resolver=self.resolver)
        by_name = {r["item_name"]: r for r in result}

        self.assertTrue(by_name["Animal Hide"]["is_custom"])
        self.assertAlmostEqual(by_name["Animal Hide"]["mu_value"], 13.0)

        self.assertFalse(by_name["Some Other Item"]["is_custom"])
        self.assertEqual(by_name["Some Other Item"]["markup_source"], "default")

    def test_aggregate_across_encounters_with_markup(self):
        """Markup should apply to the aggregated total, not per-encounter."""
        self.resolver.set_custom_markup("Animal Hide", 150.0, "percentage")
        encs = [
            _enc("e1", [_loot("Animal Hide", 100, 2.0)]),
            _enc("e2", [_loot("Animal Hide", 50, 1.0)]),
        ]
        result = aggregate_loot(encs, markup_resolver=self.resolver)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0]["tt_value"], 3.0)
        # MU is computed on aggregated TT: 3.0 * 150/100 = 4.5
        self.assertAlmostEqual(result[0]["mu_value"], 4.5)


class TestConvenienceWrappers(unittest.TestCase):

    def test_aggregate_loot_for_hunt(self):
        hunt = Hunt(
            id="h1",
            session_id="s1",
            start_time=datetime(2026, 1, 1),
            encounters=[
                _enc("e1", [_loot("Animal Hide", 100, 1.0)]),
                _enc("e2", [_loot("Soft Hide", 50, 0.5)]),
            ],
        )
        result = aggregate_loot_for_hunt(hunt)
        self.assertEqual(len(result), 2)

    def test_aggregate_loot_for_session(self):
        session = HuntSession(
            id="s1",
            start_time=datetime(2026, 1, 1),
            encounters=[
                _enc("e1", [_loot("Animal Hide", 100, 1.0)]),
                _enc("e2", [_loot("Soft Hide", 50, 0.5)]),
                _enc("e3", [_loot("Animal Hide", 200, 2.0)]),
            ],
        )
        result = aggregate_loot_for_session(session)
        self.assertEqual(len(result), 2)
        by_name = {r["item_name"]: r for r in result}
        self.assertEqual(by_name["Animal Hide"]["total_quantity"], 300)
        self.assertAlmostEqual(by_name["Animal Hide"]["tt_value"], 3.0)


class TestAllLootItemsProperty(unittest.TestCase):
    """Test the all_loot_items property on Hunt and HuntSession."""

    def test_hunt_all_loot_items(self):
        hunt = Hunt(
            id="h1",
            session_id="s1",
            start_time=datetime(2026, 1, 1),
            encounters=[
                _enc("e1", [
                    _loot("Animal Hide", 100, 1.0),
                    _loot("Shrapnel", 500, 5.0, blacklisted=True),
                ]),
                _enc("e2", [_loot("Soft Hide", 50, 0.5)]),
            ],
        )
        items = hunt.all_loot_items
        names = [li.item_name for li in items]
        self.assertIn("Animal Hide", names)
        self.assertIn("Soft Hide", names)
        self.assertNotIn("Shrapnel", names)
        self.assertEqual(len(items), 2)

    def test_session_all_loot_items(self):
        session = HuntSession(
            id="s1",
            start_time=datetime(2026, 1, 1),
            encounters=[
                _enc("e1", [
                    _loot("Animal Hide", 100, 1.0),
                    _loot("Refined", 10, 0.8, refining=True),
                ]),
                _enc("e2", [_loot("Soft Hide", 50, 0.5)]),
            ],
        )
        items = session.all_loot_items
        names = [li.item_name for li in items]
        self.assertIn("Animal Hide", names)
        self.assertIn("Soft Hide", names)
        self.assertNotIn("Refined", names)
        self.assertEqual(len(items), 2)

    def test_empty_encounters(self):
        hunt = Hunt(id="h1", session_id="s1", start_time=datetime(2026, 1, 1))
        self.assertEqual(hunt.all_loot_items, [])


if __name__ == "__main__":
    unittest.main()
