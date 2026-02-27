"""Loadout calculator — Python facade over the JS bridge.

Delegates to evaluateLoadout() in loadoutEvaluator.js for full effects
processing (gear effects, consumables, bonus properties, and capping).
"""

from .js_bridge import LoadoutJSBridge
from .models import LoadoutStats

from ..core.logger import get_logger

log = get_logger("LoadoutCalc")


class LoadoutCalculator:
    """Evaluates loadouts using the JS bridge for calculations."""

    def __init__(self, js_path: str | None = None):
        self._bridge = LoadoutJSBridge(js_path)

    def evaluate(self, loadout: dict, entities: dict) -> LoadoutStats:
        """Evaluate a loadout and return computed stats.

        Calls evaluateLoadout() which properly processes all gear effects,
        consumable effects, and bonus properties (damage, crit chance,
        crit damage, reload) with proper capping.

        Args:
            loadout: Loadout data dict (website format)
            entities: Dict of entity lists from DataClient:
                      {weapons, amplifiers, scopes_sights, absorbers,
                       implants, armors, armor_platings, armor_sets,
                       clothing, pets, stimulants, medical_tools, effects}
        """
        scopes_sights = entities.get("scopes_sights", [])
        amplifiers = entities.get("amplifiers", [])

        # Build context dict matching evaluateLoadout's expected keys
        context = {
            "weapons": entities.get("weapons", []),
            "amplifiers": amplifiers,
            "scopes": scopes_sights,
            "sights": scopes_sights,
            "absorbers": entities.get("absorbers", []),
            "matrices": amplifiers,
            "implants": entities.get("implants", []),
            "armors": entities.get("armors", []),
            "armorPlatings": entities.get("armor_platings", []),
            "armorSets": entities.get("armor_sets", []),
            "clothing": entities.get("clothing", []),
            "pets": entities.get("pets", []),
            "stimulants": entities.get("stimulants", []),
            "medicalTools": entities.get("medical_tools", []),
        }

        # Build options with effects catalog for proper effect capping
        effects_catalog = entities.get("effects", [])
        effect_caps = {}
        if effects_catalog:
            effect_caps = self._bridge.call(
                "buildEffectCaps", effects_catalog
            ) or {}

        options = {
            "effectsCatalog": effects_catalog,
            "effectCaps": effect_caps,
        }

        result = self._bridge.call("evaluateLoadout", loadout, context, options)

        if not result or not isinstance(result, dict):
            log.warning("evaluateLoadout returned empty result")
            return LoadoutStats()

        js_stats = result.get("stats") or {}

        stats = LoadoutStats()

        # Offensive
        stats.total_damage = js_stats.get("totalDamage") or 0
        stats.effective_damage = js_stats.get("effectiveDamage") or 0

        interval = js_stats.get("damageInterval")
        if isinstance(interval, dict):
            stats.damage_interval_min = interval.get("min", 0) or 0
            stats.damage_interval_max = interval.get("max", 0) or 0

        stats.hit_ability = js_stats.get("hitAbility") or 0
        stats.crit_ability = js_stats.get("critAbility") or 0
        stats.crit_chance = js_stats.get("critChance") or 0
        stats.crit_damage = js_stats.get("critDamage") or 1.0
        stats.range = js_stats.get("range") or 0
        stats.reload = js_stats.get("reload") or 0
        stats.dps = js_stats.get("dps") or 0
        stats.dpp = js_stats.get("dpp") or 0

        # Economy
        stats.decay = js_stats.get("decay") or 0
        stats.ammo_burn = js_stats.get("ammo") or 0
        stats.cost = js_stats.get("cost") or 0
        stats.efficiency = js_stats.get("efficiency") or 0
        stats.weapon_cost = js_stats.get("weaponCost") or 0
        stats.lowest_total_uses = js_stats.get("lowestTotalUses") or 0

        # Defense
        stats.armor_defense = js_stats.get("armorDefense") or 0
        stats.plate_defense = js_stats.get("plateDefense") or 0
        stats.total_defense = js_stats.get("totalDefense") or 0
        stats.top_defense_types = js_stats.get("topDefenseTypesShort") or ""
        stats.total_absorption = js_stats.get("totalAbsorption") or 0
        stats.block_chance = js_stats.get("blockChance") or 0

        # Healing
        stats.total_heal = js_stats.get("totalHeal") or 0
        stats.effective_heal = js_stats.get("effectiveHeal") or 0
        stats.hps = js_stats.get("hps") or 0
        stats.hpp = js_stats.get("hpp") or 0
        stats.heal_reload = js_stats.get("healReload") or 0
        stats.heal_total_uses = js_stats.get("healTotalUses") or 0

        return stats
