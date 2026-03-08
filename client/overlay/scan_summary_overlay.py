"""Scan summary overlay — compact draggable panel showing live scan results.

Displays skill readings as they arrive, highlights mismatches, shows scan
progress counts, and provides a 'Mark Complete' button.  Uses the same
Window-style dark theme as the detail and map overlays.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Callable

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QWidget, QPushButton, QScrollArea,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QTimer

from .overlay_widget import OverlayWidget
from ..ui.icons import svg_icon
from ..ocr.models import SkillReading, SkillScanResult, ScanProgress
from ..core.constants import (
    EVENT_SKILL_SCANNED, EVENT_OCR_PROGRESS,
    EVENT_OCR_COMPLETE, EVENT_OCR_PAGE_CHANGED, EVENT_OCR_CANCEL,
    EVENT_OCR_OVERLAYS_HIDE, EVENT_OCR_MANUAL_TRIGGER,
)
from ..core.logger import get_logger

if TYPE_CHECKING:
    from .overlay_manager import OverlayManager
    from ..core.event_bus import EventBus

log = get_logger("ScanSummary")

# --- Layout ---
SUMMARY_WIDTH = 360
BODY_HEIGHT = 300

# --- Colors (matching detail_overlay dark theme) ---
BG_COLOR = "rgba(20, 20, 30, 180)"
TITLE_BG = "rgba(30, 30, 45, 200)"
TEXT_COLOR = "#e0e0e0"
TEXT_DIM = "#999999"
TEXT_BRIGHT = "#ffffff"
ACCENT = "#00ccff"
FOOTER_BG = "rgba(25, 25, 40, 160)"
WARNING_COLOR = "#f59e0b"
WARNING_BG = "rgba(245, 158, 11, 20)"
EXCLUDED_SKILL_NAMES = {"Promoter Rating", "Reputation"}
SCAN_ACTIVE_COLOR = "#00ccff"
SCAN_DONE_COLOR = "#55dd88"
SCAN_IDLE_COLOR = "#777777"

# --- SVG icons ---
_CLOSE_SVG = (
    '<path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59'
    ' 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>'
)

_BTN_STYLE = (
    "QPushButton {"
    "  background: transparent; border: none; border-radius: 3px;"
    "  padding: 0px; margin: 0px;"
    "}"
    "QPushButton:hover {"
    "  background-color: rgba(60, 60, 80, 200);"
    "}"
)
_SPINNER_FRAMES = ("|", "/", "-", "\\")


class ScanSummaryOverlay(OverlayWidget):
    """Compact draggable overlay showing scan results with validation."""

    # Bridge signals (worker thread -> Qt main thread)
    _skill_signal = pyqtSignal(object)
    _progress_signal = pyqtSignal(object)
    _complete_signal = pyqtSignal(object)
    _page_changed_signal = pyqtSignal(object)
    _hide_signal = pyqtSignal(object)

    # Outbound
    scan_marked_complete = pyqtSignal(list)  # list[SkillReading]
    scan_entries_cleared = pyqtSignal()

    def __init__(
        self,
        *,
        config,
        config_path: str,
        event_bus: EventBus,
        manager: OverlayManager | None = None,
        skill_values_fn: Callable[[], dict[str, float]] | None = None,
    ):
        super().__init__(
            config=config,
            config_path=config_path,
            position_key="scan_summary_overlay_position",
            manager=manager,
        )
        self._event_bus = event_bus
        self._get_previous_values = skill_values_fn or (lambda: {})
        self._total_skill_count = 0  # set by first progress event
        self._dismissed = False  # True after user/system dismiss; blocks auto-show
        self._skills: list[SkillReading] = []
        self._skill_set: set[str] = set()
        self._skill_rows: dict[str, QWidget] = {}  # skill_name → row widget
        self._warning_count = 0
        self._click_origin: QPoint | None = None
        self._spinner_idx = 0
        self._spinner_timer = QTimer(self)
        self._spinner_timer.setInterval(120)
        self._spinner_timer.timeout.connect(self._tick_spinner)

        # Batch incoming skill readings to avoid per-skill UI rebuilds
        self._pending_skills: list[SkillReading] = []
        self._flush_timer = QTimer(self)
        self._flush_timer.setSingleShot(True)
        self._flush_timer.setInterval(50)
        self._flush_timer.timeout.connect(self._flush_pending_skills)

        # Auto-resize to content (required for minify to shrink the window)
        self.layout().setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)

        # --- Build UI inside _container ---
        self._container.setFixedWidth(SUMMARY_WIDTH)
        self._container.setStyleSheet(
            f"background-color: {BG_COLOR}; border-radius: 8px; padding: 0px;"
        )

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Title bar
        self._title_bar = self._build_title_bar()
        layout.addWidget(self._title_bar)

        # Body (hidden when minified)
        self._body = QWidget()
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(8, 4, 8, 4)
        body_layout.setSpacing(4)

        # Header: count + warnings
        header = QHBoxLayout()
        self._count_label = QLabel("0/165 skills read")
        self._count_label.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 11px; font-weight: bold;"
            " background: transparent;"
        )
        header.addWidget(self._count_label)
        header.addStretch()
        self._warning_label = QLabel("")
        self._warning_label.setStyleSheet(
            f"color: {WARNING_COLOR}; font-size: 11px; background: transparent;"
        )
        self._warning_label.setVisible(False)
        header.addWidget(self._warning_label)
        body_layout.addLayout(header)

        # Scrollable skill list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(BODY_HEIGHT)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 6px; background: transparent; }"
            "QScrollBar::handle:vertical {"
            "  background: rgba(255,255,255,40); border-radius: 3px;"
            "}"
        )
        self._skill_list_widget = QWidget()
        self._skill_list_widget.setStyleSheet("background: transparent;")
        self._skill_list_layout = QVBoxLayout(self._skill_list_widget)
        self._skill_list_layout.setContentsMargins(0, 0, 0, 0)
        self._skill_list_layout.setSpacing(1)
        self._skill_list_layout.addStretch()
        scroll.setWidget(self._skill_list_widget)
        body_layout.addWidget(scroll)

        # Footer: unread info + mark complete
        footer = QWidget()
        footer.setStyleSheet(
            f"background-color: {FOOTER_BG};"
            " border-bottom-left-radius: 8px;"
            " border-bottom-right-radius: 8px;"
        )
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(8, 4, 8, 4)

        self._total_label = QLabel("Total: 0")
        self._total_label.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 10px; font-weight: bold;"
            " background: transparent;"
        )
        footer_layout.addWidget(self._total_label)
        footer_layout.addStretch()

        self._scan_status = QLabel("")
        self._scan_status.setFixedWidth(16)
        self._scan_status.setAlignment(
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
        )
        self._scan_status.setStyleSheet(
            f"color: {SCAN_IDLE_COLOR}; font-size: 11px; background: transparent;"
        )
        self._scan_status.setToolTip("Idle")
        footer_layout.addWidget(self._scan_status)

        clear_color = "#ff6b6b"
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.setStyleSheet(
            f"color: {clear_color}; font-size: 10px;"
            f" background: transparent; border: 1px solid {clear_color};"
            " border-radius: 3px; padding: 2px 8px;"
        )
        self._clear_btn.clicked.connect(self._on_clear)
        footer_layout.addWidget(self._clear_btn)

        self._rescan_btn = QPushButton("Re-Scan")
        self._rescan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rescan_btn.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 10px;"
            f" background: transparent; border: 1px solid {TEXT_DIM};"
            " border-radius: 3px; padding: 2px 8px;"
        )
        self._rescan_btn.setToolTip("Scan the currently visible Skills page again")
        self._rescan_btn.clicked.connect(self._on_rescan)
        footer_layout.addWidget(self._rescan_btn)

        self._complete_btn = QPushButton("Mark Complete")
        self._complete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._complete_btn.setEnabled(False)
        self._complete_btn.clicked.connect(self._on_mark_complete)
        self._update_complete_btn_style()
        footer_layout.addWidget(self._complete_btn)

        body_layout.addWidget(footer)
        layout.addWidget(self._body)

        # --- Wire bridge signals ---
        self._skill_signal.connect(self._on_skill)
        self._progress_signal.connect(self._on_progress)
        self._complete_signal.connect(self._on_complete)
        self._page_changed_signal.connect(self._on_page_changed)
        self._hide_signal.connect(self._on_overlays_hide)

        self._cb_skill = lambda d: self._skill_signal.emit(d)
        self._cb_progress = lambda d: self._progress_signal.emit(d)
        self._cb_complete = lambda d: self._complete_signal.emit(d)
        self._cb_page = lambda d: self._page_changed_signal.emit(d)
        self._cb_hide = lambda d: self._hide_signal.emit(d)

        event_bus.subscribe(EVENT_SKILL_SCANNED, self._cb_skill)
        event_bus.subscribe(EVENT_OCR_PROGRESS, self._cb_progress)
        event_bus.subscribe(EVENT_OCR_COMPLETE, self._cb_complete)
        event_bus.subscribe(EVENT_OCR_PAGE_CHANGED, self._cb_page)
        event_bus.subscribe(EVENT_OCR_OVERLAYS_HIDE, self._cb_hide)

    # --- Title bar ---

    def _build_title_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(24)
        bar.setStyleSheet(
            f"background-color: {TITLE_BG};"
            " border-top-left-radius: 8px; border-top-right-radius: 8px;"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)

        title = QLabel("Scan Summary")
        title.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 13px; font-weight: bold;"
            " background: transparent;"
        )
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(title, 1, Qt.AlignmentFlag.AlignVCenter)

        close_btn = QPushButton()
        close_btn.setFixedSize(18, 18)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setIcon(svg_icon(_CLOSE_SVG, TEXT_DIM, 14))
        close_btn.setStyleSheet(_BTN_STYLE)
        close_btn.clicked.connect(self._on_close)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        return bar

    # --- Minify (click title bar to toggle body) ---

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._click_origin = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        click_origin = self._click_origin
        self._click_origin = None
        super().mouseReleaseEvent(event)

        if click_origin and event.button() == Qt.MouseButton.LeftButton:
            delta = (
                event.globalPosition().toPoint() - click_origin
            ).manhattanLength()
            if delta < 5:
                click_local = self.mapFromGlobal(click_origin)
                title_bottom = self._title_bar.mapTo(
                    self, QPoint(0, self._title_bar.height()),
                ).y()
                if click_local.y() <= title_bottom:
                    self._toggle_minify()

    def _toggle_minify(self):
        expanding = not self._body.isVisible()
        self._body.setVisible(expanding)
        if expanding:
            self._title_bar.setStyleSheet(
                f"background-color: {TITLE_BG};"
                " border-top-left-radius: 8px; border-top-right-radius: 8px;"
            )
        else:
            self._title_bar.setStyleSheet(
                f"background-color: {TITLE_BG}; border-radius: 8px;"
            )

    # --- Event handlers ---

    def _on_skill(self, reading: SkillReading):
        """Buffer incoming skills and flush in batches to avoid per-skill rebuilds."""
        self._pending_skills.append(reading)
        if not self._flush_timer.isActive():
            self._flush_timer.start()

    def _flush_pending_skills(self):
        """Process all buffered skill readings in one batch."""
        if not self._pending_skills:
            return

        batch = self._pending_skills
        self._pending_skills = []

        for reading in batch:
            if reading.skill_name in self._skill_set:
                # Re-scan: update existing reading in-place
                for i, s in enumerate(self._skills):
                    if s.skill_name == reading.skill_name:
                        self._skills[i] = reading
                        break
            else:
                self._skill_set.add(reading.skill_name)
                self._skills.append(reading)

        self._resort_and_rebuild_rows()
        self._update_counts()

        if not self._complete_btn.isEnabled():
            self._set_complete_enabled(True)

        if not self._dismissed and not self.wants_visible:
            self.set_wants_visible(True)

    def _on_progress(self, progress: ScanProgress):
        self._total_skill_count = progress.total_skills_expected
        self._update_counts()
        self._set_scan_done()

        if not self._dismissed and not self.wants_visible:
            self.set_wants_visible(True)

    def _on_overlays_hide(self, _data):
        """Skills window closed or lost — hide overlay (re-shows when scan resumes)."""
        # Allow auto-show again once the Skills window is reopened.
        self._dismissed = False
        self._set_scan_idle()
        self.set_wants_visible(False)

    def _on_page_changed(self, _data):
        # Keep accumulating across pages — don't clear
        self._set_scan_scanning()

    def _on_complete(self, result: SkillScanResult):
        self._resort_and_rebuild_rows()
        if self._skills:
            self._set_complete_enabled(True)
        self._update_counts()
        self._set_scan_done()

    # --- Compact skill row ---

    def _make_skill_row(self, reading: SkillReading) -> QWidget:
        row = QWidget()
        row.setFixedHeight(18)

        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(8)

        name = QLabel(reading.skill_name)
        name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(name, 1)

        rank = QLabel(reading.rank)
        rank.setFixedWidth(80)
        layout.addWidget(rank)

        points = QLabel("")
        points.setFixedWidth(105)
        points.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(points)

        # Cache label handles for in-place updates.
        row._name_label = name
        row._rank_label = rank
        row._points_label = points

        self._update_skill_row(row, reading)

        return row

    # --- Helpers ---

    def _update_complete_btn_style(self):
        """Update Mark Complete button appearance based on enabled state."""
        if self._complete_btn.isEnabled():
            self._complete_btn.setStyleSheet(
                f"color: {ACCENT}; font-size: 10px;"
                f" background: transparent; border: 1px solid {ACCENT};"
                " border-radius: 3px; padding: 2px 8px;"
            )
            self._complete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self._complete_btn.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 10px;"
                f" background: transparent; border: 1px solid rgba(100,100,100,80);"
                " border-radius: 3px; padding: 2px 8px;"
            )
            self._complete_btn.setCursor(Qt.CursorShape.ArrowCursor)

    def _set_complete_enabled(self, enabled: bool):
        """Enable/disable Mark Complete with visual feedback."""
        self._complete_btn.setEnabled(enabled)
        self._update_complete_btn_style()

    def _update_counts(self):
        counted_skills = [
            s for s in self._skills
            if s.skill_name not in EXCLUDED_SKILL_NAMES
        ]

        self._warning_count = sum(1 for s in counted_skills if s.is_mismatch)
        self._count_label.setText(
            f"{len(counted_skills)}/{self._total_skill_count} skills read"
        )
        if self._warning_count > 0:
            self._warning_label.setText(f"{self._warning_count} warnings")
            self._warning_label.setVisible(True)
        else:
            self._warning_label.setVisible(False)

        total = sum(math.trunc(s.current_points) for s in counted_skills)
        self._total_label.setText(f"Total: {total}")

    def _on_close(self):
        self._dismissed = True
        self.set_wants_visible(False)

    def _on_clear(self):
        self._event_bus.publish(EVENT_OCR_CANCEL, None)
        self.scan_entries_cleared.emit()
        self.reset()
        self.set_wants_visible(True)

    def _on_rescan(self):
        self._set_scan_scanning()
        self._event_bus.publish(EVENT_OCR_MANUAL_TRIGGER, None)
        self.set_wants_visible(True)

    def _on_mark_complete(self):
        self._event_bus.publish(EVENT_OCR_CANCEL, {"pause_until_reopen": True})
        self.scan_marked_complete.emit(list(self._skills))
        self.scan_entries_cleared.emit()
        self.reset()
        self.set_wants_visible(True)

    def reset(self):
        """Reset state for a new scan."""
        self._flush_timer.stop()
        self._pending_skills.clear()
        self._skills.clear()
        self._skill_set.clear()
        self._skill_rows.clear()
        self._warning_count = 0
        # Clear row widgets (keep the stretch spacer at the end) without repaint churn.
        self._skill_list_widget.setUpdatesEnabled(False)
        try:
            while self._skill_list_layout.count() > 1:
                item = self._skill_list_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        finally:
            self._skill_list_widget.setUpdatesEnabled(True)
            self._skill_list_widget.update()
        self._update_counts()
        self._set_scan_idle()
        self._clear_btn.setVisible(True)
        self._clear_btn.setEnabled(True)
        self._set_complete_enabled(False)

    def _tick_spinner(self):
        self._spinner_idx = (self._spinner_idx + 1) % len(_SPINNER_FRAMES)
        self._scan_status.setText(_SPINNER_FRAMES[self._spinner_idx])

    def _set_scan_scanning(self):
        if not self._spinner_timer.isActive():
            self._spinner_idx = 0
            self._scan_status.setText(_SPINNER_FRAMES[0])
            self._spinner_timer.start()
        self._scan_status.setStyleSheet(
            f"color: {SCAN_ACTIVE_COLOR}; font-size: 11px; background: transparent;"
        )
        self._scan_status.setToolTip("Scanning page...")

    def _set_scan_done(self):
        if self._spinner_timer.isActive():
            self._spinner_timer.stop()
        self._scan_status.setText("✓")
        self._scan_status.setStyleSheet(
            f"color: {SCAN_DONE_COLOR}; font-size: 11px; background: transparent;"
        )
        self._scan_status.setToolTip("Page scan complete")

    def _set_scan_idle(self):
        if self._spinner_timer.isActive():
            self._spinner_timer.stop()
        self._scan_status.setText("")
        self._scan_status.setStyleSheet(
            f"color: {SCAN_IDLE_COLOR}; font-size: 11px; background: transparent;"
        )
        self._scan_status.setToolTip("Idle")

    def _resort_and_rebuild_rows(self):
        # Warnings first; otherwise highest points first.
        self._skills.sort(
            key=lambda s: (0 if s.is_mismatch else 1, -s.current_points, s.skill_name.lower())
        )

        self._skill_list_widget.setUpdatesEnabled(False)
        try:
            for row in self._skill_rows.values():
                self._skill_list_layout.removeWidget(row)

            for reading in self._skills:
                row = self._skill_rows.get(reading.skill_name)
                if row is None:
                    row = self._make_skill_row(reading)
                    self._skill_rows[reading.skill_name] = row
                else:
                    self._update_skill_row(row, reading)
                idx = self._skill_list_layout.count() - 1
                self._skill_list_layout.insertWidget(idx, row)
        finally:
            self._skill_list_widget.setUpdatesEnabled(True)
            self._skill_list_widget.update()

    def _update_skill_row(self, row: QWidget, reading: SkillReading):
        if reading.is_mismatch:
            row.setStyleSheet(
                f"background-color: {WARNING_BG}; border-radius: 2px;"
            )
        else:
            row.setStyleSheet("background: transparent;")

        text_color = WARNING_COLOR if reading.is_mismatch else TEXT_COLOR

        name = row._name_label
        name.setText(reading.skill_name)
        name.setStyleSheet(
            f"color: {text_color}; font-size: 10px; background: transparent;"
        )

        rank = row._rank_label
        rank.setText(reading.rank)
        rank.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 10px; background: transparent;"
        )

        points_text = f"{reading.current_points:.2f}"
        if reading.estimated_points > 0 and reading.current_points <= 10000:
            diff = reading.current_points - reading.estimated_points
            sign = "+" if diff >= 0 else ""
            points_text += f" ({sign}{diff:.0f})"

        points = row._points_label
        points.setText(points_text)
        points.setStyleSheet(
            f"color: {text_color}; font-size: 10px; background: transparent;"
        )

    # --- Cleanup ---

    def stop(self):
        """Unsubscribe from events."""
        self._flush_timer.stop()
        self._spinner_timer.stop()
        self._event_bus.unsubscribe(EVENT_SKILL_SCANNED, self._cb_skill)
        self._event_bus.unsubscribe(EVENT_OCR_PROGRESS, self._cb_progress)
        self._event_bus.unsubscribe(EVENT_OCR_COMPLETE, self._cb_complete)
        self._event_bus.unsubscribe(EVENT_OCR_PAGE_CHANGED, self._cb_page)
        self._event_bus.unsubscribe(EVENT_OCR_OVERLAYS_HIDE, self._cb_hide)
        self.close()
