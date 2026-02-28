"""Tests for the notification rules engine."""

import unittest
from datetime import datetime

from client.chat_parser.models import GlobalEvent, GlobalType
from client.notifications.models import GlobalNotificationRule
from client.notifications.rules_engine import RulesEngine


def _make_event(
    player="TestPlayer",
    target="Atrox Old Alpha",
    value=100.0,
    global_type=GlobalType.KILL,
    is_hof=False,
    is_ath=False,
):
    return GlobalEvent(
        timestamp=datetime(2026, 2, 28, 12, 0, 0),
        global_type=global_type,
        player_name=player,
        target_name=target,
        value=value,
        value_unit="PED",
        location=None,
        is_hof=is_hof,
        is_ath=is_ath,
    )


class TestRulesEngine(unittest.TestCase):
    """Test rule evaluation logic."""

    def test_no_rules_no_notification(self):
        engine = RulesEngine([])
        result, rule = engine.evaluate(_make_event())
        self.assertFalse(result)
        self.assertIsNone(rule)

    def test_simple_notify_rule(self):
        rules = [GlobalNotificationRule(id="1", action="notify")]
        engine = RulesEngine(rules)
        result, rule = engine.evaluate(_make_event())
        self.assertTrue(result)
        self.assertEqual(rule.id, "1")

    def test_simple_suppress_rule(self):
        rules = [GlobalNotificationRule(id="1", action="suppress")]
        engine = RulesEngine(rules)
        result, rule = engine.evaluate(_make_event())
        self.assertFalse(result)
        self.assertEqual(rule.id, "1")

    def test_disabled_rule_skipped(self):
        rules = [GlobalNotificationRule(id="1", action="notify", enabled=False)]
        engine = RulesEngine(rules)
        result, _ = engine.evaluate(_make_event())
        self.assertFalse(result)

    def test_player_name_filter_match(self):
        rules = [
            GlobalNotificationRule(id="1", action="notify", player_name="TestPlayer")
        ]
        engine = RulesEngine(rules)
        result, _ = engine.evaluate(_make_event(player="TestPlayer"))
        self.assertTrue(result)

    def test_player_name_filter_case_insensitive(self):
        rules = [
            GlobalNotificationRule(id="1", action="notify", player_name="testplayer")
        ]
        engine = RulesEngine(rules)
        result, _ = engine.evaluate(_make_event(player="TestPlayer"))
        self.assertTrue(result)

    def test_player_name_filter_substring(self):
        rules = [
            GlobalNotificationRule(id="1", action="notify", player_name="Player")
        ]
        engine = RulesEngine(rules)
        result, _ = engine.evaluate(_make_event(player="TestPlayer"))
        self.assertTrue(result)

    def test_player_name_filter_no_match(self):
        rules = [
            GlobalNotificationRule(id="1", action="notify", player_name="Someone")
        ]
        engine = RulesEngine(rules)
        result, _ = engine.evaluate(_make_event(player="TestPlayer"))
        self.assertFalse(result)

    def test_mob_name_filter(self):
        rules = [
            GlobalNotificationRule(id="1", action="notify", mob_name="Atrox")
        ]
        engine = RulesEngine(rules)
        self.assertTrue(engine.evaluate(_make_event(target="Atrox Old Alpha"))[0])
        self.assertFalse(engine.evaluate(_make_event(target="Leviathan Stalker"))[0])

    def test_min_value_filter(self):
        rules = [
            GlobalNotificationRule(id="1", action="notify", min_value=50.0)
        ]
        engine = RulesEngine(rules)
        self.assertTrue(engine.evaluate(_make_event(value=100.0))[0])
        self.assertTrue(engine.evaluate(_make_event(value=50.0))[0])
        self.assertFalse(engine.evaluate(_make_event(value=49.99))[0])

    def test_global_type_filter(self):
        rules = [
            GlobalNotificationRule(
                id="1", action="notify", global_types=["kill", "team_kill"]
            )
        ]
        engine = RulesEngine(rules)
        self.assertTrue(
            engine.evaluate(_make_event(global_type=GlobalType.KILL))[0]
        )
        self.assertTrue(
            engine.evaluate(_make_event(global_type=GlobalType.TEAM_KILL))[0]
        )
        self.assertFalse(
            engine.evaluate(_make_event(global_type=GlobalType.CRAFT))[0]
        )

    def test_global_type_hof_alias(self):
        rules = [
            GlobalNotificationRule(id="1", action="notify", global_types=["hof"])
        ]
        engine = RulesEngine(rules)
        # HoF kill should match
        self.assertTrue(
            engine.evaluate(_make_event(global_type=GlobalType.KILL, is_hof=True))[0]
        )
        # Non-HoF kill should not match
        self.assertFalse(
            engine.evaluate(_make_event(global_type=GlobalType.KILL, is_hof=False))[0]
        )

    def test_require_hof(self):
        rules = [
            GlobalNotificationRule(id="1", action="notify", require_hof=True)
        ]
        engine = RulesEngine(rules)
        self.assertTrue(engine.evaluate(_make_event(is_hof=True))[0])
        self.assertFalse(engine.evaluate(_make_event(is_hof=False))[0])

    def test_require_ath(self):
        rules = [
            GlobalNotificationRule(id="1", action="notify", require_ath=True)
        ]
        engine = RulesEngine(rules)
        self.assertTrue(engine.evaluate(_make_event(is_ath=True))[0])
        self.assertFalse(engine.evaluate(_make_event(is_ath=False))[0])

    def test_multiple_filters_and_logic(self):
        """All non-None filters must match (AND logic)."""
        rules = [
            GlobalNotificationRule(
                id="1", action="notify",
                player_name="TestPlayer",
                mob_name="Atrox",
                min_value=50.0,
            )
        ]
        engine = RulesEngine(rules)
        # All match
        self.assertTrue(
            engine.evaluate(_make_event(player="TestPlayer", target="Atrox Old", value=100))[0]
        )
        # Player doesn't match
        self.assertFalse(
            engine.evaluate(_make_event(player="Other", target="Atrox Old", value=100))[0]
        )
        # Mob doesn't match
        self.assertFalse(
            engine.evaluate(_make_event(player="TestPlayer", target="Leviathan", value=100))[0]
        )
        # Value doesn't match
        self.assertFalse(
            engine.evaluate(_make_event(player="TestPlayer", target="Atrox Old", value=10))[0]
        )

    def test_priority_ordering_higher_first(self):
        """Higher priority rules are evaluated first."""
        rules = [
            GlobalNotificationRule(id="low", action="notify", priority=10),
            GlobalNotificationRule(id="high", action="suppress", priority=100),
        ]
        engine = RulesEngine(rules)
        result, rule = engine.evaluate(_make_event())
        self.assertFalse(result)
        self.assertEqual(rule.id, "high")

    def test_suppress_overrides_notify(self):
        """A suppress rule with higher priority blocks notification."""
        rules = [
            GlobalNotificationRule(
                id="catch-all", action="notify", priority=10
            ),
            GlobalNotificationRule(
                id="block-spammer", action="suppress", priority=100,
                player_name="SpamBot",
            ),
        ]
        engine = RulesEngine(rules)

        # SpamBot: blocked by suppress rule
        result, rule = engine.evaluate(_make_event(player="SpamBot"))
        self.assertFalse(result)
        self.assertEqual(rule.id, "block-spammer")

        # Other player: passes through to catch-all notify
        result, rule = engine.evaluate(_make_event(player="GoodPlayer"))
        self.assertTrue(result)
        self.assertEqual(rule.id, "catch-all")

    def test_first_match_wins(self):
        """Once a rule matches, subsequent rules are not checked."""
        rules = [
            GlobalNotificationRule(id="first", action="notify", priority=100),
            GlobalNotificationRule(id="second", action="suppress", priority=50),
        ]
        engine = RulesEngine(rules)
        result, rule = engine.evaluate(_make_event())
        self.assertTrue(result)
        self.assertEqual(rule.id, "first")

    def test_update_rules(self):
        engine = RulesEngine([])
        result, _ = engine.evaluate(_make_event())
        self.assertFalse(result)

        engine.update_rules([GlobalNotificationRule(id="1", action="notify")])
        result, _ = engine.evaluate(_make_event())
        self.assertTrue(result)


class TestGlobalNotificationRule(unittest.TestCase):
    """Test rule serialization."""

    def test_to_dict_omits_none(self):
        rule = GlobalNotificationRule(id="1", action="notify", player_name="Test")
        d = rule.to_dict()
        self.assertIn("id", d)
        self.assertIn("player_name", d)
        self.assertNotIn("mob_name", d)
        self.assertNotIn("min_value", d)

    def test_from_dict_roundtrip(self):
        rule = GlobalNotificationRule(
            id="abc", action="suppress", priority=50,
            player_name="Test", min_value=100.0,
            global_types=["kill", "hof"],
        )
        d = rule.to_dict()
        restored = GlobalNotificationRule.from_dict(d)
        self.assertEqual(restored.id, "abc")
        self.assertEqual(restored.action, "suppress")
        self.assertEqual(restored.priority, 50)
        self.assertEqual(restored.player_name, "Test")
        self.assertEqual(restored.min_value, 100.0)
        self.assertEqual(restored.global_types, ["kill", "hof"])

    def test_from_dict_ignores_unknown_keys(self):
        d = {"id": "1", "action": "notify", "unknown_field": "ignored"}
        rule = GlobalNotificationRule.from_dict(d)
        self.assertEqual(rule.id, "1")
        self.assertFalse(hasattr(rule, "unknown_field"))


if __name__ == "__main__":
    unittest.main()
