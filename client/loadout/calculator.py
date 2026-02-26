"""Loadout calculator — Python facade over the JS bridge."""

from .js_bridge import LoadoutJSBridge
from .models import LoadoutStats

ARMOR_SLOTS = ["Head", "Torso", "Arms", "Hands", "Legs", "Shins", "Feet"]


def _find_by_name(items: list[dict], name: str | None) -> dict | None:
    """Find an entity by its Name field, matching the website's findByName()."""
    if not name or not items:
        return None
    for item in items:
        if item.get("Name") == name:
            return item
    return None


def _resolve_armor_pieces(
    armor_data: dict, armors: list[dict], armor_platings: list[dict],
) -> tuple[list, list]:
    """Resolve armor and plate pieces per slot.

    When ManageIndividual is false the client stores only SetName / PlateName.
    We look up individual armors whose Set.Name matches the set name,
    mapping them to their slot, mirroring the website behaviour.
    """
    manage_individual = armor_data.get("ManageIndividual", False)

    if manage_individual:
        pieces = [
            _find_by_name(armors, (armor_data.get(slot) or {}).get("Name"))
            for slot in ARMOR_SLOTS
        ]
        plates = [
            _find_by_name(armor_platings, ((armor_data.get(slot) or {}).get("Plate") or {}).get("Name"))
            for slot in ARMOR_SLOTS
        ]
        return pieces, plates

    # Set mode — resolve from set names
    set_name = armor_data.get("SetName")
    plate_name = armor_data.get("PlateName")

    # Build slot → armor from all armors belonging to this set
    slot_map: dict[str, dict] = {}
    if set_name:
        for a in armors:
            if (a.get("Set") or {}).get("Name") == set_name:
                slot = (a.get("Properties") or {}).get("Slot")
                if slot and slot not in slot_map:
                    slot_map[slot] = a

    # Plates have no set/slot — one plate entity covers all slots
    plate_entity = _find_by_name(armor_platings, plate_name) if plate_name else None

    pieces = [slot_map.get(slot) for slot in ARMOR_SLOTS]
    plates = [plate_entity] * len(ARMOR_SLOTS) if plate_entity else [None] * len(ARMOR_SLOTS)
    return pieces, plates


class LoadoutCalculator:
    """Evaluates loadouts using the JS bridge for calculations."""

    def __init__(self, js_path: str | None = None):
        self._bridge = LoadoutJSBridge(js_path)

    def evaluate(self, loadout: dict, entities: dict) -> LoadoutStats:
        """Evaluate a loadout and return computed stats.

        Args:
            loadout: Loadout data dict (website format)
            entities: Dict of entity lists from DataClient:
                      {weapons, amplifiers, scopes_sights, absorbers, ...}
        """
        gear = loadout.get("Gear", {})
        weapon_data = gear.get("Weapon", {})
        armor_data = gear.get("Armor", {})
        healing_data = gear.get("Healing", {})
        skill = loadout.get("Skill", {})
        markup = loadout.get("Markup", {})

        # Resolve weapon entities
        weapon = _find_by_name(entities.get("weapons", []), weapon_data.get("Name"))
        amplifier = _find_by_name(entities.get("amplifiers", []), weapon_data.get("Amplifier", {}).get("Name"))

        scopes_sights = entities.get("scopes_sights", [])
        scope = _find_by_name(scopes_sights, weapon_data.get("Scope", {}).get("Name"))
        scope_sight = _find_by_name(scopes_sights, (weapon_data.get("Scope", {}).get("Sight") or {}).get("Name"))
        sight = _find_by_name(scopes_sights, weapon_data.get("Sight", {}).get("Name"))
        matrix = _find_by_name(entities.get("amplifiers", []), weapon_data.get("Matrix", {}).get("Name"))

        absorber = _find_by_name(entities.get("absorbers", []), weapon_data.get("Absorber", {}).get("Name"))
        implant = _find_by_name(entities.get("implants", []), weapon_data.get("Implant", {}).get("Name"))
        heal_tool = _find_by_name(entities.get("medical_tools", []), healing_data.get("Name"))

        enhancers = weapon_data.get("Enhancers", {})
        dmg_enh = enhancers.get("Damage", 0)
        eco_enh = enhancers.get("Economy", 0)
        acc_enh = enhancers.get("Accuracy", 0)
        rng_enh = enhancers.get("Range", 0)
        sm_enh = enhancers.get("SkillMod", 0)

        armor_enh = armor_data.get("Enhancers", {})
        def_enh = armor_enh.get("Defense", 0)
        dur_enh = armor_enh.get("Durability", 0)
        heal_enh = healing_data.get("Enhancers", {})

        stats = LoadoutStats()

        hit_skill = skill.get("Hit", 200)
        dmg_skill = skill.get("Dmg", 200)
        heal_skill = skill.get("Heal", 200)

        # ---- Offensive ----
        if weapon:
            stats.total_damage = self._bridge.call(
                "calculateTotalDamage", weapon, dmg_enh, 0, amplifier
            ) or 0

            interval = self._bridge.call(
                "calculateDamageInterval", weapon, dmg_skill, sm_enh, stats.total_damage
            )
            if interval:
                stats.damage_interval_min = interval.get("min", 0)
                stats.damage_interval_max = interval.get("max", 0)

            stats.hit_ability = self._bridge.call(
                "calculateHitAbility", weapon, hit_skill, sm_enh
            ) or 0
            stats.crit_ability = self._bridge.call(
                "calculateCritAbility", weapon, hit_skill, sm_enh
            ) or 0
            stats.crit_chance = self._bridge.call(
                "calculateCritChance", stats.crit_ability, acc_enh, 0
            ) or 0
            stats.crit_damage = self._bridge.call(
                "calculateCritDamage", 0
            ) or 1.0
            stats.effective_damage = self._bridge.call(
                "calculateEffectiveDamage",
                {"min": stats.damage_interval_min, "max": stats.damage_interval_max},
                stats.crit_chance, stats.crit_damage, stats.hit_ability
            ) or 0
            stats.range = self._bridge.call(
                "calculateRange", weapon, hit_skill, sm_enh, rng_enh
            ) or 0
            stats.reload = self._bridge.call(
                "calculateReload", weapon, hit_skill, sm_enh, 0
            ) or 0

            if stats.reload > 0:
                stats.dps = self._bridge.call(
                    "calculateDPS", stats.effective_damage, stats.reload
                ) or 0

            # ---- Economy ----
            stats.decay = self._bridge.call(
                "calculateDecay", weapon, dmg_enh, eco_enh,
                absorber, implant, amplifier,
                scope, scope_sight, sight, matrix, markup
            ) or 0
            stats.ammo_burn = self._bridge.call(
                "calculateAmmoBurn", weapon, dmg_enh, eco_enh, amplifier
            ) or 0
            stats.cost = self._bridge.call(
                "calculateCost", stats.decay, stats.ammo_burn, markup.get("Ammo", 100)
            ) or 0

            if stats.cost > 0:
                stats.dpp = self._bridge.call(
                    "calculateDPP", stats.effective_damage, stats.cost
                ) or 0

            stats.weapon_cost = self._bridge.call(
                "calculateWeaponCost", weapon, dmg_enh, eco_enh
            ) or 0

            stats.efficiency = self._bridge.call(
                "calculateEfficiency", weapon, stats.weapon_cost,
                dmg_enh, eco_enh, absorber, amplifier,
                scope, scope_sight, sight, matrix
            ) or 0

            stats.lowest_total_uses = self._bridge.call(
                "calculateLowestTotalUses", weapon, dmg_enh, eco_enh,
                absorber, implant, amplifier,
                scope, scope_sight, sight, matrix
            ) or 0

        # ---- Defense ----
        armors = entities.get("armors", [])
        armor_platings = entities.get("armor_platings", [])
        armor_pieces, plate_pieces = _resolve_armor_pieces(
            armor_data, armors, armor_platings,
        )

        stats.armor_defense = self._bridge.call(
            "calculateArmorDefense", armor_pieces, def_enh
        ) or 0
        stats.plate_defense = self._bridge.call(
            "calculatePlateDefense", plate_pieces
        ) or 0
        stats.total_defense = self._bridge.call(
            "calculateTotalDefense", stats.armor_defense, stats.plate_defense
        ) or 0

        # Top defense types
        armor_def_by_type = self._bridge.call(
            "calculateArmorDefenseByType", armor_pieces, def_enh
        ) or {}
        plate_def_by_type = self._bridge.call(
            "calculatePlateDefenseByType", plate_pieces
        ) or {}
        total_def_by_type = self._bridge.call(
            "calculateTotalDefenseByType", armor_def_by_type, plate_def_by_type
        ) or {}
        stats.top_defense_types = self._bridge.call(
            "formatTopDefenseTypesShort", total_def_by_type, 3
        ) or ""

        stats.total_absorption = self._bridge.call(
            "calculateTotalAbsorption", armor_pieces, plate_pieces, def_enh, dur_enh
        ) or 0
        stats.block_chance = self._bridge.call(
            "calculateBlockChance", plate_pieces
        ) or 0

        # ---- Healing ----
        if heal_tool:
            heal_heal_enh = heal_enh.get("Heal", 0)
            heal_eco_enh = heal_enh.get("Economy", 0)
            heal_sm_enh = heal_enh.get("SkillMod", 0)

            stats.total_heal = self._bridge.call(
                "calculateTotalHeal", heal_tool, heal_heal_enh
            ) or 0

            heal_interval = self._bridge.call(
                "calculateHealInterval", heal_tool, heal_skill, heal_sm_enh, heal_heal_enh
            )
            if heal_interval:
                stats.effective_heal = self._bridge.call(
                    "calculateEffectiveHeal", heal_interval
                ) or 0

            stats.heal_reload = self._bridge.call(
                "calculateHealReload", heal_tool, heal_skill, heal_sm_enh
            ) or 0

            if stats.heal_reload > 0:
                stats.hps = self._bridge.call(
                    "calculateHPS", stats.effective_heal, stats.heal_reload
                ) or 0

            heal_decay = self._bridge.call(
                "calculateHealDecay", heal_tool, heal_heal_enh, heal_eco_enh,
                markup.get("HealingTool", 100),
            )
            if heal_decay and stats.effective_heal:
                stats.hpp = self._bridge.call(
                    "calculateHPP", stats.effective_heal, heal_decay
                ) or 0

            stats.heal_total_uses = self._bridge.call(
                "calculateHealTotalUses", heal_tool, heal_heal_enh, heal_eco_enh
            ) or 0

        return stats
