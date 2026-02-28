from abc import ABC, abstractmethod

from ...core.event_bus import EventBus
from ...core.database import Database
from ..models import ParsedLine


class BaseHandler(ABC):
    """Abstract base for all chat message handlers."""

    def __init__(self, event_bus: EventBus, db: Database):
        self._event_bus = event_bus
        self._db = db
        self.suppress_events = False
        self.ingestion_enabled = False  # Set True when authenticated; gates globals/trade DB writes

    @abstractmethod
    def can_handle(self, parsed_line: ParsedLine) -> bool:
        """Return True if this handler can process the given line."""
        ...

    @abstractmethod
    def handle(self, parsed_line: ParsedLine) -> None:
        """Process the parsed line and emit events / persist data."""
        ...
