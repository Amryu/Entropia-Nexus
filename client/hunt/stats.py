"""Hunt session statistics aggregation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .running_stats import SessionRunningStats
from .session import HuntSession, Hunt, MobEncounter

if TYPE_CHECKING:
    from .markup_resolver import MarkupResolver


def aggregate_by_mob(session: HuntSession) -> dict[str, dict]:
    """Aggregate encounter stats grouped by mob name.

    Returns: {mob_name: {kills, damage_dealt, damage_taken, loot, avg_damage, ...}}
    """
    mobs: dict[str, dict] = {}

    for enc in session.encounters:
        if enc.mob_name not in mobs:
            mobs[enc.mob_name] = {
                "kills": 0,
                "damage_dealt": 0.0,
                "damage_taken": 0.0,
                "heals_received": 0.0,
                "loot_total": 0.0,
                "shots_fired": 0,
                "critical_hits": 0,
                "target_avoids": 0,
            }

        stats = mobs[enc.mob_name]
        stats["kills"] += 1
        stats["damage_dealt"] += enc.damage_dealt
        stats["damage_taken"] += enc.damage_taken
        stats["heals_received"] += enc.heals_received
        stats["loot_total"] += enc.loot_total_ped
        stats["shots_fired"] += enc.shots_fired
        stats["critical_hits"] += enc.critical_hits
        stats["target_avoids"] += enc.target_avoids

    # Calculate averages
    for mob_name, stats in mobs.items():
        kills = stats["kills"]
        if kills > 0:
            stats["avg_damage_per_kill"] = stats["damage_dealt"] / kills
            stats["avg_loot_per_kill"] = stats["loot_total"] / kills
        else:
            stats["avg_damage_per_kill"] = 0
            stats["avg_loot_per_kill"] = 0

        shots = stats["shots_fired"]
        if shots > 0:
            stats["crit_rate"] = stats["critical_hits"] / shots
            stats["hit_rate"] = shots / (shots + stats["target_avoids"])
        else:
            stats["crit_rate"] = 0
            stats["hit_rate"] = 0

    return mobs


def aggregate_by_tool(
    source: HuntSession | list[MobEncounter],
) -> dict[str, dict]:
    """Aggregate stats grouped by tool name.

    Accepts a HuntSession (session scope) or a list of MobEncounter
    (hunt scope, filtered scope). Returns:
    {tool_name: {shots, damage, crits, encounters_used}}
    """
    if isinstance(source, HuntSession):
        encounters = source.encounters
    else:
        encounters = source

    tools: dict[str, dict] = {}

    for enc in encounters:
        for tool_name, ts in enc.tool_stats.items():
            if tool_name not in tools:
                tools[tool_name] = {
                    "shots_fired": 0,
                    "damage_dealt": 0.0,
                    "critical_hits": 0,
                    "encounters_used": 0,
                }
            tools[tool_name]["shots_fired"] += ts.shots_fired
            tools[tool_name]["damage_dealt"] += ts.damage_dealt
            tools[tool_name]["critical_hits"] += ts.critical_hits
            tools[tool_name]["encounters_used"] += 1

    # Calculate averages
    for stats in tools.values():
        shots = stats["shots_fired"]
        if shots > 0:
            stats["avg_damage_per_shot"] = stats["damage_dealt"] / shots
            stats["crit_rate"] = stats["critical_hits"] / shots
        else:
            stats["avg_damage_per_shot"] = 0
            stats["crit_rate"] = 0

    return tools


def aggregate_loot(encounters: list[MobEncounter],
                   markup_resolver: MarkupResolver | None = None) -> list[dict]:
    """Aggregate loot items across encounters, grouped by item name.

    Returns list of dicts sorted by TT value descending:
    [{
        "item_name": str,
        "total_quantity": int,
        "tt_value": float,
        "mu_value": float,
        "markup_source": str,     # "custom", "inventory", "ingame", "exchange", "default"
        "is_custom": bool,
    }]

    Excludes blacklisted and refining output items.
    """
    # Accumulate by item name
    items: dict[str, dict] = {}

    for enc in encounters:
        for li in enc.loot_items:
            if li.is_blacklisted or li.is_refining_output:
                continue
            name = li.item_name
            if name not in items:
                items[name] = {
                    "item_name": name,
                    "total_quantity": 0,
                    "tt_value": 0.0,
                }
            items[name]["total_quantity"] += li.quantity
            items[name]["tt_value"] += li.value_ped

    # Compute MU values
    result = []
    for entry in items.values():
        if markup_resolver:
            mu_value, source = markup_resolver.compute_mu_value(
                entry["item_name"], entry["tt_value"]
            )
        else:
            mu_value = entry["tt_value"]
            source = "default"

        entry["mu_value"] = mu_value
        entry["markup_source"] = source
        entry["is_custom"] = source == "custom"
        result.append(entry)

    # Sort by TT value descending
    result.sort(key=lambda x: x["tt_value"], reverse=True)
    return result


def aggregate_loot_for_hunt(hunt: Hunt,
                            markup_resolver: MarkupResolver | None = None) -> list[dict]:
    """Aggregate loot items across all encounters in a hunt."""
    return aggregate_loot(hunt.encounters, markup_resolver)


def aggregate_loot_for_session(session: HuntSession,
                               markup_resolver: MarkupResolver | None = None) -> list[dict]:
    """Aggregate loot items across all encounters in a session."""
    return aggregate_loot(session.encounters, markup_resolver)


def session_economy(session: HuntSession, cost_per_use: float = 0) -> dict:
    """Calculate session economy stats.

    Args:
        cost_per_use: Total cost per shot (from loadout calculator), in PED.
    """
    total_shots = sum(e.shots_fired for e in session.encounters)
    total_cost = total_shots * cost_per_use
    total_loot = session.total_loot

    return {
        "total_shots": total_shots,
        "total_cost": total_cost,
        "total_loot": total_loot,
        "profit_loss": total_loot - total_cost,
        "return_pct": (total_loot / total_cost * 100) if total_cost > 0 else 0,
        "cost_per_kill": total_cost / session.kill_count if session.kill_count > 0 else 0,
        "loot_per_kill": total_loot / session.kill_count if session.kill_count > 0 else 0,
    }


def mob_efficiency_report(session_stats: SessionRunningStats) -> list[dict]:
    """Per-mob efficiency report with min/max/avg and DPP comparison.

    Returns list of dicts sorted by kill count descending.
    """
    result = []
    for mob_name, stats in session_stats.get_all_mob_stats().items():
        entry = stats.to_dict()
        result.append(entry)
    result.sort(key=lambda x: x["kill_count"], reverse=True)
    return result


def encounters_economy(encounters: list[MobEncounter]) -> dict:
    """Economy summary computed directly from an encounter list.

    Mirrors the shape of session_economy_from_stats but operates on an
    arbitrary slice of encounters (used for hunt-scope dashboard stats
    where there is no dedicated SessionRunningStats to read from).
    """
    total_shots = 0
    total_cost = 0.0
    total_loot = 0.0
    total_kills = 0
    total_deaths = 0
    kill_cost_sum = 0.0
    for enc in encounters:
        total_shots += enc.shots_fired
        total_cost += enc.cost
        total_loot += enc.loot_total_ped
        if enc.outcome == "kill":
            total_kills += 1
            kill_cost_sum += enc.cost
        if enc.death_count:
            total_deaths += enc.death_count
    return {
        "total_shots": total_shots,
        "total_cost": round(total_cost, 4),
        "total_loot": round(total_loot, 4),
        "total_kills": total_kills,
        "total_deaths": total_deaths,
        "profit_loss": round(total_loot - total_cost, 4),
        "return_pct": round((total_loot / total_cost * 100), 2) if total_cost > 0 else 0,
        "cost_per_kill": round(kill_cost_sum / total_kills, 4) if total_kills > 0 else 0,
        "loot_per_kill": round(total_loot / total_kills, 4) if total_kills > 0 else 0,
    }


def mu_consumed(
    encounters: list[MobEncounter],
    markup_resolver: "MarkupResolver | None" = None,
    gear_overrides: dict | None = None,
) -> float | None:
    """Total markup consumed (ammo MU + (L) decay above TT) for *encounters*.

    Phase 1 returns None so the dashboard shows a placeholder. Phase 2
    wires in gear overrides and per-ammo MU resolution; until then the
    value cannot be computed accurately, so we refuse to guess.
    """
    return None


def session_economy_from_stats(session_stats: SessionRunningStats) -> dict:
    """Session economy using running stats (no encounter iteration)."""
    all_stats = session_stats.get_all_mob_stats()

    total_shots = sum(s.total_shots for s in all_stats.values())
    total_cost = sum(s.total_cost for s in all_stats.values())
    total_loot = sum(s.total_loot for s in all_stats.values())
    total_kills = sum(s.kill_count for s in all_stats.values())
    total_deaths = sum(s.death_count for s in all_stats.values())

    return {
        "total_shots": total_shots,
        "total_cost": round(total_cost, 4),
        "total_loot": round(total_loot, 4),
        "total_kills": total_kills,
        "total_deaths": total_deaths,
        "profit_loss": round(total_loot - total_cost, 4),
        "return_pct": round((total_loot / total_cost * 100), 2) if total_cost > 0 else 0,
        "cost_per_kill": round(total_cost / total_kills, 4) if total_kills > 0 else 0,
        "loot_per_kill": round(total_loot / total_kills, 4) if total_kills > 0 else 0,
    }
