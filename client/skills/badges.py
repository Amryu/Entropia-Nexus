"""Skill badge resolution — HP, Loot, and Defense badges.

Port of MobCodex.svelte getSkillBadges() logic.
"""

from __future__ import annotations

from dataclasses import dataclass

LOOTER_PROFESSIONS = ("Animal Looter", "Mutant Looter", "Robot Looter")
DEFENSE_PROFESSIONS = ("Evader", "Dodger", "Jammer")
DEFENSE_SHORT_LABELS = {"Evader": "Eva", "Dodger": "Dod", "Jammer": "Jam"}


@dataclass
class Badge:
    """A skill badge (HP, Loot, or Defense)."""
    badge_type: str   # "hp", "loot", "defense"
    level: str        # "high", "medium", "low", "ineffective"
    label: str        # Display label ("HP", "Loot", "Eva", "Dod", "Jam")
    value: float      # Underlying metric (HPIncrease or weight)


def get_skill_badges(
    skill_name: str,
    skill_metadata: list[dict],
    professions: list[dict] | None = None,
) -> list[Badge]:
    """Compute badges for a single skill.

    Args:
        skill_name: Name of the skill.
        skill_metadata: Normalized skill metadata list.
            Each entry: {Name, Category, HPIncrease, Professions: [{Name, Weight}]}
        professions: Not used directly (profession weights are in skill_metadata.Professions).

    Returns:
        List of Badge objects.
    """
    skill = None
    for s in skill_metadata:
        if s.get("Name") == skill_name:
            skill = s
            break
    if skill is None:
        return []

    badges: list[Badge] = []

    # HP badge
    hp_increase = skill.get("HPIncrease") or 0
    if hp_increase > 0:
        if hp_increase <= 800:
            if hp_increase >= 500:
                level = "high"
            elif hp_increase >= 200:
                level = "medium"
            else:
                level = "low"
        else:
            level = "ineffective"
        badges.append(Badge("hp", level, "HP", hp_increase))

    # Loot badge — check weight to looter professions
    skill_professions = skill.get("Professions", [])
    if skill_professions:
        prof_weights = {p.get("Name", ""): p.get("Weight", 0) for p in skill_professions}

        looter_weights = []
        for prof_name in LOOTER_PROFESSIONS:
            w = prof_weights.get(prof_name, 0)
            if w and w > 0:
                looter_weights.append(w)

        if looter_weights:
            max_weight = max(looter_weights)
            if max_weight >= 0.8:
                level = "high"
            elif max_weight >= 0.4:
                level = "medium"
            else:
                level = "low"
            badges.append(Badge("loot", level, "Loot", max_weight))

        # Defense badge — check weight to Evader/Dodger/Jammer
        max_defense_weight = 0.0
        max_defense_prof = None
        for prof_name in DEFENSE_PROFESSIONS:
            w = prof_weights.get(prof_name, 0)
            if w and w > max_defense_weight:
                max_defense_weight = w
                max_defense_prof = prof_name

        if max_defense_prof and max_defense_weight > 0:
            short_label = DEFENSE_SHORT_LABELS[max_defense_prof]
            if max_defense_weight >= 0.8:
                level = "high"
            elif max_defense_weight >= 0.4:
                level = "medium"
            else:
                level = "low"
            badges.append(Badge("defense", level, short_label, max_defense_weight))

    return badges
