import unittest
from datetime import datetime
from unittest.mock import MagicMock

from client.chat_parser.handlers.combat import CombatHandler
from client.chat_parser.models import MessageType, ParsedLine


def _make_system_line(msg: str) -> ParsedLine:
    return ParsedLine(
        timestamp=datetime(2026, 2, 8, 15, 38, 46),
        channel="System",
        username="",
        message=msg,
        raw_line=f"2026-02-08 15:38:46 [System] [] {msg}",
        line_number=1,
    )


class TestCombatHandler(unittest.TestCase):
    def setUp(self):
        self.bus = MagicMock()
        self.db = MagicMock()
        self.handler = CombatHandler(self.bus, self.db)

    def test_damage_dealt(self):
        line = _make_system_line("You inflicted 200.5 points of damage")
        self.assertTrue(self.handler.can_handle(line))
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.event_type, MessageType.DAMAGE_DEALT)
        self.assertAlmostEqual(event.amount, 200.5)

    def test_critical_hit(self):
        line = _make_system_line("Critical hit - Additional damage! You inflicted 406.3 points of damage")
        self.assertTrue(self.handler.can_handle(line))
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.event_type, MessageType.CRITICAL_HIT)
        self.assertAlmostEqual(event.amount, 406.3)

    def test_damage_received(self):
        line = _make_system_line("You took 17.3 points of damage")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.event_type, MessageType.DAMAGE_RECEIVED)
        self.assertAlmostEqual(event.amount, 17.3)

    def test_self_heal(self):
        line = _make_system_line("You healed yourself 39.5 points")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.event_type, MessageType.SELF_HEAL)
        self.assertAlmostEqual(event.amount, 39.5)

    def test_deflect(self):
        line = _make_system_line("Damage deflected!")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.event_type, MessageType.DEFLECT)
        self.assertIsNone(event.amount)

    def test_player_evade(self):
        line = _make_system_line("You Evaded the attack")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.event_type, MessageType.PLAYER_EVADE)

    def test_player_dodge(self):
        line = _make_system_line("You Dodged the attack")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.event_type, MessageType.PLAYER_DODGE)

    def test_player_jam(self):
        line = _make_system_line("You Jammed the attack")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.event_type, MessageType.PLAYER_JAM)

    def test_mob_miss(self):
        line = _make_system_line("The attack missed you")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.event_type, MessageType.MOB_MISS)

    def test_target_jam(self):
        line = _make_system_line("The target Jammed your attack")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.event_type, MessageType.TARGET_JAM)

    def test_target_dodge(self):
        line = _make_system_line("The target Dodged your attack")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.event_type, MessageType.TARGET_DODGE)

    def test_target_evade(self):
        line = _make_system_line("The target Evaded your attack")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.event_type, MessageType.TARGET_EVADE)

    def test_rejects_loot(self):
        line = _make_system_line("You received Shrapnel x (52) Value: 0.0052 PED")
        self.assertFalse(self.handler.can_handle(line))

    def test_rejects_skill_gain(self):
        line = _make_system_line("You have gained 0.6347 experience in your Engineering skill")
        self.assertFalse(self.handler.can_handle(line))


if __name__ == "__main__":
    unittest.main()
