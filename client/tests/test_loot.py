import unittest
from datetime import datetime
from unittest.mock import MagicMock

from client.chat_parser.handlers.loot import LootHandler
from client.chat_parser.models import ParsedLine
from client.core.constants import EVENT_LOOT_GROUP


def _make_loot_line(msg: str, ts: datetime) -> ParsedLine:
    return ParsedLine(
        timestamp=ts,
        channel="System",
        username="",
        message=msg,
        raw_line=f"{ts.strftime('%Y-%m-%d %H:%M:%S')} [System] [] {msg}",
        line_number=1,
    )


class TestLootHandler(unittest.TestCase):
    def setUp(self):
        self.bus = MagicMock()
        self.db = MagicMock()
        self.handler = LootHandler(self.bus, self.db)

    def test_can_handle_loot(self):
        line = _make_loot_line("You received Metal Residue x (3) Value: 0.0300 PED", datetime(2026, 2, 7, 11, 19, 50))
        self.assertTrue(self.handler.can_handle(line))

    def test_rejects_non_loot(self):
        line = _make_loot_line("You inflicted 200.5 points of damage", datetime(2026, 2, 7, 11, 19, 50))
        self.assertFalse(self.handler.can_handle(line))

    def test_single_item_group(self):
        ts = datetime(2026, 2, 7, 11, 19, 50)
        self.handler.handle(_make_loot_line("You received Metal Residue x (3) Value: 0.0300 PED", ts))
        # Flush by advancing timestamp
        self.handler.notify_timestamp_advanced(datetime(2026, 2, 7, 11, 19, 51))

        self.bus.publish.assert_called_once()
        group = self.bus.publish.call_args[0][1]
        self.assertEqual(len(group.items), 1)
        self.assertEqual(group.items[0].item_name, "Metal Residue")
        self.assertEqual(group.items[0].quantity, 3)
        self.assertAlmostEqual(group.items[0].value_ped, 0.03)

    def test_multi_item_group(self):
        ts = datetime(2026, 2, 7, 11, 20, 39)
        self.handler.handle(_make_loot_line("You received Explosive Projectiles x (1166) Value: 0.1166 PED", ts))
        self.handler.handle(_make_loot_line("You received Metal Residue x (8) Value: 0.0800 PED", ts))
        self.handler.handle(_make_loot_line("You received Shrapnel x (29) Value: 0.0029 PED", ts))
        self.handler.flush()

        self.bus.publish.assert_called_once()
        group = self.bus.publish.call_args[0][1]
        self.assertEqual(len(group.items), 3)
        self.assertAlmostEqual(group.total_value_ped, 0.1166 + 0.08 + 0.0029, places=4)

    def test_double_shrapnel_group(self):
        """Two shrapnel entries from same kill (stack reaching 100M)."""
        ts = datetime(2026, 2, 8, 15, 38, 56)
        self.handler.handle(_make_loot_line("You received Shrapnel x (4762) Value: 0.4762 PED", ts))
        self.handler.handle(_make_loot_line("You received Shrapnel x (5690) Value: 0.5690 PED", ts))
        self.handler.handle(_make_loot_line("You received Molisk Tooth x (4) Value: 0.0400 PED", ts))
        self.handler.flush()

        group = self.bus.publish.call_args[0][1]
        self.assertEqual(len(group.items), 3)
        shrapnel_items = [i for i in group.items if i.item_name == "Shrapnel"]
        self.assertEqual(len(shrapnel_items), 2)

    def test_separate_groups_different_timestamps(self):
        ts1 = datetime(2026, 2, 7, 11, 19, 50)
        ts2 = datetime(2026, 2, 7, 11, 20, 2)

        self.handler.handle(_make_loot_line("You received Metal Residue x (3) Value: 0.0300 PED", ts1))
        self.handler.handle(_make_loot_line("You received Shrapnel x (52) Value: 0.0052 PED", ts1))
        self.handler.handle(_make_loot_line("You received Metal Residue x (1) Value: 0.0100 PED", ts2))
        self.handler.flush()

        self.assertEqual(self.bus.publish.call_count, 2)
        group1 = self.bus.publish.call_args_list[0][0][1]
        group2 = self.bus.publish.call_args_list[1][0][1]
        self.assertEqual(len(group1.items), 2)
        self.assertEqual(len(group2.items), 1)

    def test_flush_on_timestamp_advance(self):
        ts = datetime(2026, 2, 7, 11, 19, 50)
        self.handler.handle(_make_loot_line("You received Shrapnel x (52) Value: 0.0052 PED", ts))
        self.handler.notify_timestamp_advanced(datetime(2026, 2, 7, 11, 19, 51))

        self.bus.publish.assert_called_once()

    def test_no_flush_on_same_timestamp(self):
        ts = datetime(2026, 2, 7, 11, 19, 50)
        self.handler.handle(_make_loot_line("You received Shrapnel x (52) Value: 0.0052 PED", ts))
        self.handler.notify_timestamp_advanced(ts)

        self.bus.publish.assert_not_called()

    # -- DB persistence tests --

    def test_db_persists_with_name_when_no_resolver(self):
        """Without a resolver, item_name is stored and item_id is None."""
        ts = datetime(2026, 2, 7, 11, 19, 50)
        self.handler.handle(_make_loot_line("You received Metal Residue x (3) Value: 0.0300 PED", ts))
        self.handler.flush()

        self.db.insert_loot_events.assert_called_once()
        rows = self.db.insert_loot_events.call_args[0][0]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], ts.isoformat())  # timestamp
        self.assertEqual(rows[0][1], "Metal Residue")  # item_name kept
        self.assertIsNone(rows[0][2])                   # item_id
        self.assertEqual(rows[0][3], 3)                  # quantity
        self.assertAlmostEqual(rows[0][4], 0.03)         # value_ped

    def test_db_stores_both_name_and_id_when_resolved(self):
        """When the resolver returns an ID, item_name is always kept (NOT NULL)."""
        self.handler._item_resolver = lambda name: 42 if name == "Metal Residue" else None
        ts = datetime(2026, 2, 7, 11, 19, 50)
        self.handler.handle(_make_loot_line("You received Metal Residue x (3) Value: 0.0300 PED", ts))
        self.handler.flush()

        rows = self.db.insert_loot_events.call_args[0][0]
        self.assertEqual(rows[0][1], "Metal Residue")  # item_name always kept
        self.assertEqual(rows[0][2], 42)                # item_id stored

    def test_db_mixed_resolved_and_unresolved(self):
        """Both resolved and unresolved items always keep item_name."""
        self.handler._item_resolver = lambda name: 99 if name == "Shrapnel" else None
        ts = datetime(2026, 2, 7, 11, 20, 39)
        self.handler.handle(_make_loot_line("You received Shrapnel x (29) Value: 0.0029 PED", ts))
        self.handler.handle(_make_loot_line("You received Rare Gizmo x (1) Value: 5.0000 PED", ts))
        self.handler.flush()

        rows = self.db.insert_loot_events.call_args[0][0]
        # Shrapnel resolved — name kept, id stored
        self.assertEqual(rows[0][1], "Shrapnel")
        self.assertEqual(rows[0][2], 99)
        # Rare Gizmo unresolved — name kept, id None
        self.assertEqual(rows[1][1], "Rare Gizmo")
        self.assertIsNone(rows[1][2])

    def test_db_persists_during_catchup(self):
        """Loot events are persisted even during catchup (suppress_events=True)."""
        self.handler.suppress_events = True
        ts = datetime(2026, 2, 7, 11, 19, 50)
        self.handler.handle(_make_loot_line("You received Metal Residue x (3) Value: 0.0300 PED", ts))
        self.handler.flush()

        self.db.insert_loot_events.assert_called_once()
        self.bus.publish.assert_not_called()

    def test_db_batch_contains_all_group_items(self):
        ts = datetime(2026, 2, 7, 11, 20, 39)
        self.handler.handle(_make_loot_line("You received Explosive Projectiles x (1166) Value: 0.1166 PED", ts))
        self.handler.handle(_make_loot_line("You received Metal Residue x (8) Value: 0.0800 PED", ts))
        self.handler.handle(_make_loot_line("You received Shrapnel x (29) Value: 0.0029 PED", ts))
        self.handler.flush()

        rows = self.db.insert_loot_events.call_args[0][0]
        self.assertEqual(len(rows), 3)
        names = [r[1] for r in rows]
        self.assertEqual(names, ["Explosive Projectiles", "Metal Residue", "Shrapnel"])


if __name__ == "__main__":
    unittest.main()
