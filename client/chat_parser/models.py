from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class MessageType(Enum):
    # Skill gains
    SKILL_GAIN = "skill_gain"

    # Your attacks on target
    DAMAGE_DEALT = "damage_dealt"
    CRITICAL_HIT = "critical_hit"
    TARGET_JAM = "target_jam"
    TARGET_DODGE = "target_dodge"
    TARGET_EVADE = "target_evade"

    # Target's attacks on you
    DAMAGE_RECEIVED = "damage_received"
    DEFLECT = "deflect"
    PLAYER_EVADE = "player_evade"
    PLAYER_DODGE = "player_dodge"
    PLAYER_JAM = "player_jam"
    MOB_MISS = "mob_miss"

    # Self
    SELF_HEAL = "self_heal"

    # Death / revival
    PLAYER_DEATH = "player_death"
    PLAYER_REVIVED = "player_revived"

    # Equipment
    ENHANCER_BREAK = "enhancer_break"
    TIER_INCREASE = "tier_increase"

    # Loot
    LOOT_ITEM = "loot_item"

    # Globals
    GLOBAL_KILL = "global_kill"
    GLOBAL_TEAM_KILL = "global_team_kill"
    GLOBAL_DEPOSIT = "global_deposit"
    GLOBAL_CRAFT = "global_craft"
    GLOBAL_RARE_ITEM = "global_rare_item"
    GLOBAL_DISCOVERY = "global_discovery"
    GLOBAL_TIER = "global_tier"

    # Chat
    TRADE_CHAT = "trade_chat"

    UNKNOWN = "unknown"


@dataclass
class ParsedLine:
    """Raw parsed line before classification."""
    timestamp: datetime
    channel: str
    username: str
    message: str
    raw_line: str
    line_number: int


@dataclass
class SkillGainEvent:
    timestamp: datetime
    skill_name: str
    amount: float
    is_attribute: bool  # True = short format (e.g., "You have gained 0.0248 Bravado")


@dataclass
class CombatEvent:
    timestamp: datetime
    event_type: MessageType
    amount: Optional[float] = None  # None for deflect/evade/miss/jam/dodge


@dataclass
class EnhancerBreakEvent:
    timestamp: datetime
    enhancer_name: str
    item_name: str
    remaining: int
    shrapnel_ped: float


@dataclass
class EffectReceivedEvent:
    """A 'Received Effect Over Time: <name>' system message.

    The effect can be applied by the player's own tool (e.g. Divine
    Intervention Chip) OR by another player (e.g. a team healer).  This
    event carries only the raw fact; cost attribution happens downstream
    after cross-checking with the active-tool OCR.
    """
    timestamp: datetime
    effect_name: str


@dataclass
class LootItem:
    timestamp: datetime
    item_name: str
    quantity: int
    value_ped: float


@dataclass
class LootGroup:
    """Items from a single kill/action, grouped by shared timestamp."""
    timestamp: datetime
    items: list[LootItem] = field(default_factory=list)
    total_value_ped: float = 0.0


class GlobalType(Enum):
    KILL = "kill"
    TEAM_KILL = "team_kill"
    DEPOSIT = "deposit"
    CRAFT = "craft"
    FISH = "fish"
    RARE_ITEM = "rare_item"
    DISCOVERY = "discovery"
    TIER = "tier"
    EXAMINE = "examine"
    PVP = "pvp"


@dataclass
class GlobalEvent:
    timestamp: datetime
    global_type: GlobalType
    player_name: str
    target_name: str
    value: float
    value_unit: str  # "PED" or "PEC"
    location: Optional[str] = None
    is_hof: bool = False
    is_ath: bool = False


@dataclass
class TierIncreaseEvent:
    timestamp: datetime
    item_name: str
    tier: float


@dataclass
class PlayerDeathEvent:
    timestamp: datetime
    mob_name: str  # Mob name + maturity, adjective already stripped


@dataclass
class PlayerRevivedEvent:
    timestamp: datetime


@dataclass
class TradeChatMessage:
    timestamp: datetime
    channel: str
    username: str
    message: str
