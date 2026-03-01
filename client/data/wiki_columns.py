"""Column definitions for wiki entity tables.

Ported from individual wiki page column defs on the website — keep in sync.
"""

from __future__ import annotations

import math


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def deep_get(obj: dict, *keys, default=None):
    """Safe nested dict access — equivalent to JS optional chaining."""
    for k in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(k)
        if obj is None:
            return default
    return obj


# --- Format helpers ---

def fmt(decimals: int):
    return lambda v: f"{v:.{decimals}f}" if v is not None else "-"

def fmt_int(v):
    return str(v) if v is not None else "-"

def fmt_str(v):
    return v or "-"

def fmt_bool(v):
    if v is True or v == 1:
        return "Yes"
    if v is False or v == 0:
        return "No"
    return "-"

def fmt_trim(max_decimals: int):
    def _format(v):
        if v is None:
            return "-"
        if v == 0:
            return "0"
        s = f"{v:.{max_decimals}f}".rstrip("0").rstrip(".")
        return s or "0"
    return _format

def _fmt_cooldown(v):
    return f"{v}s" if v is not None else "-"

def _fmt_exportable(v):
    if v is not None and v > 0:
        return f"Lvl {v}"
    return "No"

def _fmt_nutrio(v):
    if v is None:
        return "-"
    return f"{v / 100:.2f} PED"

def _fmt_percent(v):
    if v is None:
        return "-"
    return f"{v * 100:.0f}%"

def _fmt_zoom(v):
    if v is None:
        return "-"
    return f"{v:.1f}x"

def _fmt_skill_pct(v):
    if v is None:
        return "-"
    return f"{v}%"


# ---------------------------------------------------------------------------
# Weapon calculation helpers
# ---------------------------------------------------------------------------

_DAMAGE_TYPES = ("Impact", "Cut", "Stab", "Penetration", "Shrapnel",
                 "Burn", "Cold", "Acid", "Electric")

def weapon_total_damage(item: dict):
    d = deep_get(item, "Properties", "Damage")
    if not d:
        return None
    return sum(d.get(t) or 0 for t in _DAMAGE_TYPES)

def weapon_effective_damage(item: dict):
    total = weapon_total_damage(item)
    if total is None or total == 0:
        return None
    return total * (0.88 * 0.75 + 0.02 * 1.75)

def weapon_reload(item: dict):
    upm = deep_get(item, "Properties", "UsesPerMinute")
    if not upm:
        return None
    return 60 / upm

def weapon_cost_per_use(item: dict):
    decay = deep_get(item, "Properties", "Economy", "Decay")
    if decay is None:
        return None
    ammo_burn = deep_get(item, "Properties", "Economy", "AmmoBurn", default=0)
    return decay + (ammo_burn / 100)

def weapon_dps(item: dict):
    reload = weapon_reload(item)
    eff = weapon_effective_damage(item)
    if eff is None or reload is None:
        return None
    return eff / reload

def weapon_dpp(item: dict):
    cost = weapon_cost_per_use(item)
    eff = weapon_effective_damage(item)
    if cost is None or cost == 0 or eff is None:
        return None
    return eff / cost

def weapon_total_uses(item: dict):
    max_tt = deep_get(item, "Properties", "Economy", "MaxTT")
    min_tt = deep_get(item, "Properties", "Economy", "MinTT", default=0)
    decay = deep_get(item, "Properties", "Economy", "Decay")
    if max_tt is None or decay is None or decay == 0:
        return None
    return math.floor((max_tt - min_tt) / (decay / 100))


# ---------------------------------------------------------------------------
# Armor calculation helpers
# ---------------------------------------------------------------------------

def armor_total_defense(item: dict):
    d = deep_get(item, "Properties", "Defense")
    if not d:
        return None
    return sum(d.get(t) or 0 for t in _DAMAGE_TYPES)

def _armor_total_absorption(item: dict):
    total_def = armor_total_defense(item)
    max_tt = deep_get(item, "Properties", "Economy", "MaxTT")
    min_tt = deep_get(item, "Properties", "Economy", "MinTT", default=0)
    decay = deep_get(item, "Properties", "Economy", "Decay")
    if total_def is None or max_tt is None or decay is None or decay == 0:
        return None
    return total_def * ((max_tt - min_tt) / (decay / 100))


# ---------------------------------------------------------------------------
# Mob calculation helpers
# ---------------------------------------------------------------------------

def mob_level_max(item: dict):
    mats = item.get("Maturities") if isinstance(item, dict) else None
    if not isinstance(mats, list) or not mats:
        return None
    levels = [deep_get(m, "Properties", "Level") for m in mats]
    levels = [l for l in levels if l is not None]
    return max(levels) if levels else None

def mob_health_max(item: dict):
    mats = item.get("Maturities") if isinstance(item, dict) else None
    if not isinstance(mats, list) or not mats:
        return None
    values = [deep_get(m, "Properties", "Health") for m in mats]
    values = [h for h in values if h is not None]
    return max(values) if values else None

def mob_smallest_hp_per_level(item: dict):
    mats = item.get("Maturities") if isinstance(item, dict) else None
    if not isinstance(mats, list) or not mats:
        return None
    best = None
    for m in mats:
        health = deep_get(m, "Properties", "Health")
        level = deep_get(m, "Properties", "Level")
        if health is not None and level is not None and level > 0:
            ratio = health / level
            if best is None or ratio < best:
                best = ratio
    return best

def _mob_damage_max(item: dict):
    """Max total damage across all maturities."""
    mats = item.get("Maturities") if isinstance(item, dict) else None
    if not isinstance(mats, list) or not mats:
        return None
    best = None
    for m in mats:
        d = deep_get(m, "Properties", "Damage")
        if d:
            total = sum(d.get(t) or 0 for t in _DAMAGE_TYPES)
            if total > 0 and (best is None or total > best):
                best = total
    return best

def _is_cat4_mob(item: dict):
    return 1 if deep_get(item, "Species", "Properties", "CodexType") == "MobLooter" else 0


# ---------------------------------------------------------------------------
# Skill level helpers (shared by weapons, tools, medical)
# ---------------------------------------------------------------------------

def _get_min_level(item: dict):
    skill = deep_get(item, "Properties", "Skill")
    if not skill:
        return None
    hit = deep_get(skill, "Hit", "LearningIntervalStart")
    dmg = deep_get(skill, "Dmg", "LearningIntervalStart")
    if hit is not None and dmg is not None:
        return max(hit, dmg)
    return hit if hit is not None else dmg

def _get_max_level(item: dict):
    skill = deep_get(item, "Properties", "Skill")
    if not skill:
        return None
    hit = deep_get(skill, "Hit", "LearningIntervalEnd")
    dmg = deep_get(skill, "Dmg", "LearningIntervalEnd")
    if hit is not None and dmg is not None:
        return max(hit, dmg)
    return hit if hit is not None else dmg


# ---------------------------------------------------------------------------
# Medical tool helpers
# ---------------------------------------------------------------------------

def _medical_effective_healing(item: dict):
    max_heal = deep_get(item, "Properties", "MaxHeal")
    min_heal = deep_get(item, "Properties", "MinHeal")
    if max_heal is None or min_heal is None:
        return None
    return (max_heal + min_heal) / 2

def _medical_hps(item: dict):
    reload = weapon_reload(item)  # Same formula: 60 / UsesPerMinute
    eff_heal = _medical_effective_healing(item)
    if reload is None or eff_heal is None:
        return None
    return eff_heal / reload

def _medical_hpp(item: dict):
    cost = weapon_cost_per_use(item)  # Same formula: Decay + AmmoBurn/100
    eff_heal = _medical_effective_healing(item)
    if cost is None or cost == 0 or eff_heal is None:
        return None
    return eff_heal / cost


# ---------------------------------------------------------------------------
# Blueprint helpers
# ---------------------------------------------------------------------------

def _blueprint_cost(item: dict):
    materials = item.get("Materials")
    if not materials:
        return None
    total = 0.0
    for mat in materials:
        mat_tt = deep_get(mat, "Item", "Properties", "Economy", "MaxTT", default=0)
        amount = mat.get("Amount") or 0
        total += mat_tt * amount
    return total if total > 0 else None

def _has_item_tag(name: str | None, tag: str) -> bool:
    return f"({tag})" in (name or "")


# ---------------------------------------------------------------------------
# Excavator helpers
# ---------------------------------------------------------------------------

def _excavator_eff_per_ped(item: dict):
    eff = deep_get(item, "Properties", "Efficiency")
    decay = deep_get(item, "Properties", "Economy", "Decay")
    if eff is None or decay is None or decay == 0:
        return None
    return eff / (decay / 100)


# ---------------------------------------------------------------------------
# Column definitions per entity type
# ---------------------------------------------------------------------------
# Keyed by pageTypeId.
# Each column: { key, header, get_value: callable(item)->value, format: callable(value)->str }

COLUMN_DEFS: dict[str, dict[str, dict]] = {
    "weapons": {
        "class":        {"key": "class",        "header": "Class",    "get_value": lambda i: deep_get(i, "Properties", "Class"), "format": fmt_str},
        "type":         {"key": "type",         "header": "Type",     "get_value": lambda i: deep_get(i, "Properties", "Type"), "format": fmt_str},
        "dps":          {"key": "dps",          "header": "DPS",      "get_value": weapon_dps, "format": fmt(1)},
        "dpp":          {"key": "dpp",          "header": "DPP",      "get_value": weapon_dpp, "format": fmt(2)},
        "eff":          {"key": "eff",          "header": "Eff.",     "get_value": lambda i: deep_get(i, "Properties", "Economy", "Efficiency"), "format": fmt(1)},
        "costPerUse":   {"key": "costPerUse",   "header": "Cost/Use", "get_value": weapon_cost_per_use, "format": fmt(4)},
        "maxtt":        {"key": "maxtt",        "header": "Max TT",   "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "effectiveDmg": {"key": "effectiveDmg", "header": "Eff Dmg",  "get_value": weapon_effective_damage, "format": fmt(1)},
        "damage":       {"key": "damage",       "header": "Damage",   "get_value": weapon_total_damage, "format": fmt(1)},
        "range":        {"key": "range",        "header": "Range",    "get_value": lambda i: deep_get(i, "Properties", "Range"), "format": fmt_int},
        "upm":          {"key": "upm",          "header": "UPM",      "get_value": lambda i: deep_get(i, "Properties", "UsesPerMinute"), "format": fmt_int},
        "sib":          {"key": "sib",          "header": "SiB",      "get_value": lambda i: deep_get(i, "Properties", "Skill", "IsSiB"), "format": fmt_bool},
        "minLevel":     {"key": "minLevel",     "header": "Min Lv",   "get_value": _get_min_level, "format": fmt_int},
        "maxLevel":     {"key": "maxLevel",     "header": "Max Lv",   "get_value": _get_max_level, "format": fmt_int},
        "cooldown":     {"key": "cooldown",     "header": "CD",       "get_value": lambda i: deep_get(i, "Properties", "Mindforce", "Cooldown"), "format": _fmt_cooldown},
        "cooldownGroup": {"key": "cooldownGroup", "header": "CD Grp", "get_value": lambda i: deep_get(i, "Properties", "Mindforce", "CooldownGroup"), "format": fmt_str},
        "decay":        {"key": "decay",        "header": "Decay",    "get_value": lambda i: deep_get(i, "Properties", "Economy", "Decay"), "format": fmt(2)},
        "ammo":         {"key": "ammo",         "header": "Ammo",     "get_value": lambda i: deep_get(i, "Properties", "Economy", "AmmoBurn"), "format": fmt_int},
        "uses":         {"key": "uses",         "header": "Uses",     "get_value": weapon_total_uses, "format": fmt_int},
        "weight":       {"key": "weight",       "header": "Weight",   "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
        "mintt":        {"key": "mintt",        "header": "Min TT",   "get_value": lambda i: deep_get(i, "Properties", "Economy", "MinTT"), "format": fmt(2)},
        "category":     {"key": "category",     "header": "Category", "get_value": lambda i: deep_get(i, "Properties", "Category"), "format": fmt_str},
    },

    "materials": {
        "type":   {"key": "type",   "header": "Type",   "get_value": lambda i: deep_get(i, "Properties", "Type"), "format": fmt_str},
        "weight": {"key": "weight", "header": "Weight", "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
        "value":  {"key": "value",  "header": "Value",  "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
    },

    "blueprints": {
        "type":       {"key": "type",       "header": "Type",       "get_value": lambda i: deep_get(i, "Properties", "Type"), "format": fmt_str},
        "profession": {"key": "profession", "header": "Profession", "get_value": lambda i: deep_get(i, "Profession", "Name"), "format": fmt_str},
        "level":      {"key": "level",      "header": "Level",      "get_value": lambda i: deep_get(i, "Properties", "Level"), "format": fmt_int},
        "product":    {"key": "product",    "header": "Product",    "get_value": lambda i: deep_get(i, "Product", "Name"), "format": fmt_str},
        "cost":       {"key": "cost",       "header": "Cost",       "get_value": _blueprint_cost, "format": fmt(2)},
        "sib":        {"key": "sib",        "header": "SiB",        "get_value": lambda i: deep_get(i, "Properties", "Skill", "IsSiB"), "format": fmt_bool},
        "limited":    {"key": "limited",    "header": "Ltd",        "get_value": lambda i: _has_item_tag(i.get("Name"), "L"), "format": fmt_bool},
        "book":       {"key": "book",       "header": "Book",       "get_value": lambda i: deep_get(i, "Book", "Name"), "format": fmt_str},
        "boosted":    {"key": "boosted",    "header": "Boosted",    "get_value": lambda i: deep_get(i, "Properties", "IsBoosted"), "format": fmt_bool},
    },

    "armorsets": {
        "defense":     {"key": "defense",     "header": "Def.",   "get_value": armor_total_defense, "format": fmt(1)},
        "durability":  {"key": "durability",  "header": "Dur.",   "get_value": lambda i: deep_get(i, "Properties", "Economy", "Durability"), "format": fmt(1)},
        "impact":      {"key": "impact",      "header": "Imp",    "get_value": lambda i: deep_get(i, "Properties", "Defense", "Impact"), "format": fmt(1)},
        "cut":         {"key": "cut",         "header": "Cut",    "get_value": lambda i: deep_get(i, "Properties", "Defense", "Cut"), "format": fmt(1)},
        "stab":        {"key": "stab",        "header": "Stab",   "get_value": lambda i: deep_get(i, "Properties", "Defense", "Stab"), "format": fmt(1)},
        "penetration": {"key": "penetration", "header": "Pen",    "get_value": lambda i: deep_get(i, "Properties", "Defense", "Penetration"), "format": fmt(1)},
        "shrapnel":    {"key": "shrapnel",    "header": "Shrp",   "get_value": lambda i: deep_get(i, "Properties", "Defense", "Shrapnel"), "format": fmt(1)},
        "burn":        {"key": "burn",        "header": "Burn",   "get_value": lambda i: deep_get(i, "Properties", "Defense", "Burn"), "format": fmt(1)},
        "cold":        {"key": "cold",        "header": "Cold",   "get_value": lambda i: deep_get(i, "Properties", "Defense", "Cold"), "format": fmt(1)},
        "acid":        {"key": "acid",        "header": "Acid",   "get_value": lambda i: deep_get(i, "Properties", "Defense", "Acid"), "format": fmt(1)},
        "electric":    {"key": "electric",    "header": "Elec",   "get_value": lambda i: deep_get(i, "Properties", "Defense", "Electric"), "format": fmt(1)},
        "absorption":  {"key": "absorption",  "header": "Abs",    "get_value": _armor_total_absorption, "format": fmt(1)},
        "maxtt":       {"key": "maxtt",       "header": "Max TT", "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "weight":      {"key": "weight",      "header": "Weight", "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
    },

    "clothing": {
        "slot":    {"key": "slot",    "header": "Slot",    "get_value": lambda i: deep_get(i, "Properties", "Slot"), "format": fmt_str},
        "type":    {"key": "type",    "header": "Type",    "get_value": lambda i: deep_get(i, "Properties", "Type"), "format": fmt_str},
        "effects": {"key": "effects", "header": "Effects", "get_value": lambda i: len(i.get("EffectsOnEquip") or i.get("Effects") or []) + len(deep_get(i, "Set", "EffectsOnSetEquip") or []) > 0, "format": fmt_bool},
        "gender":  {"key": "gender",  "header": "Gender",  "get_value": lambda i: deep_get(i, "Properties", "Gender"), "format": fmt_str},
        "weight":  {"key": "weight",  "header": "Weight",  "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
        "maxTT":   {"key": "maxTT",   "header": "Max TT",  "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "set":     {"key": "set",     "header": "Set",     "get_value": lambda i: deep_get(i, "Set", "Name"), "format": fmt_str},
    },

    "vehicles": {
        "type":       {"key": "type",       "header": "Type",   "get_value": lambda i: deep_get(i, "Properties", "Type"), "format": fmt_str},
        "speed":      {"key": "speed",      "header": "Speed",  "get_value": lambda i: deep_get(i, "Properties", "MaxSpeed"), "format": fmt_int},
        "fuel":       {"key": "fuel",       "header": "Fuel",   "get_value": lambda i: deep_get(i, "Properties", "Economy", "FuelConsumptionActive") or deep_get(i, "Properties", "Economy", "FuelConsumptionPassive"), "format": fmt(2)},
        "passengers": {"key": "passengers", "header": "Seats",  "get_value": lambda i: deep_get(i, "Properties", "PassengerCount"), "format": fmt_int},
        "maxSI":      {"key": "maxSI",      "header": "Max SI", "get_value": lambda i: deep_get(i, "Properties", "MaxStructuralIntegrity"), "format": fmt_int},
        "weight":     {"key": "weight",     "header": "Weight", "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
        "maxTT":      {"key": "maxTT",      "header": "Max TT", "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "durability": {"key": "durability", "header": "Dur.",   "get_value": lambda i: deep_get(i, "Properties", "Economy", "Durability"), "format": fmt_int},
    },

    "pets": {
        "rarity":        {"key": "rarity",        "header": "Rarity",  "get_value": lambda i: deep_get(i, "Properties", "Rarity"), "format": fmt_str},
        "effects":       {"key": "effects",       "header": "Effects", "get_value": lambda i: len(i.get("Effects") or []), "format": fmt_int},
        "planet":        {"key": "planet",        "header": "Planet",  "get_value": lambda i: deep_get(i, "Planet", "Name"), "format": fmt_str},
        "tamingLevel":   {"key": "tamingLevel",   "header": "Taming",  "get_value": lambda i: deep_get(i, "Properties", "TamingLevel"), "format": fmt_int},
        "training":      {"key": "training",      "header": "Training", "get_value": lambda i: deep_get(i, "Properties", "TrainingDifficulty"), "format": fmt_str},
        "exportable":    {"key": "exportable",    "header": "Export",  "get_value": lambda i: deep_get(i, "Properties", "ExportableLevel"), "format": _fmt_exportable},
        "nutrioCapacity": {"key": "nutrioCapacity", "header": "Nutrio", "get_value": lambda i: deep_get(i, "Properties", "NutrioCapacity"), "format": _fmt_nutrio},
    },

    "mobs": {
        "hpPerLevel": {"key": "hpPerLevel", "header": "HP/Lvl",  "get_value": mob_smallest_hp_per_level, "format": fmt(1)},
        "level":      {"key": "level",      "header": "Level",   "get_value": mob_level_max, "format": fmt_int},
        "hp":         {"key": "hp",         "header": "HP",      "get_value": mob_health_max, "format": fmt_int},
        "cat4":       {"key": "cat4",       "header": "Cat 4",   "get_value": _is_cat4_mob, "format": fmt_bool},
        "damage":     {"key": "damage",     "header": "Damage",  "get_value": _mob_damage_max, "format": fmt_int},
        "type":       {"key": "type",       "header": "Type",    "get_value": lambda i: i.get("EntityType"), "format": fmt_str},
        "planet":     {"key": "planet",     "header": "Planet",  "get_value": lambda i: deep_get(i, "Planet", "Name"), "format": fmt_str},
        "sweatable":  {"key": "sweatable",  "header": "Sweat",   "get_value": lambda i: deep_get(i, "Properties", "IsSweatable"), "format": fmt_bool},
        "apm":        {"key": "apm",        "header": "APM",     "get_value": lambda i: deep_get(i, "Properties", "AttacksPerMinute"), "format": fmt_int},
        "atkRange":   {"key": "atkRange",   "header": "Range",   "get_value": lambda i: deep_get(i, "Properties", "AttackRange"), "format": fmt_int},
    },

    "skills": {
        "category":    {"key": "category",    "header": "Category", "get_value": lambda i: deep_get(i, "Category", "Name"), "format": fmt_str},
        "hpIncrease":  {"key": "hpIncrease",  "header": "HP+",      "get_value": lambda i: deep_get(i, "Properties", "HpIncrease", default=0), "format": fmt_trim(1)},
        "professions": {"key": "professions", "header": "Profs",    "get_value": lambda i: len(i.get("Professions") or []), "format": fmt_int},
        "hidden":      {"key": "hidden",      "header": "Hidden",   "get_value": lambda i: deep_get(i, "Properties", "IsHidden"), "format": fmt_bool},
        "extractable": {"key": "extractable", "header": "Extract",  "get_value": lambda i: deep_get(i, "Properties", "IsExtractable"), "format": fmt_bool},
    },

    "professions": {
        "category":    {"key": "category",    "header": "Category", "get_value": lambda i: deep_get(i, "Category", "Name"), "format": fmt_str},
        "skills":      {"key": "skills",      "header": "Skills",   "get_value": lambda i: len(i.get("Skills") or []), "format": fmt_int},
        "totalWeight": {"key": "totalWeight", "header": "Weight",   "get_value": lambda i: sum((s.get("Weight") or 0) for s in (i.get("Skills") or [])), "format": fmt(1)},
        "unlocks":     {"key": "unlocks",     "header": "Unlocks",  "get_value": lambda i: len(i.get("Unlocks") or []), "format": fmt_int},
    },

    "vendors": {
        "planet":   {"key": "planet",   "header": "Planet",   "get_value": lambda i: deep_get(i, "Planet", "Name"), "format": fmt_str},
        "category": {"key": "category", "header": "Category", "get_value": lambda i: deep_get(i, "Properties", "Category"), "format": fmt_str},
        "offers":   {"key": "offers",   "header": "Offers",   "get_value": lambda i: len(i.get("Offers") or []), "format": fmt_int},
        "limited":  {"key": "limited",  "header": "Limited",  "get_value": lambda i: sum(1 for o in (i.get("Offers") or []) if o.get("IsLimited")), "format": fmt_int},
    },

    "missions": {
        "type":   {"key": "type",   "header": "Type",   "get_value": lambda i: deep_get(i, "Properties", "Type"), "format": fmt_str},
        "planet": {"key": "planet", "header": "Planet", "get_value": lambda i: deep_get(i, "Planet", "Name"), "format": fmt_str},
        "chain":  {"key": "chain",  "header": "Chain",  "get_value": lambda i: deep_get(i, "MissionChain", "Name"), "format": fmt_str},
    },

    "locations": {
        "type":        {"key": "type",        "header": "Type",   "get_value": lambda i: deep_get(i, "Properties", "Type"), "format": fmt_str},
        "planet":      {"key": "planet",      "header": "Planet", "get_value": lambda i: deep_get(i, "Planet", "Name"), "format": fmt_str},
        "coordinates": {"key": "coordinates", "header": "Coords", "get_value": lambda i: deep_get(i, "Properties", "Coordinates", "Longitude"), "format": fmt_int},
        "parent":      {"key": "parent",      "header": "Parent", "get_value": lambda i: deep_get(i, "ParentLocation", "Name"), "format": fmt_str},
    },

    "weaponamplifiers": {
        "damage":    {"key": "damage",    "header": "Damage",   "get_value": weapon_total_damage, "format": fmt(1)},
        "dpp":       {"key": "dpp",       "header": "DPP",      "get_value": weapon_dpp, "format": fmt(2)},
        "eff":       {"key": "eff",       "header": "Eff.",     "get_value": lambda i: deep_get(i, "Properties", "Economy", "Efficiency"), "format": fmt(1)},
        "type":      {"key": "type",      "header": "Type",     "get_value": lambda i: deep_get(i, "Properties", "Type"), "format": fmt_str},
        "decay":     {"key": "decay",     "header": "Decay",    "get_value": lambda i: deep_get(i, "Properties", "Economy", "Decay"), "format": fmt(2)},
        "ammoBurn":  {"key": "ammoBurn",  "header": "Ammo",     "get_value": lambda i: deep_get(i, "Properties", "Economy", "AmmoBurn"), "format": fmt_int},
        "cost":      {"key": "cost",      "header": "Cost/Use", "get_value": weapon_cost_per_use, "format": fmt(4)},
        "maxtt":     {"key": "maxtt",     "header": "Max TT",   "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "totalUses": {"key": "totalUses", "header": "Uses",     "get_value": weapon_total_uses, "format": fmt_int},
        "weight":    {"key": "weight",    "header": "Weight",   "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
        "dps":       {"key": "dps",       "header": "DPS",      "get_value": weapon_dps, "format": fmt(1)},
    },

    # Generic items — used for simple sub-types (sights/scopes, absorbers, etc.)
    "items": {
        "weight": {"key": "weight", "header": "Weight", "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
        "maxtt":  {"key": "maxtt",  "header": "Max TT", "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "decay":  {"key": "decay",  "header": "Decay",  "get_value": lambda i: deep_get(i, "Properties", "Economy", "Decay"), "format": fmt(2)},
    },

    # --- Medical ---

    "medicaltools": {
        "hps":           {"key": "hps",           "header": "HPS",      "get_value": _medical_hps, "format": fmt(1)},
        "hpp":           {"key": "hpp",           "header": "HPP",      "get_value": _medical_hpp, "format": fmt(1)},
        "interval":      {"key": "interval",      "header": "Interval", "get_value": weapon_reload, "format": _fmt_cooldown},
        "upm":           {"key": "upm",           "header": "UPM",      "get_value": lambda i: deep_get(i, "Properties", "UsesPerMinute"), "format": fmt_int},
        "cost":          {"key": "cost",          "header": "Cost",     "get_value": weapon_cost_per_use, "format": fmt(4)},
        "maxtt":         {"key": "maxtt",         "header": "Max TT",   "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "maxHeal":       {"key": "maxHeal",       "header": "Max Heal", "get_value": lambda i: deep_get(i, "Properties", "MaxHeal"), "format": fmt(1)},
        "decay":         {"key": "decay",         "header": "Decay",    "get_value": lambda i: deep_get(i, "Properties", "Economy", "Decay"), "format": fmt(2)},
        "sib":           {"key": "sib",           "header": "SiB",      "get_value": lambda i: deep_get(i, "Properties", "Skill", "IsSiB"), "format": fmt_bool},
        "minLevel":      {"key": "minLevel",      "header": "Min Lv",   "get_value": _get_min_level, "format": fmt_int},
        "maxLevel":      {"key": "maxLevel",      "header": "Max Lv",   "get_value": _get_max_level, "format": fmt_int},
        "cooldown":      {"key": "cooldown",      "header": "CD",       "get_value": lambda i: deep_get(i, "Properties", "Mindforce", "Cooldown"), "format": _fmt_cooldown},
        "cooldownGroup": {"key": "cooldownGroup", "header": "CD Grp",   "get_value": lambda i: deep_get(i, "Properties", "Mindforce", "CooldownGroup"), "format": fmt_str},
        "weight":        {"key": "weight",        "header": "Weight",   "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
    },

    "medicalchips": {
        "hps":           {"key": "hps",           "header": "HPS",      "get_value": _medical_hps, "format": fmt(1)},
        "hpp":           {"key": "hpp",           "header": "HPP",      "get_value": _medical_hpp, "format": fmt(1)},
        "interval":      {"key": "interval",      "header": "Interval", "get_value": weapon_reload, "format": _fmt_cooldown},
        "upm":           {"key": "upm",           "header": "UPM",      "get_value": lambda i: deep_get(i, "Properties", "UsesPerMinute"), "format": fmt_int},
        "cost":          {"key": "cost",          "header": "Cost",     "get_value": weapon_cost_per_use, "format": fmt(4)},
        "maxtt":         {"key": "maxtt",         "header": "Max TT",   "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "maxHeal":       {"key": "maxHeal",       "header": "Max Heal", "get_value": lambda i: deep_get(i, "Properties", "MaxHeal"), "format": fmt(1)},
        "range":         {"key": "range",         "header": "Range",    "get_value": lambda i: deep_get(i, "Properties", "Range"), "format": fmt_int},
        "decay":         {"key": "decay",         "header": "Decay",    "get_value": lambda i: deep_get(i, "Properties", "Economy", "Decay"), "format": fmt(2)},
        "ammo":          {"key": "ammo",          "header": "Ammo",     "get_value": lambda i: deep_get(i, "Properties", "Economy", "AmmoBurn"), "format": fmt_int},
        "sib":           {"key": "sib",           "header": "SiB",      "get_value": lambda i: deep_get(i, "Properties", "Skill", "IsSiB"), "format": fmt_bool},
        "minLevel":      {"key": "minLevel",      "header": "Min Lv",   "get_value": _get_min_level, "format": fmt_int},
        "maxLevel":      {"key": "maxLevel",      "header": "Max Lv",   "get_value": _get_max_level, "format": fmt_int},
        "cooldown":      {"key": "cooldown",      "header": "CD",       "get_value": lambda i: deep_get(i, "Properties", "Mindforce", "Cooldown"), "format": _fmt_cooldown},
        "cooldownGroup": {"key": "cooldownGroup", "header": "CD Grp",   "get_value": lambda i: deep_get(i, "Properties", "Mindforce", "CooldownGroup"), "format": fmt_str},
        "weight":        {"key": "weight",        "header": "Weight",   "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
    },

    # --- Tools ---

    "finders": {
        "upm":           {"key": "upm",           "header": "UPM",      "get_value": lambda i: deep_get(i, "Properties", "UsesPerMinute"), "format": fmt_int},
        "decay":         {"key": "decay",         "header": "Decay",    "get_value": lambda i: deep_get(i, "Properties", "Economy", "Decay"), "format": fmt(2)},
        "depth":         {"key": "depth",         "header": "Depth",    "get_value": lambda i: deep_get(i, "Properties", "Depth"), "format": fmt_int},
        "range":         {"key": "range",         "header": "Range",    "get_value": lambda i: deep_get(i, "Properties", "Range"), "format": fmt_int},
        "ammoBurn":      {"key": "ammoBurn",      "header": "Ammo",     "get_value": lambda i: deep_get(i, "Properties", "Economy", "AmmoBurn"), "format": fmt_int},
        "cost":          {"key": "cost",          "header": "Cost/Use", "get_value": weapon_cost_per_use, "format": fmt(4)},
        "maxtt":         {"key": "maxtt",         "header": "Max TT",   "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "totalUses":     {"key": "totalUses",     "header": "Uses",     "get_value": weapon_total_uses, "format": fmt_int},
        "sib":           {"key": "sib",           "header": "SiB",      "get_value": lambda i: deep_get(i, "Properties", "Skill", "IsSiB"), "format": fmt_bool},
        "minLevel":      {"key": "minLevel",      "header": "Min Lv",   "get_value": _get_min_level, "format": fmt_int},
        "maxLevel":      {"key": "maxLevel",      "header": "Max Lv",   "get_value": _get_max_level, "format": fmt_int},
        "weight":        {"key": "weight",        "header": "Weight",   "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
    },

    "scanners": {
        "upm":       {"key": "upm",       "header": "UPM",    "get_value": lambda i: deep_get(i, "Properties", "UsesPerMinute"), "format": fmt_int},
        "decay":     {"key": "decay",     "header": "Decay",  "get_value": lambda i: deep_get(i, "Properties", "Economy", "Decay"), "format": fmt(2)},
        "range":     {"key": "range",     "header": "Range",  "get_value": lambda i: deep_get(i, "Properties", "Range"), "format": fmt_int},
        "depth":     {"key": "depth",     "header": "Depth",  "get_value": lambda i: deep_get(i, "Properties", "Depth"), "format": fmt_int},
        "maxtt":     {"key": "maxtt",     "header": "Max TT", "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "mintt":     {"key": "mintt",     "header": "Min TT", "get_value": lambda i: deep_get(i, "Properties", "Economy", "MinTT"), "format": fmt(2)},
        "totalUses": {"key": "totalUses", "header": "Uses",   "get_value": weapon_total_uses, "format": fmt_int},
        "weight":    {"key": "weight",    "header": "Weight", "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
    },

    "refiners": {
        "upm":       {"key": "upm",       "header": "UPM",    "get_value": lambda i: deep_get(i, "Properties", "UsesPerMinute"), "format": fmt_int},
        "decay":     {"key": "decay",     "header": "Decay",  "get_value": lambda i: deep_get(i, "Properties", "Economy", "Decay"), "format": fmt(2)},
        "maxtt":     {"key": "maxtt",     "header": "Max TT", "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "mintt":     {"key": "mintt",     "header": "Min TT", "get_value": lambda i: deep_get(i, "Properties", "Economy", "MinTT"), "format": fmt(2)},
        "totalUses": {"key": "totalUses", "header": "Uses",   "get_value": weapon_total_uses, "format": fmt_int},
        "weight":    {"key": "weight",    "header": "Weight", "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
    },

    "excavators": {
        "upm":        {"key": "upm",        "header": "UPM",     "get_value": lambda i: deep_get(i, "Properties", "UsesPerMinute"), "format": fmt_int},
        "decay":      {"key": "decay",      "header": "Decay",   "get_value": lambda i: deep_get(i, "Properties", "Economy", "Decay"), "format": fmt(2)},
        "efficiency": {"key": "efficiency", "header": "Effic.",  "get_value": lambda i: deep_get(i, "Properties", "Efficiency"), "format": fmt_int},
        "effPerPed":  {"key": "effPerPed",  "header": "Eff/PED", "get_value": _excavator_eff_per_ped, "format": fmt(1)},
        "maxtt":      {"key": "maxtt",      "header": "Max TT",  "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "totalUses":  {"key": "totalUses",  "header": "Uses",    "get_value": weapon_total_uses, "format": fmt_int},
        "sib":        {"key": "sib",        "header": "SiB",     "get_value": lambda i: deep_get(i, "Properties", "Skill", "IsSiB"), "format": fmt_bool},
        "minLevel":   {"key": "minLevel",   "header": "Min Lv",  "get_value": _get_min_level, "format": fmt_int},
        "maxLevel":   {"key": "maxLevel",   "header": "Max Lv",  "get_value": _get_max_level, "format": fmt_int},
        "weight":     {"key": "weight",     "header": "Weight",  "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
    },

    "teleportationchips": {
        "upm":           {"key": "upm",           "header": "UPM",      "get_value": lambda i: deep_get(i, "Properties", "UsesPerMinute"), "format": fmt_int},
        "decay":         {"key": "decay",         "header": "Decay",    "get_value": lambda i: deep_get(i, "Properties", "Economy", "Decay"), "format": fmt(2)},
        "cost":          {"key": "cost",          "header": "Cost/Use", "get_value": weapon_cost_per_use, "format": fmt(4)},
        "range":         {"key": "range",         "header": "Range",    "get_value": lambda i: deep_get(i, "Properties", "Range"), "format": fmt_int},
        "ammoBurn":      {"key": "ammoBurn",      "header": "Ammo",     "get_value": lambda i: deep_get(i, "Properties", "Economy", "AmmoBurn"), "format": fmt_int},
        "maxtt":         {"key": "maxtt",         "header": "Max TT",   "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "sib":           {"key": "sib",           "header": "SiB",      "get_value": lambda i: deep_get(i, "Properties", "Skill", "IsSiB"), "format": fmt_bool},
        "minLevel":      {"key": "minLevel",      "header": "Min Lv",   "get_value": _get_min_level, "format": fmt_int},
        "maxLevel":      {"key": "maxLevel",      "header": "Max Lv",   "get_value": _get_max_level, "format": fmt_int},
        "cooldown":      {"key": "cooldown",      "header": "CD",       "get_value": lambda i: deep_get(i, "Properties", "Mindforce", "Cooldown"), "format": _fmt_cooldown},
        "cooldownGroup": {"key": "cooldownGroup", "header": "CD Grp",   "get_value": lambda i: deep_get(i, "Properties", "Mindforce", "CooldownGroup"), "format": fmt_str},
    },

    "misctools": {
        "upm":       {"key": "upm",       "header": "UPM",    "get_value": lambda i: deep_get(i, "Properties", "UsesPerMinute"), "format": fmt_int},
        "decay":     {"key": "decay",     "header": "Decay",  "get_value": lambda i: deep_get(i, "Properties", "Economy", "Decay"), "format": fmt(2)},
        "maxtt":     {"key": "maxtt",     "header": "Max TT", "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "mintt":     {"key": "mintt",     "header": "Min TT", "get_value": lambda i: deep_get(i, "Properties", "Economy", "MinTT"), "format": fmt(2)},
        "totalUses": {"key": "totalUses", "header": "Uses",   "get_value": weapon_total_uses, "format": fmt_int},
        "sib":       {"key": "sib",       "header": "SiB",    "get_value": lambda i: deep_get(i, "Properties", "Skill", "IsSiB"), "format": fmt_bool},
        "minLevel":  {"key": "minLevel",  "header": "Min Lv", "get_value": _get_min_level, "format": fmt_int},
        "maxLevel":  {"key": "maxLevel",  "header": "Max Lv", "get_value": _get_max_level, "format": fmt_int},
        "weight":    {"key": "weight",    "header": "Weight", "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
    },

    # --- Attachments ---

    "enhancers": {
        "type":   {"key": "type",   "header": "Type",   "get_value": lambda i: deep_get(i, "Properties", "Type"), "format": fmt_str},
        "tier":   {"key": "tier",   "header": "Tier",   "get_value": lambda i: deep_get(i, "Properties", "Tier") or i.get("Tier"), "format": fmt_int},
        "tool":   {"key": "tool",   "header": "Tool",   "get_value": lambda i: deep_get(i, "Properties", "Tool"), "format": fmt_str},
        "socket": {"key": "socket", "header": "Socket", "get_value": lambda i: deep_get(i, "Properties", "Socket"), "format": fmt_int},
        "maxtt":  {"key": "maxtt",  "header": "Max TT", "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "weight": {"key": "weight", "header": "Weight", "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
        "value":  {"key": "value",  "header": "Value",  "get_value": lambda i: deep_get(i, "Properties", "Economy", "Value"), "format": fmt(2)},
    },

    "mindforceimplants": {
        "abs":      {"key": "abs",      "header": "Absorption", "get_value": lambda i: deep_get(i, "Properties", "Economy", "Absorption"), "format": _fmt_percent},
        "maxLevel": {"key": "maxLevel", "header": "Max Lvl",    "get_value": lambda i: deep_get(i, "Properties", "MaxProfessionLevel"), "format": fmt_int},
        "lvl":      {"key": "lvl",      "header": "Level",      "get_value": lambda i: deep_get(i, "Properties", "Mindforce", "Level") or deep_get(i, "Properties", "Level"), "format": fmt_int},
        "maxTT":    {"key": "maxTT",    "header": "Max TT",     "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "minTT":    {"key": "minTT",    "header": "Min TT",     "get_value": lambda i: deep_get(i, "Properties", "Economy", "MinTT"), "format": fmt(2)},
        "weight":   {"key": "weight",   "header": "Weight",     "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
    },

    "sightsscopes": {
        "type":       {"key": "type",       "header": "Type",        "get_value": lambda i: deep_get(i, "Properties", "Type"), "format": fmt_str},
        "eff":        {"key": "eff",        "header": "Efficiency",  "get_value": lambda i: deep_get(i, "Properties", "Economy", "Efficiency"), "format": fmt(1)},
        "zoom":       {"key": "zoom",       "header": "Zoom",        "get_value": lambda i: deep_get(i, "Properties", "Zoom"), "format": _fmt_zoom},
        "decay":      {"key": "decay",      "header": "Decay",       "get_value": lambda i: deep_get(i, "Properties", "Economy", "Decay"), "format": fmt(2)},
        "skillMod":   {"key": "skillMod",   "header": "Skill Mod",   "get_value": lambda i: deep_get(i, "Properties", "SkillModification"), "format": _fmt_skill_pct},
        "skillBonus": {"key": "skillBonus", "header": "Skill Bonus", "get_value": lambda i: deep_get(i, "Properties", "SkillBonus"), "format": _fmt_skill_pct},
        "maxTT":      {"key": "maxTT",      "header": "Max TT",      "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "weight":     {"key": "weight",     "header": "Weight",      "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
    },

    "absorbers": {
        "abs":    {"key": "abs",    "header": "Absorption",  "get_value": lambda i: deep_get(i, "Properties", "Economy", "Absorption"), "format": _fmt_percent},
        "eff":    {"key": "eff",    "header": "Efficiency",  "get_value": lambda i: deep_get(i, "Properties", "Economy", "Efficiency"), "format": fmt(1)},
        "maxTT":  {"key": "maxTT",  "header": "Max TT",      "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "minTT":  {"key": "minTT",  "header": "Min TT",      "get_value": lambda i: deep_get(i, "Properties", "Economy", "MinTT"), "format": fmt(2)},
        "weight": {"key": "weight", "header": "Weight",      "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
    },

    "finderamplifiers": {
        "decay":     {"key": "decay",     "header": "Decay",      "get_value": lambda i: deep_get(i, "Properties", "Economy", "Decay"), "format": fmt(2)},
        "finderEff": {"key": "finderEff", "header": "Efficiency", "get_value": lambda i: deep_get(i, "Properties", "Efficiency"), "format": fmt(1)},
        "minLevel":  {"key": "minLevel",  "header": "Min Lvl",    "get_value": lambda i: deep_get(i, "Properties", "MinProfessionLevel"), "format": fmt_int},
        "maxTT":     {"key": "maxTT",     "header": "Max TT",     "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "minTT":     {"key": "minTT",     "header": "Min TT",     "get_value": lambda i: deep_get(i, "Properties", "Economy", "MinTT"), "format": fmt(2)},
        "totalUses": {"key": "totalUses", "header": "Uses",       "get_value": weapon_total_uses, "format": fmt_int},
        "weight":    {"key": "weight",    "header": "Weight",     "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
    },

    "armorplatings": {
        "defense":    {"key": "defense",    "header": "Total Def",  "get_value": armor_total_defense, "format": fmt(1)},
        "durability": {"key": "durability", "header": "Durability", "get_value": lambda i: deep_get(i, "Properties", "Economy", "Durability"), "format": fmt_int},
        "maxTT":      {"key": "maxTT",      "header": "Max TT",     "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "minTT":      {"key": "minTT",      "header": "Min TT",     "get_value": lambda i: deep_get(i, "Properties", "Economy", "MinTT"), "format": fmt(2)},
        "weight":     {"key": "weight",     "header": "Weight",     "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
    },

    # --- Consumables ---

    "stimulants": {
        "type":    {"key": "type",    "header": "Type",    "get_value": lambda i: deep_get(i, "Properties", "Type"), "format": fmt_str},
        "effects": {"key": "effects", "header": "Effects", "get_value": lambda i: len(i.get("EffectsOnConsume") or []), "format": fmt_int},
        "weight":  {"key": "weight",  "header": "Weight",  "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
        "maxtt":   {"key": "maxtt",   "header": "Max TT",  "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
    },

    "capsules": {
        "mob":        {"key": "mob",        "header": "Mob",        "get_value": lambda i: deep_get(i, "Mob", "Name"), "format": fmt_str},
        "mobType":    {"key": "mobType",    "header": "Mob Type",   "get_value": lambda i: deep_get(i, "Mob", "Type"), "format": fmt_str},
        "profession": {"key": "profession", "header": "Profession", "get_value": lambda i: deep_get(i, "Profession", "Name"), "format": fmt_str},
        "minLevel":   {"key": "minLevel",   "header": "Min Lv",    "get_value": _get_min_level, "format": fmt_int},
        "maxtt":      {"key": "maxtt",      "header": "Max TT",    "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
    },

    # --- Furnishings ---

    "furniture": {
        "type":   {"key": "type",   "header": "Type",   "get_value": lambda i: deep_get(i, "Properties", "Type"), "format": fmt_str},
        "tt":     {"key": "tt",     "header": "TT",     "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "mintt":  {"key": "mintt",  "header": "Min TT", "get_value": lambda i: deep_get(i, "Properties", "Economy", "MinTT"), "format": fmt(2)},
        "weight": {"key": "weight", "header": "Weight", "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
    },

    "storagecontainers": {
        "cap":       {"key": "cap",       "header": "Items",   "get_value": lambda i: deep_get(i, "Properties", "ItemCapacity"), "format": fmt_int},
        "weightCap": {"key": "weightCap", "header": "Wt. Cap", "get_value": lambda i: deep_get(i, "Properties", "WeightCapacity"), "format": fmt(1)},
        "tt":        {"key": "tt",        "header": "TT",      "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "mintt":     {"key": "mintt",     "header": "Min TT",  "get_value": lambda i: deep_get(i, "Properties", "Economy", "MinTT"), "format": fmt(2)},
        "weight":    {"key": "weight",    "header": "Weight",  "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
    },

    "signs": {
        "ratio":      {"key": "ratio",      "header": "Ratio",  "get_value": lambda i: deep_get(i, "Properties", "Display", "AspectRatio"), "format": fmt_str},
        "itemPoints": {"key": "itemPoints", "header": "Points", "get_value": lambda i: deep_get(i, "Properties", "ItemPoints"), "format": fmt_int},
        "tt":         {"key": "tt",         "header": "TT",     "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "mintt":      {"key": "mintt",      "header": "Min TT", "get_value": lambda i: deep_get(i, "Properties", "Economy", "MinTT"), "format": fmt(2)},
        "cost":       {"key": "cost",       "header": "Cost",   "get_value": lambda i: deep_get(i, "Properties", "Economy", "Cost"), "format": fmt(2)},
        "weight":     {"key": "weight",     "header": "Weight", "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
    },
}


# ---------------------------------------------------------------------------
# Full-width default column keys per type
# ---------------------------------------------------------------------------
# Matches the website's navFullWidthColumns per entity page.
# In condensed view the first 5 columns are shown automatically.
# Users can customize via the column config dialog; all COLUMN_DEFS keys
# remain available.

DEFAULT_COLUMNS: dict[str, list[str]] = {
    "weapons":            ["class", "type", "dps", "dpp", "eff", "costPerUse", "maxtt", "effectiveDmg", "range", "upm", "sib", "minLevel", "maxLevel", "cooldown", "cooldownGroup"],
    "materials":          ["type", "weight", "value"],
    "blueprints":         ["type", "profession", "level", "product", "cost", "sib", "limited", "book", "boosted"],
    "armorsets":          ["defense", "durability", "impact", "cut", "stab", "penetration", "shrapnel", "burn", "cold", "acid", "electric", "absorption", "maxtt"],
    "clothing":           ["slot", "type", "effects", "gender", "weight", "maxTT", "set"],
    "vehicles":           ["type", "speed", "fuel", "passengers", "maxSI", "weight", "maxTT", "durability"],
    "pets":               ["rarity", "effects", "planet", "tamingLevel", "training", "exportable", "nutrioCapacity"],
    "mobs":               ["hpPerLevel", "level", "hp", "cat4", "damage", "type", "planet", "sweatable", "apm", "atkRange"],
    "skills":             ["category", "hpIncrease", "professions", "hidden", "extractable"],
    "professions":        ["category", "skills", "totalWeight", "unlocks"],
    "vendors":            ["planet", "category", "offers", "limited"],
    "missions":           ["type", "planet", "chain"],
    "locations":          ["type", "planet", "coordinates", "parent"],
    "weaponamplifiers":   ["damage", "dpp", "eff", "type", "decay", "ammoBurn", "cost", "maxtt", "totalUses", "weight"],
    "items":              ["weight", "maxtt", "decay"],
    "medicaltools":       ["hps", "hpp", "interval", "upm", "cost", "maxtt", "maxHeal", "decay", "sib", "minLevel", "maxLevel", "cooldown", "cooldownGroup", "weight"],
    "medicalchips":       ["hps", "hpp", "interval", "upm", "cost", "maxtt", "maxHeal", "range", "decay", "ammo", "sib", "minLevel", "maxLevel", "cooldown", "cooldownGroup"],
    "finders":            ["upm", "decay", "depth", "range", "ammoBurn", "cost", "maxtt", "totalUses", "sib", "minLevel", "maxLevel"],
    "scanners":           ["upm", "decay", "range", "depth", "maxtt", "mintt", "totalUses", "weight"],
    "refiners":           ["upm", "decay", "maxtt", "mintt", "totalUses", "weight"],
    "excavators":         ["upm", "decay", "efficiency", "effPerPed", "maxtt", "totalUses", "sib", "minLevel", "maxLevel", "weight"],
    "teleportationchips": ["upm", "decay", "cost", "range", "ammoBurn", "maxtt", "sib", "minLevel", "maxLevel", "cooldown", "cooldownGroup"],
    "misctools":          ["upm", "decay", "maxtt", "mintt", "totalUses", "sib", "minLevel", "maxLevel", "weight"],
    "enhancers":          ["type", "tier", "tool", "socket", "maxtt", "weight"],
    "mindforceimplants":  ["abs", "maxLevel", "lvl", "maxTT", "minTT", "weight"],
    "sightsscopes":       ["type", "eff", "zoom", "decay", "skillMod", "skillBonus", "maxTT", "weight"],
    "absorbers":          ["abs", "eff", "maxTT", "minTT", "weight"],
    "finderamplifiers":   ["decay", "finderEff", "minLevel", "maxTT", "minTT", "totalUses", "weight"],
    "armorplatings":      ["defense", "durability", "maxTT", "minTT", "weight"],
    "stimulants":         ["type", "effects", "weight", "maxtt"],
    "capsules":           ["mob", "mobType", "profession", "minLevel", "maxtt"],
    "furniture":          ["type", "tt", "mintt", "weight"],
    "storagecontainers":  ["cap", "weightCap", "tt", "mintt", "weight"],
    "signs":              ["ratio", "itemPoints", "tt", "mintt", "cost", "weight"],
}


# ---------------------------------------------------------------------------
# Leaf category → (DataClient method name, pageTypeId)
# ---------------------------------------------------------------------------

LEAF_DATA_MAP: dict[str, tuple[str, str]] = {
    # Items — top-level leaves
    "Weapons":                   ("get_weapons",             "weapons"),
    "Armor Sets":                ("get_armor_sets",           "armorsets"),
    "Clothing":                  ("get_clothing",             "clothing"),
    "Materials":                 ("get_materials",            "materials"),
    "Blueprints":                ("get_blueprints",           "blueprints"),
    "Vehicles":                  ("get_vehicles",             "vehicles"),
    "Pets":                      ("get_pets",                 "pets"),
    "Strongboxes":               ("get_strongboxes",          "items"),
    # Attachments
    "Weapon Amplifiers":         ("get_amplifiers",           "weaponamplifiers"),
    "Sights/Scopes":             ("get_scopes_and_sights",    "sightsscopes"),
    "Absorbers":                 ("get_absorbers",            "absorbers"),
    "Finder Amplifiers":         ("get_finder_amplifiers",    "finderamplifiers"),
    "Armor Platings":            ("get_armor_platings",       "armorplatings"),
    "Enhancers":                 ("get_enhancers",            "enhancers"),
    "Mindforce Implants":        ("get_implants",             "mindforceimplants"),
    # Medical
    "Medical Tools":             ("get_medical_tools",        "medicaltools"),
    "Medical Chips":             ("get_medical_chips",        "medicalchips"),
    # Tools
    "Refiners":                  ("get_refiners",             "refiners"),
    "Scanners":                  ("get_scanners",             "scanners"),
    "Finders":                   ("get_finders",              "finders"),
    "Excavators":                ("get_excavators",           "excavators"),
    "Teleportation Chips":       ("get_teleportation_chips",  "teleportationchips"),
    "Effect Chips":              ("get_effect_chips",         "teleportationchips"),
    "Misc. Tools":               ("get_misc_tools",           "misctools"),
    # Consumables
    "Stimulants":                ("get_stimulants",           "stimulants"),
    "Creature Control Capsules": ("get_capsules",             "capsules"),
    # Furnishings
    "Furniture":                 ("get_furniture",            "furniture"),
    "Decorations":               ("get_decorations",          "furniture"),
    "Storage Containers":        ("get_storage_containers",   "storagecontainers"),
    "Signs":                     ("get_signs",                "signs"),
    # Information
    "Mobs":                      ("get_mobs",                 "mobs"),
    "Skills":                    ("get_skills",               "skills"),
    "Professions":               ("get_professions",          "professions"),
    "Vendors":                   ("get_vendors",              "vendors"),
    "Missions":                  ("get_missions",             "missions"),
    "Locations":                 ("get_locations",            "locations"),
}


def get_item_name(item: dict) -> str:
    """Extract display name from an entity dict."""
    return item.get("DisplayName") or item.get("Name") or ""
