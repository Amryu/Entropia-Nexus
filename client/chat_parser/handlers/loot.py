from typing import Optional

from ...core.constants import EVENT_LOOT_GROUP, LOOT_PATTERN
from ..models import LootGroup, LootItem, ParsedLine
from .base import BaseHandler


class LootHandler(BaseHandler):
    """Handles loot messages and groups items by timestamp.

    Items from a single kill/action share the exact same timestamp.
    The group is flushed when a line with a later timestamp arrives.
    """

    def __init__(self, event_bus, db):
        super().__init__(event_bus, db)
        self._pending_group: Optional[LootGroup] = None

    def can_handle(self, parsed_line: ParsedLine) -> bool:
        if parsed_line.channel != "System" or parsed_line.username != "":
            return False
        return parsed_line.message.startswith("You received ")

    def handle(self, parsed_line: ParsedLine) -> None:
        match = LOOT_PATTERN.match(parsed_line.message)
        if not match:
            return

        item = LootItem(
            timestamp=parsed_line.timestamp,
            item_name=match.group(1),
            quantity=int(match.group(2)),
            value_ped=float(match.group(3)),
        )

        if self._pending_group and self._pending_group.timestamp == parsed_line.timestamp:
            self._pending_group.items.append(item)
            self._pending_group.total_value_ped += item.value_ped
        else:
            self._flush_pending()
            self._pending_group = LootGroup(
                timestamp=parsed_line.timestamp,
                items=[item],
                total_value_ped=item.value_ped,
            )

    def notify_timestamp_advanced(self, timestamp) -> None:
        """Called by the classifier when a line with a later timestamp arrives.
        Flushes the pending group if its timestamp is older."""
        if self._pending_group and timestamp > self._pending_group.timestamp:
            self._flush_pending()

    def flush(self) -> None:
        """Force-flush any pending group (called on shutdown/EOF)."""
        self._flush_pending()

    def _flush_pending(self) -> None:
        if not self._pending_group:
            return

        group = self._pending_group
        self._pending_group = None

        if not self.suppress_events:
            self._event_bus.publish(EVENT_LOOT_GROUP, group)
        self._db.insert_loot_group(
            timestamp=group.timestamp.isoformat(),
            total_value=group.total_value_ped,
            items=[(item.item_name, item.quantity, item.value_ped) for item in group.items],
        )
