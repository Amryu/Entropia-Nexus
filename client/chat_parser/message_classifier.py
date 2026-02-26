from .handlers.base import BaseHandler
from .handlers.combat import CombatHandler
from .handlers.death_revival import DeathRevivalHandler
from .handlers.enhancer import EnhancerBreakHandler
from .handlers.globals import GlobalsHandler
from .handlers.loot import LootHandler
from .handlers.skill_gain import SkillGainHandler
from .handlers.tier import TierHandler
from .handlers.trade_chat import TradeChatHandler
from .models import ParsedLine
from ..core.event_bus import EventBus
from ..core.database import Database


class MessageClassifier:
    """Routes parsed lines to appropriate handlers based on channel and content.

    System messages are checked against handlers in priority order.
    Globals and trade channels are routed directly.
    The loot handler is notified of timestamp advances to flush pending groups.
    """

    def __init__(self, event_bus: EventBus, db: Database):
        self._event_bus = event_bus
        self._db = db

        # Create handlers
        self._skill_gain = SkillGainHandler(event_bus, db)
        self._combat = CombatHandler(event_bus, db)
        self._death_revival = DeathRevivalHandler(event_bus, db)
        self._loot = LootHandler(event_bus, db)
        self._enhancer = EnhancerBreakHandler(event_bus, db)
        self._tier = TierHandler(event_bus, db)
        self._globals = GlobalsHandler(event_bus, db)
        self._trade = TradeChatHandler(event_bus, db)

        # System handlers in priority order
        # Death/revival before combat — "You were killed by" must not fall through
        self._system_handlers: list[BaseHandler] = [
            self._skill_gain,
            self._loot,
            self._tier,
            self._enhancer,
            self._death_revival,
            self._combat,
        ]

    def classify_and_handle(self, parsed_line: ParsedLine) -> None:
        """Route a parsed line to the appropriate handler."""
        # Always notify loot handler of timestamp advances (for grouping)
        self._loot.notify_timestamp_advanced(parsed_line.timestamp)

        # Globals channel
        if self._globals.can_handle(parsed_line):
            self._globals.handle(parsed_line)
            return

        # Trade channels
        if self._trade.can_handle(parsed_line):
            self._trade.handle(parsed_line)
            return

        # System messages
        if parsed_line.channel == "System" and parsed_line.username == "":
            for handler in self._system_handlers:
                if handler.can_handle(parsed_line):
                    handler.handle(parsed_line)
                    return

    def flush(self) -> None:
        """Flush any pending state in handlers (call on shutdown/EOF)."""
        self._loot.flush()
