from ...core.constants import EVENT_TRADE_CHAT, TRADE_CHANNEL_PATTERN
from ..models import ParsedLine, TradeChatMessage
from .base import BaseHandler


class TradeChatHandler(BaseHandler):
    """Handles messages from trade channels (any channel with 'trade' or 'trading' in name)."""

    def can_handle(self, parsed_line: ParsedLine) -> bool:
        return bool(TRADE_CHANNEL_PATTERN.search(parsed_line.channel))

    def handle(self, parsed_line: ParsedLine) -> None:
        event = TradeChatMessage(
            timestamp=parsed_line.timestamp,
            channel=parsed_line.channel,
            username=parsed_line.username,
            message=parsed_line.message,
        )

        self._event_bus.publish(EVENT_TRADE_CHAT, event)
        self._db.insert_trade_message(
            timestamp=event.timestamp.isoformat(),
            channel=event.channel,
            username=event.username,
            message=event.message,
        )
