"""Tool inference engine — matches observed damage values to weapon signatures.

When OCR tool detection is unavailable, this engine infers which weapon was
used based on whether the observed damage falls within a weapon's damage
interval (min-max range from the loadout calculator).

Also maintains a tool change timeline for retroactive attribution when a
tool is detected mid-encounter via OCR.
"""

from datetime import datetime

from ..core.logger import get_logger
from .combat_action_log import SOURCE_PRIORITY
from .session import WeaponSignature

log = get_logger("ToolInference")


class ToolInferenceEngine:
    """Infers weapon/tool from observed damage values using loadout signatures.

    Responsibilities:
    - Damage-range inference: match observed damage to known weapon intervals
    - Tool change timeline: track when OCR detects tool switches
    - Retroactive enrichment: re-attribute events using the timeline
    - Cost lookup: map tool names to cost-per-shot
    """

    def __init__(self):
        self._signatures: list[WeaponSignature] = []

        # Tool change timeline — ordered chronologically
        # list of (timestamp, tool_name)
        self._tool_timeline: list[tuple[datetime, str]] = []

    @property
    def has_signatures(self) -> bool:
        return len(self._signatures) > 0

    def load_signature(self, weapon_name: str, damage_min: float,
                       damage_max: float, total_damage: float,
                       cost_per_shot: float, crit_damage: float = 1.0):
        """Register a weapon signature for matching."""
        sig = WeaponSignature(
            weapon_name=weapon_name,
            damage_min=damage_min,
            damage_max=damage_max,
            total_damage=total_damage,
            cost_per_shot=cost_per_shot,
            crit_damage=crit_damage,
        )
        # Avoid duplicates
        self._signatures = [s for s in self._signatures if s.weapon_name != weapon_name]
        self._signatures.append(sig)
        log.info("Loaded signature: %s (%.1f - %.1f dmg, crit_dmg=%.2f, %.4f cost/shot)",
                 weapon_name, damage_min, damage_max, crit_damage, cost_per_shot)

    def load_from_loadout_stats(self, weapon_name: str, stats) -> None:
        """Load a signature from a LoadoutStats object."""
        if not weapon_name or stats.damage_interval_min <= 0:
            return
        cost_ped = stats.cost / 100  # PEC → PED
        log.info("Loading from stats: %s, stats.cost=%.4f PEC → %.6f PED/shot",
                 weapon_name, stats.cost, cost_ped)
        self.load_signature(
            weapon_name=weapon_name,
            damage_min=stats.damage_interval_min,
            damage_max=stats.damage_interval_max,
            total_damage=stats.total_damage,
            cost_per_shot=cost_ped,
            crit_damage=getattr(stats, 'crit_damage', 1.0),
        )

    def infer_tool(self, damage: float, is_crit: bool = False) -> tuple[str | None, float, float]:
        """Match a damage value to known signatures.

        For critical hits, the damage interval is extended:
        crit_min = damage_min + damage_max * crit_damage
        crit_max = damage_max + damage_max * crit_damage

        Returns (weapon_name, confidence, cost_per_shot).
        If no match, returns (None, 0, 0).
        """
        if not self._signatures or damage <= 0:
            return None, 0.0, 0.0

        best_match: str | None = None
        best_confidence = 0.0
        best_cost = 0.0

        for sig in self._signatures:
            if is_crit:
                # Crit adds damage_max * crit_damage on top of the base damage
                check_min = sig.damage_min + sig.damage_max * sig.crit_damage
                check_max = sig.damage_max + sig.damage_max * sig.crit_damage
            else:
                check_min = sig.damage_min
                check_max = sig.damage_max

            if check_min <= damage <= check_max:
                interval_width = check_max - check_min
                if interval_width > 0:
                    confidence = min(0.95, 0.7 + 0.25 * (1.0 - interval_width / sig.total_damage))
                else:
                    confidence = 0.95

                if confidence > best_confidence:
                    best_match = sig.weapon_name
                    best_confidence = confidence
                    best_cost = sig.cost_per_shot

        return best_match, best_confidence, best_cost

    def get_cost_per_shot(self, tool_name: str) -> float:
        """Look up the cost per shot for a known weapon."""
        for sig in self._signatures:
            if sig.weapon_name == tool_name:
                return sig.cost_per_shot
        return 0.0

    # -- Tool timeline --------------------------------------------------------

    def on_tool_detected(self, tool_name: str, timestamp: datetime):
        """Record a tool change on the timeline.

        Called when OCR or another source identifies the active tool.
        """
        # Avoid duplicates if same tool detected repeatedly
        if self._tool_timeline and self._tool_timeline[-1][1] == tool_name:
            return
        self._tool_timeline.append((timestamp, tool_name))

    def reset_timeline(self):
        """Clear the tool timeline (e.g., on new session)."""
        self._tool_timeline.clear()

    # -- Retroactive enrichment -----------------------------------------------

    def enrich_actions(self, actions) -> list[tuple[str, str, str, float]]:
        """Re-attribute actions using the tool timeline.

        Args:
            actions: Iterable of objects with .id, .timestamp, .tool_name,
                     .tool_source, and .event_type attributes (CombatAction
                     from CombatActionLog).

        Uses the timeline to determine which tool was active at each event's
        timestamp:
        - Events before first known tool: backward-fill from first tool
        - Events between tool A and tool B: attribute to A
        - Events after last tool change: attribute to last tool

        Returns list of (event_id, tool_name, tool_source, confidence) for
        events that would be updated. Does NOT mutate the actions.
        """
        if not self._tool_timeline:
            return []

        enriched = []
        for action in actions:
            if action.event_type not in ("damage_dealt", "critical_hit"):
                continue

            # Respect attribution priority — don't downgrade
            existing_priority = SOURCE_PRIORITY.get(action.tool_source, 0)
            new_priority = SOURCE_PRIORITY.get("ocr_timeline", 0)
            if action.tool_name is not None and existing_priority >= new_priority:
                continue

            resolved_tool = self._resolve_tool_at(action.timestamp)
            if resolved_tool:
                enriched.append((action.id, resolved_tool, "ocr_timeline", 0.85))

        if enriched:
            log.info("Timeline enrichment: %d events eligible", len(enriched))
        return enriched

    def _resolve_tool_at(self, timestamp: datetime) -> str | None:
        """Find which tool was active at a given timestamp using the timeline."""
        if not self._tool_timeline:
            return None

        # If before first tool change, backward-fill from first tool
        if timestamp <= self._tool_timeline[0][0]:
            return self._tool_timeline[0][1]

        # Find the last tool change at or before this timestamp
        active_tool = self._tool_timeline[0][1]
        for change_time, tool_name in self._tool_timeline:
            if change_time > timestamp:
                break
            active_tool = tool_name
        return active_tool

    def clear(self):
        """Reset all state."""
        self._signatures.clear()
        self._tool_timeline.clear()
