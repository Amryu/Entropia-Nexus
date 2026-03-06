"""Notification system data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


# Notification sources
SOURCE_GLOBAL = "global"
SOURCE_TRADE_CHAT = "trade_chat"
SOURCE_NEXUS = "nexus"
SOURCE_SYSTEM = "system"
SOURCE_STREAM = "stream"
SOURCE_EXCHANGE = "exchange"
SOURCE_TRACKER = "tracker"


@dataclass
class Notification:
    """A single notification entry."""

    id: str  # UUID
    source: str  # SOURCE_* constant
    title: str
    body: str
    timestamp: datetime
    read: bool = False
    priority: str = "normal"  # "low", "normal", "high"
    metadata: dict = field(default_factory=dict)
    server_id: int | None = None


@dataclass
class GlobalNotificationRule:
    """A rule for filtering global loot events.

    All non-None filter fields use AND logic (all must match).
    Rules are evaluated in priority order (highest first); first match wins.
    """

    id: str  # UUID
    enabled: bool = True
    action: str = "notify"  # "notify" or "suppress"
    priority: int = 0  # Higher = evaluated first

    # Filter criteria (all optional; all non-None must match)
    player_name: str | None = None  # Substring, case-insensitive
    mob_name: str | None = None  # Substring on target_name
    item_name: str | None = None  # Substring on target_name
    min_value: float | None = None  # Minimum PED value
    global_types: list[str] | None = None  # e.g. ["kill", "hof", "ath"]
    require_hof: bool | None = None
    require_ath: bool | None = None

    def to_dict(self) -> dict:
        """Serialize for JSON config (omit None values)."""
        d = {}
        for k, v in self.__dict__.items():
            if v is not None:
                d[k] = v
        return d

    @classmethod
    def from_dict(cls, d: dict) -> GlobalNotificationRule:
        """Deserialize from JSON config dict."""
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)


@dataclass
class TradeKeywordEntry:
    """A single trade chat keyword/item filter entry.

    When trade chat notifications are enabled and entries exist, only
    messages matching at least one enabled entry trigger notifications.
    """

    id: str  # UUID
    pattern: str  # keyword text, regex pattern, or item name
    is_regex: bool = False
    is_item: bool = False  # True when selected from item database
    item_id: int | None = None  # exchange item ID if is_item
    planet: str = ""  # "" = all planets
    enabled: bool = True

    def to_dict(self) -> dict:
        d = {}
        for k, v in self.__dict__.items():
            if v is not None:
                d[k] = v
        return d

    @classmethod
    def from_dict(cls, d: dict) -> TradeKeywordEntry:
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)
