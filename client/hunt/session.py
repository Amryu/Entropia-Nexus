"""Hunt session and encounter data models."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EncounterToolStats:
    """Per-tool damage breakdown within an encounter."""
    tool_name: str
    shots_fired: int = 0
    damage_dealt: float = 0.0
    critical_hits: int = 0


@dataclass
class CombatEventDetail:
    """Individual combat event for tool inference and retroactive enrichment."""
    id: str
    encounter_id: str
    timestamp: datetime
    event_type: str  # damage_dealt, critical_hit, damage_received, etc.
    amount: float = 0.0
    tool_name: str | None = None
    tool_source: str | None = None  # 'ocr', 'inferred', 'loadout'
    inferred_confidence: float = 0.0


@dataclass
class EncounterLootItem:
    """A loot item attributed to an encounter, with classification."""
    item_name: str
    quantity: int
    value_ped: float
    is_blacklisted: bool = False
    is_refining_output: bool = False
    is_in_loot_table: bool = True  # True when mob unknown (assume valid)


@dataclass
class WeaponSignature:
    """Precomputed weapon damage signature for tool inference."""
    weapon_name: str
    damage_min: float
    damage_max: float
    total_damage: float
    cost_per_shot: float  # decay + ammo burn
    crit_damage: float = 1.0  # multiplier: 1 + (BonusCritDamage% / 100)


@dataclass
class SessionLoadoutEntry:
    """A timestamped loadout snapshot within a hunt session."""
    id: int | None = None          # DB auto-increment
    session_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    loadout_data: dict = field(default_factory=dict)   # Full loadout JSON
    weapon_name: str | None = None
    cost_per_shot: float = 0.0
    damage_min: float = 0.0
    damage_max: float = 0.0
    crit_damage: float = 1.0      # crit multiplier: 1 + (BonusCritDamage% / 100)
    source: str = "snapshot"       # 'snapshot', 'user_edit', 'external_update', 'auto_detected'


@dataclass
class MobEncounter:
    """A single combat encounter with one mob."""
    id: str
    session_id: str
    mob_name: str
    mob_name_source: str  # 'ocr', 'interpolated', 'user'
    start_time: datetime
    end_time: datetime | None = None
    hunt_id: str | None = None

    # Combat stats
    damage_dealt: float = 0.0
    damage_taken: float = 0.0
    heals_received: float = 0.0
    shots_fired: int = 0
    critical_hits: int = 0

    # Defensive (evade/dodge/jam are the same mechanic per combat type)
    player_avoids: int = 0   # player evaded/dodged/jammed mob attack
    target_avoids: int = 0   # mob evaded/dodged/jammed player attack
    mob_misses: int = 0      # mob missed player (separate mechanic)
    deflects: int = 0        # player deflected mob attack
    blocks: int = 0          # player blocked mob attack (0.0 damage received)

    # Loot
    loot_total_ped: float = 0.0
    loot_items: list[EncounterLootItem] = field(default_factory=list)

    # Cost (populated by tool inference)
    cost: float = 0.0

    # Global / Hall of Fame
    is_global: bool = False
    is_hof: bool = False

    # Attribution
    confidence: float = 1.0
    tool_stats: dict[str, EncounterToolStats] = field(default_factory=dict)

    # Outcome tracking
    outcome: str = "kill"  # "kill", "death", "abandoned", "timeout", "force_closed", "merged"
    death_count: int = 0
    killed_by_mob: str | None = None   # Mob name from death message (attribution confirmation)
    is_open_ended: bool = False        # True if ended without a kill (pending resolution)
    merged_into: str | None = None     # ID of encounter this was merged into
    merged_from: list[str] = field(default_factory=list)  # IDs of encounters merged into this one

    @property
    def effective_loot_ped(self) -> float:
        """Loot total excluding blacklisted and refining items.

        Falls back to loot_total_ped when no individual items are tracked
        (e.g. encounters from before per-item tracking).
        """
        if not self.loot_items:
            return self.loot_total_ped
        return sum(
            li.value_ped for li in self.loot_items
            if not li.is_blacklisted and not li.is_refining_output
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "hunt_id": self.hunt_id,
            "mob_name": self.mob_name,
            "mob_name_source": self.mob_name_source,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "damage_dealt": self.damage_dealt,
            "damage_taken": self.damage_taken,
            "heals_received": self.heals_received,
            "shots_fired": self.shots_fired,
            "critical_hits": self.critical_hits,
            "loot_total_ped": self.effective_loot_ped,
            "loot_items": [
                {
                    "item_name": li.item_name,
                    "quantity": li.quantity,
                    "value_ped": li.value_ped,
                    "is_blacklisted": li.is_blacklisted,
                    "is_refining_output": li.is_refining_output,
                    "is_in_loot_table": li.is_in_loot_table,
                }
                for li in self.loot_items
            ],
            "cost": self.cost,
            "confidence": self.confidence,
            "is_global": self.is_global,
            "is_hof": self.is_hof,
            "tool_stats": {
                name: {
                    "shots": s.shots_fired,
                    "damage": s.damage_dealt,
                    "crits": s.critical_hits,
                }
                for name, s in self.tool_stats.items()
            },
            "outcome": self.outcome,
            "death_count": self.death_count,
            "killed_by_mob": self.killed_by_mob,
            "is_open_ended": self.is_open_ended,
            "merged_into": self.merged_into,
            "merged_from": self.merged_from,
        }


@dataclass
class Hunt:
    """A logical hunt — group of encounters at one location against one mob type.

    Hunts are auto-detected within a session based on mob type changes.
    Mixed spawns (multiple mob types interleaving) do NOT trigger splits.
    """
    id: str
    session_id: str
    start_time: datetime
    end_time: datetime | None = None
    primary_mob: str | None = None
    location_label: str | None = None

    encounters: list[MobEncounter] = field(default_factory=list)

    @property
    def kill_count(self) -> int:
        return len([e for e in self.encounters if e.outcome == "kill"])

    @property
    def death_count(self) -> int:
        return sum(e.death_count for e in self.encounters)

    @property
    def total_damage_dealt(self) -> float:
        return sum(e.damage_dealt for e in self.encounters)

    @property
    def total_damage_taken(self) -> float:
        return sum(e.damage_taken for e in self.encounters)

    @property
    def total_loot(self) -> float:
        return sum(e.effective_loot_ped for e in self.encounters)

    @property
    def total_cost(self) -> float:
        return sum(e.cost for e in self.encounters)

    @property
    def return_pct(self) -> float | None:
        if self.total_cost <= 0:
            return None
        return (self.total_loot / self.total_cost) * 100

    @property
    def global_count(self) -> int:
        return sum(1 for e in self.encounters if e.is_global)

    @property
    def hof_count(self) -> int:
        return sum(1 for e in self.encounters if e.is_hof)

    @property
    def all_loot_items(self) -> list[EncounterLootItem]:
        """Flat list of non-blacklisted, non-refining loot items across encounters."""
        items = []
        for enc in self.encounters:
            for li in enc.loot_items:
                if not li.is_blacklisted and not li.is_refining_output:
                    items.append(li)
        return items

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "primary_mob": self.primary_mob,
            "location_label": self.location_label,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "kill_count": self.kill_count,
            "death_count": self.death_count,
            "damage_dealt": self.total_damage_dealt,
            "damage_taken": self.total_damage_taken,
            "loot_total": self.total_loot,
            "cost": self.total_cost,
            "return_pct": self.return_pct,
            "global_count": self.global_count,
            "hof_count": self.hof_count,
        }


@dataclass
class HuntSession:
    """A hunting session containing multiple mob encounters."""
    id: str
    start_time: datetime
    end_time: datetime | None = None
    loadout_id: str | None = None
    primary_mob: str | None = None
    notes: str | None = None

    encounters: list[MobEncounter] = field(default_factory=list)
    hunts: list[Hunt] = field(default_factory=list)
    expected_tools: list[str] = field(default_factory=list)
    loadout_entries: list[SessionLoadoutEntry] = field(default_factory=list)

    # Session auto-timeout tracking
    last_event_time: datetime | None = None

    @property
    def total_damage_dealt(self) -> float:
        return sum(e.damage_dealt for e in self.encounters)

    @property
    def total_damage_taken(self) -> float:
        return sum(e.damage_taken for e in self.encounters)

    @property
    def total_loot(self) -> float:
        return sum(e.effective_loot_ped for e in self.encounters)

    @property
    def total_cost(self) -> float:
        return sum(e.cost for e in self.encounters)

    @property
    def kill_count(self) -> int:
        return len([e for e in self.encounters if e.outcome == "kill"])

    @property
    def death_count(self) -> int:
        return sum(e.death_count for e in self.encounters)

    @property
    def all_loot_items(self) -> list[EncounterLootItem]:
        """Flat list of non-blacklisted, non-refining loot items across encounters."""
        items = []
        for enc in self.encounters:
            for li in enc.loot_items:
                if not li.is_blacklisted and not li.is_refining_output:
                    items.append(li)
        return items

    def to_summary(self) -> dict:
        hunt_summaries = [h.to_dict() for h in self.hunts]
        return {
            "session_id": self.id,
            "kills": self.kill_count,
            "deaths": self.death_count,
            "damage_dealt": self.total_damage_dealt,
            "damage_taken": self.total_damage_taken,
            "loot_total": self.total_loot,
            "total_cost": self.total_cost,
            "hunt_count": len(self.hunts),
            "hunts": hunt_summaries,
        }
