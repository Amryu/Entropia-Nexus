from ...core.constants import ENHANCER_BREAK_PATTERN, EVENT_ENHANCER_BREAK
from ..models import EnhancerBreakEvent, ParsedLine
from .base import BaseHandler


class EnhancerBreakHandler(BaseHandler):
    """Handles enhancer break messages."""

    def can_handle(self, parsed_line: ParsedLine) -> bool:
        if parsed_line.channel != "System" or parsed_line.username != "":
            return False
        return parsed_line.message.startswith("Your enhancer ")

    def handle(self, parsed_line: ParsedLine) -> None:
        match = ENHANCER_BREAK_PATTERN.match(parsed_line.message)
        if not match:
            return

        event = EnhancerBreakEvent(
            timestamp=parsed_line.timestamp,
            enhancer_name=match.group(1),
            item_name=match.group(2),
            remaining=int(match.group(3)),
            shrapnel_ped=float(match.group(4)),
        )

        self._event_bus.publish(EVENT_ENHANCER_BREAK, event)
        self._db.insert_enhancer_break(
            timestamp=event.timestamp.isoformat(),
            enhancer_name=event.enhancer_name,
            item_name=event.item_name,
            remaining=event.remaining,
            shrapnel_ped=event.shrapnel_ped,
        )
