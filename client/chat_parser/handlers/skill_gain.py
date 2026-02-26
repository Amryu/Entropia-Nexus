from ...core.constants import (
    EVENT_SKILL_GAIN,
    SKILL_DIRECT_PATTERN,
    SKILL_EXP_PATTERN,
)
from ..models import ParsedLine, SkillGainEvent
from .base import BaseHandler


class SkillGainHandler(BaseHandler):
    """Handles skill gain messages in two formats:
    - 'You have gained 0.6347 experience in your Manufacture Mechanical Equipment skill'
    - 'You have gained 0.0248 Bravado' (attributes/general)
    """

    def can_handle(self, parsed_line: ParsedLine) -> bool:
        if parsed_line.channel != "System" or parsed_line.username != "":
            return False
        return parsed_line.message.startswith("You have gained ")

    def handle(self, parsed_line: ParsedLine) -> None:
        msg = parsed_line.message

        # Try the full format first: "experience in your ... skill"
        match = SKILL_EXP_PATTERN.match(msg)
        if match:
            event = SkillGainEvent(
                timestamp=parsed_line.timestamp,
                skill_name=match.group(2),
                amount=float(match.group(1)),
                is_attribute=False,
            )
            self._emit(event)
            return

        # Try the short format: "You have gained 0.0248 Bravado"
        match = SKILL_DIRECT_PATTERN.match(msg)
        if match:
            event = SkillGainEvent(
                timestamp=parsed_line.timestamp,
                skill_name=match.group(2),
                amount=float(match.group(1)),
                is_attribute=True,
            )
            self._emit(event)

    def _emit(self, event: SkillGainEvent):
        self._event_bus.publish(EVENT_SKILL_GAIN, event)
        self._db.insert_skill_gain(
            timestamp=event.timestamp.isoformat(),
            skill_name=event.skill_name,
            amount=event.amount,
            is_attribute=event.is_attribute,
        )
