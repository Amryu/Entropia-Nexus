"""Session-scoped in-memory combat action log.

Records every combat action (offensive and defensive) for the session
lifetime. Actions are aggregated into encounters but kept until session
end for real-time queries (DPS, efficiency, combat replay).
"""

from dataclasses import dataclass, field
from datetime import datetime

from ..core.logger import get_logger

log = get_logger("CombatLog")

# Tool attribution source priorities (higher = stronger evidence).
# Never overwrite a higher-priority source with a lower one.
SOURCE_PRIORITY = {
    "ocr_reload": 4,    # Reload bar confirmed firing
    "ocr_direct": 3,    # OCR tool was current and not stale at event time
    "ocr": 3,           # Legacy alias for ocr_direct
    "ocr_timeline": 2,  # Retroactive from tool change timeline
    "inferred": 1,      # Damage-range matching
}


@dataclass
class CombatAction:
    """A single combat action with full context."""

    id: str
    encounter_id: str | None
    timestamp: datetime
    event_type: str  # damage_dealt, critical_hit, damage_received, self_heal,
    #                  player_evade, player_dodge, player_jam, target_evade,
    #                  target_dodge, target_jam, mob_miss, deflect, block
    amount: float = 0.0
    tool_name: str | None = None
    tool_source: str | None = None  # "ocr_reload", "ocr_direct", "ocr_timeline", "inferred"
    confidence: float = 0.0


class CombatActionLog:
    """Session-scoped buffer of all combat actions.

    Thread-safety: all public methods are safe to call from any thread.
    The underlying list is only appended to (never reordered/removed),
    and individual field updates are atomic at the Python level.
    """

    def __init__(self):
        self._actions: list[CombatAction] = []
        self._by_encounter: dict[str, list[CombatAction]] = {}
        self._by_id: dict[str, CombatAction] = {}

    def __len__(self) -> int:
        return len(self._actions)

    def append(self, action: CombatAction) -> None:
        """Append a combat action to the log."""
        self._actions.append(action)
        self._by_id[action.id] = action
        if action.encounter_id:
            self._by_encounter.setdefault(action.encounter_id, []).append(action)

    def get_all(self) -> list[CombatAction]:
        """Return all actions in chronological order."""
        return list(self._actions)

    def get_by_encounter(self, encounter_id: str) -> list[CombatAction]:
        """Return actions for a specific encounter."""
        return list(self._by_encounter.get(encounter_id, []))

    def get_by_id(self, action_id: str) -> CombatAction | None:
        """Look up a single action by ID."""
        return self._by_id.get(action_id)

    def get_unattributed_since(self, since: datetime) -> list[CombatAction]:
        """Return damage events with no tool attribution since a timestamp.

        Only returns damage-type events (damage_dealt, critical_hit) since
        defensive events don't have tool attribution.
        """
        result = []
        # Walk backwards from end for efficiency (most recent first)
        for action in reversed(self._actions):
            if action.timestamp < since:
                break
            if (action.event_type in ("damage_dealt", "critical_hit")
                    and action.tool_name is None):
                result.append(action)
        result.reverse()  # Return in chronological order
        return result

    def get_upgradeable_since(self, since: datetime,
                               target_source: str) -> list[CombatAction]:
        """Return damage events that can be upgraded to a higher-priority source.

        Returns events since `since` whose current attribution has lower
        priority than `target_source`, including unattributed events.
        """
        target_priority = SOURCE_PRIORITY.get(target_source, 0)
        result = []
        for action in reversed(self._actions):
            if action.timestamp < since:
                break
            if action.event_type not in ("damage_dealt", "critical_hit"):
                continue
            current_priority = SOURCE_PRIORITY.get(action.tool_source, 0)
            if current_priority < target_priority:
                result.append(action)
        result.reverse()
        return result

    def update_tool(self, action_id: str, tool_name: str,
                    source: str, confidence: float) -> bool:
        """Update tool attribution on an action.

        Respects priority: never overwrites a higher-priority source.
        Returns True if the update was applied.
        """
        action = self._by_id.get(action_id)
        if not action:
            return False

        # Check priority — don't downgrade
        existing_priority = SOURCE_PRIORITY.get(action.tool_source, 0)
        new_priority = SOURCE_PRIORITY.get(source, 0)
        if existing_priority >= new_priority and action.tool_name is not None:
            return False

        action.tool_name = tool_name
        action.tool_source = source
        action.confidence = confidence
        return True

    def update_encounter_id(self, action_id: str, encounter_id: str) -> None:
        """Assign an action to an encounter (e.g., when encounter starts after event)."""
        action = self._by_id.get(action_id)
        if not action:
            return

        # Remove from old encounter index
        if action.encounter_id and action.encounter_id in self._by_encounter:
            old_list = self._by_encounter[action.encounter_id]
            try:
                old_list.remove(action)
            except ValueError:
                pass

        action.encounter_id = encounter_id
        self._by_encounter.setdefault(encounter_id, []).append(action)

    def clear(self) -> None:
        """Clear all actions (called on session end)."""
        self._actions.clear()
        self._by_encounter.clear()
        self._by_id.clear()
