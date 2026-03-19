"""Human-readable tracking log — shows what the tracker is doing in real-time.

Produces a structured log of chat log entries and OCR enrichment so users
can see exactly how data flows through the tracking pipeline.
"""

from datetime import datetime

from ..core.constants import EVENT_TRACKING_LOG
from ..core.logger import get_logger

log = get_logger("TrackingLog")


class TrackingLog:
    """Produces a visible, human-readable log of tracking activity.

    Each entry is both logged via the Python logger and published as an
    event for potential UI consumption. The log shows:
    - Chat log events as they arrive (damage, loot, death, etc.)
    - OCR readings (tool name, reload state, mob name, lock)
    - Tool attribution decisions (direct OCR, reload correlation, inference)
    - Retroactive corrections
    - Encounter lifecycle events
    """

    MAX_ENTRIES = 500  # Keep last N entries in memory for UI display

    def __init__(self, event_bus):
        self._event_bus = event_bus
        self._entries: list[dict] = []

    @property
    def entries(self) -> list[dict]:
        """Recent log entries in chronological order."""
        return list(self._entries)

    def clear(self):
        self._entries.clear()

    def _emit(self, category: str, message: str, details: dict | None = None):
        """Emit a log entry."""
        entry = {
            "time": datetime.utcnow().isoformat(timespec="milliseconds"),
            "category": category,
            "message": message,
            "details": details or {},
        }
        self._entries.append(entry)
        if len(self._entries) > self.MAX_ENTRIES:
            self._entries = self._entries[-self.MAX_ENTRIES:]

        log.info("[%s] %s", category, message)
        self._event_bus.publish(EVENT_TRACKING_LOG, entry)

    # -- Chat log events ------------------------------------------------------

    def combat_event(self, event_type: str, amount: float, timestamp: datetime):
        """Log a combat event from the chat log."""
        if event_type in ("damage_dealt", "critical_hit"):
            prefix = "CRIT" if event_type == "critical_hit" else "HIT"
            self._emit("combat", f"{prefix} {amount:.1f} dmg", {
                "type": event_type, "amount": amount,
            })
        elif event_type == "damage_received":
            if amount > 0.0:
                self._emit("combat", f"TOOK {amount:.1f} dmg")
            # block (0.0 damage) suppressed from log — still in DB
        elif event_type == "self_heal":
            self._emit("combat", f"HEALED {amount:.1f}")
        elif event_type in ("player_evade", "player_dodge", "player_jam"):
            self._emit("combat", f"Player {event_type.split('_')[1]}")
        elif event_type in ("target_evade", "target_dodge", "target_jam"):
            self._emit("combat", f"Target {event_type.split('_')[1]}")
        elif event_type == "mob_miss":
            self._emit("combat", "Mob missed")
        # deflect and block suppressed from log — still recorded in DB

    def loot_received(self, total_ped: float, item_count: int, mob_name: str | None):
        """Log loot received."""
        mob = f" from {mob_name}" if mob_name else ""
        self._emit("loot", f"LOOT {total_ped:.2f} PED ({item_count} items){mob}")

    def death(self, mob_name: str):
        """Log player death."""
        self._emit("death", f"DIED to {mob_name}")

    def global_event(self, mob_name: str, value: float, is_hof: bool):
        """Log a global event."""
        hof = " (HoF!)" if is_hof else ""
        self._emit("global", f"GLOBAL: {mob_name} — {value:.0f} PED{hof}")

    # -- OCR events -----------------------------------------------------------

    def ocr_tool_detected(self, tool_name: str):
        """Log OCR tool detection."""
        self._emit("ocr", f"Tool: {tool_name}")

    def ocr_reload_drop(self, tool_name: str | None, reload_pct: float):
        """Log reload bar drop."""
        tool = tool_name or "?"
        self._emit("ocr", f"Reload drop → {reload_pct:.0f}% (tool: {tool})")

    def ocr_mob_detected(self, mob_name: str, source: str):
        """Log mob name detection."""
        self._emit("ocr", f"Target: {mob_name} (via {source})")

    def ocr_lock_lost(self):
        """Log target lock lost."""
        self._emit("ocr", "Target lock lost")

    # -- Tool attribution -----------------------------------------------------

    def tool_attributed(self, event_type: str, amount: float,
                        tool_name: str, source: str, confidence: float):
        """Log a tool attribution decision."""
        self._emit("tool", f"{tool_name} ← {amount:.1f} ({source}, {confidence:.0%})", {
            "tool": tool_name, "source": source, "confidence": confidence,
        })

    def tool_retroactive(self, count: int, tool_name: str, source: str):
        """Log retroactive tool attribution."""
        self._emit("tool", f"Retroactive: {count} events → {tool_name} ({source})")

    # -- Encounter lifecycle --------------------------------------------------

    def encounter_started(self, mob_name: str, source: str):
        """Log encounter start."""
        self._emit("encounter", f"Started: {mob_name} ({source})")

    def encounter_ended(self, mob_name: str, outcome: str,
                        damage_dealt: float, cost: float):
        """Log encounter end."""
        self._emit("encounter", (
            f"Ended: {mob_name} — {outcome} "
            f"(dmg: {damage_dealt:.1f}, cost: {cost:.4f} PED)"
        ))

    def session_started(self, session_id: str):
        """Log session start."""
        self._emit("session", f"Session started: {session_id[:8]}")

    def session_ended(self, session_id: str, kills: int, cost: float):
        """Log session end."""
        self._emit("session", f"Session ended: {kills} kills, {cost:.2f} PED cost")

    def recalculated(self, encounter_count: int):
        """Log full recalculation."""
        self._emit("session", f"Stats recalculated for {encounter_count} encounters")

    def session_info(self, message: str):
        """Log a general session/system info message."""
        self._emit("session", message)
