from ...core.constants import EVENT_TIER_INCREASE, TIER_INCREASE_PATTERN
from ..models import ParsedLine, TierIncreaseEvent
from .base import BaseHandler


class TierHandler(BaseHandler):
    """Handles item tier increase messages.

    Format: 'Your Angel Harness (M) has reached tier 7.21'
    """

    def can_handle(self, parsed_line: ParsedLine) -> bool:
        if parsed_line.channel != "System" or parsed_line.username != "":
            return False
        return parsed_line.message.startswith("Your ") and "has reached tier" in parsed_line.message

    def handle(self, parsed_line: ParsedLine) -> None:
        match = TIER_INCREASE_PATTERN.match(parsed_line.message)
        if not match:
            return

        event = TierIncreaseEvent(
            timestamp=parsed_line.timestamp,
            item_name=match.group(1),
            tier=float(match.group(2)),
        )

        self._event_bus.publish(EVENT_TIER_INCREASE, event)
        self._db.insert_tier_increase(
            timestamp=event.timestamp.isoformat(),
            item_name=event.item_name,
            tier=event.tier,
        )
