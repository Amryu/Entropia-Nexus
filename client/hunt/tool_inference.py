"""Tool inference engine — matches observed damage values to weapon signatures.

When OCR tool detection is unavailable, this engine infers which weapon was
used based on whether the observed damage falls within a weapon's damage
interval (min-max range from the loadout calculator).
"""

import uuid
from datetime import datetime, timedelta

from ..core.logger import get_logger
from .session import CombatEventDetail, WeaponSignature

log = get_logger("ToolInference")

# How long to buffer events awaiting retroactive tool enrichment
BUFFER_WINDOW = timedelta(seconds=5)


class ToolInferenceEngine:
    """Infers weapon/tool from observed damage values using loadout signatures."""

    def __init__(self):
        self._signatures: list[WeaponSignature] = []
        self._pending_events: list[CombatEventDetail] = []

    @property
    def has_signatures(self) -> bool:
        return len(self._signatures) > 0

    def load_signature(self, weapon_name: str, damage_min: float,
                       damage_max: float, total_damage: float,
                       cost_per_shot: float):
        """Register a weapon signature for matching."""
        sig = WeaponSignature(
            weapon_name=weapon_name,
            damage_min=damage_min,
            damage_max=damage_max,
            total_damage=total_damage,
            cost_per_shot=cost_per_shot,
        )
        # Avoid duplicates
        self._signatures = [s for s in self._signatures if s.weapon_name != weapon_name]
        self._signatures.append(sig)
        log.info("Loaded signature: %s (%.1f - %.1f dmg, %.4f cost/shot)",
                 weapon_name, damage_min, damage_max, cost_per_shot)

    def load_from_loadout_stats(self, weapon_name: str, stats) -> None:
        """Load a signature from a LoadoutStats object."""
        if not weapon_name or stats.damage_interval_min <= 0:
            return
        self.load_signature(
            weapon_name=weapon_name,
            damage_min=stats.damage_interval_min,
            damage_max=stats.damage_interval_max,
            total_damage=stats.total_damage,
            cost_per_shot=stats.cost,
        )

    def infer_tool(self, damage: float) -> tuple[str | None, float, float]:
        """Match a damage value to known signatures.

        Returns (weapon_name, confidence, cost_per_shot).
        If no match, returns (None, 0, 0).
        """
        if not self._signatures or damage <= 0:
            return None, 0.0, 0.0

        best_match: str | None = None
        best_confidence = 0.0
        best_cost = 0.0

        for sig in self._signatures:
            if sig.damage_min <= damage <= sig.damage_max:
                # Within damage interval — high confidence
                # Tighter intervals give higher confidence
                interval_width = sig.damage_max - sig.damage_min
                if interval_width > 0:
                    # Narrower intervals → higher confidence
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

    def create_event(self, encounter_id: str, timestamp: datetime,
                     event_type: str, amount: float,
                     tool_name: str | None = None,
                     tool_source: str | None = None,
                     confidence: float = 0.0) -> CombatEventDetail:
        """Create a CombatEventDetail and optionally buffer it for enrichment."""
        event = CombatEventDetail(
            id=str(uuid.uuid4()),
            encounter_id=encounter_id,
            timestamp=timestamp,
            event_type=event_type,
            amount=amount,
            tool_name=tool_name,
            tool_source=tool_source,
            inferred_confidence=confidence,
        )
        return event

    def buffer_event(self, event: CombatEventDetail):
        """Buffer an event for retroactive enrichment when OCR arrives late."""
        self._pending_events.append(event)
        self._trim_buffer()

    def enrich_buffered(self, tool_name: str, source: str) -> list[CombatEventDetail]:
        """Back-fill buffered events with newly-arrived tool info.

        Called when OCR or another source identifies the active tool.
        Returns the list of events that were enriched.
        """
        self._trim_buffer()
        enriched = []
        for event in self._pending_events:
            if event.tool_name is None:
                event.tool_name = tool_name
                event.tool_source = source
                event.inferred_confidence = 1.0 if source == "ocr" else 0.8
                enriched.append(event)
        self._pending_events.clear()
        if enriched:
            log.info("Retroactively enriched %d events with tool: %s", len(enriched), tool_name)
        return enriched

    def clear(self):
        """Reset all state."""
        self._signatures.clear()
        self._pending_events.clear()

    def _trim_buffer(self):
        """Remove events older than the buffer window."""
        cutoff = datetime.utcnow() - BUFFER_WINDOW
        self._pending_events = [e for e in self._pending_events if e.timestamp > cutoff]
