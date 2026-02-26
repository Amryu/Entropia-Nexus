"""Column definitions for wiki entity tables.

Ported from nexus/src/lib/search-columns.js — keep in sync.
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


# ---------------------------------------------------------------------------
# Column definitions per entity type
# ---------------------------------------------------------------------------
# Keyed by pageTypeId (matches website localStorage wiki-nav-columns-{id}).
# Each column: { key, header, get_value: callable(item)->value, format: callable(value)->str }

COLUMN_DEFS: dict[str, dict[str, dict]] = {
    "weapons": {
        "class":        {"key": "class",        "header": "Class",    "get_value": lambda i: deep_get(i, "Properties", "Class"), "format": fmt_str},
        "type":         {"key": "type",         "header": "Type",     "get_value": lambda i: deep_get(i, "Properties", "Type"), "format": fmt_str},
        "dps":          {"key": "dps",          "header": "DPS",      "get_value": weapon_dps, "format": fmt(1)},
        "dpp":          {"key": "dpp",          "header": "DPP",      "get_value": weapon_dpp, "format": fmt(2)},
        "eff":          {"key": "eff",          "header": "Eff.",     "get_value": lambda i: deep_get(i, "Properties", "Economy", "Efficiency"), "format": fmt(1)},
        "effectiveDmg": {"key": "effectiveDmg", "header": "Eff Dmg",  "get_value": weapon_effective_damage, "format": fmt(1)},
        "damage":       {"key": "damage",       "header": "Damage",   "get_value": weapon_total_damage, "format": fmt(1)},
        "range":        {"key": "range",        "header": "Range",    "get_value": lambda i: deep_get(i, "Properties", "Range"), "format": fmt_int},
        "upm":          {"key": "upm",          "header": "Uses",     "get_value": lambda i: deep_get(i, "Properties", "UsesPerMinute"), "format": fmt_int},
        "maxtt":        {"key": "maxtt",        "header": "Max TT",   "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "decay":        {"key": "decay",        "header": "Decay",    "get_value": lambda i: deep_get(i, "Properties", "Economy", "Decay"), "format": fmt(2)},
        "ammo":         {"key": "ammo",         "header": "Ammo",     "get_value": lambda i: deep_get(i, "Properties", "Economy", "AmmoBurn"), "format": fmt_int},
        "uses":         {"key": "uses",         "header": "Uses",     "get_value": weapon_total_uses, "format": fmt_int},
        "sib":          {"key": "sib",          "header": "SiB",      "get_value": lambda i: deep_get(i, "Properties", "Skill", "IsSiB"), "format": fmt_bool},
        "costPerUse":   {"key": "costPerUse",   "header": "Cost/Use", "get_value": weapon_cost_per_use, "format": fmt(4)},
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
        "sib":        {"key": "sib",        "header": "SiB",        "get_value": lambda i: deep_get(i, "Properties", "Skill", "IsSiB"), "format": fmt_bool},
    },

    "armorsets": {
        "defense":     {"key": "defense",     "header": "Def.",  "get_value": armor_total_defense, "format": fmt(1)},
        "durability":  {"key": "durability",  "header": "Dur.",  "get_value": lambda i: deep_get(i, "Properties", "Economy", "Durability"), "format": fmt(1)},
        "impact":      {"key": "impact",      "header": "Imp",   "get_value": lambda i: deep_get(i, "Properties", "Defense", "Impact"), "format": fmt(1)},
        "cut":         {"key": "cut",         "header": "Cut",   "get_value": lambda i: deep_get(i, "Properties", "Defense", "Cut"), "format": fmt(1)},
        "stab":        {"key": "stab",        "header": "Stab",  "get_value": lambda i: deep_get(i, "Properties", "Defense", "Stab"), "format": fmt(1)},
        "penetration": {"key": "penetration", "header": "Pen",   "get_value": lambda i: deep_get(i, "Properties", "Defense", "Penetration"), "format": fmt(1)},
        "shrapnel":    {"key": "shrapnel",    "header": "Shrp",  "get_value": lambda i: deep_get(i, "Properties", "Defense", "Shrapnel"), "format": fmt(1)},
        "burn":        {"key": "burn",        "header": "Burn",  "get_value": lambda i: deep_get(i, "Properties", "Defense", "Burn"), "format": fmt(1)},
        "cold":        {"key": "cold",        "header": "Cold",  "get_value": lambda i: deep_get(i, "Properties", "Defense", "Cold"), "format": fmt(1)},
        "acid":        {"key": "acid",        "header": "Acid",  "get_value": lambda i: deep_get(i, "Properties", "Defense", "Acid"), "format": fmt(1)},
        "electric":    {"key": "electric",    "header": "Elec",  "get_value": lambda i: deep_get(i, "Properties", "Defense", "Electric"), "format": fmt(1)},
        "maxtt":       {"key": "maxtt",       "header": "Max TT", "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "weight":      {"key": "weight",      "header": "Weight", "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
    },

    "clothing": {
        "slot":   {"key": "slot",   "header": "Slot",   "get_value": lambda i: deep_get(i, "Properties", "Slot"), "format": fmt_str},
        "type":   {"key": "type",   "header": "Type",   "get_value": lambda i: deep_get(i, "Properties", "Type"), "format": fmt_str},
        "gender": {"key": "gender", "header": "Gender", "get_value": lambda i: deep_get(i, "Properties", "Gender"), "format": fmt_str},
        "weight": {"key": "weight", "header": "Weight", "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
        "maxTT":  {"key": "maxTT",  "header": "Max TT", "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
    },

    "vehicles": {
        "type":       {"key": "type",       "header": "Type",   "get_value": lambda i: deep_get(i, "Properties", "Type"), "format": fmt_str},
        "speed":      {"key": "speed",      "header": "Speed",  "get_value": lambda i: deep_get(i, "Properties", "MaxSpeed"), "format": fmt_int},
        "fuel":       {"key": "fuel",       "header": "Fuel",   "get_value": lambda i: deep_get(i, "Properties", "Economy", "FuelConsumptionActive") or deep_get(i, "Properties", "Economy", "FuelConsumptionPassive"), "format": fmt(2)},
        "passengers": {"key": "passengers", "header": "Seats",  "get_value": lambda i: deep_get(i, "Properties", "PassengerCount"), "format": fmt_int},
        "maxSI":      {"key": "maxSI",      "header": "Max SI", "get_value": lambda i: deep_get(i, "Properties", "MaxStructuralIntegrity"), "format": fmt_int},
        "weight":     {"key": "weight",     "header": "Weight", "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
        "maxTT":      {"key": "maxTT",      "header": "Max TT", "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
    },

    "pets": {
        "rarity":      {"key": "rarity",      "header": "Rarity",  "get_value": lambda i: deep_get(i, "Properties", "Rarity"), "format": fmt_str},
        "effects":     {"key": "effects",     "header": "Effects", "get_value": lambda i: len(i.get("Effects") or []), "format": fmt_int},
        "planet":      {"key": "planet",      "header": "Planet",  "get_value": lambda i: deep_get(i, "Planet", "Name"), "format": fmt_str},
        "tamingLevel": {"key": "tamingLevel", "header": "Taming",  "get_value": lambda i: deep_get(i, "Properties", "TamingLevel"), "format": fmt_int},
    },

    "mobs": {
        "hpPerLevel": {"key": "hpPerLevel", "header": "HP/Lvl", "get_value": mob_smallest_hp_per_level, "format": fmt(1)},
        "level":      {"key": "level",      "header": "Level",  "get_value": mob_level_max, "format": fmt_int},
        "hp":         {"key": "hp",         "header": "HP",     "get_value": mob_health_max, "format": fmt_int},
        "type":       {"key": "type",       "header": "Type",   "get_value": lambda i: i.get("EntityType"), "format": fmt_str},
        "planet":     {"key": "planet",     "header": "Planet", "get_value": lambda i: deep_get(i, "Planet", "Name"), "format": fmt_str},
        "sweatable":  {"key": "sweatable",  "header": "Sweat",  "get_value": lambda i: deep_get(i, "Properties", "IsSweatable"), "format": fmt_bool},
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
    },

    "missions": {
        "type":   {"key": "type",   "header": "Type",   "get_value": lambda i: deep_get(i, "Properties", "Type"), "format": fmt_str},
        "planet": {"key": "planet", "header": "Planet", "get_value": lambda i: deep_get(i, "Planet", "Name"), "format": fmt_str},
        "chain":  {"key": "chain",  "header": "Chain",  "get_value": lambda i: deep_get(i, "MissionChain", "Name"), "format": fmt_str},
    },

    "locations": {
        "type":   {"key": "type",   "header": "Type",   "get_value": lambda i: deep_get(i, "Properties", "Type"), "format": fmt_str},
        "planet": {"key": "planet", "header": "Planet", "get_value": lambda i: deep_get(i, "Planet", "Name"), "format": fmt_str},
    },

    "weaponamplifiers": {
        "type":   {"key": "type",   "header": "Type",   "get_value": lambda i: deep_get(i, "Properties", "Type"), "format": fmt_str},
        "eff":    {"key": "eff",    "header": "Eff.",   "get_value": lambda i: deep_get(i, "Properties", "Economy", "Efficiency"), "format": fmt(1)},
        "dps":    {"key": "dps",    "header": "DPS",    "get_value": weapon_dps, "format": fmt(1)},
        "damage": {"key": "damage", "header": "Damage", "get_value": weapon_total_damage, "format": fmt(1)},
        "maxtt":  {"key": "maxtt",  "header": "Max TT", "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "decay":  {"key": "decay",  "header": "Decay",  "get_value": lambda i: deep_get(i, "Properties", "Economy", "Decay"), "format": fmt(2)},
        "ammo":   {"key": "ammo",   "header": "Ammo",   "get_value": lambda i: deep_get(i, "Properties", "Economy", "AmmoBurn"), "format": fmt_int},
        "weight": {"key": "weight", "header": "Weight", "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
    },

    "items": {
        "weight": {"key": "weight", "header": "Weight", "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
        "maxtt":  {"key": "maxtt",  "header": "Max TT", "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "decay":  {"key": "decay",  "header": "Decay",  "get_value": lambda i: deep_get(i, "Properties", "Economy", "Decay"), "format": fmt(2)},
    },

    "medicalchips": {
        "maxtt":  {"key": "maxtt",  "header": "Max TT", "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "decay":  {"key": "decay",  "header": "Decay",  "get_value": lambda i: deep_get(i, "Properties", "Economy", "Decay"), "format": fmt(2)},
        "weight": {"key": "weight", "header": "Weight", "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
    },

    "finders": {
        "range":  {"key": "range",  "header": "Range",  "get_value": lambda i: deep_get(i, "Properties", "Range"), "format": fmt_int},
        "depth":  {"key": "depth",  "header": "Depth",  "get_value": lambda i: deep_get(i, "Properties", "Depth"), "format": fmt_int},
        "maxtt":  {"key": "maxtt",  "header": "Max TT", "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
        "decay":  {"key": "decay",  "header": "Decay",  "get_value": lambda i: deep_get(i, "Properties", "Economy", "Decay"), "format": fmt(2)},
        "weight": {"key": "weight", "header": "Weight", "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
    },

    "enhancers": {
        "type":   {"key": "type",   "header": "Type",   "get_value": lambda i: deep_get(i, "Properties", "Type"), "format": fmt_str},
        "value":  {"key": "value",  "header": "Value",  "get_value": lambda i: deep_get(i, "Properties", "Economy", "Value"), "format": fmt(2)},
        "weight": {"key": "weight", "header": "Weight", "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
    },

    "furnishings": {
        "weight": {"key": "weight", "header": "Weight", "get_value": lambda i: deep_get(i, "Properties", "Weight"), "format": fmt_int},
        "maxtt":  {"key": "maxtt",  "header": "Max TT", "get_value": lambda i: deep_get(i, "Properties", "Economy", "MaxTT"), "format": fmt(2)},
    },
}


# ---------------------------------------------------------------------------
# Default column keys per type
# ---------------------------------------------------------------------------

# Show all available columns by default — users can customize via the config dialog.
DEFAULT_COLUMNS: dict[str, list[str]] = {
    page_type: list(cols.keys()) for page_type, cols in COLUMN_DEFS.items()
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
    "Sights/Scopes":             ("get_scopes_and_sights",    "items"),
    "Absorbers":                 ("get_absorbers",            "items"),
    "Finder Amplifiers":         ("get_finder_amplifiers",    "items"),
    "Armor Platings":            ("get_armor_platings",       "items"),
    "Enhancers":                 ("get_enhancers",            "enhancers"),
    "Mindforce Implants":        ("get_implants",             "items"),
    # Medical Tools
    "Medical Tools":             ("get_medical_tools",        "weapons"),
    "Medical Chips":             ("get_medical_chips",        "medicalchips"),
    # Tools
    "Refiners":                  ("get_refiners",             "items"),
    "Scanners":                  ("get_scanners",             "items"),
    "Finders":                   ("get_finders",              "finders"),
    "Excavators":                ("get_excavators",           "items"),
    "Teleportation Chips":       ("get_teleportation_chips",  "items"),
    "Effect Chips":              ("get_effect_chips",         "items"),
    "Misc. Tools":               ("get_misc_tools",           "items"),
    # Consumables
    "Stimulants":                ("get_stimulants",           "materials"),
    "Creature Control Capsules": ("get_capsules",             "items"),
    # Furnishings
    "Furniture":                 ("get_furniture",            "furnishings"),
    "Decorations":               ("get_decorations",          "furnishings"),
    "Storage Containers":        ("get_storage_containers",   "furnishings"),
    "Signs":                     ("get_signs",                "furnishings"),
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
