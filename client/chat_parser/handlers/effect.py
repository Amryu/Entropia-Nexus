"""Handler for 'Received Effect Over Time: <name>' system messages.

Examples observed in chat.log::

    [System] [] Received Effect Over Time: Heal
    [System] [] Received Effect Over Time: Divine Intervention
    [System] [] Received Effect Over Time: Increased Critical Chance

The effect can be applied by the player's own tool (e.g. a Divine
Intervention Chip the player just used) OR by another player (e.g. a
healer in the same team).  Attribution to the player's own tool use
happens downstream in the hunt tracker, where the OCR-detected active
tool is cross-checked against a known effect-to-tool mapping.

This handler only emits the raw event.
"""

from ...core.constants import EFFECT_OVER_TIME_PATTERN, EVENT_EFFECT_RECEIVED
from ..models import EffectReceivedEvent, ParsedLine
from .base import BaseHandler


class EffectOverTimeHandler(BaseHandler):
    """Detects 'Received Effect Over Time' system messages."""

    def can_handle(self, parsed_line: ParsedLine) -> bool:
        if parsed_line.channel != "System" or parsed_line.username != "":
            return False
        return parsed_line.message.startswith("Received Effect Over Time:")

    def handle(self, parsed_line: ParsedLine) -> None:
        match = EFFECT_OVER_TIME_PATTERN.match(parsed_line.message)
        if not match:
            return
        effect_name = match.group(1).strip()
        if not effect_name:
            return

        event = EffectReceivedEvent(
            timestamp=parsed_line.timestamp,
            effect_name=effect_name,
        )

        if not self.suppress_events:
            self._event_bus.publish(EVENT_EFFECT_RECEIVED, event)
