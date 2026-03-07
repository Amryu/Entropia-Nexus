from datetime import datetime, timedelta

from ...core.constants import EVENT_TRADE_CHAT, TRADE_CHANNEL_PATTERN
from ..models import ParsedLine, TradeChatMessage
from .base import BaseHandler

# Trade messages older than this are rejected by the server (MAX_EVENT_AGE_MS = 24h).
# Don't bother saving them to the local DB.
MAX_TRADE_AGE = timedelta(days=1)


class TradeChatHandler(BaseHandler):
    """Handles messages from trade channels (any channel with 'trade' or 'trading' in name)."""

    suppress_events: bool = False  # Set during catchup to skip EventBus publish

    def can_handle(self, parsed_line: ParsedLine) -> bool:
        return bool(TRADE_CHANNEL_PATTERN.search(parsed_line.channel))

    def handle(self, parsed_line: ParsedLine) -> None:
        event = TradeChatMessage(
            timestamp=parsed_line.timestamp,
            channel=parsed_line.channel,
            username=parsed_line.username,
            message=parsed_line.message,
        )

        if not self.suppress_events:
            self._event_bus.publish(EVENT_TRADE_CHAT, event)
        if self.ingestion_enabled:
            if datetime.now() - event.timestamp > MAX_TRADE_AGE:
                return
            self._db.insert_trade_message(
                timestamp=event.timestamp.isoformat(),
                channel=event.channel,
                username=event.username,
                message=event.message,
            )
