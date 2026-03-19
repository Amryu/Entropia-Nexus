"""Reload-based tool correlator — uses reload bar transitions to attribute tools.

When the OCR reload bar drops from >=100% to <100%, the currently shown tool
was just fired. This module correlates that transition with recent unattributed
damage events in the CombatActionLog, providing higher-confidence tool
attribution than damage-range inference alone.

Handles:
- Single shots: one damage event attributed per reload drop
- Rapid fire: multiple events between OCR frames all attributed to same tool
- Late OCR: retroactive attribution within a configurable correlation window
"""

from datetime import datetime, timedelta

from ..core.logger import get_logger
from .combat_action_log import CombatActionLog

log = get_logger("ReloadCorr")


class ReloadCorrelator:
    """Correlates reload bar drops with recent damage events for tool attribution.

    Instantiated per session by HuntTracker. Receives reload transitions
    via callback from OCRStateTracker.
    """

    def __init__(self, config, combat_log: CombatActionLog, db):
        self._config = config
        self._combat_log = combat_log
        self._db = db

        self._correlation_window = timedelta(
            milliseconds=getattr(config, 'reload_correlation_window_ms', 500)
        )
        self._enabled = getattr(config, 'reload_correlation_enabled', True)

        # State
        self._last_drop_time: datetime | None = None
        self._last_drop_tool: str | None = None

    def on_reload_drop(self, tool_name: str | None, timestamp: datetime) -> int:
        """Handle a reload bar drop (>=100 → <100).

        Finds unattributed damage events within the correlation window and
        attributes them to the given tool.

        Args:
            tool_name: The tool name from OCR at time of drop. May be None
                       if OCR tool detection is unavailable.
            timestamp: When the drop was detected.

        Returns:
            Number of events retroactively attributed.
        """
        if not self._enabled or not tool_name:
            return 0

        self._last_drop_time = timestamp
        self._last_drop_tool = tool_name

        # Find damage events that can be upgraded to ocr_reload within the window
        window_start = timestamp - self._correlation_window
        upgradeable = self._combat_log.get_upgradeable_since(window_start, "ocr_reload")

        if not upgradeable:
            return 0

        attributed_count = 0
        for action in upgradeable:
            # Only attribute events that are within the window
            if action.timestamp > timestamp:
                continue  # Future events (shouldn't happen, but be safe)

            updated = self._combat_log.update_tool(
                action.id, tool_name, "ocr_reload", 0.95
            )
            if updated:
                # Also update the DB record
                self._db.update_combat_event_tool(
                    action.id, tool_name, "ocr_reload", 0.95
                )
                attributed_count += 1

        if attributed_count:
            log.debug("Reload drop: attributed %d events to %s",
                      attributed_count, tool_name)

        return attributed_count

    @property
    def last_drop_tool(self) -> str | None:
        """The tool that was active at the last reload drop."""
        return self._last_drop_tool

    @property
    def last_drop_time(self) -> datetime | None:
        """Timestamp of the last reload drop."""
        return self._last_drop_time
