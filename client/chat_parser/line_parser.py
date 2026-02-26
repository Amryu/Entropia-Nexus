from datetime import datetime
from typing import Optional

from ..core.constants import HTML_ENTITIES, LINE_PATTERN, TIMESTAMP_FORMAT
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

        try:
            timestamp = datetime.strptime(timestamp_str, TIMESTAMP_FORMAT)
        except ValueError:
            return None

        # Decode HTML entities in the message
        message = self._decode_html_entities(message)

        return ParsedLine(
            timestamp=timestamp,
            channel=channel,
            username=username,
            message=message,
            raw_line=raw_line,
            line_number=line_number,
        )

    @staticmethod
    def _decode_html_entities(text: str) -> str:
        for entity, char in HTML_ENTITIES.items():
            text = text.replace(entity, char)
        return text
