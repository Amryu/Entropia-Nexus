from ...core.constants import (
    COMBAT_CRIT_PATTERN,
    COMBAT_DAMAGE_DEALT_PATTERN,
    COMBAT_DAMAGE_RECEIVED_PATTERN,
    COMBAT_DEFLECT_PATTERN,
    COMBAT_MOB_MISS_PATTERN,
    COMBAT_PLAYER_DODGE_PATTERN,
    COMBAT_PLAYER_EVADE_PATTERN,
    COMBAT_PLAYER_JAM_PATTERN,
    COMBAT_SELF_HEAL_PATTERN,
    COMBAT_TARGET_DODGE_PATTERN,
    COMBAT_TARGET_EVADE_PATTERN,
    COMBAT_TARGET_JAM_PATTERN,
    EVENT_COMBAT,
)
from ..models import CombatEvent, MessageType, ParsedLine
from .base import BaseHandler

# Ordered list: patterns with capture groups first, then exact matches.
# Critical hit MUST come before regular damage dealt.
_COMBAT_PATTERNS = [
    (COMBAT_CRIT_PATTERN, MessageType.CRITICAL_HIT, True),
    (COMBAT_DAMAGE_DEALT_PATTERN, MessageType.DAMAGE_DEALT, True),
    (COMBAT_DAMAGE_RECEIVED_PATTERN, MessageType.DAMAGE_RECEIVED, True),
    (COMBAT_SELF_HEAL_PATTERN, MessageType.SELF_HEAL, True),
    (COMBAT_DEFLECT_PATTERN, MessageType.DEFLECT, False),
    (COMBAT_PLAYER_EVADE_PATTERN, MessageType.PLAYER_EVADE, False),
    (COMBAT_PLAYER_DODGE_PATTERN, MessageType.PLAYER_DODGE, False),
    (COMBAT_PLAYER_JAM_PATTERN, MessageType.PLAYER_JAM, False),
    (COMBAT_MOB_MISS_PATTERN, MessageType.MOB_MISS, False),
    (COMBAT_TARGET_JAM_PATTERN, MessageType.TARGET_JAM, False),
    (COMBAT_TARGET_DODGE_PATTERN, MessageType.TARGET_DODGE, False),
    (COMBAT_TARGET_EVADE_PATTERN, MessageType.TARGET_EVADE, False),
]

# Quick prefixes to fast-reject non-combat messages
_COMBAT_PREFIXES = (
    "You inflicted",
    "Critical hit",
    "You took",
    "You healed",
    "Damage deflected",
    "You Evaded",
    "You Dodged",
    "You Jammed",
    "The attack missed",
    "The target Jammed",
    "The target Dodged",
    "The target Evaded",
)


class CombatHandler(BaseHandler):
    """Handles all combat-related messages."""

    def can_handle(self, parsed_line: ParsedLine) -> bool:
        if parsed_line.channel != "System" or parsed_line.username != "":
            return False
        return parsed_line.message.startswith(_COMBAT_PREFIXES)

    def handle(self, parsed_line: ParsedLine) -> None:
        msg = parsed_line.message
        for pattern, msg_type, has_amount in _COMBAT_PATTERNS:
            match = pattern.match(msg)
            if match:
                amount = float(match.group(1)) if has_amount else None
                event = CombatEvent(
                    timestamp=parsed_line.timestamp,
                    event_type=msg_type,
                    amount=amount,
                )
                self._event_bus.publish(EVENT_COMBAT, event)
                self._db.insert_combat_event(
                    timestamp=event.timestamp.isoformat(),
                    event_type=msg_type.value,
                    amount=amount,
                )
                return
