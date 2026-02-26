import unittest
from datetime import datetime
from unittest.mock import MagicMock

from client.chat_parser.handlers.globals import GlobalsHandler
from client.chat_parser.models import GlobalType, ParsedLine


def _make_global_line(msg: str) -> ParsedLine:
    return ParsedLine(
        timestamp=datetime(2026, 2, 7, 11, 19, 15),
        channel="Globals",
        username="",
        message=msg,
        raw_line=f"2026-02-07 11:19:15 [Globals] [] {msg}",
        line_number=1,
    )


class TestGlobalsHandler(unittest.TestCase):
    def setUp(self):
        self.bus = MagicMock()
        self.db = MagicMock()
        self.handler = GlobalsHandler(self.bus, self.db)

    def test_regular_kill(self):
        line = _make_global_line("Anthony Malcom Denton killed a creature (Leviathan Stalker) with a value of 85 PED!")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.global_type, GlobalType.KILL)
        self.assertEqual(event.player_name, "Anthony Malcom Denton")
        self.assertEqual(event.target_name, "Leviathan Stalker")
        self.assertAlmostEqual(event.value, 85.0)
        self.assertEqual(event.value_unit, "PED")
        self.assertFalse(event.is_hof)
        self.assertFalse(event.is_ath)
        self.assertIsNone(event.location)

    def test_kill_with_location(self):
        line = _make_global_line("Balto Baltazar Zar killed a creature (Araneatrox Young) with a value of 59 PED at Takuta Plateau!")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.global_type, GlobalType.KILL)
        self.assertEqual(event.location, "Takuta Plateau")

    def test_team_kill(self):
        line = _make_global_line('Team "(Shared Loot)" killed a creature (Warrior C1-TF) with a value of 102 PED!')
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.global_type, GlobalType.TEAM_KILL)
        self.assertEqual(event.player_name, "(Shared Loot)")
        self.assertEqual(event.target_name, "Warrior C1-TF")
        self.assertAlmostEqual(event.value, 102.0)

    def test_deposit(self):
        line = _make_global_line("joseph abouzouz gharby found a deposit (Caldorite Stone) with a value of 176 PED at F.O.M.A. - FORTUNA!")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.global_type, GlobalType.DEPOSIT)
        self.assertEqual(event.target_name, "Caldorite Stone")
        self.assertEqual(event.location, "F.O.M.A. - FORTUNA")

    def test_craft(self):
        line = _make_global_line("Sleezy BLEEZY GREEEEEEZLY constructed an item (Explosive Projectiles) worth 74 PED!")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.global_type, GlobalType.CRAFT)
        self.assertEqual(event.target_name, "Explosive Projectiles")
        self.assertFalse(event.is_hof)

    def test_craft_with_hof(self):
        line = _make_global_line("Dainius dainiusha666 Danik constructed an item (Shrapnel) worth 116 PED! A record has been added to the Hall of Fame!")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.global_type, GlobalType.CRAFT)
        self.assertTrue(event.is_hof)

    def test_kill_with_hof(self):
        line = _make_global_line("Romi impi Tinkels killed a creature (Enslaved Daudaormur Stalker) with a value of 720 PED! A record has been added to the Hall of Fame!")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.global_type, GlobalType.KILL)
        self.assertTrue(event.is_hof)
        self.assertAlmostEqual(event.value, 720.0)

    def test_rare_item(self):
        line = _make_global_line("Eleonora Elayne WithoutSpoon has found a rare item (Modified Hyperion Armor Catalyst) with a value of 40 PEC! A record has been added to the Hall of Fame!")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.global_type, GlobalType.RARE_ITEM)
        self.assertEqual(event.target_name, "Modified Hyperion Armor Catalyst")
        self.assertEqual(event.value_unit, "PEC")
        self.assertAlmostEqual(event.value, 40.0)
        self.assertTrue(event.is_hof)

    def test_rejects_non_globals_channel(self):
        line = ParsedLine(
            timestamp=datetime(2026, 2, 7, 11, 19, 15),
            channel="System",
            username="",
            message="test",
            raw_line="",
            line_number=1,
        )
        self.assertFalse(self.handler.can_handle(line))

    def test_deposit_with_hof(self):
        line = _make_global_line("mlin chaos boss found a deposit (Lysterium Stone) with a value of 349 PED at F.O.M.A. -- FORTUNA!! A record has been added to the Hall of Fame!")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.global_type, GlobalType.DEPOSIT)
        self.assertTrue(event.is_hof)
        self.assertEqual(event.target_name, "Lysterium Stone")


if __name__ == "__main__":
    unittest.main()
