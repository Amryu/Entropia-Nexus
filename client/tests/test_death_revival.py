"""Tests for death/revival detection: handler, patterns, and classifier routing."""

import unittest
from datetime import datetime
from unittest.mock import MagicMock

from client.chat_parser.handlers.death_revival import DeathRevivalHandler
from client.chat_parser.message_classifier import MessageClassifier
from client.chat_parser.models import ParsedLine
from client.core.constants import (
    DEATH_PATTERN, REVIVAL_PATTERN,
    EVENT_PLAYER_DEATH, EVENT_PLAYER_REVIVED,
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


# ---------------------------------------------------------------------------
# Pattern tests
# ---------------------------------------------------------------------------

class TestDeathPattern(unittest.TestCase):

    def test_standard_death_message(self):
        match = DEATH_PATTERN.match("You were killed by the agitated Atrox Young")
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "Atrox Young")

    def test_long_mob_name_with_maturity(self):
        match = DEATH_PATTERN.match(
            "You were killed by the ferocious Cryomusoid Elite Glacior"
        )
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "Cryomusoid Elite Glacior")

    def test_single_word_mob_name(self):
        match = DEATH_PATTERN.match("You were killed by the savage Atrox")
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "Atrox")

    def test_adjective_stripped_correctly(self):
        """The regex captures everything after 'the <adjective> '."""
        match = DEATH_PATTERN.match("You were killed by the mighty Foul Young")
        self.assertIsNotNone(match)
        # "mighty" is the adjective (stripped by regex), "Foul Young" is the mob
        self.assertEqual(match.group(1), "Foul Young")

    def test_non_death_message_no_match(self):
        match = DEATH_PATTERN.match("You inflicted 50.0 points of damage")
        self.assertIsNone(match)


class TestRevivalPattern(unittest.TestCase):

    def test_revival_message(self):
        match = REVIVAL_PATTERN.match("You have been revived")
        self.assertIsNotNone(match)

    def test_non_revival_no_match(self):
        match = REVIVAL_PATTERN.match("You have been defeated")
        self.assertIsNone(match)


# ---------------------------------------------------------------------------
# Handler tests
# ---------------------------------------------------------------------------

class TestDeathRevivalHandler(unittest.TestCase):

    def setUp(self):
        self.event_bus = MagicMock()
        self.db = MagicMock()
        self.handler = DeathRevivalHandler(self.event_bus, self.db)

    def test_can_handle_death(self):
        line = _make_parsed_line(
            message="You were killed by the agitated Atrox Young"
        )
        self.assertTrue(self.handler.can_handle(line))

    def test_can_handle_revival(self):
        line = _make_parsed_line(message="You have been revived")
        self.assertTrue(self.handler.can_handle(line))

    def test_cannot_handle_combat(self):
        line = _make_parsed_line(message="You inflicted 50.0 points of damage")
        self.assertFalse(self.handler.can_handle(line))

    def test_cannot_handle_non_system_channel(self):
        line = _make_parsed_line(
            channel="Local", username="SomePlayer",
            message="You were killed by the agitated Atrox Young"
        )
        self.assertFalse(self.handler.can_handle(line))

    def test_cannot_handle_system_with_username(self):
        line = _make_parsed_line(
            channel="System", username="SomePlayer",
            message="You were killed by the agitated Atrox Young"
        )
        self.assertFalse(self.handler.can_handle(line))

    def test_handle_death_publishes_event(self):
        line = _make_parsed_line(
            message="You were killed by the agitated Atrox Young"
        )
        self.handler.handle(line)
        self.event_bus.publish.assert_called_once()
        event_type, event_data = self.event_bus.publish.call_args.args
        self.assertEqual(event_type, EVENT_PLAYER_DEATH)
        self.assertEqual(event_data.mob_name, "Atrox Young")
        self.assertEqual(event_data.timestamp, line.timestamp)

    def test_handle_revival_publishes_event(self):
        line = _make_parsed_line(message="You have been revived")
        self.handler.handle(line)
        self.event_bus.publish.assert_called_once()
        event_type, event_data = self.event_bus.publish.call_args.args
        self.assertEqual(event_type, EVENT_PLAYER_REVIVED)
        self.assertEqual(event_data.timestamp, line.timestamp)


# ---------------------------------------------------------------------------
# Classifier routing tests (real handlers, mocked bus/db)
# ---------------------------------------------------------------------------

class TestClassifierDeathRevivalRouting(unittest.TestCase):

    def setUp(self):
        self.event_bus = MagicMock()
        self.db = MagicMock()
        self.classifier = MessageClassifier(self.event_bus, self.db)

    def _published_event_types(self):
        return [c.args[0] for c in self.event_bus.publish.call_args_list]

    def test_death_message_routed(self):
        line = _make_parsed_line(
            message="You were killed by the ferocious Cryomusoid Elite Glacior"
        )
        self.classifier.classify_and_handle(line)
        self.assertIn(EVENT_PLAYER_DEATH, self._published_event_types())

    def test_revival_message_routed(self):
        line = _make_parsed_line(message="You have been revived")
        self.classifier.classify_and_handle(line)
        self.assertIn(EVENT_PLAYER_REVIVED, self._published_event_types())

    def test_death_not_routed_as_combat(self):
        """Death message must NOT fall through to combat handler."""
        from client.core.constants import EVENT_COMBAT
        line = _make_parsed_line(
            message="You were killed by the agitated Atrox Young"
        )
        self.classifier.classify_and_handle(line)
        self.assertNotIn(EVENT_COMBAT, self._published_event_types())

    def test_player_chat_death_text_ignored(self):
        """A player typing the death message in chat should be ignored."""
        line = _make_parsed_line(
            channel="System", username="SomePlayer",
            message="You were killed by the agitated Atrox Young"
        )
        self.classifier.classify_and_handle(line)
        self.event_bus.publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
