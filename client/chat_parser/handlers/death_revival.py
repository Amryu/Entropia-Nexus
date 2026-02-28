from ...core.constants import DEATH_PATTERN, REVIVAL_PATTERN, EVENT_PLAYER_DEATH, EVENT_PLAYER_REVIVED
from ..models import ParsedLine, PlayerDeathEvent, PlayerRevivedEvent
from .base import BaseHandler


_DEATH_REVIVAL_PREFIXES = (
    "You were killed by",
    "You have been revived",
)


class DeathRevivalHandler(BaseHandler):
    """Handles player death and revival messages."""

    def can_handle(self, parsed_line: ParsedLine) -> bool:
        if parsed_line.channel != "System" or parsed_line.username != "":
            return False
        return parsed_line.message.startswith(_DEATH_REVIVAL_PREFIXES)

    def handle(self, parsed_line: ParsedLine) -> None:
        msg = parsed_line.message

        # Death: "You were killed by the <adjective> <Mob Name + Maturity>"
        match = DEATH_PATTERN.match(msg)
        if match:
            mob_name = match.group(1)
            event = PlayerDeathEvent(
                timestamp=parsed_line.timestamp,
                mob_name=mob_name,
            )
            if not self.suppress_events:
                self._event_bus.publish(EVENT_PLAYER_DEATH, event)
            return

        # Revival: "You have been revived"
        if REVIVAL_PATTERN.match(msg):
            event = PlayerRevivedEvent(timestamp=parsed_line.timestamp)
            if not self.suppress_events:
                self._event_bus.publish(EVENT_PLAYER_REVIVED, event)
