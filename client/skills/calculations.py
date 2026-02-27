"""Skill and profession calculation utilities.

Port of nexus/src/lib/utils/skillCalculations.js and codexUtils.js.
"""

from __future__ import annotations

BASE_HP = 80
ATTRIBUTE_MULTIPLIER = 100

# Codex reward divisors: PED cycle cost per PED of skill gained
CODEX_REWARD_DIVISORS = {"cat1": 200, "cat2": 320, "cat3": 640, "cat4": 1000}

CODEX_SKILL_CATEGORIES: dict[str, list[str]] = {
    "cat1": [
        "Aim", "Anatomy", "Athletics", "BLP Weaponry Technology", "Combat Reflexes",
        "Dexterity", "Handgun", "Heavy Melee Weapons", "Laser Weaponry Technology",
        "Light Melee Weapons", "Longblades", "Power Fist", "Rifle", "Shortblades",
        "Weapons Handling",
    ],
    "cat2": [
        "Clubs", "Courage", "Cryogenics", "Diagnosis", "Electrokinesis",
        "Inflict Melee Damage", "Inflict Ranged Damage", "Melee Combat",
        "Perception", "Plasma Weaponry Technology", "Pyrokinesis",
    ],
    "cat3": [
        "Alertness", "Bioregenesis", "Bravado", "Concentration", "Dodge",
        "Evade", "First Aid", "Telepathy", "Translocation", "Vehicle Repairing",
    ],
    "cat4": [
        "Analysis", "Animal Lore", "Biology", "Botany", "Computer",
        "Explosive Projectile Weaponry Technology", "Heavy Weapons",
        "Support Weapon Systems", "Zoology",
    ],
}

# Reverse lookup: skill name → codex category
_SKILL_TO_CODEX_CATEGORY: dict[str, str] = {}


def _build_codex_map() -> dict[str, str]:
    if _SKILL_TO_CODEX_CATEGORY:
        return _SKILL_TO_CODEX_CATEGORY
    for category, skills in CODEX_SKILL_CATEGORIES.items():
        for skill in skills:
            _SKILL_TO_CODEX_CATEGORY.setdefault(skill, category)
    return _SKILL_TO_CODEX_CATEGORY


def get_codex_category(skill_name: str) -> str | None:
    """Get the codex category for a skill name, or None."""
    return _build_codex_map().get(skill_name)


def build_attribute_skill_set(skill_metadata: list[dict]) -> set[str]:
    """Build a set of attribute skill names from metadata.

    Args:
        skill_metadata: List of skill dicts with 'Name' and 'Category' keys.
    """
    return {s["Name"] for s in skill_metadata if s.get("Category") == "Attributes"}


def effective_points(
    points: float, skill_name: str, attribute_skills: set[str]
) -> float:
    """Get effective skill points, applying x100 for attribute skills."""
    if skill_name in attribute_skills:
        return points * ATTRIBUTE_MULTIPLIER
    return points


def calculate_profession_level(
    skill_values: dict[str, float],
    profession_skills: list[dict],
    attribute_skills: set[str] | None = None,
) -> float:
    """Calculate a single profession level.

    Formula: Σ(effective_points × weight) / 10000

    Args:
        skill_values: {skill_name: raw_points}
        profession_skills: list of {Name, Weight}
        attribute_skills: set of attribute skill names (for x100 multiplier)
    """
    if attribute_skills is None:
        attribute_skills = set()
    total = 0.0
    for skill in profession_skills:
        name = skill.get("Name", "")
        weight = skill.get("Weight", 0) or 0
        points = skill_values.get(name, 0)
        eff = effective_points(points, name, attribute_skills)
        total += eff * weight
    return total / 10000


def calculate_all_profession_levels(
    skill_values: dict[str, float],
    professions: list[dict],
    skill_metadata: list[dict] | None = None,
) -> dict[str, float]:
    """Calculate all profession levels.

    Args:
        skill_values: {skill_name: raw_points}
        professions: list of {Name, Skills: [{Name, Weight}]}
        skill_metadata: skill metadata for attribute detection
    """
    attr_skills = build_attribute_skill_set(skill_metadata or [])
    return {
        prof["Name"]: calculate_profession_level(
            skill_values, prof.get("Skills", []), attr_skills
        )
        for prof in professions
    }


def calculate_hp(
    skill_values: dict[str, float],
    skill_metadata: list[dict],
) -> float:
    """Calculate total HP from skill values.

    Formula: 80 + Σ(effective_points / HPIncrease)

    Args:
        skill_values: {skill_name: raw_points}
        skill_metadata: list of {Name, Category, HPIncrease}
    """
    attr_skills = build_attribute_skill_set(skill_metadata)
    hp = float(BASE_HP)
    for skill in skill_metadata:
        hp_inc = skill.get("HPIncrease")
        if hp_inc is not None and hp_inc > 0:
            name = skill["Name"]
            points = skill_values.get(name, 0)
            if points > 0:
                eff = effective_points(points, name, attr_skills)
                hp += eff / hp_inc
    return hp


def find_cheapest_profession_path(
    current_skills: dict[str, float],
    profession_skills: list[dict],
    current_level: float,
    target_level: float,
    markups: dict[str, float] | None = None,
    method_overrides: dict[str, str] | None = None,
    attribute_skills: set[str] | None = None,
) -> dict:
    """Find cheapest path to a target profession level.

    Greedy allocation by cost-efficiency.

    Returns:
        {totalCost, allocations: [{skill, currentPoints, addedPoints, method, cost, levelGain}], feasible}
    """
    if markups is None:
        markups = {}
    if method_overrides is None:
        method_overrides = {}
    if attribute_skills is None:
        attribute_skills = set()

    level_gap = target_level - current_level
    if level_gap <= 0:
        return {"totalCost": 0, "allocations": [], "feasible": True}

    skill_options = []
    for skill in profession_skills:
        name = skill.get("Name", "")
        weight = skill.get("Weight", 0) or 0
        if method_overrides.get(name) == "none":
            continue

        codex_cat = get_codex_category(name)
        override = method_overrides.get(name)

        codex_cost_per_ped = CODEX_REWARD_DIVISORS.get(codex_cat, float("inf")) if codex_cat else float("inf")
        markup = markups.get(name, 100)
        chip_cost_per_ped = markup / 100

        if override == "codex" and codex_cat:
            method = "codex"
            cheaper_cost = codex_cost_per_ped
        elif override == "chip":
            method = "chip"
            cheaper_cost = chip_cost_per_ped
        else:
            cheaper_cost = min(codex_cost_per_ped, chip_cost_per_ped)
            method = "codex" if codex_cost_per_ped <= chip_cost_per_ped else "chip"

        multiplier = ATTRIBUTE_MULTIPLIER if name in attribute_skills else 1
        level_per_point = (multiplier * weight) / 10000
        efficiency = level_per_point / cheaper_cost if cheaper_cost > 0 else 0

        skill_options.append({
            "skill": name,
            "weight": weight,
            "codex_cat": codex_cat,
            "cheaper_cost": cheaper_cost,
            "method": method,
            "level_per_point": level_per_point,
            "efficiency": efficiency,
        })

    skill_options.sort(key=lambda o: o["efficiency"], reverse=True)

    allocations = []
    remaining = level_gap
    total_cost = 0.0

    for opt in skill_options:
        if remaining <= 0:
            break
        if opt["efficiency"] <= 0:
            continue

        points_needed = (remaining * 10000) / (
            (ATTRIBUTE_MULTIPLIER if opt["skill"] in attribute_skills else 1) * opt["weight"]
        )
        cost = points_needed * opt["cheaper_cost"]

        allocations.append({
            "skill": opt["skill"],
            "currentPoints": current_skills.get(opt["skill"], 0),
            "addedPoints": points_needed,
            "method": opt["method"],
            "codexCategory": opt["codex_cat"],
            "cost": cost,
            "levelGain": points_needed * opt["level_per_point"],
        })

        total_cost += cost
        remaining -= points_needed * opt["level_per_point"]

    return {
        "totalCost": total_cost,
        "allocations": allocations,
        "feasible": remaining <= 0.0001,
    }


def find_cheapest_hp_path(
    current_skills: dict[str, float],
    skill_metadata: list[dict],
    current_hp: float,
    target_hp: float,
    markups: dict[str, float] | None = None,
    method_overrides: dict[str, str] | None = None,
) -> dict:
    """Find cheapest path to a target HP.

    Greedy allocation by cost-efficiency.

    Returns:
        {totalCost, allocations: [{skill, currentPoints, addedPoints, method, cost, hpGain}], feasible}
    """
    if markups is None:
        markups = {}
    if method_overrides is None:
        method_overrides = {}

    attr_skills = build_attribute_skill_set(skill_metadata)

    hp_gap = target_hp - current_hp
    if hp_gap <= 0:
        return {"totalCost": 0, "allocations": [], "feasible": True}

    skill_options = []
    for skill in skill_metadata:
        hp_inc = skill.get("HPIncrease")
        name = skill["Name"]
        if hp_inc is None or hp_inc <= 0:
            continue
        if method_overrides.get(name) == "none":
            continue

        codex_cat = get_codex_category(name)
        override = method_overrides.get(name)

        codex_cost_per_ped = CODEX_REWARD_DIVISORS.get(codex_cat, float("inf")) if codex_cat else float("inf")
        markup = markups.get(name, 100)
        chip_cost_per_ped = markup / 100

        if override == "codex" and codex_cat:
            method = "codex"
            cheaper_cost = codex_cost_per_ped
        elif override == "chip":
            method = "chip"
            cheaper_cost = chip_cost_per_ped
        else:
            cheaper_cost = min(codex_cost_per_ped, chip_cost_per_ped)
            method = "codex" if codex_cost_per_ped <= chip_cost_per_ped else "chip"

        multiplier = ATTRIBUTE_MULTIPLIER if name in attr_skills else 1
        hp_per_point = multiplier / hp_inc
        efficiency = hp_per_point / cheaper_cost if cheaper_cost > 0 else 0

        skill_options.append({
            "skill": name,
            "hp_increase": hp_inc,
            "hp_per_point": hp_per_point,
            "codex_cat": codex_cat,
            "cheaper_cost": cheaper_cost,
            "method": method,
            "efficiency": efficiency,
        })

    skill_options.sort(key=lambda o: o["efficiency"], reverse=True)

    allocations = []
    remaining_hp = hp_gap
    total_cost = 0.0

    for opt in skill_options:
        if remaining_hp <= 0:
            break
        if opt["efficiency"] <= 0:
            continue

        points_needed = remaining_hp * opt["hp_increase"] / (
            ATTRIBUTE_MULTIPLIER if opt["skill"] in attr_skills else 1
        )
        cost = points_needed * opt["cheaper_cost"]

        allocations.append({
            "skill": opt["skill"],
            "currentPoints": current_skills.get(opt["skill"], 0),
            "addedPoints": points_needed,
            "method": opt["method"],
            "codexCategory": opt["codex_cat"],
            "cost": cost,
            "hpGain": points_needed * opt["hp_per_point"],
        })

        total_cost += cost
        remaining_hp -= points_needed * opt["hp_per_point"]

    return {
        "totalCost": total_cost,
        "allocations": allocations,
        "feasible": remaining_hp <= 0.0001,
    }
