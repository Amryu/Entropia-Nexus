"""Enhancer state — tracks per-slot enhancer counts during a hunt session.

Enhancers break randomly during combat. This module tracks the current
count per slot and supports incremental decrements from chat.log break
events, as well as manual adjustments by the user.

The state is separate from the base loadout — it overlays the loadout's
enhancer fields before evaluation so the cost/damage calculations
reflect the actual current enhancer configuration.
"""

import copy
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime

from ..core.logger import get_logger

log = get_logger("EnhancerState")

# Map enhancer break names (from chat.log) to (category, slot) pairs.
# The chat message is: "Your enhancer {name} on your {item} broke..."
# Names are matched case-insensitively via substring.
_ENHANCER_NAME_MAP: list[tuple[str, str, str]] = [
    # (pattern, category, slot)
    ("damage", "weapon", "Damage"),
    ("economy", "weapon", "Economy"),      # Could also be healing — disambiguated by item
    ("accuracy", "weapon", "Accuracy"),
    ("range", "weapon", "Range"),
    ("skill mod", "weapon", "SkillMod"),
    ("skillmod", "weapon", "SkillMod"),
    ("defense", "armor", "Defense"),
    ("durability", "armor", "Durability"),
    ("heal", "healing", "Heal"),
]

MAX_ENHANCERS_PER_SLOT = 100


@dataclass
class EnhancerState:
    """Tracks enhancer counts for the current session."""

    # Weapon enhancers
    weapon_damage: int = 0
    weapon_economy: int = 0
    weapon_accuracy: int = 0
    weapon_range: int = 0
    weapon_skill_mod: int = 0

    # Armor enhancers
    armor_defense: int = 0
    armor_durability: int = 0

    # Healing enhancers
    healing_heal: int = 0
    healing_economy: int = 0
    healing_skill_mod: int = 0

    # --- Slot access helpers -------------------------------------------------

    _SLOT_MAP = {
        ("weapon", "Damage"): "weapon_damage",
        ("weapon", "Economy"): "weapon_economy",
        ("weapon", "Accuracy"): "weapon_accuracy",
        ("weapon", "Range"): "weapon_range",
        ("weapon", "SkillMod"): "weapon_skill_mod",
        ("armor", "Defense"): "armor_defense",
        ("armor", "Durability"): "armor_durability",
        ("healing", "Heal"): "healing_heal",
        ("healing", "Economy"): "healing_economy",
        ("healing", "SkillMod"): "healing_skill_mod",
    }

    def get_slot(self, category: str, slot: str) -> int:
        attr = self._SLOT_MAP.get((category, slot))
        return getattr(self, attr, 0) if attr else 0

    def set_slot(self, category: str, slot: str, value: int):
        attr = self._SLOT_MAP.get((category, slot))
        if attr:
            setattr(self, attr, max(0, min(MAX_ENHANCERS_PER_SLOT, value)))

    # --- Break handling ------------------------------------------------------

    def apply_break(self, enhancer_name: str, item_name: str,
                    remaining: int | None = None) -> dict | None:
        """Decrement the matching enhancer slot based on the break event.

        Args:
            enhancer_name: Name from chat.log (e.g., "Damage Enhancer (L)")
            item_name: The item it broke on (used for disambiguation)
            remaining: Count remaining on the item (from chat.log), if available

        Returns:
            Dict with {category, slot, old_count, new_count} if matched, else None.
        """
        name_lower = enhancer_name.lower()

        for pattern, category, slot in _ENHANCER_NAME_MAP:
            if pattern in name_lower:
                # Disambiguation: "economy" could be weapon or healing
                if slot == "Economy" and category == "weapon":
                    # If the item looks like a healing tool, remap
                    item_lower = item_name.lower() if item_name else ""
                    if any(kw in item_lower for kw in ("fap", "heal", "med", "vivo")):
                        category = "healing"

                attr = self._SLOT_MAP.get((category, slot))
                if not attr:
                    continue

                old_count = getattr(self, attr, 0)
                if remaining is not None:
                    # Chat.log tells us the exact remaining count
                    new_count = remaining
                else:
                    new_count = max(0, old_count - 1)

                setattr(self, attr, new_count)
                log.info("Enhancer break: %s.%s %d → %d (%s on %s)",
                         category, slot, old_count, new_count, enhancer_name, item_name)
                return {
                    "category": category,
                    "slot": slot,
                    "old_count": old_count,
                    "new_count": new_count,
                }

        log.warning("Unmatched enhancer break: %r on %r", enhancer_name, item_name)
        return None

    # --- Loadout integration -------------------------------------------------

    @classmethod
    def from_loadout(cls, loadout: dict) -> "EnhancerState":
        """Initialize from a loadout's existing enhancer fields."""
        gear = loadout.get("Gear", {})
        weapon_enh = gear.get("Weapon", {}).get("Enhancers", {})
        armor_enh = gear.get("Armor", {}).get("Enhancers", {})
        healing_enh = gear.get("Healing", {}).get("Enhancers", {})

        return cls(
            weapon_damage=weapon_enh.get("Damage", 0),
            weapon_economy=weapon_enh.get("Economy", 0),
            weapon_accuracy=weapon_enh.get("Accuracy", 0),
            weapon_range=weapon_enh.get("Range", 0),
            weapon_skill_mod=weapon_enh.get("SkillMod", 0),
            armor_defense=armor_enh.get("Defense", 0),
            armor_durability=armor_enh.get("Durability", 0),
            healing_heal=healing_enh.get("Heal", 0),
            healing_economy=healing_enh.get("Economy", 0),
            healing_skill_mod=healing_enh.get("SkillMod", 0),
        )

    def apply_to_loadout(self, loadout: dict) -> dict:
        """Return a copy of the loadout with current enhancer counts applied."""
        lo = copy.deepcopy(loadout)
        gear = lo.setdefault("Gear", {})

        weapon = gear.setdefault("Weapon", {})
        weapon_enh = weapon.setdefault("Enhancers", {})
        weapon_enh["Damage"] = self.weapon_damage
        weapon_enh["Economy"] = self.weapon_economy
        weapon_enh["Accuracy"] = self.weapon_accuracy
        weapon_enh["Range"] = self.weapon_range
        weapon_enh["SkillMod"] = self.weapon_skill_mod

        armor = gear.setdefault("Armor", {})
        armor_enh = armor.setdefault("Enhancers", {})
        armor_enh["Defense"] = self.armor_defense
        armor_enh["Durability"] = self.armor_durability

        healing = gear.setdefault("Healing", {})
        healing_enh = healing.setdefault("Enhancers", {})
        healing_enh["Heal"] = self.healing_heal
        healing_enh["Economy"] = self.healing_economy
        healing_enh["SkillMod"] = self.healing_skill_mod

        return lo

    def total_count(self) -> int:
        """Total enhancers across all slots."""
        return sum(
            getattr(self, attr) for attr in self._SLOT_MAP.values()
        )

    def to_dict(self) -> dict:
        """Serialize to a plain dict for DB storage."""
        return {
            "weapon": {
                "Damage": self.weapon_damage,
                "Economy": self.weapon_economy,
                "Accuracy": self.weapon_accuracy,
                "Range": self.weapon_range,
                "SkillMod": self.weapon_skill_mod,
            },
            "armor": {
                "Defense": self.armor_defense,
                "Durability": self.armor_durability,
            },
            "healing": {
                "Heal": self.healing_heal,
                "Economy": self.healing_economy,
                "SkillMod": self.healing_skill_mod,
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EnhancerState":
        """Deserialize from a plain dict."""
        weapon = data.get("weapon", {})
        armor = data.get("armor", {})
        healing = data.get("healing", {})
        return cls(
            weapon_damage=weapon.get("Damage", 0),
            weapon_economy=weapon.get("Economy", 0),
            weapon_accuracy=weapon.get("Accuracy", 0),
            weapon_range=weapon.get("Range", 0),
            weapon_skill_mod=weapon.get("SkillMod", 0),
            armor_defense=armor.get("Defense", 0),
            armor_durability=armor.get("Durability", 0),
            healing_heal=healing.get("Heal", 0),
            healing_economy=healing.get("Economy", 0),
            healing_skill_mod=healing.get("SkillMod", 0),
        )
