"""Enhancer state — tracks per-slot enhancer stacks during a hunt session.

Each enhancer type on an item has N slots (set in the loadout, e.g., Damage=3).
Each slot holds a stack of up to 100 enhancers. The loadout evaluator uses the
number of ACTIVE slots (stacks with count > 0) — not the total enhancer count.

When an enhancer breaks, one unit is removed from a stack. Only when a stack
hits 0 does the effective slot count decrease, changing the evaluation result.
"""

import copy
import json
from dataclasses import dataclass, field
from datetime import datetime

from ..core.logger import get_logger

log = get_logger("EnhancerState")

MAX_STACK_SIZE = 100

# Map enhancer break names (from chat.log) to (category, slot_key) pairs.
# Matched case-insensitively via substring.
_ENHANCER_NAME_MAP: list[tuple[str, str, str]] = [
    ("damage", "weapon", "Damage"),
    ("economy", "weapon", "Economy"),
    ("accuracy", "weapon", "Accuracy"),
    ("range", "weapon", "Range"),
    ("skill mod", "weapon", "SkillMod"),
    ("skillmod", "weapon", "SkillMod"),
    ("defense", "armor", "Defense"),
    ("durability", "armor", "Durability"),
    ("heal", "healing", "Heal"),
]

# All known (category, slot_key) pairs
ALL_SLOTS = [
    ("weapon", "Damage"),
    ("weapon", "Economy"),
    ("weapon", "Accuracy"),
    ("weapon", "Range"),
    ("weapon", "SkillMod"),
    ("armor", "Defense"),
    ("armor", "Durability"),
    ("healing", "Heal"),
    ("healing", "Economy"),
    ("healing", "SkillMod"),
]


@dataclass
class EnhancerSlot:
    """A single enhancer type on an item: N slots, each with a stack count."""
    num_slots: int = 0          # How many slots are configured (from loadout)
    stacks: list[int] = field(default_factory=list)  # Per-slot stack counts

    @property
    def active_slots(self) -> int:
        """Number of slots with count > 0 — this is what the evaluator uses."""
        return sum(1 for s in self.stacks if s > 0)

    @property
    def total_count(self) -> int:
        """Total enhancers across all stacks."""
        return sum(self.stacks)

    def break_one(self) -> bool:
        """Remove one enhancer from the last non-empty stack.

        Returns True if a stack was depleted (active slots changed).
        """
        # Deplete from the last non-empty stack
        for i in range(len(self.stacks) - 1, -1, -1):
            if self.stacks[i] > 0:
                self.stacks[i] -= 1
                return self.stacks[i] == 0  # True if slot just emptied
        return False

    def set_total(self, total: int):
        """Set total count by distributing evenly across slots."""
        if self.num_slots <= 0:
            self.stacks = []
            return
        per_slot = total // self.num_slots
        remainder = total % self.num_slots
        self.stacks = [per_slot + (1 if i < remainder else 0)
                        for i in range(self.num_slots)]

    @classmethod
    def from_loadout(cls, num_slots: int, stack_size: int = MAX_STACK_SIZE) -> "EnhancerSlot":
        """Create a fully stacked slot from a loadout's enhancer count."""
        if num_slots <= 0:
            return cls(num_slots=0, stacks=[])
        return cls(
            num_slots=num_slots,
            stacks=[stack_size] * num_slots,
        )

    def to_dict(self) -> dict:
        return {"num_slots": self.num_slots, "stacks": list(self.stacks)}

    @classmethod
    def from_dict(cls, data: dict) -> "EnhancerSlot":
        return cls(
            num_slots=data.get("num_slots", 0),
            stacks=list(data.get("stacks", [])),
        )


class EnhancerState:
    """Tracks all enhancer slots for the current session.

    Each (category, slot_key) pair maps to an EnhancerSlot with N stacks.
    The evaluator input is the number of active slots (stacks > 0).
    """

    def __init__(self):
        # (category, slot_key) → EnhancerSlot
        self._slots: dict[tuple[str, str], EnhancerSlot] = {}

    def get_slot(self, category: str, slot_key: str) -> EnhancerSlot:
        return self._slots.get((category, slot_key), EnhancerSlot())

    def set_slot(self, category: str, slot_key: str, slot: EnhancerSlot):
        self._slots[(category, slot_key)] = slot

    def active_count(self, category: str, slot_key: str) -> int:
        """Number of active slots (what the evaluator uses)."""
        return self.get_slot(category, slot_key).active_slots

    def total_enhancers(self) -> int:
        """Total enhancers across all slots and stacks."""
        return sum(s.total_count for s in self._slots.values())

    def total_active_slots(self) -> int:
        """Total active slots across all categories."""
        return sum(s.active_slots for s in self._slots.values())

    # -- Break handling -------------------------------------------------------

    def apply_break(self, enhancer_name: str, item_name: str,
                    remaining: int | None = None) -> dict | None:
        """Handle an enhancer break from chat.log.

        Args:
            enhancer_name: e.g., "Damage Enhancer (L)"
            item_name: The item it broke on
            remaining: Total remaining for this type on this item

        Returns:
            Delta dict if matched, else None.
        """
        name_lower = enhancer_name.lower()

        for pattern, category, slot_key in _ENHANCER_NAME_MAP:
            if pattern not in name_lower:
                continue

            # Disambiguate economy: weapon vs healing
            if slot_key == "Economy" and category == "weapon":
                item_lower = (item_name or "").lower()
                if any(kw in item_lower for kw in ("fap", "heal", "med", "vivo")):
                    category = "healing"

            slot = self.get_slot(category, slot_key)
            old_active = slot.active_slots
            old_total = slot.total_count

            if remaining is not None and slot.num_slots > 0:
                # Set total from the "remaining" message and redistribute
                slot.set_total(remaining)
            else:
                slot.break_one()

            new_active = slot.active_slots
            new_total = slot.total_count
            self._slots[(category, slot_key)] = slot

            slot_changed = old_active != new_active
            log.info("Enhancer break: %s.%s total %d→%d, active slots %d→%d%s",
                     category, slot_key, old_total, new_total,
                     old_active, new_active,
                     " (SLOT DEPLETED)" if slot_changed else "")

            return {
                "category": category,
                "slot": slot_key,
                "old_total": old_total,
                "new_total": new_total,
                "old_active": old_active,
                "new_active": new_active,
                "slot_changed": slot_changed,
            }

        log.warning("Unmatched enhancer break: %r on %r", enhancer_name, item_name)
        return None

    # -- Loadout integration --------------------------------------------------

    @classmethod
    def from_loadout(cls, loadout: dict,
                     stack_size: int = MAX_STACK_SIZE) -> "EnhancerState":
        """Initialize from a loadout's enhancer fields (fully stacked)."""
        state = cls()
        gear = loadout.get("Gear", {})

        weapon_enh = gear.get("Weapon", {}).get("Enhancers", {})
        armor_enh = gear.get("Armor", {}).get("Enhancers", {})
        healing_enh = gear.get("Healing", {}).get("Enhancers", {})

        enh_map = {
            "weapon": weapon_enh,
            "armor": armor_enh,
            "healing": healing_enh,
        }

        for category, slot_key in ALL_SLOTS:
            src = enh_map.get(category, {})
            num_slots = src.get(slot_key, 0)
            if num_slots > 0:
                state._slots[(category, slot_key)] = EnhancerSlot.from_loadout(
                    num_slots, stack_size,
                )

        return state

    def apply_to_loadout(self, loadout: dict) -> dict:
        """Return a loadout copy with active slot counts as enhancer values."""
        lo = copy.deepcopy(loadout)
        gear = lo.setdefault("Gear", {})

        # Map category → gear key → Enhancers dict
        targets = {
            "weapon": gear.setdefault("Weapon", {}).setdefault("Enhancers", {}),
            "armor": gear.setdefault("Armor", {}).setdefault("Enhancers", {}),
            "healing": gear.setdefault("Healing", {}).setdefault("Enhancers", {}),
        }

        for (category, slot_key), slot in self._slots.items():
            enh_dict = targets.get(category)
            if enh_dict is not None:
                enh_dict[slot_key] = slot.active_slots

        return lo

    # -- Serialization --------------------------------------------------------

    def to_dict(self) -> dict:
        result = {}
        for (cat, key), slot in self._slots.items():
            result.setdefault(cat, {})[key] = slot.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "EnhancerState":
        state = cls()
        for cat, slots in data.items():
            for key, slot_data in slots.items():
                state._slots[(cat, key)] = EnhancerSlot.from_dict(slot_data)
        return state

    def summary(self) -> str:
        """Human-readable summary of enhancer state."""
        parts = []
        for (cat, key), slot in sorted(self._slots.items()):
            if slot.num_slots > 0:
                parts.append(f"{cat}.{key}: {slot.active_slots}/{slot.num_slots} "
                             f"slots ({slot.total_count} total)")
        return ", ".join(parts) if parts else "No enhancers"
