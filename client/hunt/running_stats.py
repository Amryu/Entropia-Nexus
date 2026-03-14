"""Running statistics for hunt sessions — incremental aggregation.

Uses Welford's online algorithm for single-pass min/max/avg/variance
so we never need to iterate the full encounter list.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .session import MobEncounter


@dataclass
class RunningAggregate:
    """Single-pass min/max/avg/variance via Welford's online algorithm."""
    count: int = 0
    total: float = 0.0
    min_val: float = float('inf')
    max_val: float = float('-inf')
    _mean: float = 0.0
    _m2: float = 0.0

    def update(self, value: float):
        self.count += 1
        self.total += value
        if value < self.min_val:
            self.min_val = value
        if value > self.max_val:
            self.max_val = value
        # Welford's algorithm
        delta = value - self._mean
        self._mean += delta / self.count
        delta2 = value - self._mean
        self._m2 += delta * delta2

    @property
    def avg(self) -> float:
        return self._mean if self.count > 0 else 0.0

    @property
    def variance(self) -> float:
        if self.count < 2:
            return 0.0
        return self._m2 / (self.count - 1)

    @property
    def std_dev(self) -> float:
        return math.sqrt(self.variance)

    def to_dict(self) -> dict:
        if self.count == 0:
            return {"count": 0, "avg": 0, "min": 0, "max": 0,
                    "total": 0, "std_dev": 0}
        return {
            "count": self.count,
            "avg": round(self.avg, 4),
            "min": round(self.min_val, 4),
            "max": round(self.max_val, 4),
            "total": round(self.total, 4),
            "std_dev": round(self.std_dev, 4),
        }


@dataclass
class MobRunningStats:
    """Per-mob-type running statistics, updated per finalized encounter."""
    mob_name: str
    mob_id: int | None = None

    kill_count: int = 0
    death_count: int = 0

    damage_per_kill: RunningAggregate = field(default_factory=RunningAggregate)
    cost_per_kill: RunningAggregate = field(default_factory=RunningAggregate)
    loot_per_kill: RunningAggregate = field(default_factory=RunningAggregate)
    shots_per_kill: RunningAggregate = field(default_factory=RunningAggregate)

    total_damage: float = 0.0
    total_cost: float = 0.0
    total_loot: float = 0.0
    total_shots: int = 0
    total_crits: int = 0
    total_target_avoids: int = 0

    # Efficiency tracking
    expected_dpp: float | None = None  # damage per pec from loadout
    actual_dpp: RunningAggregate = field(default_factory=RunningAggregate)

    def on_encounter_finalized(self, enc: MobEncounter):
        """Update stats with a finalized encounter."""
        if enc.outcome == "kill":
            self.kill_count += 1
            self.damage_per_kill.update(enc.damage_dealt)
            self.cost_per_kill.update(enc.cost)
            self.loot_per_kill.update(enc.effective_loot_ped)
            self.shots_per_kill.update(enc.shots_fired)

            # Efficiency: actual damage per pec
            if enc.shots_fired > 0 and enc.cost > 0:
                actual = enc.damage_dealt / (enc.cost * 100)
                self.actual_dpp.update(actual)

        self.death_count += enc.death_count
        self.total_damage += enc.damage_dealt
        self.total_cost += enc.cost
        self.total_loot += enc.effective_loot_ped
        self.total_shots += enc.shots_fired
        self.total_crits += enc.critical_hits
        self.total_target_avoids += enc.target_avoids

    def efficiency_metrics(self) -> dict:
        """Compare actual vs expected DPP from loadout.

        Returns empty dict if no data available.
        efficiency_ratio < 1 means mob costs more than expected.
        overhead_pct > 0 means % extra cost vs theoretical.
        """
        if not self.expected_dpp or self.actual_dpp.count == 0:
            return {}

        ratio = self.actual_dpp.avg / self.expected_dpp
        overhead_pct = ((1 / ratio) - 1) * 100 if ratio > 0 else None
        return {
            "expected_dpp": round(self.expected_dpp, 4),
            "actual_dpp_avg": round(self.actual_dpp.avg, 4),
            "actual_dpp_min": round(self.actual_dpp.min_val, 4),
            "actual_dpp_max": round(self.actual_dpp.max_val, 4),
            "efficiency_ratio": round(ratio, 4),
            "overhead_pct": round(overhead_pct, 2) if overhead_pct is not None else None,
        }

    def to_dict(self) -> dict:
        result = {
            "mob_name": self.mob_name,
            "mob_id": self.mob_id,
            "kill_count": self.kill_count,
            "death_count": self.death_count,
            "damage_per_kill": self.damage_per_kill.to_dict(),
            "cost_per_kill": self.cost_per_kill.to_dict(),
            "loot_per_kill": self.loot_per_kill.to_dict(),
            "shots_per_kill": self.shots_per_kill.to_dict(),
            "total_damage": round(self.total_damage, 4),
            "total_cost": round(self.total_cost, 4),
            "total_loot": round(self.total_loot, 4),
            "total_shots": self.total_shots,
            "total_crits": self.total_crits,
            "total_target_avoids": self.total_target_avoids,
        }
        # Derived rates
        if self.total_shots > 0:
            result["crit_rate"] = round(self.total_crits / self.total_shots, 4)
            result["hit_rate"] = round(
                self.total_shots / (self.total_shots + self.total_target_avoids), 4
            )
        else:
            result["crit_rate"] = 0
            result["hit_rate"] = 0

        efficiency = self.efficiency_metrics()
        if efficiency:
            result["efficiency"] = efficiency

        return result


class SessionRunningStats:
    """Manages per-mob running stats for a session.

    Updated incrementally on each encounter finalization.
    Replaces the need to iterate session.encounters for aggregation.
    """

    def __init__(self, expected_dpp: float | None = None):
        self._mob_stats: dict[str, MobRunningStats] = {}
        self._expected_dpp = expected_dpp

    def set_expected_dpp(self, dpp: float | None):
        """Update expected DPP from loadout evaluation."""
        self._expected_dpp = dpp
        # Update existing mob stats entries
        for stats in self._mob_stats.values():
            stats.expected_dpp = dpp

    def on_encounter_finalized(self, enc: MobEncounter):
        """Update per-mob stats with a finalized encounter."""
        mob_key = enc.mob_name
        if mob_key not in self._mob_stats:
            self._mob_stats[mob_key] = MobRunningStats(
                mob_name=enc.mob_name,
                mob_id=getattr(enc, 'mob_id', None),
                expected_dpp=self._expected_dpp,
            )
        self._mob_stats[mob_key].on_encounter_finalized(enc)

    def get_mob_stats(self, mob_name: str) -> MobRunningStats | None:
        return self._mob_stats.get(mob_name)

    def get_all_mob_stats(self) -> dict[str, MobRunningStats]:
        return dict(self._mob_stats)

    def to_dict(self) -> dict:
        return {
            name: stats.to_dict()
            for name, stats in self._mob_stats.items()
        }
