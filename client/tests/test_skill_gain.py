import unittest
from datetime import datetime
from unittest.mock import MagicMock

from client.chat_parser.handlers.skill_gain import SkillGainHandler
from client.chat_parser.models import ParsedLine, SkillGainEvent
from client.core.constants import EVENT_SKILL_GAIN


def _make_system_line(msg: str, ts: datetime = None) -> ParsedLine:
    return ParsedLine(
        timestamp=ts or datetime(2026, 2, 7, 11, 19, 38),
        channel="System",
        username="",
        message=msg,
        raw_line=f"2026-02-07 11:19:38 [System] [] {msg}",
        line_number=1,
    )


class TestSkillGainHandler(unittest.TestCase):
    def setUp(self):
        self.bus = MagicMock()
        self.db = MagicMock()
        self.handler = SkillGainHandler(self.bus, self.db)

    def test_can_handle_skill_exp(self):
        line = _make_system_line("You have gained 0.6347 experience in your Manufacture Mechanical Equipment skill")
        self.assertTrue(self.handler.can_handle(line))

    def test_can_handle_attribute(self):
        line = _make_system_line("You have gained 0.0248 Bravado")
        self.assertTrue(self.handler.can_handle(line))

    def test_rejects_non_skill(self):
        line = _make_system_line("You received Metal Residue x (3) Value: 0.0300 PED")
        self.assertFalse(self.handler.can_handle(line))

    def test_rejects_non_system(self):
        line = ParsedLine(
            timestamp=datetime(2026, 2, 7, 11, 19, 38),
            channel="Rookie",
            username="Test",
            message="You have gained something",
            raw_line="",
            line_number=1,
        )
        self.assertFalse(self.handler.can_handle(line))

    def test_handle_skill_exp(self):
        line = _make_system_line("You have gained 0.6347 experience in your Manufacture Mechanical Equipment skill")
        self.handler.handle(line)
        self.bus.publish.assert_called_once()
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.skill_name, "Manufacture Mechanical Equipment")
        self.assertAlmostEqual(event.amount, 0.6347)
        self.assertFalse(event.is_attribute)

    def test_handle_attribute(self):
        line = _make_system_line("You have gained 0.0248 Bravado")
        self.handler.handle(line)
        self.bus.publish.assert_called_once()
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.skill_name, "Bravado")
        self.assertAlmostEqual(event.amount, 0.0248)
        self.assertTrue(event.is_attribute)

    def test_handle_multi_word_attribute(self):
        line = _make_system_line("You have gained 0.0996 Quickness")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.skill_name, "Quickness")

    def test_db_called(self):
        line = _make_system_line("You have gained 0.0639 experience in your Engineering skill")
        self.handler.handle(line)
        self.db.insert_skill_gain.assert_called_once()
        call_kwargs = self.db.insert_skill_gain.call_args[1]
        self.assertEqual(call_kwargs["skill_name"], "Engineering")
        self.assertAlmostEqual(call_kwargs["amount"], 0.0639)


if __name__ == "__main__":
    unittest.main()
