import unittest
from datetime import datetime
from unittest.mock import MagicMock

from client.chat_parser.models import ParsedLine
from client.chat_parser.message_classifier import MessageClassifier
from client.core.constants import (
    EVENT_COMBAT, EVENT_LOOT_GROUP, EVENT_SKILL_GAIN,
    EVENT_GLOBAL, EVENT_TRADE_CHAT,
)


def _make_parsed_line(channel="System", username="", message="test",
                      timestamp=None):
    return ParsedLine(
        timestamp=timestamp or datetime(2026, 1, 1, 12, 0, 0),
        channel=channel,
        username=username,
        message=message,
        raw_line=f"2026-01-01 12:00:00 [{channel}] [{username}] {message}",
        line_number=1,
    )


class TestMessageClassifierRouting(unittest.TestCase):
    """Tests that real messages route through real can_handle methods
    to the correct handler, publishing the expected event type.

    Only EventBus and Database are mocked (external dependencies).
    All handler routing logic is exercised for real.
    """

    def setUp(self):
        self.event_bus = MagicMock()
        self.db = MagicMock()
        self.classifier = MessageClassifier(self.event_bus, self.db)

    def _published_event_types(self):
        """Return list of event_type strings from event_bus.publish calls."""
        return [c.args[0] for c in self.event_bus.publish.call_args_list]

    # -- Combat routing --

    def test_combat_damage_dealt(self):
        line = _make_parsed_line(message="You inflicted 50.0 points of damage")
        self.classifier.classify_and_handle(line)
        types = self._published_event_types()
        self.assertIn(EVENT_COMBAT, types)
        combat_call = [c for c in self.event_bus.publish.call_args_list
                       if c.args[0] == EVENT_COMBAT][0]
        self.assertAlmostEqual(combat_call.args[1].amount, 50.0)

    def test_combat_critical_hit(self):
        line = _make_parsed_line(
            message="Critical hit - Additional damage! You inflicted 75.5 points of damage"
        )
        self.classifier.classify_and_handle(line)
        combat_call = [c for c in self.event_bus.publish.call_args_list
                       if c.args[0] == EVENT_COMBAT][0]
        self.assertAlmostEqual(combat_call.args[1].amount, 75.5)

    def test_combat_evade(self):
        line = _make_parsed_line(message="You Evaded the attack")
        self.classifier.classify_and_handle(line)
        self.assertIn(EVENT_COMBAT, self._published_event_types())

    def test_combat_target_dodge(self):
        line = _make_parsed_line(message="The target Dodged your attack")
        self.classifier.classify_and_handle(line)
        self.assertIn(EVENT_COMBAT, self._published_event_types())

    # -- Skill routing --

    def test_skill_gain_experience_format(self):
        line = _make_parsed_line(
            message="You have gained 0.6347 experience in your Laser Weaponry skill"
        )
        self.classifier.classify_and_handle(line)
        self.assertIn(EVENT_SKILL_GAIN, self._published_event_types())
        skill_call = [c for c in self.event_bus.publish.call_args_list
                      if c.args[0] == EVENT_SKILL_GAIN][0]
        self.assertEqual(skill_call.args[1].skill_name, "Laser Weaponry")

    def test_skill_gain_direct_format(self):
        line = _make_parsed_line(message="You have gained 0.0248 Bravado")
        self.classifier.classify_and_handle(line)
        self.assertIn(EVENT_SKILL_GAIN, self._published_event_types())

    # -- Loot routing --

    def test_loot_flushed_on_later_timestamp(self):
        ts1 = datetime(2026, 1, 1, 12, 0, 0)
        ts2 = datetime(2026, 1, 1, 12, 0, 1)
        loot_line = _make_parsed_line(
            message="You received Animal Oil x (5) Value: 1.25 PED",
            timestamp=ts1,
        )
        later_line = _make_parsed_line(
            message="You inflicted 30.0 points of damage",
            timestamp=ts2,
        )
        self.classifier.classify_and_handle(loot_line)
        self.classifier.classify_and_handle(later_line)
        self.assertIn(EVENT_LOOT_GROUP, self._published_event_types())

    def test_loot_groups_items_by_timestamp(self):
        """Multiple loot items with the same timestamp form one group."""
        ts = datetime(2026, 1, 1, 12, 0, 0)
        line1 = _make_parsed_line(
            message="You received Animal Oil x (5) Value: 1.25 PED",
            timestamp=ts,
        )
        line2 = _make_parsed_line(
            message="You received Shrapnel x (12) Value: 0.12 PED",
            timestamp=ts,
        )
        self.classifier.classify_and_handle(line1)
        self.classifier.classify_and_handle(line2)
        self.classifier.flush()
        loot_calls = [c for c in self.event_bus.publish.call_args_list
                      if c.args[0] == EVENT_LOOT_GROUP]
        self.assertEqual(len(loot_calls), 1)  # One group, not two
        group = loot_calls[0].args[1]
        self.assertEqual(len(group.items), 2)
        self.assertAlmostEqual(group.total_value_ped, 1.37)

    def test_loot_flush_on_shutdown(self):
        loot_line = _make_parsed_line(
            message="You received Animal Oil x (5) Value: 1.25 PED",
        )
        self.classifier.classify_and_handle(loot_line)
        self.assertNotIn(EVENT_LOOT_GROUP, self._published_event_types())
        self.classifier.flush()
        self.assertIn(EVENT_LOOT_GROUP, self._published_event_types())

    # -- Globals routing --

    def test_globals_kill_routed(self):
        line = _make_parsed_line(
            channel="Globals",
            username="",
            message="Player killed a creature (Atrox) with a value of 100 PED!",
        )
        self.classifier.classify_and_handle(line)
        self.assertIn(EVENT_GLOBAL, self._published_event_types())
        global_call = [c for c in self.event_bus.publish.call_args_list
                       if c.args[0] == EVENT_GLOBAL][0]
        self.assertAlmostEqual(global_call.args[1].value, 100.0)
        self.assertEqual(global_call.args[1].target_name, "Atrox")

    def test_globals_hof(self):
        line = _make_parsed_line(
            channel="Globals",
            username="",
            message="Player killed a creature (Atrox) with a value of 500 PED! "
                    "A record has been added to the Hall of Fame!",
        )
        self.classifier.classify_and_handle(line)
        global_call = [c for c in self.event_bus.publish.call_args_list
                       if c.args[0] == EVENT_GLOBAL][0]
        self.assertTrue(global_call.args[1].is_hof)

    # -- Trade routing --

    def test_trade_channel_routed(self):
        line = _make_parsed_line(
            channel="Trade",
            username="SomeTrader",
            message="WTS: Armatrix LR-35 (L) 130%",
        )
        self.classifier.classify_and_handle(line)
        self.assertIn(EVENT_TRADE_CHAT, self._published_event_types())

    # -- Non-routed messages --

    def test_local_chat_not_routed(self):
        line = _make_parsed_line(
            channel="Local",
            username="SomePlayer",
            message="Hello everyone!",
        )
        self.classifier.classify_and_handle(line)
        self.event_bus.publish.assert_not_called()

    def test_system_message_with_username_ignored(self):
        """System messages with a username are player messages, not system events."""
        line = _make_parsed_line(
            channel="System",
            username="SomePlayer",
            message="You inflicted 50.0 points of damage",
        )
        self.classifier.classify_and_handle(line)
        self.event_bus.publish.assert_not_called()

    def test_unrecognized_system_message_ignored(self):
        line = _make_parsed_line(message="Some random system text that matches nothing")
        self.classifier.classify_and_handle(line)
        self.event_bus.publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
