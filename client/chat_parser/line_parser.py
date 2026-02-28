from datetime import datetime
from html import unescape
from typing import Optional

from ..core.constants import LINE_PATTERN
from .models import ParsedLine


class LineParser:
    """Parses a raw chat.log line into a ParsedLine."""

    def parse(self, raw_line: str, line_number: int) -> Optional[ParsedLine]:
        raw_line = raw_line.rstrip('\n\r')
        if not raw_line:
            return None

        match = LINE_PATTERN.match(raw_line)
        if not match:
            return None

        timestamp_str, channel, username, message = match.groups()

        # Manual timestamp parsing — ~10x faster than datetime.strptime.
        # Format is fixed: "YYYY-MM-DD HH:MM:SS" (19 chars).
        try:
            timestamp = datetime(
                int(timestamp_str[0:4]),    # year
                int(timestamp_str[5:7]),    # month
                int(timestamp_str[8:10]),   # day
                int(timestamp_str[11:13]),  # hour
                int(timestamp_str[14:16]),  # minute
                int(timestamp_str[17:19]),  # second
            )
        except (ValueError, IndexError):
            return None

        # Chat.log uses HTML entities in message text (e.g. &quot; for ")
        if '&' in message:
            message = unescape(message)

        return ParsedLine(
            timestamp=timestamp,
            channel=channel,
            username=username,
            message=message,
            raw_line=raw_line,
            line_number=line_number,
        )
