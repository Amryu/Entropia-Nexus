"""Hunt session statistics aggregation."""

from .session import HuntSession, MobEncounter


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


def aggregate_by_tool(session: HuntSession) -> dict[str, dict]:
    """Aggregate stats grouped by tool name.

    Returns: {tool_name: {shots, damage, crits, encounters_used}}
    """
    tools: dict[str, dict] = {}

    for enc in session.encounters:
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
