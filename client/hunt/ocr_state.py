"""OCR state tracker — collects readings from OCR detectors.

All OCR data is optional and unreliable. The tracker provides a
centralized view of the latest readings and staleness detection
so the hunt tracker can use OCR as supporting evidence without
coupling OCR-specific logic into the main tracking code.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ..core.constants import (
    EVENT_PLAYER_STATUS_UPDATE, EVENT_PLAYER_STATUS_LOST,
    EVENT_TARGET_LOCK_UPDATE, EVENT_TARGET_LOCK_LOST,
    EVENT_RADAR_COORDINATES, EVENT_RADAR_LOST,
    EVENT_ACTIVE_TOOL_CHANGED,
)
from ..core.logger import get_logger

log = get_logger("OCRState")


@dataclass
class OCRState:
    """Current state from OCR detectors. All fields optional/unreliable."""

    # Player status (EVENT_PLAYER_STATUS_UPDATE)
    health_pct: float | None = None
    reload_pct: float | None = None
    reload_completed_at: datetime | None = None  # last reload 0->100 transition
    tool_equipped: bool | None = None
    status_last_seen: datetime | None = None

    # Target lock (EVENT_TARGET_LOCK_UPDATE)
    target_hp_pct: float | None = None
    target_is_shared: bool | None = None
    target_raw_name: str | None = None
    target_last_seen: datetime | None = None

    # Location (EVENT_RADAR_COORDINATES)
    lon: float | None = None
    lat: float | None = None
    location_confidence: float = 0.0
    location_last_seen: datetime | None = None

    # Tool (EVENT_ACTIVE_TOOL_CHANGED)
    ocr_tool_name: str | None = None
    tool_last_seen: datetime | None = None


class OCRStateTracker:
    """Subscribes to OCR events and maintains current state.

    Designed for the hunt tracker to query without subscribing
    to individual OCR events directly.
    """

    STALE_THRESHOLD = timedelta(seconds=10)

    def __init__(self, event_bus):
        self._state = OCRState()
        self._prev_reload_pct: float | None = None

        event_bus.subscribe(EVENT_PLAYER_STATUS_UPDATE, self._on_player_status)
        event_bus.subscribe(EVENT_PLAYER_STATUS_LOST, self._on_player_status_lost)
        event_bus.subscribe(EVENT_TARGET_LOCK_UPDATE, self._on_target_lock)
        event_bus.subscribe(EVENT_TARGET_LOCK_LOST, self._on_target_lock_lost)
        event_bus.subscribe(EVENT_RADAR_COORDINATES, self._on_radar)
        event_bus.subscribe(EVENT_RADAR_LOST, self._on_radar_lost)
        event_bus.subscribe(EVENT_ACTIVE_TOOL_CHANGED, self._on_tool)

    @property
    def state(self) -> OCRState:
        return self._state

    def is_stale(self, field: str) -> bool:
        """Check if a specific OCR reading is stale (>10s old or never received)."""
        timestamp_map = {
            "status": self._state.status_last_seen,
            "target": self._state.target_last_seen,
            "location": self._state.location_last_seen,
            "tool": self._state.tool_last_seen,
        }
        ts = timestamp_map.get(field)
        if ts is None:
            return True
        return (datetime.utcnow() - ts) > self.STALE_THRESHOLD

    # -- Event handlers -------------------------------------------------------

    def _on_player_status(self, data):
        now = datetime.utcnow()
        self._state.status_last_seen = now

        if isinstance(data, dict):
            self._state.health_pct = data.get("health_pct")
            new_reload = data.get("reload_pct")
            self._state.tool_equipped = data.get("tool_equipped")

            if new_reload is not None:
                # Detect reload completion: went from <100 to >=100
                if (self._prev_reload_pct is not None
                        and self._prev_reload_pct < 100
                        and new_reload >= 100):
                    self._state.reload_completed_at = now
                self._prev_reload_pct = new_reload
                self._state.reload_pct = new_reload

    def _on_player_status_lost(self, _data):
        self._state.health_pct = None
        self._state.reload_pct = None
        self._state.tool_equipped = None
        self._prev_reload_pct = None

    def _on_target_lock(self, data):
        now = datetime.utcnow()
        self._state.target_last_seen = now

        if isinstance(data, dict):
            self._state.target_hp_pct = data.get("hp_pct")
            self._state.target_is_shared = data.get("is_shared")
            self._state.target_raw_name = data.get("raw_name")

    def _on_target_lock_lost(self, _data):
        self._state.target_hp_pct = None
        self._state.target_is_shared = None
        self._state.target_raw_name = None

    def _on_radar(self, data):
        now = datetime.utcnow()
        self._state.location_last_seen = now

        if isinstance(data, dict):
            self._state.lon = data.get("lon")
            self._state.lat = data.get("lat")
            self._state.location_confidence = data.get("confidence", 0.0)

    def _on_radar_lost(self, _data):
        self._state.lon = None
        self._state.lat = None
        self._state.location_confidence = 0.0

    def _on_tool(self, data):
        now = datetime.utcnow()
        self._state.tool_last_seen = now

        if isinstance(data, dict):
            self._state.ocr_tool_name = data.get("tool_name")
        else:
            self._state.ocr_tool_name = str(data) if data else None
