"""OCR scan progress overlay — Qt-based, always-on-top, draggable, position persisted."""

from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from .base_overlay import BaseOverlay
from ..core.event_bus import EventBus
from ..core.constants import (
    EVENT_OCR_PROGRESS, EVENT_OCR_COMPLETE,
    EVENT_OCR_OVERLAYS_HIDE, EVENT_OCR_OVERLAYS_SHOW,
    EVENT_DEBUG_REGIONS,
)
from ..ocr.models import ScanProgress, SkillScanResult


AUTO_HIDE_DELAY_MS = 5000

ACCENT_COLOR = "#00d4aa"
FG_COLOR = "#e0e0e0"
DIM_COLOR = "#888888"


class ProgressOverlay(BaseOverlay):
    """Small always-on-top overlay that shows OCR scan progress.

    Displays:
    - Total skills found / expected
    - Current category being scanned
    - Current page / total pages
    - Individual missing skill names when 10 or fewer remain

    Auto-hides 5 seconds after scan completion.
    """

    # Bridge signals for cross-thread dispatch (EventBus → Qt main thread)
    _progress_signal = pyqtSignal(object)
    _complete_signal = pyqtSignal(object)
    _hide_signal = pyqtSignal(object)    # data: done_callback
    _show_signal = pyqtSignal()
    _regions_signal = pyqtSignal(object)

    def __init__(self, *, config, config_path: str, event_bus: EventBus):
        super().__init__(
            config=config,
            config_path=config_path,
            position_key="progress_overlay_position",
        )
        self._event_bus = event_bus
        self._was_visible_before_hide = False
        self._hide_timer = None

        self.setMinimumWidth(320)

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        # Title
        title = QLabel("Skills Scan")
        title.setStyleSheet(
            f"color: {ACCENT_COLOR}; font-weight: bold; font-size: 11px;"
        )
        layout.addWidget(title)

        # Progress (e.g. "47 / 165 skills")
        self._progress_label = QLabel("Initializing...")
        self._progress_label.setStyleSheet(
            f"color: {FG_COLOR}; font-weight: bold; font-size: 14px;"
        )
        layout.addWidget(self._progress_label)

        # Category + page row
        info_row = QHBoxLayout()
        info_row.setContentsMargins(0, 0, 0, 0)

        self._category_label = QLabel("")
        self._category_label.setStyleSheet(
            f"color: {DIM_COLOR}; font-size: 9px;"
        )
        info_row.addWidget(self._category_label)

        info_row.addStretch()

        self._page_label = QLabel("")
        self._page_label.setStyleSheet(
            f"color: {DIM_COLOR}; font-size: 9px;"
        )
        info_row.addWidget(self._page_label)

        layout.addLayout(info_row)

        # Missing skills container (shown when ≤10 remain)
        self._missing_layout = QVBoxLayout()
        self._missing_layout.setContentsMargins(0, 4, 0, 0)
        self._missing_layout.setSpacing(0)
        layout.addLayout(self._missing_layout)
        self._missing_labels: list[QLabel] = []

        # Status line (shown on completion)
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            f"color: {ACCENT_COLOR}; font-size: 9px;"
        )
        layout.addWidget(self._status_label)

        # Wire bridge signals → slots
        self._progress_signal.connect(self._update_progress)
        self._complete_signal.connect(self._show_complete)
        self._hide_signal.connect(self._do_hide_for_capture)
        self._show_signal.connect(self._do_show_after_capture)
        self._regions_signal.connect(self._reposition_on_window)

        # Subscribe to EventBus (callbacks come from worker threads)
        self._event_bus.subscribe(EVENT_OCR_PROGRESS, self._on_progress)
        self._event_bus.subscribe(EVENT_OCR_COMPLETE, self._on_complete)
        self._event_bus.subscribe(EVENT_OCR_OVERLAYS_HIDE, self._on_hide_request)
        self._event_bus.subscribe(EVENT_OCR_OVERLAYS_SHOW, self._on_show_request)
        self._event_bus.subscribe(EVENT_DEBUG_REGIONS, self._on_regions)

        self.hide()  # Hidden until scan starts

    def stop(self):
        """Unsubscribe from events."""
        self._event_bus.unsubscribe(EVENT_OCR_PROGRESS, self._on_progress)
        self._event_bus.unsubscribe(EVENT_OCR_COMPLETE, self._on_complete)
        self._event_bus.unsubscribe(EVENT_OCR_OVERLAYS_HIDE, self._on_hide_request)
        self._event_bus.unsubscribe(EVENT_OCR_OVERLAYS_SHOW, self._on_show_request)
        self._event_bus.unsubscribe(EVENT_DEBUG_REGIONS, self._on_regions)

    # --- EventBus callbacks (called from worker threads) ---

    def _on_progress(self, progress: ScanProgress):
        self._progress_signal.emit(progress)

    def _on_complete(self, result: SkillScanResult):
        self._complete_signal.emit(result)

    def _on_hide_request(self, done_callback):
        self._hide_signal.emit(done_callback)

    def _on_show_request(self, _data):
        self._show_signal.emit()

    def _on_regions(self, data: dict):
        window = data.get("window")
        if window:
            self._regions_signal.emit(window)

    # --- Qt main-thread slots ---

    def _update_progress(self, progress: ScanProgress):
        """Update UI with current progress."""
        if not self.isVisible():
            self.show()

        # Cancel any pending auto-hide
        if self._hide_timer is not None:
            self._hide_timer.stop()
            self._hide_timer = None

        self._progress_label.setText(
            f"{progress.skills_found} / {progress.total_skills_expected} skills"
        )
        self._category_label.setText(progress.current_category)
        self._page_label.setText(
            f"Page {progress.current_page}/{progress.total_pages}"
        )
        self._status_label.setText("")
        self._update_missing_list(progress.missing_names)

    def _show_complete(self, result: SkillScanResult):
        """Show completion state and schedule auto-hide."""
        self._progress_label.setText(
            f"{result.total_found} / {result.total_expected} skills"
        )
        self._category_label.setText("")
        self._page_label.setText("")
        self._status_label.setText("Scan complete!")

        if len(result.missing_skills) <= 10:
            self._update_missing_list(result.missing_skills)
        else:
            self._update_missing_list([])

        # Auto-hide after delay
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)
        self._hide_timer.start(AUTO_HIDE_DELAY_MS)

    def _do_hide_for_capture(self, done_callback):
        """Hide overlay before screen capture, then call done_callback."""
        self._was_visible_before_hide = self.isVisible()
        if self._was_visible_before_hide:
            self.hide()
        done_callback()

    def _do_show_after_capture(self):
        """Restore overlay after screen capture."""
        if self._was_visible_before_hide:
            self.show()

    def _reposition_on_window(self, window_bounds):
        """Move overlay to the bottom of the skills window (~87% height)."""
        wx, wy, _ww, wh = window_bounds
        x = wx
        y = wy + int(wh * 0.87)

        # Clamp to screen bounds
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = max(geo.x(), min(x, geo.right() - self.width()))
            y = max(geo.y(), min(y, geo.bottom() - self.height()))

        self.move(x, y)

    def _update_missing_list(self, names: list[str]):
        """Update the list of missing skill names."""
        # Remove excess labels
        while len(self._missing_labels) > len(names):
            lbl = self._missing_labels.pop()
            self._missing_layout.removeWidget(lbl)
            lbl.deleteLater()

        # Add labels if needed
        while len(self._missing_labels) < len(names):
            lbl = QLabel()
            lbl.setStyleSheet(f"color: {DIM_COLOR}; font-size: 8px;")
            self._missing_layout.addWidget(lbl)
            self._missing_labels.append(lbl)

        # Update text
        for lbl, name in zip(self._missing_labels, names):
            lbl.setText(f"  - {name}")
