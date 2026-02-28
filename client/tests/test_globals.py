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

    def test_examine_storage_container(self):
        line = _make_global_line("Zal Mitchos Gaal examined Storage Container in Akbal - Sector 3 and found something with a value of 78 PED!")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.global_type, GlobalType.EXAMINE)
        self.assertEqual(event.player_name, "Zal Mitchos Gaal")
        self.assertEqual(event.target_name, "Storage Container")
        self.assertAlmostEqual(event.value, 78.0)
        self.assertEqual(event.value_unit, "PED")
        self.assertEqual(event.location, "Akbal - Sector 3")

    def test_examine_container_with_hof(self):
        line = _make_global_line("Atrox Atrox Killer examined Container in Lotus Gold Solo and found something with a value of 1138 PED! A record has been added to the Hall of Fame!")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.global_type, GlobalType.EXAMINE)
        self.assertEqual(event.target_name, "Container")
        self.assertEqual(event.location, "Lotus Gold Solo")
        self.assertAlmostEqual(event.value, 1138.0)
        self.assertTrue(event.is_hof)

    def test_examine_sacred_idol(self):
        line = _make_global_line("danka soul needue examined Sacred Idol in The Fire Temple and found something with a value of 379 PED!")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.global_type, GlobalType.EXAMINE)
        self.assertEqual(event.target_name, "Sacred Idol")
        self.assertEqual(event.location, "The Fire Temple")

    def test_pvp_defeated_in_a_row(self):
        line = _make_global_line("Big Bob Rollo defeated 12 others in a row before succumbing! A record has been added to the Hall of Fame!")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.global_type, GlobalType.PVP)
        self.assertEqual(event.player_name, "Big Bob Rollo")
        self.assertEqual(event.target_name, "PvP")
        self.assertAlmostEqual(event.value, 12.0)
        self.assertEqual(event.value_unit, "kills")
        self.assertTrue(event.is_hof)

    def test_pvp_defeated_as_mob(self):
        line = _make_global_line("Mega Voltage  Jak defeated 19 others as a Yule Daudaormur ! A record has been added to the Hall of Fame!")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.global_type, GlobalType.PVP)
        self.assertEqual(event.player_name, "Mega Voltage  Jak")
        self.assertAlmostEqual(event.value, 19.0)
        self.assertTrue(event.is_hof)

    def test_discovery(self):
        line = _make_global_line("Jessica aJK Eschweiler is the first colonist to discover Hyperion Arm Guards, Perfected (F)!")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.global_type, GlobalType.DISCOVERY)
        self.assertEqual(event.player_name, "Jessica aJK Eschweiler")
        self.assertEqual(event.target_name, "Hyperion Arm Guards, Perfected (F)")
        self.assertAlmostEqual(event.value, 0)

    def test_tier_record(self):
        line = _make_global_line("Geir MrGersh Mathiesen is the first colonist to reach tier 7 for A.R.C. Adept Leg Guards (M,L)!")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.global_type, GlobalType.TIER)
        self.assertEqual(event.player_name, "Geir MrGersh Mathiesen")
        self.assertEqual(event.target_name, "A.R.C. Adept Leg Guards (M,L)")
        self.assertAlmostEqual(event.value, 7.0)
        self.assertEqual(event.value_unit, "TIER")


if __name__ == "__main__":
    unittest.main()
