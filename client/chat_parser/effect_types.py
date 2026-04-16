"""Classification of 'Received Effect Over Time' names.

All effect-over-time messages represent temporary buffs. Semantics:

- The first application during an inactive period fires a message.
- Subsequent uses while the buff is still active silently refresh its
  duration — no new message is emitted.
- Once the buff expires, the next use fires a new message.

This means effect messages can NEVER be used as a per-use counter. They
are only useful as "buff X just became (or was refreshed to) active"
signals — which is still enough to:

1. Detect which buffs are active right now, so the enhancer inference
   engine can pause whenever a damage/heal modifier is present.
2. Confirm that the player recently used a tool whose name contains the
   effect (e.g. 'Divine Intervention' <-> Divine Intervention Chip) —
   useful for one-time confirmation, not cost-per-shot accounting.

Cost attribution for heal tools MUST come from the actual heal numbers in
chat (SELF_HEAL events), not from counting effect messages.

Categories:

- DAMAGE_MOD:   affects damage output or crit behaviour — enhancer
                inference on weapons must pause while any is active.
- HEAL_MOD:     affects heal output — enhancer inference on medical
                tools must pause while any is active.
- PASSIVE:      affects something unrelated to damage/heal (skill gain,
                speed, max HP, etc.). Safe to ignore for inference.
- UNKNOWN:      not in the catalog; treated conservatively (no pause).
"""

from __future__ import annotations

from enum import Enum


class EffectCategory(str, Enum):
    DAMAGE_MOD = "damage_mod"
    HEAL_MOD = "heal_mod"
    PASSIVE = "passive"
    UNKNOWN = "unknown"


# Canonical effect names observed in chat logs, mapped to category.
# Keys are compared case-insensitively in classify_effect().
_CATALOG: dict[str, EffectCategory] = {
    # Damage-output modifiers — pause damage enhancer detection.
    # Note: the enhancer inference engine already excludes crits from
    # its sample intake, so crit-only buffs (Increased Critical Chance/
    # Damage) don't skew the regular-hit range and are classified
    # PASSIVE rather than DAMAGE_MOD. Equipped items that modify
    # damage (amplifiers, scopes, sights) are already baked into the
    # loadout-evaluated damage range, so they aren't listed here
    # either — only transient external buffs need tracking.
    "might": EffectCategory.DAMAGE_MOD,
    "berserker": EffectCategory.DAMAGE_MOD,
    "increased damage": EffectCategory.DAMAGE_MOD,

    # Crit-only buffs — irrelevant because crits are excluded from
    # enhancer sample intake. Treated as passive for pause purposes.
    "increased critical chance": EffectCategory.PASSIVE,
    "increased critical damage": EffectCategory.PASSIVE,

    # Heal-output modifiers — pause heal enhancer detection.
    "increased healing": EffectCategory.HEAL_MOD,
    "decreased healing": EffectCategory.HEAL_MOD,
    # 'Heal' itself is the generic heal-over-time tick from a medical
    # tool. It doesn't change heal output, but it's unreliable as a use
    # counter (refresh doesn't re-fire) and not relevant for enhancer
    # inference — classify as PASSIVE so it's ignored by the pause logic.
    "heal": EffectCategory.PASSIVE,

    # Discrete utility effects — tool confirmation signal only, no
    # impact on damage/heal enhancer inference.
    "divine intervention": EffectCategory.PASSIVE,
    "auto loot": EffectCategory.PASSIVE,

    # Unrelated passive buffs — ignore for inference purposes.
    "increased health": EffectCategory.PASSIVE,
    "increased regeneration": EffectCategory.PASSIVE,
    "increased reload speed": EffectCategory.PASSIVE,
    "increased run speed": EffectCategory.PASSIVE,
    "increased skill gain": EffectCategory.PASSIVE,
}


def classify_effect(effect_name: str) -> EffectCategory:
    """Return the category of a 'Received Effect Over Time' name.

    Matching is case-insensitive and trimmed.  Unknown names return
    ``EffectCategory.UNKNOWN`` so the caller can log them for later
    classification.
    """
    if not effect_name:
        return EffectCategory.UNKNOWN
    return _CATALOG.get(effect_name.strip().lower(), EffectCategory.UNKNOWN)


def pauses_damage_inference(effect_name: str) -> bool:
    """True if the effect modifies damage output or crit behaviour.

    EnhancerInferenceEngine must pause its damage-based detection while
    any such buff is active.
    """
    return classify_effect(effect_name) == EffectCategory.DAMAGE_MOD


def pauses_heal_inference(effect_name: str) -> bool:
    """True if the effect modifies heal output.

    EnhancerInferenceEngine must pause its heal-based detection while
    any such buff is active.
    """
    return classify_effect(effect_name) == EffectCategory.HEAL_MOD
