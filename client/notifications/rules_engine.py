"""Rules engine for evaluating global events against notification rules.

Rules are sorted by priority (descending). The first matching rule wins.
If the first match is "suppress", the event is silenced.
If the first match is "notify", a notification is triggered.
If no rules match, no notification fires (opt-in model).
"""

from __future__ import annotations

from ..chat_parser.models import GlobalEvent
from .models import GlobalNotificationRule


class RulesEngine:
    """Evaluates GlobalEvent objects against an ordered list of rules."""

    def __init__(self, rules: list[GlobalNotificationRule] | None = None):
        self._rules: list[GlobalNotificationRule] = []
        if rules:
            self.update_rules(rules)

    def update_rules(self, rules: list[GlobalNotificationRule]) -> None:
        """Replace all rules (re-sorts by priority descending)."""
        self._rules = sorted(rules, key=lambda r: -r.priority)

    def evaluate(self, event: GlobalEvent) -> tuple[bool, GlobalNotificationRule | None]:
        """Check *event* against rules.

        Returns:
            (should_notify, matched_rule) — matched_rule is None when no rule matched.
        """
        for rule in self._rules:
            if not rule.enabled:
                continue
            if self._matches(rule, event):
                return (rule.action == "notify", rule)
        return (False, None)

    @staticmethod
    def _matches(rule: GlobalNotificationRule, event: GlobalEvent) -> bool:
        """Return True if all non-None filters in *rule* match *event*."""

        # Player name (substring, case-insensitive)
        if rule.player_name is not None:
            if rule.player_name.lower() not in event.player_name.lower():
                return False

        # Mob / item name (both check target_name)
        if rule.mob_name is not None:
            if rule.mob_name.lower() not in event.target_name.lower():
                return False
        if rule.item_name is not None:
            if rule.item_name.lower() not in event.target_name.lower():
                return False

        # Minimum PED value
        if rule.min_value is not None:
            if event.value < rule.min_value:
                return False

        # Global type filter (with hof/ath aliases)
        if rule.global_types is not None:
            aliases = [event.global_type.value]
            if event.is_hof:
                aliases.append("hof")
            if event.is_ath:
                aliases.append("ath")
            if not any(a in rule.global_types for a in aliases):
                return False

        # HoF / ATH requirements
        if rule.require_hof is True and not event.is_hof:
            return False
        if rule.require_ath is True and not event.is_ath:
            return False

        return True
