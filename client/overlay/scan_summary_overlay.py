"""Scan summary overlay — compact draggable panel showing live scan results.

Displays skill readings as they arrive, highlights mismatches, shows scan
progress counts, and provides a 'Mark Complete' button.  Uses the same
Window-style dark theme as the detail and map overlays.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QWidget, QPushButton, QScrollArea,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal

from .overlay_widget import OverlayWidget
from ..ui.icons import svg_icon
from ..ocr.models import SkillReading, SkillScanResult, ScanProgress
from ..core.constants import (
    EVENT_SKILL_SCANNED, EVENT_OCR_PROGRESS,
    EVENT_OCR_COMPLETE, EVENT_OCR_PAGE_CHANGED, EVENT_OCR_CANCEL,
    EVENT_OCR_OVERLAYS_HIDE,
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

        cancel_color = "#ff6b6b"
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setStyleSheet(
            f"color: {cancel_color}; font-size: 10px;"
            f" background: transparent; border: 1px solid {cancel_color};"
            " border-radius: 3px; padding: 2px 8px;"
        )
        self._cancel_btn.clicked.connect(self._on_cancel)
        footer_layout.addWidget(self._cancel_btn)

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
        if reading.skill_name in self._skill_set:
            # Re-scan: update existing reading and row widget
            for i, s in enumerate(self._skills):
                if s.skill_name == reading.skill_name:
                    old_mismatch = s.is_mismatch
                    self._skills[i] = reading
                    if old_mismatch and not reading.is_mismatch:
                        self._warning_count = max(0, self._warning_count - 1)
                    elif not old_mismatch and reading.is_mismatch:
                        self._warning_count += 1
                    break
            # Replace the row widget in-place
            old_row = self._skill_rows.get(reading.skill_name)
            if old_row is not None:
                idx = self._skill_list_layout.indexOf(old_row)
                if idx >= 0:
                    self._skill_list_layout.removeWidget(old_row)
                    old_row.deleteLater()
                    new_row = self._make_skill_row(reading)
                    self._skill_list_layout.insertWidget(idx, new_row)
                    self._skill_rows[reading.skill_name] = new_row
            self._update_counts()
            return

        self._skill_set.add(reading.skill_name)
        self._skills.append(reading)

        if reading.is_mismatch:
            self._warning_count += 1

        # Insert row before the stretch spacer
        row = self._make_skill_row(reading)
        idx = self._skill_list_layout.count() - 1
        self._skill_list_layout.insertWidget(idx, row)
        self._skill_rows[reading.skill_name] = row

        self._update_counts()

        # Enable Mark Complete as soon as first skill is scanned
        if not self._complete_btn.isEnabled():
            self._set_complete_enabled(True)

        if not self._dismissed and not self.wants_visible:
            self.set_wants_visible(True)

    def _on_progress(self, progress: ScanProgress):
        self._total_skill_count = progress.total_skills_expected
        self._update_counts()

        if not self._dismissed and not self.wants_visible:
            self.set_wants_visible(True)

    def _on_overlays_hide(self, _data):
        """Skills window closed or lost — hide overlay (re-shows when scan resumes)."""
        self.set_wants_visible(False)

    def _on_page_changed(self, _data):
        # Keep accumulating across pages — don't clear
        pass

    def _on_complete(self, result: SkillScanResult):
        self._cancel_btn.setVisible(False)
        if self._skills:
            self._set_complete_enabled(True)
        self._update_counts()

    # --- Compact skill row ---

    def _make_skill_row(self, reading: SkillReading) -> QWidget:
        row = QWidget()
        row.setFixedHeight(18)

        if reading.is_mismatch:
            row.setStyleSheet(
                f"background-color: {WARNING_BG}; border-radius: 2px;"
            )
        else:
            row.setStyleSheet("background: transparent;")

        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(8)

        text_color = WARNING_COLOR if reading.is_mismatch else TEXT_COLOR

        name = QLabel(reading.skill_name)
        name.setStyleSheet(
            f"color: {text_color}; font-size: 10px; background: transparent;"
        )
        name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(name, 1)

        rank = QLabel(reading.rank)
        rank.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 10px; background: transparent;"
        )
        rank.setFixedWidth(80)
        layout.addWidget(rank)

        points_text = f"{reading.current_points:.2f}"
        if reading.estimated_points > 0 and reading.current_points <= 10000:
            diff = reading.current_points - reading.estimated_points
            sign = "+" if diff >= 0 else ""
            points_text += f" ({sign}{diff:.0f})"
        points = QLabel(points_text)
        points.setStyleSheet(
            f"color: {text_color}; font-size: 10px; background: transparent;"
        )
        points.setFixedWidth(105)
        points.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(points)

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
        self._count_label.setText(
            f"{len(self._skills)}/{self._total_skill_count} skills read"
        )
        if self._warning_count > 0:
            self._warning_label.setText(f"{self._warning_count} warnings")
            self._warning_label.setVisible(True)
        else:
            self._warning_label.setVisible(False)

        total = sum(s.current_points for s in self._skills)
        self._total_label.setText(f"Total: {total:.2f}")

    def _on_close(self):
        self._dismissed = True
        self.set_wants_visible(False)

    def _on_cancel(self):
        self._event_bus.publish(EVENT_OCR_CANCEL, None)
        self._dismissed = True
        self.reset()
        self.set_wants_visible(False)

    def _on_mark_complete(self):
        # Stop any ongoing scan
        if self._cancel_btn.isVisible():
            self._event_bus.publish(EVENT_OCR_CANCEL, None)
        self.scan_marked_complete.emit(list(self._skills))
        self._dismissed = True
        self.reset()
        self.set_wants_visible(False)

    def reset(self):
        """Reset state for a new scan."""
        self._skills.clear()
        self._skill_set.clear()
        self._skill_rows.clear()
        self._warning_count = 0
        # Clear row widgets (keep the stretch spacer at the end)
        while self._skill_list_layout.count() > 1:
            item = self._skill_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._update_counts()
        self._cancel_btn.setVisible(True)
        self._cancel_btn.setEnabled(True)
        self._set_complete_enabled(False)

    # --- Cleanup ---

    def stop(self):
        """Unsubscribe from events."""
        self._event_bus.unsubscribe(EVENT_SKILL_SCANNED, self._cb_skill)
        self._event_bus.unsubscribe(EVENT_OCR_PROGRESS, self._cb_progress)
        self._event_bus.unsubscribe(EVENT_OCR_COMPLETE, self._cb_complete)
        self._event_bus.unsubscribe(EVENT_OCR_PAGE_CHANGED, self._cb_page)
        self._event_bus.unsubscribe(EVENT_OCR_OVERLAYS_HIDE, self._cb_hide)
        self.close()
