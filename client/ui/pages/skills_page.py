"""Skills page — 6-tab interface for skill management, progression, and optimization."""

import csv
import io
import json
import threading
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QScrollArea, QComboBox, QCheckBox,
    QProgressBar, QLineEdit, QDoubleSpinBox, QFrame,
    QSizePolicy, QFileDialog, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QCursor
from PyQt6.QtWidgets import QGraphicsOpacityEffect

from ...core.thread_utils import invoke_on_main

from ...skills.calculations import (
    calculate_all_profession_levels, calculate_profession_level,
    build_attribute_skill_set,
)
from ...skills.badges import get_skill_badges, Badge
from ...skills.skill_ids import id_to_name_map, name_to_id_map
from ...core.logger import get_logger
from ...skills.sync import SkillDataManager
from ..theme import (
    SECONDARY, BORDER, BORDER_HOVER, TEXT_MUTED,
    SUCCESS, SUCCESS_BG, WARNING, WARNING_BG,
    ACCENT, ACCENT_LIGHT, PRIMARY,
)
from ..widgets.multi_line_chart import MultiLineChart, ChartSeries, CHART_COLORS


log = get_logger("SkillsPage")


RANKLESS_CATEGORIES = {"Attributes", "Social"}


def _rank_from_thresholds(points: float, thresholds: list[dict],
                          category: str | None = None) -> tuple[str, float]:
    """Thread-safe rank calculation (no self access)."""
    if category and category in RANKLESS_CATEGORIES:
        return ("", 0.0)
    if not thresholds or points <= 0:
        return ("Inexperienced", 0.0)
    rank_name = thresholds[0]["name"]
    current_threshold = 0
    next_threshold = thresholds[0]["threshold"] if thresholds else 0
    for i, rank in enumerate(thresholds):
        if points >= rank["threshold"]:
            rank_name = rank["name"]
            current_threshold = rank["threshold"]
            next_threshold = (
                thresholds[i + 1]["threshold"]
                if i + 1 < len(thresholds)
                else current_threshold
            )
        else:
            break
    if next_threshold > current_threshold:
        progress = (points - current_threshold) / (next_threshold - current_threshold) * 100
    else:
        progress = 100.0
    return (rank_name, min(progress, 100.0))


# ── Constants ──────────────────────────────────────────────────────────────
CARD_MIN_WIDTH = 180
CARD_MAX_WIDTH = 260
CARD_HEIGHT = 80
CARD_ROW_HEIGHT = CARD_HEIGHT + 6   # card + grid spacing
_CARD_BATCH_ROWS = 2  # max rows of cards to create per event-loop frame
HEADER_ROW_HEIGHT = 36
_HEADER_LABEL_HEIGHT = 24           # actual label height within the row

# badge_type → level → (background, text_color, border_or_none)
BADGE_STYLES = {
    "hp": {
        "high":        (SUCCESS, "#ffffff", None),
        "medium":      (SUCCESS, "#ffffff", None),
        "low":         (SUCCESS_BG, SUCCESS, SUCCESS),
        "ineffective": (SUCCESS_BG, SUCCESS, SUCCESS),
    },
    "loot": {
        "high":   (WARNING, "#000000", None),
        "medium": (WARNING_BG, WARNING, WARNING),
        "low":    ("transparent", WARNING, WARNING),
    },
    "defense": {
        "high":   (ACCENT, "#ffffff", None),
        "medium": (ACCENT_LIGHT, ACCENT, ACCENT),
        "low":    ("transparent", ACCENT, ACCENT),
    },
}

TIME_PERIODS = [
    ("1 hour", 1 / 24),
    ("24 hours", 1),
    ("1 week", 7),
    ("1 month", 30),
    ("3 months", 90),
    ("6 months", 180),
    ("1 year", 365),
    ("All", 0),
]

# Tab indices
TAB_DASHBOARD = 0
TAB_SKILLS = 1
TAB_PROFESSIONS = 2
TAB_ANALYTICS = 3
TAB_OPTIMIZER = 4
TAB_SCANNING = 5

# Pre-computed card styles (avoid per-widget setStyleSheet f-string overhead)
_SKILL_CARD_STYLE = f"""
    SkillCard {{
        background-color: {SECONDARY};
        border: 1px solid {BORDER};
        border-radius: 8px;
    }}
    SkillCard:hover {{
        border-color: {BORDER_HOVER};
    }}
"""
_PROF_CARD_STYLE = f"""
    ProfessionCard {{
        background-color: {SECONDARY};
        border: 1px solid {BORDER};
        border-radius: 8px;
    }}
    ProfessionCard:hover {{
        border-color: {BORDER_HOVER};
    }}
"""
_CARD_NAME_STYLE = "font-weight: bold; font-size: 11px; background: transparent; border: none;"
_CARD_RANK_STYLE = f"font-size: 10px; color: {TEXT_MUTED}; background: transparent; border: none;"
_CARD_POINTS_STYLE = "font-size: 10px; background: transparent; border: none;"
_CARD_WEIGHT_STYLE = f"font-size: 9px; color: {ACCENT}; background: transparent; border: none;"
_CARD_GAIN_STYLE = f"font-size: 9px; color: {SUCCESS}; background: transparent; border: none;"
_CARD_HEADER_STYLE = (
    f"font-weight: bold; font-size: 13px; color: {TEXT_MUTED}; "
    f"border-bottom: 1px solid {BORDER}; padding: 6px 0 2px 0; "
    f"background: transparent;"
)
_BADGE_STYLE_CACHE: dict[tuple, str] = {}


class _ElidedLabel(QLabel):
    """QLabel that truncates text with ellipsis when it doesn't fit."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._full_text = text

    def resizeEvent(self, event):
        super().resizeEvent(event)
        fm = self.fontMetrics()
        elided = fm.elidedText(self._full_text, Qt.TextElideMode.ElideRight,
                               self.width())
        self.setText(elided)


class NumericTableWidgetItem(QTableWidgetItem):
    """Table item with numeric sorting semantics."""

    def __init__(self, text: str, value: float):
        super().__init__(text)
        self._value = float(value)

    def __lt__(self, other):
        if isinstance(other, NumericTableWidgetItem):
            return self._value < other._value
        try:
            return self._value < float(other.text())
        except Exception:
            return super().__lt__(other)


class SkillCard(QFrame):
    """Compact skill card for grid view."""

    clicked = pyqtSignal(str)
    value_edited = pyqtSignal(str, float)

    def __init__(self, skill_name: str, points: float, rank: str,
                 progress: float, badges: list[Badge],
                 dimmed: bool = False, weight: int | None = None,
                 gain: float = 0.0, parent=None):
        super().__init__(parent)
        self._skill_name = skill_name
        self._points = points
        self._editing = False
        self._weight = weight

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMinimumWidth(CARD_MIN_WIDTH)
        self.setMaximumWidth(CARD_MAX_WIDTH)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setToolTip("Click to see related professions. Double-click value to edit.")
        self.setStyleSheet(_SKILL_CARD_STYLE)
        self.setFixedHeight(CARD_HEIGHT)
        if dimmed:
            effect = QGraphicsOpacityEffect(self)
            effect.setOpacity(0.35)
            self.setGraphicsEffect(effect)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        # Row 1: Name + Badges (top-right)
        top_row = QHBoxLayout()
        top_row.setSpacing(4)
        name_label = _ElidedLabel(skill_name)
        name_label.setStyleSheet(_CARD_NAME_STYLE)
        name_label.setFixedHeight(16)
        top_row.addWidget(name_label, 1)

        if badges:
            for badge in badges:
                bl = QLabel(badge.label)
                style = self._badge_style(badge)
                bl.setStyleSheet(style)
                top_row.addWidget(bl)
        layout.addLayout(top_row)

        # Row 2: Rank + Weight + Points
        info_row = QHBoxLayout()
        info_row.setSpacing(4)
        rank_label = QLabel(rank)
        rank_label.setStyleSheet(_CARD_RANK_STYLE)
        info_row.addWidget(rank_label)
        if weight is not None:
            weight_label = QLabel(f"{weight}%")
            weight_label.setStyleSheet(_CARD_WEIGHT_STYLE)
            info_row.addWidget(weight_label)
        info_row.addStretch()

        self._points_label = QLabel(f"{points:.2f}")
        self._points_label.setStyleSheet(_CARD_POINTS_STYLE)
        info_row.addWidget(self._points_label)

        if gain > 0.001:
            gain_label = QLabel(f"+{gain:.4f}")
            gain_label.setStyleSheet(_CARD_GAIN_STYLE)
            info_row.addWidget(gain_label)

        self._edit_input = None  # created lazily on first edit
        self._info_row = info_row

        layout.addLayout(info_row)

        # Row 3: Progress bar
        bar = QProgressBar()
        bar.setMaximum(1000)
        bar.setValue(int(progress * 10))
        bar.setTextVisible(False)
        bar.setFixedHeight(6)
        layout.addWidget(bar)
        layout.addStretch()

    @staticmethod
    def _badge_style(badge: Badge) -> str:
        """Build QSS for a badge label based on type and level (cached)."""
        key = (badge.badge_type, badge.level)
        cached = _BADGE_STYLE_CACHE.get(key)
        if cached is not None:
            return cached
        type_styles = BADGE_STYLES.get(badge.badge_type, {})
        bg, fg, border = type_styles.get(badge.level, ("#666", "#fff", None))
        parts = [
            f"background-color: {bg};",
            f"color: {fg};",
            "font-size: 9px;",
            "font-weight: 600;",
            "padding: 1px 4px;",
            "border-radius: 3px;",
            f"border: 1px solid {border};" if border else "border: none;",
        ]
        style = " ".join(parts)
        _BADGE_STYLE_CACHE[key] = style
        return style

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._skill_name)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_edit()
        super().mouseDoubleClickEvent(event)

    def _ensure_edit_input(self):
        """Create the edit spin box lazily on first use."""
        if self._edit_input is not None:
            return
        self._edit_input = QDoubleSpinBox()
        self._edit_input.setDecimals(2)
        self._edit_input.setMaximum(999999)
        self._edit_input.setMinimumWidth(80)
        self._edit_input.setVisible(False)
        self._edit_input.editingFinished.connect(self._finish_edit)
        self._info_row.addWidget(self._edit_input)

    def _start_edit(self):
        if self._editing:
            return
        self._editing = True
        self._ensure_edit_input()
        self._points_label.setVisible(False)
        self._edit_input.setValue(self._points)
        self._edit_input.setVisible(True)
        self._edit_input.setFocus()
        self._edit_input.selectAll()

    def _finish_edit(self):
        if not self._editing:
            return
        self._editing = False
        new_val = self._edit_input.value()
        self._edit_input.setVisible(False)
        self._points_label.setVisible(True)
        if abs(new_val - self._points) > 0.00001:
            self._points = new_val
            self._points_label.setText(f"{new_val:.2f}")
            self.value_edited.emit(self._skill_name, new_val)


class ProfessionCard(QFrame):
    """Compact profession card for grid view — matches SkillCard layout."""

    clicked = pyqtSignal(str)

    def __init__(self, prof_name: str, level: float, skill_count: int,
                 category: str = "", weight: int | None = None,
                 parent=None):
        super().__init__(parent)
        self._prof_name = prof_name

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMinimumWidth(CARD_MIN_WIDTH)
        self.setMaximumWidth(CARD_MAX_WIDTH)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setToolTip("Click to see contributing skills.")
        self.setStyleSheet(_PROF_CARD_STYLE)
        self.setFixedHeight(CARD_HEIGHT)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        # Row 1: Name
        name_label = _ElidedLabel(prof_name)
        name_label.setStyleSheet(_CARD_NAME_STYLE)
        name_label.setFixedHeight(16)
        layout.addWidget(name_label)

        # Row 2: "Level N" + weight + level value
        info_row = QHBoxLayout()
        info_row.setSpacing(4)
        level_int = int(level)
        rank_label = QLabel(f"Level {level_int}")
        rank_label.setStyleSheet(_CARD_RANK_STYLE)
        info_row.addWidget(rank_label)
        if weight is not None:
            weight_label = QLabel(f"{weight}%")
            weight_label.setStyleSheet(_CARD_WEIGHT_STYLE)
            info_row.addWidget(weight_label)
        info_row.addStretch()
        level_label = QLabel(f"{level:.2f}")
        level_label.setStyleSheet(_CARD_POINTS_STYLE)
        info_row.addWidget(level_label)
        layout.addLayout(info_row)

        # Row 3: Progress bar (fractional part of level)
        bar = QProgressBar()
        bar.setMaximum(1000)
        bar.setValue(int((level - level_int) * 1000))
        bar.setTextVisible(False)
        bar.setFixedHeight(6)
        layout.addWidget(bar)
        layout.addStretch()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._prof_name)
        super().mousePressEvent(event)


class _GoalProgressCard(QFrame):
    """Compact card showing goal progress with bar and stats."""

    edit_clicked = pyqtSignal(int)
    delete_clicked = pyqtSignal(int)
    visibility_toggled = pyqtSignal(int, bool)  # (goal_id, visible)

    # SVG paths for eye icons (16x16 viewBox)
    _EYE_OPEN = (
        '<svg viewBox="0 0 16 16" width="14" height="14">'
        '<path d="M8 3C4.5 3 1.5 5.5 0.5 8c1 2.5 4 5 7.5 5s6.5-2.5 7.5-5c-1-2.5-4-5-7.5-5z" '
        'fill="none" stroke="{color}" stroke-width="1.2"/>'
        '<circle cx="8" cy="8" r="2.5" fill="none" stroke="{color}" stroke-width="1.2"/>'
        '</svg>'
    )
    _EYE_CLOSED = (
        '<svg viewBox="0 0 16 16" width="14" height="14">'
        '<path d="M8 3C4.5 3 1.5 5.5 0.5 8c1 2.5 4 5 7.5 5s6.5-2.5 7.5-5c-1-2.5-4-5-7.5-5z" '
        'fill="none" stroke="{color}" stroke-width="1.2"/>'
        '<circle cx="8" cy="8" r="2.5" fill="none" stroke="{color}" stroke-width="1.2"/>'
        '<line x1="3" y1="13" x2="13" y2="3" stroke="{color}" stroke-width="1.2"/>'
        '</svg>'
    )

    def __init__(self, goal: dict, skill_values: dict[str, float],
                 profession_levels: dict[str, float], *, visible: bool = True,
                 parent=None):
        super().__init__(parent)
        self._goal_id = goal["id"]
        self._goal = goal
        self._visible = visible
        self.setStyleSheet(
            f"_GoalProgressCard {{ background-color: {SECONDARY}; "
            f"border: 1px solid {BORDER}; border-radius: 6px; }}"
        )
        self.setFixedHeight(60)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 20)
        layout.setSpacing(6)

        is_prof = goal["goal_type"] == "profession_level"
        start = goal.get("start_value") or 0
        target = goal["target_value"]

        # Compute progress
        current, pct = self._compute_progress(skill_values, profession_levels)

        # Row 1: name + range (current) + pct + eye + edit + X
        top = QHBoxLayout()
        top.setSpacing(6)

        name_label = QLabel(goal["target_name"])
        name_label.setStyleSheet("font-weight: bold; font-size: 12px; background: transparent; border: none;")
        top.addWidget(name_label)

        if is_prof:
            range_text = f"Lv {start:.1f} \u2192 {target:.1f}"
        else:
            range_text = f"{start:,.0f} \u2192 {target:,.0f} pts"
        range_label = QLabel(range_text)
        range_label.setStyleSheet(f"font-size: 10px; color: {TEXT_MUTED}; background: transparent; border: none;")
        top.addWidget(range_label)

        top.addStretch()

        self._pct_label = QLabel(self._format_progress(is_prof, current, pct))
        self._pct_label.setStyleSheet("font-size: 11px; font-weight: bold; background: transparent; border: none;")
        top.addWidget(self._pct_label)

        # Eye toggle
        eye_btn = QPushButton()
        eye_btn.setFixedSize(20, 20)
        eye_btn.setStyleSheet("padding: 0; border: none; background: transparent;")
        eye_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        eye_btn.setToolTip("Toggle chart visibility")
        eye_btn.clicked.connect(self._toggle_visibility)
        self._eye_btn = eye_btn
        self._update_eye_icon()
        top.addWidget(eye_btn)

        edit_btn = QPushButton("Edit")
        edit_btn.setFixedSize(32, 20)
        edit_btn.setStyleSheet(
            f"font-size: 10px; padding: 0; border: none; background: transparent; color: {ACCENT};"
        )
        edit_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        edit_btn.clicked.connect(lambda: self.edit_clicked.emit(self._goal_id))
        top.addWidget(edit_btn)

        del_btn = QPushButton("X")
        del_btn.setFixedSize(18, 20)
        del_btn.setStyleSheet(
            f"font-size: 10px; padding: 0; border: none; background: transparent; color: {TEXT_MUTED};"
        )
        del_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        del_btn.clicked.connect(lambda: self.delete_clicked.emit(self._goal_id))
        top.addWidget(del_btn)
        layout.addLayout(top)

        # Row 2: full-width progress bar
        self._bar = QProgressBar()
        self._bar.setMaximum(1000)
        self._bar.setValue(int(pct * 10))
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(8)
        layout.addWidget(self._bar)

    def _toggle_visibility(self):
        self._visible = not self._visible
        self._update_eye_icon()
        self.visibility_toggled.emit(self._goal_id, self._visible)

    def _update_eye_icon(self):
        from PyQt6.QtSvg import QSvgRenderer
        from PyQt6.QtGui import QIcon, QPixmap, QPainter as _QPainter
        svg_template = self._EYE_OPEN if self._visible else self._EYE_CLOSED
        color = TEXT_MUTED
        svg_data = svg_template.format(color=color).encode()
        renderer = QSvgRenderer(svg_data)
        pixmap = QPixmap(14, 14)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = _QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        self._eye_btn.setIcon(QIcon(pixmap))

    @property
    def goal_id(self) -> int:
        return self._goal_id

    @property
    def is_chart_visible(self) -> bool:
        return self._visible

    @staticmethod
    def _format_progress(is_prof: bool, current: float, pct: float) -> str:
        if is_prof:
            return f"Lv {current:.1f}  {pct:.1f}%"
        else:
            return f"{current:,.0f} pts  {pct:.1f}%"

    def _compute_progress(self, skill_values, profession_levels):
        """Compute current value and progress percentage."""
        goal = self._goal
        is_prof = goal["goal_type"] == "profession_level"
        if is_prof:
            current = profession_levels.get(goal["target_name"], 0)
        else:
            current = skill_values.get(goal["target_name"], 0)
        start = goal.get("start_value") or 0
        target = goal["target_value"]
        progress_range = target - start
        if progress_range > 0:
            pct = min(100, max(0, (current - start) / progress_range * 100))
        else:
            pct = 100 if current >= target else 0
        return current, pct

    def update_progress(self, skill_values: dict[str, float],
                        profession_levels: dict[str, float]):
        """Update progress bar and label in-place (no widget rebuild)."""
        goal = self._goal
        current, pct = self._compute_progress(skill_values, profession_levels)
        self._bar.setValue(int(pct * 10))
        is_prof = goal["goal_type"] == "profession_level"
        self._pct_label.setText(self._format_progress(is_prof, current, pct))


class SkillsPage(QWidget):
    """Skills management page with 6 tabs."""

    navigation_changed = pyqtSignal(object)  # sub_state dict or None

    def __init__(self, *, signals, oauth, nexus_client, data_client=None,
                 config=None, config_path="config.json", event_bus=None, db=None):
        super().__init__()
        self._signals = signals
        self._oauth = oauth
        self._nexus_client = nexus_client
        self._data_client = data_client
        self._config = config
        self._config_path = config_path
        self._event_bus = event_bus
        self._db = db

        # Data manager
        self._manager = SkillDataManager(data_client, nexus_client, db=db)

        # View state
        self._skills_view_mode = "grid"     # "grid" or "list"
        self._prof_view_mode = "grid"
        self._skills_grid_cols = 0           # cached column count for resize debounce
        self._prof_grid_cols = 0
        self._skills_grid_deferred = False
        self._prof_grid_deferred = False
        self._skill_filter_profession = None  # filter skills by profession name
        self._prof_filter_skill = None        # filter professions by skill name
        self._last_scan_result = None
        self._synced = False
        self._syncing = False  # guard against concurrent sync calls

        # Skill gains since last baseline (scan/import)
        self._skill_gains: dict[str, float] = {}  # {skill_name: accumulated_gain}
        self._pre_scan_gains: dict[str, float] = {}  # gains before first scan
        self._gains_loaded = False
        self._gain_refresh_pending = False

        # Rank lookup (loaded lazily)
        self._rank_thresholds: list[dict] = []

        # Dashboard state
        self._active_goals: list[dict] = []
        self._hidden_goal_ids: set[int] = set()  # goals hidden from chart
        self._goal_page_idx = 0  # pagination index
        self._dash_period_idx = 3  # default "1 month" (index into TIME_PERIODS)
        self._dash_custom_range: tuple[int, int] | None = None  # (from_ts, to_ts)
        self._dash_loaded = False
        self._dash_view_mode = "goals"  # "goals", "top_gains", or "custom"
        self._dash_graph_mode = "skills"  # "skills" or "professions"
        self._dash_last_top_gains: list[dict] = []
        self._dash_last_top_timeseries: list[dict] = []
        self._dash_last_goal_timeseries: list[dict] = []
        self._dash_last_custom_timeseries: list[dict] = []
        self._dash_custom_skill_ids: list[int] = []
        self._dash_custom_prof_names: list[str] = []
        self._dash_custom_mode: str = "skills"  # "skills" | "professions"
        self._dash_last_baselines: dict[int, float] = {}

        # Guard: suppress navigation_changed during set_sub_state restore
        self._applying_sub_state: bool = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Tab widget (no page header)
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                border-top: 1px solid {BORDER};
            }}
        """)
        self._build_dashboard_tab()
        self._build_skills_tab()
        self._build_professions_tab()
        self._build_analytics_tab()
        self._build_optimizer_tab()
        self._build_scanning_tab()
        layout.addWidget(self._tabs)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        # Connect signals
        signals.ocr_progress.connect(self._on_ocr_progress)
        signals.ocr_complete.connect(self._on_ocr_complete)
        signals.skill_scanned.connect(self._on_skill_scanned)
        signals.ocr_page_changed.connect(self._on_ocr_page_changed)
        signals.auth_state_changed.connect(self._on_auth_changed)
        if event_bus:
            signals.config_changed.connect(self._on_config_changed)
        signals.skill_gain.connect(self._on_skill_gain)

        # Debounce resize → avoids rebuilding grid on every pixel
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(80)
        self._resize_timer.timeout.connect(self._on_resize_settled)

        # Periodic rollup refresh (every 5 minutes)
        self._rollup_timer = QTimer(self)
        self._rollup_timer.setInterval(5 * 60 * 1000)
        self._rollup_timer.timeout.connect(self._refresh_rollups_bg)
        self._rollup_timer.start()

        # Initial data load (deferred, skipped if prewarm_data() was called)
        self._data_prewarmed = False
        QTimer.singleShot(200, self._initial_load)

    # ── Tab Builders ──────────────────────────────────────────────────────

    def _build_skills_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)

        # Toolbar
        toolbar = QHBoxLayout()

        self._skills_view_toggle = QPushButton("List View")
        self._skills_view_toggle.setMinimumWidth(100)
        self._skills_view_toggle.clicked.connect(self._toggle_skills_view)
        toolbar.addWidget(self._skills_view_toggle)

        toolbar.addWidget(QLabel("Sort:"))
        self._skills_sort = QComboBox()
        self._skills_sort.setMinimumWidth(160)
        self._skills_sort.addItems(["Category", "Level", "HP Contribution",
                                    "Evader/Dodger/Jammer", "Looter", "Gain"])
        self._skills_sort.currentIndexChanged.connect(self._refresh_skills_display)
        toolbar.addWidget(self._skills_sort)

        toolbar.addWidget(QLabel("Profession:"))
        self._skills_prof_filter = QComboBox()
        self._skills_prof_filter.setMinimumWidth(160)
        self._skills_prof_filter.addItem("All")
        self._skills_prof_filter.currentTextChanged.connect(self._on_skills_prof_filter)
        toolbar.addWidget(self._skills_prof_filter)

        self._skills_clear_btn = QPushButton("Clear Filters")
        self._skills_clear_btn.clicked.connect(self._clear_skills_filters)
        toolbar.addWidget(self._skills_clear_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Grid view — virtual scroll (only visible cards are created)
        self._skills_scroll = QScrollArea()
        self._skills_scroll.setWidgetResizable(True)
        self._skills_grid_container = QWidget()
        self._skills_loading_label = QLabel("Loading...", self._skills_grid_container)
        self._skills_loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._skills_loading_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        self._skills_loading_label.setGeometry(0, 0, 400, 30)
        self._skills_scroll.setWidget(self._skills_grid_container)
        self._skills_scroll.verticalScrollBar().valueChanged.connect(
            self._render_visible_skill_cards
        )
        self._skills_vgrid_rows: list[tuple] = []
        self._skills_vgrid_widgets: dict[int, list[QWidget]] = {}
        self._skills_vgrid_card_w = CARD_MIN_WIDTH
        self._skills_version = 0
        layout.addWidget(self._skills_scroll)

        # List view (table, hidden by default)
        self._skills_table = QTableWidget()
        self._skills_table.setColumnCount(7)
        self._skills_table.setHorizontalHeaderLabels(
            ["Name", "Category", "Level", "Points", "Gain", "HP", "Badges"]
        )
        self._skills_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._skills_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._skills_table.cellDoubleClicked.connect(self._on_skills_table_dblclick)
        self._skills_table.cellClicked.connect(self._on_skills_table_click)
        self._skills_table.setVisible(False)
        layout.addWidget(self._skills_table)

        self._tabs.addTab(tab, "Skills")

    def _build_professions_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)

        # Toolbar
        toolbar = QHBoxLayout()

        self._prof_view_toggle = QPushButton("List View")
        self._prof_view_toggle.setMinimumWidth(100)
        self._prof_view_toggle.clicked.connect(self._toggle_prof_view)
        toolbar.addWidget(self._prof_view_toggle)

        toolbar.addWidget(QLabel("Sort:"))
        self._prof_sort = QComboBox()
        self._prof_sort.addItems(["Category", "Level", "Skill Count"])
        self._prof_sort.currentIndexChanged.connect(self._refresh_prof_display)
        toolbar.addWidget(self._prof_sort)

        toolbar.addWidget(QLabel("Skill:"))
        self._prof_skill_filter = QComboBox()
        self._prof_skill_filter.addItem("All")
        self._prof_skill_filter.currentTextChanged.connect(self._on_prof_skill_filter)
        toolbar.addWidget(self._prof_skill_filter)

        self._prof_clear_btn = QPushButton("Clear Filters")
        self._prof_clear_btn.clicked.connect(self._clear_prof_filters)
        toolbar.addWidget(self._prof_clear_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Grid view — virtual scroll
        self._prof_scroll = QScrollArea()
        self._prof_scroll.setWidgetResizable(True)
        self._prof_grid_container = QWidget()
        self._prof_loading_label = QLabel("Loading...", self._prof_grid_container)
        self._prof_loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._prof_loading_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        self._prof_loading_label.setGeometry(0, 0, 400, 30)
        self._prof_scroll.setWidget(self._prof_grid_container)
        self._prof_scroll.verticalScrollBar().valueChanged.connect(
            self._render_visible_prof_cards
        )
        self._prof_vgrid_rows: list[tuple] = []
        self._prof_vgrid_widgets: dict[int, list[QWidget]] = {}
        self._prof_vgrid_card_w = CARD_MIN_WIDTH
        self._prof_version = 0
        layout.addWidget(self._prof_scroll)

        # List view (hidden)
        self._prof_table = QTableWidget()
        self._prof_table.setColumnCount(4)
        self._prof_table.setHorizontalHeaderLabels(
            ["Name", "Category", "Level", "Skill Count"]
        )
        self._prof_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._prof_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._prof_table.cellClicked.connect(self._on_prof_table_click)
        self._prof_table.setVisible(False)
        layout.addWidget(self._prof_table)

        self._tabs.addTab(tab, "Professions")

    def _build_dashboard_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)

        # Controls row: time period buttons + Add Goal
        controls = QHBoxLayout()
        controls.setSpacing(4)
        self._dash_period_btns: list[QPushButton] = []
        for idx, (label, _days) in enumerate(TIME_PERIODS):
            btn = QPushButton(label)
            btn.setFixedHeight(26)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(partial(self._on_dash_period_changed, idx))
            self._dash_period_btns.append(btn)
            controls.addWidget(btn)
        self._dash_custom_period_btn = QPushButton("Custom")
        self._dash_custom_period_btn.setFixedHeight(26)
        self._dash_custom_period_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._dash_custom_period_btn.clicked.connect(self._on_custom_period)
        controls.addWidget(self._dash_custom_period_btn)
        controls.addStretch()
        # View mode dropdown
        self._dash_view_combo = QComboBox()
        self._dash_view_combo.setFixedHeight(26)
        self._dash_view_combo.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._dash_view_combo.currentIndexChanged.connect(self._on_dash_view_changed)
        self._dash_view_combo.hide()
        controls.addWidget(self._dash_view_combo)
        self._dash_graph_mode_btn = QPushButton("Professions")
        self._dash_graph_mode_btn.setFixedHeight(26)
        self._dash_graph_mode_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._dash_graph_mode_btn.clicked.connect(self._on_graph_mode_toggle)
        self._dash_graph_mode_btn.hide()
        controls.addWidget(self._dash_graph_mode_btn)
        self._dash_pick_skills_btn = QPushButton("Pick Skills/Professions")
        self._dash_pick_skills_btn.setFixedHeight(26)
        self._dash_pick_skills_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._dash_pick_skills_btn.clicked.connect(self._on_pick_skills)
        controls.addWidget(self._dash_pick_skills_btn)
        self._dash_add_goal_btn = QPushButton("+ Add Goal")
        self._dash_add_goal_btn.setFixedHeight(26)
        self._dash_add_goal_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._dash_add_goal_btn.clicked.connect(self._on_add_goal)
        controls.addWidget(self._dash_add_goal_btn)
        layout.addLayout(controls)

        # Scroll area for dashboard content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._dash_content = QWidget()
        self._dash_content_layout = QVBoxLayout(self._dash_content)
        self._dash_content_layout.setContentsMargins(0, 4, 0, 0)
        scroll.setWidget(self._dash_content)
        layout.addWidget(scroll)

        # Goals container
        self._dash_goals_container = QWidget()
        self._dash_goals_layout = QVBoxLayout(self._dash_goals_container)
        self._dash_goals_layout.setContentsMargins(0, 0, 0, 0)
        self._dash_goals_layout.setSpacing(4)
        self._dash_goals_container.hide()
        self._dash_content_layout.addWidget(self._dash_goals_container)

        # Chart
        self._dash_chart = MultiLineChart()
        self._dash_chart.setMinimumHeight(200)
        self._dash_chart.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._dash_chart.hide()
        self._dash_content_layout.addWidget(self._dash_chart, 1)

        # Top gains table
        self._dash_gains_label = QLabel()
        self._dash_gains_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        self._dash_gains_label.hide()
        self._dash_content_layout.addWidget(self._dash_gains_label)

        self._dash_gains_table = QTableWidget()
        self._dash_gains_table.setColumnCount(4)
        self._dash_gains_table.setHorizontalHeaderLabels(
            ["Skill", "Gained", "Current", "Rank"]
        )
        _ghdr = self._dash_gains_table.horizontalHeader()
        _ghdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        _ghdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        _ghdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        _ghdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        _ghdr.resizeSection(1, 110)
        _ghdr.resizeSection(2, 100)
        _ghdr.resizeSection(3, 200)
        self._dash_gains_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self._dash_gains_table.hide()
        self._dash_content_layout.addWidget(self._dash_gains_table)

        # Onboarding / empty state
        self._dash_onboarding = QLabel()
        self._dash_onboarding.setWordWrap(True)
        self._dash_onboarding.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dash_onboarding.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 14px; padding: 40px 20px;"
        )
        self._dash_onboarding.setText(
            "No skill data yet.\n\n"
            "To start tracking your progression:\n"
            "1. Go to the Scanning tab to scan your skills from the game\n"
            "2. Or import skills from a file in the Scanning tab\n"
            "3. Skill gains from the chat log are tracked automatically\n\n"
            "Once you have data, this dashboard will show your progress."
        )
        self._dash_onboarding.hide()
        self._dash_content_layout.addWidget(self._dash_onboarding)

        # Loading label
        self._dash_loading = QLabel("Loading...")
        self._dash_loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dash_loading.setStyleSheet(f"color: {TEXT_MUTED}; padding: 20px;")
        self._dash_loading.hide()
        self._dash_content_layout.addWidget(self._dash_loading)

        # Style active period button
        self._update_dash_period_buttons()

        self._tabs.addTab(tab, "Dashboard")

    def _build_analytics_tab(self):
        """Analytics tab — Coming Soon.

        Planned features:
        - Skill gain breakdown by source (hunting, codex, ESIs)
        - Data sources: client/core/database.py skill_gains table (from chat parser)
        - Codex gains identification via known codex skill categories
        - ESI gains from manual imports (delta with no matching chat events)
        - Time-based analysis: gains per session, per day, per week
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addStretch()
        coming = QLabel("Coming Soon")
        coming.setStyleSheet("font-size: 18px; color: #888;")
        coming.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(coming)
        desc = QLabel(
            "This tab will break down skill gains by source:\n"
            "hunting, codex rewards, and ESI implants."
        )
        desc.setStyleSheet("color: #666;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)
        layout.addStretch()
        self._tabs.addTab(tab, "Analytics")

    def _build_optimizer_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)

        layout.addStretch()
        coming_soon = QLabel("Coming Soon")
        coming_soon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        coming_soon.setStyleSheet("font-size: 18px; font-weight: bold; color: gray;")
        layout.addWidget(coming_soon)
        layout.addStretch()

        self._tabs.addTab(tab, "Optimizer")

    def _build_scanning_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)

        # Scan mode
        scan_group = QGroupBox("Scan Settings")
        scan_layout = QVBoxLayout(scan_group)

        self._auto_scan_check = QCheckBox("Enable automated scanning")
        self._auto_scan_check.setChecked(getattr(self._config, "ocr_auto_scan_enabled", True))
        self._auto_scan_check.toggled.connect(self._on_auto_scan_toggled)
        scan_layout.addWidget(self._auto_scan_check)

        self._debug_overlay_check = QCheckBox("Debug overlay (show detected regions)")
        self._debug_overlay_check.setChecked(self._config.scan_overlay_debug)
        self._debug_overlay_check.toggled.connect(self._on_debug_overlay_toggled)
        scan_layout.addWidget(self._debug_overlay_check)

        btn_row = QHBoxLayout()
        self._manual_scan_btn = QPushButton("Run Manual Scan")
        self._manual_scan_btn.clicked.connect(self._trigger_manual_scan)
        self._manual_scan_btn.setEnabled(not self._auto_scan_check.isChecked())
        btn_row.addWidget(self._manual_scan_btn)
        btn_row.addStretch()
        scan_layout.addLayout(btn_row)

        layout.addWidget(scan_group)

        # Import / Export
        io_group = QGroupBox("Import / Export")
        io_layout = QVBoxLayout(io_group)

        io_desc = QLabel("Export or import skill values as CSV, TSV, or JSON.")
        io_desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        io_layout.addWidget(io_desc)

        io_btn_row = QHBoxLayout()
        self._export_btn = QPushButton("Export Skills")
        self._export_btn.clicked.connect(self._on_export_skills)
        io_btn_row.addWidget(self._export_btn)

        self._import_btn = QPushButton("Import Skills")
        self._import_btn.clicked.connect(self._on_import_skills)
        io_btn_row.addWidget(self._import_btn)

        io_btn_row.addStretch()
        io_layout.addLayout(io_btn_row)

        layout.addWidget(io_group)

        # Last scan results table
        self._scan_results_group = QGroupBox("Scan Results")
        results_layout = QVBoxLayout(self._scan_results_group)

        self._scan_info_label = QLabel("")
        self._scan_info_label.setStyleSheet("color: #999; font-size: 10px;")
        results_layout.addWidget(self._scan_info_label)

        self._scan_results_table = QTableWidget()
        self._scan_results_table.setColumnCount(4)
        self._scan_results_table.setHorizontalHeaderLabels(
            ["Name", "Rank", "Est. Points", "Skill Points"]
        )
        self._scan_results_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._scan_results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._scan_results_table.setSortingEnabled(True)
        self._scan_results_table.horizontalHeader().setSortIndicatorShown(True)
        self._scan_warning_count = 0
        self._scan_skill_rows: dict[str, QTableWidgetItem] = {}
        self._scan_skill_warnings: dict[str, bool] = {}
        self._suppress_next_scan_complete = False
        results_layout.addWidget(self._scan_results_table)

        layout.addWidget(self._scan_results_group)

        self._tabs.addTab(tab, "Scanning")

    # ── Data Loading ──────────────────────────────────────────────────────

    def _initial_load(self):
        """Load metadata and sync skills on startup."""
        if self._data_prewarmed:
            return
        threading.Thread(target=self._load_data_bg, daemon=True, name="skills-load").start()

    def _do_data_load(self):
        """Core data loading logic (no UI scheduling). Safe from any thread."""
        self._manager.refresh_metadata()
        self._load_rank_thresholds()

        synced = False
        if self._oauth.is_authenticated():
            synced = self._manager.sync_from_nexus()
            self._synced = synced
        if not synced:
            self._manager.load_from_local()
            self._synced = False

    def _load_data_bg(self):
        self._do_data_load()
        # Update UI on main thread
        QTimer.singleShot(0, self._on_data_loaded)

    def prewarm_data(self):
        """Load skills data during splash — fast parts synchronous, network in background.

        Metadata comes from the SQLite disk cache (fast). Local skill values
        come from the local DB (fast). Remote sync is deferred to a background
        thread so the splash doesn't hang on network timeouts.
        """
        try:
            # Fast: metadata + rank thresholds (disk-cached API data)
            self._manager.refresh_metadata()
            self._load_rank_thresholds()
            # Fast: local DB values — enough to build the card grid
            self._manager.load_from_local()
            self._synced = False
            self._data_prewarmed = True
            self._on_data_loaded(sync=True)
        except Exception:
            log.exception("Skills data prewarm failed — will retry on timer")
            return

        # Slow: network sync in background (merges remote + uploads dirty)
        if self._oauth.is_authenticated() and not self._syncing:
            import threading
            def _bg_sync():
                if self._syncing:
                    return
                self._syncing = True
                try:
                    synced = self._manager.sync_from_nexus()
                    self._synced = synced
                    if synced:
                        QTimer.singleShot(0, self._on_data_loaded)
                except Exception:
                    log.exception("Background skills sync failed")
                finally:
                    self._syncing = False
            threading.Thread(target=_bg_sync, daemon=True, name="skills-sync").start()

    def flush_prewarm(self):
        """Build deferred grids synchronously. Call after show() while splash
        still covers the screen so card creation doesn't cause a visible freeze.
        """
        if self._skills_grid_deferred:
            self._refresh_skills_display(sync=True)
        if self._prof_grid_deferred:
            self._refresh_prof_display(sync=True)

    def _ensure_gains_loaded(self):
        """Load gains from DB on first access (lazy). Currently disabled."""
        # Disabled — skill_gains table can have millions of rows and the
        # aggregation query is expensive.  Live gains from the chat parser
        # still accumulate in self._skill_gains via _on_skill_gain().
        return

    def _load_gains_from_db(self):
        """Load accumulated gains since last scan baseline from the local DB."""
        self._gains_loaded = True
        if not self._db:
            return
        from ...skills.skill_ids import id_to_name_map

        baseline_ts = self._db.get_last_scan_timestamp()
        if baseline_ts is None:
            # No OCR scan yet — use last sync time so we don't aggregate
            # the entire skill_gains history (can be millions of rows).
            baseline_ts = self._db.get_last_sync_timestamp() or 0
        gains_by_id = self._db.get_skill_gains_since(baseline_ts)
        id_names = id_to_name_map()

        # Merge DB gains with any live gains already accumulated
        for skill_id, total in gains_by_id.items():
            name = id_names.get(skill_id)
            if name:
                self._skill_gains[name] = self._skill_gains.get(name, 0) + total

        # Load pre-scan gains (gains recorded before the first scan).
        # These are already baked into the scan values, so we store them
        # separately to allow computing pre-scan starting points for goals.
        if baseline_ts and baseline_ts > 0:
            pre_gains_by_id = self._db.get_skill_gains_before(baseline_ts)
            for skill_id, total in pre_gains_by_id.items():
                name = id_names.get(skill_id)
                if name:
                    self._pre_scan_gains[name] = total

    def _load_rank_thresholds(self):
        """Load rank thresholds for level/progress display."""
        try:
            ranks = self._manager.skill_ranks
            if ranks and isinstance(ranks, dict):
                rows = ranks.get("Table", {}).get("Rows", [])
                self._rank_thresholds = sorted(
                    [{"name": r["Name"], "threshold": int(r["Skill"])} for r in rows],
                    key=lambda r: r["threshold"],
                )
            elif ranks and isinstance(ranks, list):
                self._rank_thresholds = sorted(ranks, key=lambda r: r.get("threshold", 0))
        except Exception:
            self._rank_thresholds = []

    def _get_rank_and_progress(self, points: float,
                               category: str | None = None) -> tuple[str, float]:
        """Get rank name and progress % for a given skill point value."""
        if category and category in RANKLESS_CATEGORIES:
            return ("", 0.0)
        if not self._rank_thresholds or points <= 0:
            return ("Inexperienced", 0.0)

        rank_name = self._rank_thresholds[0]["name"]
        current_threshold = 0
        next_threshold = self._rank_thresholds[0]["threshold"] if self._rank_thresholds else 0

        for i, rank in enumerate(self._rank_thresholds):
            if points >= rank["threshold"]:
                rank_name = rank["name"]
                current_threshold = rank["threshold"]
                next_threshold = (
                    self._rank_thresholds[i + 1]["threshold"]
                    if i + 1 < len(self._rank_thresholds)
                    else current_threshold
                )
            else:
                break

        if next_threshold > current_threshold:
            progress = (points - current_threshold) / (next_threshold - current_threshold) * 100
        else:
            progress = 100.0

        return (rank_name, min(progress, 100.0))

    def _on_data_loaded(self, *, sync=False):
        """Called on main thread after background data load.

        When *sync* is True the refresh methods run synchronously (used during
        splash prewarm so the event loop doesn't need to be running).
        """
        meta = self._manager.skill_metadata
        profs = self._manager.professions

        # Populate filter dropdowns
        self._skills_prof_filter.blockSignals(True)
        self._skills_prof_filter.clear()
        self._skills_prof_filter.addItem("All")
        for p in sorted(profs, key=lambda x: x.get("Name", "")):
            self._skills_prof_filter.addItem(p["Name"])
        self._skills_prof_filter.blockSignals(False)

        self._prof_skill_filter.blockSignals(True)
        self._prof_skill_filter.clear()
        self._prof_skill_filter.addItem("All")
        for s in sorted(meta, key=lambda x: x.get("Name", "")):
            if not s.get("IsHidden"):
                self._prof_skill_filter.addItem(s["Name"])
        self._prof_skill_filter.blockSignals(False)

        # Refresh displays
        self._refresh_skills_display(sync=sync)
        self._refresh_prof_display(sync=sync)

        if sync:
            # During prewarm, skip dashboard and goal checks — they'll run
            # when the event loop starts via the deferred _initial_load path
            # or when the user navigates to those tabs.
            return

        # Always refresh dashboard so goal cards have up-to-date skill data
        self._dash_loaded = False
        self._refresh_dashboard()

        # Check goal completion (off main thread — DB lock may be held by watcher)
        threading.Thread(
            target=self._check_goal_completion, daemon=True, name="goal-check",
        ).start()

    # ── Skills Tab ────────────────────────────────────────────────────────

    def _toggle_skills_view(self):
        if self._skills_view_mode == "grid":
            self._skills_view_mode = "list"
            self._skills_view_toggle.setText("Grid View")
            self._skills_scroll.setVisible(False)
            self._skills_table.setVisible(True)
        else:
            self._skills_view_mode = "grid"
            self._skills_view_toggle.setText("List View")
            self._skills_scroll.setVisible(True)
            self._skills_table.setVisible(False)
        self._refresh_skills_display()

    def _on_skills_prof_filter(self, text: str):
        if text == "All":
            self._skill_filter_profession = None
        else:
            self._skill_filter_profession = text
        self._refresh_skills_display()
        self._emit_nav()

    def _clear_skills_filters(self):
        self._skill_filter_profession = None
        self._skills_prof_filter.setCurrentText("All")
        self._skills_sort.setCurrentIndex(0)
        self._refresh_skills_display()

    def _refresh_skills_display(self, *, sync=False):
        self._ensure_gains_loaded()
        view_mode = self._skills_view_mode
        self._skills_version += 1
        version = self._skills_version

        # Capture state for background thread
        skill_filter_prof = self._skill_filter_profession
        sort_idx = self._skills_sort.currentIndex()
        gains = dict(self._skill_gains)
        rank_thresholds = self._rank_thresholds

        # Capture viewport width on main thread (Qt widget access)
        skills_viewport_w = self._skills_scroll.viewport().width() - 20

        # Grid deferred check — must happen on main thread before spawning
        if view_mode == "grid" and skills_viewport_w <= 0:
            self._skills_grid_deferred = True
            if not sync:
                QTimer.singleShot(50, self._flush_deferred_grids)
            return

        # Show loading state
        if view_mode == "grid":
            self._skills_loading_label.setText("Loading\u2026")
            self._skills_loading_label.setVisible(True)

        def compute():
            meta = self._manager.skill_metadata
            values = self._manager.skill_values
            attr_skills = build_attribute_skill_set(meta)

            # Filter (mirrors _get_filtered_skills but with captured state)
            if skill_filter_prof:
                filtered = [
                    s for s in meta
                    if any(p.get("Name") == skill_filter_prof
                           for p in s.get("Professions", []))
                ]
            else:
                filtered = [s for s in meta if not s.get("IsHidden")]

            # Sort
            if sort_idx == 0:
                filtered.sort(key=lambda s: (s.get("Category") or "", s["Name"]))
            elif sort_idx == 1:
                filtered.sort(key=lambda s: values.get(s["Name"], 0), reverse=True)
            elif sort_idx == 2:
                filtered.sort(key=lambda s: s.get("HPIncrease") or 9999)
            elif sort_idx == 3:
                def defense_sort(s):
                    for p in s.get("Professions", []):
                        if p.get("Name") in ("Evader", "Dodger", "Jammer"):
                            return -(p.get("Weight") or 0)
                    return 0
                filtered.sort(key=defense_sort)
            elif sort_idx == 4:
                def looter_sort(s):
                    for p in s.get("Professions", []):
                        if p.get("Name", "").endswith("Looter"):
                            return -(p.get("Weight") or 0)
                    return 0
                filtered.sort(key=looter_sort)
            elif sort_idx == 5:
                filtered.sort(key=lambda s: gains.get(s["Name"], 0), reverse=True)

            if view_mode == "grid":
                # Build row model for virtual grid
                return ("grid", self._build_skills_row_model(
                    filtered, values, meta, gains, rank_thresholds,
                    skill_filter_prof, sort_idx, skills_viewport_w,
                ))
            else:
                # Build table row data
                rows = []
                for skill in filtered:
                    name = skill["Name"]
                    points = values.get(name, 0)
                    rank, _ = _rank_from_thresholds(points, rank_thresholds, skill.get("Category"))
                    badges = get_skill_badges(name, meta)
                    hp_inc = skill.get("HPIncrease") or 0
                    gain = gains.get(name, 0.0)
                    dimmed = points == 0 and gain < 0.001
                    rows.append((name, skill.get("Category") or "", rank,
                                 points, gain, hp_inc, badges, dimmed))
                return ("table", rows)

        def apply(result):
            if self._skills_version != version:
                return
            kind, data = result
            try:
                if kind == "grid":
                    self._apply_skills_grid(data)
                else:
                    self._apply_skills_table(data)
            except RuntimeError:
                pass

        if sync:
            try:
                result = compute()
            except Exception:
                log.exception("skills compute error")
                result = ("grid" if view_mode == "grid" else "table",
                          ([], 0, CARD_MIN_WIDTH, False) if view_mode == "grid" else [])
            apply(result)
            return

        def worker():
            try:
                result = compute()
            except Exception:
                log.exception("skills compute error")
                result = ("grid" if view_mode == "grid" else "table",
                          ([], 0, CARD_MIN_WIDTH, False) if view_mode == "grid" else [])
            invoke_on_main(lambda: apply(result))

        threading.Thread(target=worker, daemon=True, name="skills-grid").start()

    @staticmethod
    def _build_skills_row_model(skills, values, all_meta, gains,
                                rank_thresholds, skill_filter_prof, sort_idx,
                                available):
        """Build virtual grid row model (safe for background thread).

        Returns (rows, total_height, card_w, deferred).
        """
        if available <= 0:
            return ([], 0, CARD_MIN_WIDTH, True)
        cols = max(1, available // (CARD_MIN_WIDTH + 6))
        card_w = min(CARD_MAX_WIDTH, max(CARD_MIN_WIDTH, (available - (cols - 1) * 6) // cols))

        rows: list[tuple] = []
        sort_by_category = sort_idx == 0
        current_category = None
        pending: list[tuple] = []
        y = 0

        def flush_pending():
            nonlocal y
            if pending:
                rows.append(("cards", y, CARD_ROW_HEIGHT, list(pending)))
                y += CARD_ROW_HEIGHT
                pending.clear()

        for skill in skills:
            if sort_by_category:
                cat = skill.get("Category") or "Uncategorized"
                if cat != current_category:
                    flush_pending()
                    current_category = cat
                    rows.append(("header", y, HEADER_ROW_HEIGHT, cat))
                    y += HEADER_ROW_HEIGHT

            name = skill["Name"]
            points = values.get(name, 0)
            rank, progress = _rank_from_thresholds(points, rank_thresholds, skill.get("Category"))
            badges = get_skill_badges(name, all_meta)
            weight = None
            if skill_filter_prof:
                for p in skill.get("Professions", []):
                    if p.get("Name") == skill_filter_prof:
                        weight = p.get("Weight", 0)
                        break
            gain = gains.get(name, 0.0)
            dimmed = points == 0 and gain < 0.001
            pending.append((name, points, rank, progress, badges, dimmed, weight, gain))
            if len(pending) >= cols:
                flush_pending()

        flush_pending()
        return (rows, y, card_w, False)

    def _apply_skills_grid(self, data):
        """Apply pre-computed grid row model on main thread."""
        self._clear_skills_vgrid()
        rows, total_height, card_w, deferred = data

        if deferred:
            self._skills_grid_deferred = True
            return

        self._skills_grid_deferred = False
        self._skills_loading_label.setVisible(False)

        if not rows:
            self._skills_loading_label.setText(
                "No skills to display. Scan, import, or login to sync."
            )
            self._skills_loading_label.setVisible(True)
            self._skills_grid_container.setMinimumHeight(30)
            return

        available = self._skills_scroll.viewport().width() - 20
        cols = max(1, available // (CARD_MIN_WIDTH + 6))
        self._skills_grid_cols = cols
        self._skills_vgrid_card_w = card_w
        self._skills_vgrid_rows = rows
        self._skills_grid_container.setMinimumHeight(total_height + 12)
        self._render_visible_skill_cards()

    def _apply_skills_table(self, rows):
        """Apply pre-computed table data on main thread."""
        self._skills_table.setUpdatesEnabled(False)
        try:
            self._skills_table.setRowCount(len(rows))
            for i, (name, category, rank, points, gain, hp_inc,
                    badges, dimmed) in enumerate(rows):
                fg = Qt.GlobalColor.gray if dimmed else None

                items = []
                items.append(QTableWidgetItem(name))
                items.append(QTableWidgetItem(category))
                items.append(QTableWidgetItem(rank))

                pts_item = QTableWidgetItem(f"{points:.2f}")
                pts_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                items.append(pts_item)

                gain_text = f"+{gain:.4f}" if gain > 0.001 else ""
                gain_item = QTableWidgetItem(gain_text)
                gain_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if gain > 0.001:
                    gain_item.setForeground(QColor(SUCCESS))
                items.append(gain_item)

                hp_text = str(hp_inc) if hp_inc > 0 else ""
                items.append(QTableWidgetItem(hp_text))

                badge_text = " ".join(b.label for b in badges)
                items.append(QTableWidgetItem(badge_text))

                for col, item in enumerate(items):
                    if fg:
                        item.setForeground(fg)
                    self._skills_table.setItem(i, col, item)
        finally:
            self._skills_table.setUpdatesEnabled(True)

    def _clear_skills_vgrid(self):
        """Remove all visible card widgets from the virtual grid."""
        for widgets in self._skills_vgrid_widgets.values():
            for w in widgets:
                w.deleteLater()
        self._skills_vgrid_widgets.clear()
        self._skills_vgrid_rows.clear()

    def _render_visible_skill_cards(self):
        """Create/destroy card widgets based on scroll position.

        Creates at most ``_CARD_BATCH_ROWS`` rows per call and schedules
        itself again if more rows still need widgets, preventing the main
        thread from freezing on large initial renders.
        """
        rows = self._skills_vgrid_rows
        if not rows:
            return
        scroll_y = self._skills_scroll.verticalScrollBar().value()
        view_h = self._skills_scroll.viewport().height()
        top = scroll_y - CARD_ROW_HEIGHT  # small buffer
        bottom = scroll_y + view_h + CARD_ROW_HEIGHT
        card_w = self._skills_vgrid_card_w

        new_visible: set[int] = set()
        for i, (kind, y, h, _data) in enumerate(rows):
            if y + h < top:
                continue
            if y > bottom:
                break
            new_visible.add(i)

        # Remove rows no longer visible
        for idx in list(self._skills_vgrid_widgets):
            if idx not in new_visible:
                for w in self._skills_vgrid_widgets[idx]:
                    w.deleteLater()
                del self._skills_vgrid_widgets[idx]

        # Create newly visible rows in small batches to avoid freezing
        container = self._skills_grid_container
        created = 0
        container.setUpdatesEnabled(False)
        try:
            for idx in sorted(new_visible):
                if idx in self._skills_vgrid_widgets:
                    continue
                kind, y, h, data = rows[idx]
                widgets: list[QWidget] = []
                if kind == "header":
                    lbl = QLabel(data, container)
                    lbl.setStyleSheet(_CARD_HEADER_STYLE)
                    lbl.setGeometry(0, y, container.width(), _HEADER_LABEL_HEIGHT)
                    lbl.show()
                    widgets.append(lbl)
                else:  # cards
                    for ci, (name, points, rank, progress, badges,
                             dimmed, weight, gain) in enumerate(data):
                        card = SkillCard(name, points, rank, progress, badges,
                                        dimmed=dimmed, weight=weight, gain=gain,
                                        parent=container)
                        card.clicked.connect(self._on_skill_card_clicked)
                        card.value_edited.connect(self._on_skill_value_edited)
                        card.setGeometry(ci * (card_w + 6), y, card_w, CARD_HEIGHT)
                        card.show()
                        widgets.append(card)
                self._skills_vgrid_widgets[idx] = widgets
                created += 1
                if created >= _CARD_BATCH_ROWS:
                    break
        finally:
            container.setUpdatesEnabled(True)

        # Schedule next batch if there are still uncreated visible rows
        if created >= _CARD_BATCH_ROWS:
            QTimer.singleShot(0, self._render_visible_skill_cards)

    def _on_skills_table_click(self, row, col):
        item = self._skills_table.item(row, 0)
        if item:
            self._navigate_to_professions_for_skill(item.text())

    def _on_skills_table_dblclick(self, row, col):
        if col == 3:  # Points column
            name_item = self._skills_table.item(row, 0)
            pts_item = self._skills_table.item(row, 3)
            if name_item and pts_item:
                skill_name = name_item.text()
                try:
                    current = float(pts_item.text())
                except ValueError:
                    current = 0
                # Make cell editable temporarily
                pts_item.setFlags(pts_item.flags() | Qt.ItemFlag.ItemIsEditable)
                self._skills_table.editItem(pts_item)
                # Store info for when editing finishes
                self._skills_table._editing_skill = skill_name

    def _on_skill_card_clicked(self, skill_name: str):
        self._navigate_to_professions_for_skill(skill_name)

    def _on_skill_value_edited(self, skill_name: str, new_value: float):
        """Handle manual skill value correction."""
        threading.Thread(
            target=self._manager.apply_correction,
            args=(skill_name, new_value),
            daemon=True, name="skill-correct",
        ).start()

    # ── Navigation (integrates with MainWindow title bar back/forward) ──

    def set_sub_state(self, state):
        """Restore a previously saved sub-state (called by MainWindow on back/forward)."""
        if state is None:
            return
        self._applying_sub_state = True
        try:
            tab_idx = state.get("tab", 0)
            skill_filter = state.get("skill_filter")
            prof_filter = state.get("prof_filter")

            self._skill_filter_profession = skill_filter
            self._prof_filter_skill = prof_filter
            self._skills_prof_filter.setCurrentText(
                skill_filter if skill_filter else "All"
            )
            self._prof_skill_filter.setCurrentText(
                prof_filter if prof_filter else "All"
            )
            self._tabs.setCurrentIndex(tab_idx)
        finally:
            self._applying_sub_state = False

    def _emit_nav(self):
        """Emit navigation_changed with current sub-state."""
        if self._applying_sub_state:
            return
        self.navigation_changed.emit({
            "tab": self._tabs.currentIndex(),
            "skill_filter": self._skill_filter_profession,
            "prof_filter": self._prof_filter_skill,
        })

    def _navigate_to_professions_for_skill(self, skill_name: str):
        """Switch to Professions tab filtered by a skill."""
        self._applying_sub_state = True
        try:
            self._prof_filter_skill = skill_name
            self._prof_skill_filter.setCurrentText(skill_name)
            self._tabs.setCurrentIndex(TAB_PROFESSIONS)
        finally:
            self._applying_sub_state = False
        self._emit_nav()

    # ── Professions Tab ───────────────────────────────────────────────────

    def _toggle_prof_view(self):
        if self._prof_view_mode == "grid":
            self._prof_view_mode = "list"
            self._prof_view_toggle.setText("Grid View")
            self._prof_scroll.setVisible(False)
            self._prof_table.setVisible(True)
        else:
            self._prof_view_mode = "grid"
            self._prof_view_toggle.setText("List View")
            self._prof_scroll.setVisible(True)
            self._prof_table.setVisible(False)
        self._refresh_prof_display()

    def _on_prof_skill_filter(self, text: str):
        if text == "All":
            self._prof_filter_skill = None
        else:
            self._prof_filter_skill = text
        self._refresh_prof_display()
        self._emit_nav()

    def _clear_prof_filters(self):
        self._prof_filter_skill = None
        self._prof_skill_filter.setCurrentText("All")
        self._prof_sort.setCurrentIndex(0)
        self._refresh_prof_display()

    def _refresh_prof_display(self, *, sync=False):
        view_mode = self._prof_view_mode
        self._prof_version += 1
        version = self._prof_version

        # Capture state for background thread
        prof_filter_skill = self._prof_filter_skill
        sort_idx = self._prof_sort.currentIndex()
        prof_viewport_w = self._prof_scroll.viewport().width() - 20

        # Grid deferred check — must happen on main thread before spawning
        if view_mode == "grid" and prof_viewport_w <= 0:
            self._prof_grid_deferred = True
            if not sync:
                QTimer.singleShot(50, self._flush_deferred_grids)
            return

        # Show loading state
        if view_mode == "grid":
            self._prof_loading_label.setText("Loading\u2026")
            self._prof_loading_label.setVisible(True)

        def compute():
            profs = self._manager.professions
            values = self._manager.skill_values
            meta = self._manager.skill_metadata
            levels = calculate_all_profession_levels(values, profs, meta)

            # Filter by skill
            if prof_filter_skill:
                profs = [
                    p for p in profs
                    if any(
                        s.get("Name") == prof_filter_skill
                        for s in p.get("Skills", [])
                    )
                ]

            # Annotate with level
            result = []
            for p in profs:
                level = levels.get(p["Name"], 0)
                result.append({**p, "_level": level})

            # Sort
            if sort_idx == 0:
                result.sort(key=lambda p: (p.get("Category") or "", p["Name"]))
            elif sort_idx == 1:
                result.sort(key=lambda p: p["_level"], reverse=True)
            elif sort_idx == 2:
                result.sort(key=lambda p: len(p.get("Skills", [])), reverse=True)

            if view_mode == "grid":
                return ("grid", self._build_prof_row_model(
                    result, prof_filter_skill, sort_idx, prof_viewport_w))
            else:
                rows = []
                for prof in result:
                    rows.append((prof["Name"], prof.get("Category") or "",
                                 prof["_level"], len(prof.get("Skills", []))))
                return ("table", rows)

        def apply(data):
            if self._prof_version != version:
                return
            kind, payload = data
            try:
                if kind == "grid":
                    self._apply_prof_grid(payload)
                else:
                    self._apply_prof_table(payload)
            except RuntimeError:
                pass

        if sync:
            try:
                data = compute()
            except Exception:
                log.exception("prof compute error")
                data = ("grid" if view_mode == "grid" else "table",
                        ([], 0, CARD_MIN_WIDTH, False) if view_mode == "grid" else [])
            apply(data)
            return

        def worker():
            try:
                data = compute()
            except Exception:
                log.exception("prof compute error")
                data = ("grid" if view_mode == "grid" else "table",
                        ([], 0, CARD_MIN_WIDTH, False) if view_mode == "grid" else [])
            invoke_on_main(lambda: apply(data))

        threading.Thread(target=worker, daemon=True, name="prof-grid").start()

    @staticmethod
    def _build_prof_row_model(profs, prof_filter_skill, sort_idx, available):
        """Build virtual grid row model for professions (safe for background thread).

        Returns (rows, total_height, card_w, deferred).
        """
        if available <= 0:
            return ([], 0, CARD_MIN_WIDTH, True)
        cols = max(1, available // (CARD_MIN_WIDTH + 6))
        card_w = min(CARD_MAX_WIDTH, max(CARD_MIN_WIDTH, (available - (cols - 1) * 6) // cols))

        rows: list[tuple] = []
        sort_by_category = sort_idx == 0
        current_category = None
        pending: list[tuple] = []
        y = 0

        def flush_pending():
            nonlocal y
            if pending:
                rows.append(("cards", y, CARD_ROW_HEIGHT, list(pending)))
                y += CARD_ROW_HEIGHT
                pending.clear()

        for prof in profs:
            if sort_by_category:
                cat = prof.get("Category") or "Uncategorized"
                if cat != current_category:
                    flush_pending()
                    current_category = cat
                    rows.append(("header", y, HEADER_ROW_HEIGHT, cat))
                    y += HEADER_ROW_HEIGHT

            weight = None
            if prof_filter_skill:
                for s in prof.get("Skills", []):
                    if s.get("Name") == prof_filter_skill:
                        weight = s.get("Weight", 0)
                        break

            pending.append((prof["Name"], prof["_level"],
                           len(prof.get("Skills", [])), weight))
            if len(pending) >= cols:
                flush_pending()

        flush_pending()
        return (rows, y, card_w, False)

    def _apply_prof_grid(self, data):
        """Apply pre-computed prof grid row model on main thread."""
        self._clear_prof_vgrid()
        rows, total_height, card_w, deferred = data

        if deferred:
            self._prof_grid_deferred = True
            return

        self._prof_grid_deferred = False
        self._prof_loading_label.setVisible(False)

        if not rows:
            self._prof_loading_label.setText("No professions to display.")
            self._prof_loading_label.setVisible(True)
            self._prof_grid_container.setMinimumHeight(30)
            return

        available = self._prof_scroll.viewport().width() - 20
        cols = max(1, available // (CARD_MIN_WIDTH + 6))
        self._prof_grid_cols = cols
        self._prof_vgrid_card_w = card_w
        self._prof_vgrid_rows = rows
        self._prof_grid_container.setMinimumHeight(total_height + 12)
        self._render_visible_prof_cards()

    def _apply_prof_table(self, rows):
        """Apply pre-computed prof table data on main thread."""
        self._prof_table.setUpdatesEnabled(False)
        try:
            self._prof_table.setRowCount(len(rows))
            for i, (name, category, level, skill_count) in enumerate(rows):
                self._prof_table.setItem(i, 0, QTableWidgetItem(name))
                self._prof_table.setItem(i, 1, QTableWidgetItem(category))

                level_item = QTableWidgetItem(f"{level:.2f}")
                level_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self._prof_table.setItem(i, 2, level_item)

                count_item = QTableWidgetItem(str(skill_count))
                count_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self._prof_table.setItem(i, 3, count_item)
        finally:
            self._prof_table.setUpdatesEnabled(True)

    def _clear_prof_vgrid(self):
        for widgets in self._prof_vgrid_widgets.values():
            for w in widgets:
                w.deleteLater()
        self._prof_vgrid_widgets.clear()
        self._prof_vgrid_rows.clear()

    def _render_visible_prof_cards(self):
        """Create/destroy profession card widgets based on scroll position.

        Uses the same batched creation strategy as skill cards.
        """
        rows = self._prof_vgrid_rows
        if not rows:
            return
        scroll_y = self._prof_scroll.verticalScrollBar().value()
        view_h = self._prof_scroll.viewport().height()
        top = scroll_y - CARD_ROW_HEIGHT
        bottom = scroll_y + view_h + CARD_ROW_HEIGHT
        card_w = self._prof_vgrid_card_w

        new_visible: set[int] = set()
        for i, (kind, y, h, _data) in enumerate(rows):
            if y + h < top:
                continue
            if y > bottom:
                break
            new_visible.add(i)

        for idx in list(self._prof_vgrid_widgets):
            if idx not in new_visible:
                for w in self._prof_vgrid_widgets[idx]:
                    w.deleteLater()
                del self._prof_vgrid_widgets[idx]

        container = self._prof_grid_container
        created = 0
        container.setUpdatesEnabled(False)
        try:
            for idx in sorted(new_visible):
                if idx in self._prof_vgrid_widgets:
                    continue
                kind, y, h, data = rows[idx]
                widgets: list[QWidget] = []
                if kind == "header":
                    lbl = QLabel(data, container)
                    lbl.setStyleSheet(_CARD_HEADER_STYLE)
                    lbl.setGeometry(0, y, container.width(), _HEADER_LABEL_HEIGHT)
                    lbl.show()
                    widgets.append(lbl)
                else:
                    for ci, (name, level, skill_count, weight) in enumerate(data):
                        card = ProfessionCard(name, level, skill_count,
                                             weight=weight, parent=container)
                        card.clicked.connect(self._on_prof_card_clicked)
                        card.setGeometry(ci * (card_w + 6), y, card_w, CARD_HEIGHT)
                        card.show()
                        widgets.append(card)
                self._prof_vgrid_widgets[idx] = widgets
                created += 1
                if created >= _CARD_BATCH_ROWS:
                    break
        finally:
            container.setUpdatesEnabled(True)

        if created >= _CARD_BATCH_ROWS:
            QTimer.singleShot(0, self._render_visible_prof_cards)

    def _on_prof_table_click(self, row, col):
        item = self._prof_table.item(row, 0)
        if item:
            self._navigate_to_skills_for_profession(item.text())

    def _on_prof_card_clicked(self, prof_name: str):
        self._navigate_to_skills_for_profession(prof_name)

    def _navigate_to_skills_for_profession(self, prof_name: str):
        """Switch to Skills tab filtered by a profession."""
        self._applying_sub_state = True
        try:
            self._skill_filter_profession = prof_name
            self._skills_prof_filter.setCurrentText(prof_name)
            self._tabs.setCurrentIndex(TAB_SKILLS)
        finally:
            self._applying_sub_state = False
        self._emit_nav()

    # ── Dashboard Tab ────────────────────────────────────────────────────

    def _update_dash_period_buttons(self):
        """Style period buttons, highlighting the active one."""
        active_style = (
            f"padding: 2px 8px; background-color: {ACCENT}; color: {PRIMARY}; "
            f"font-weight: bold; border: none; border-radius: 3px;"
        )
        inactive_style = (
            f"padding: 2px 8px; background-color: {SECONDARY}; "
            f"border: 1px solid {BORDER}; border-radius: 3px;"
        )
        for i, btn in enumerate(self._dash_period_btns):
            btn.setStyleSheet(active_style if i == self._dash_period_idx else inactive_style)
        # Custom button: active when using a custom range
        is_custom = self._dash_period_idx == -1
        self._dash_custom_period_btn.setStyleSheet(active_style if is_custom else inactive_style)

    def _on_dash_period_changed(self, idx: int):
        self._dash_period_idx = idx
        self._dash_custom_range = None
        self._update_dash_period_buttons()
        self._refresh_dashboard()

    def _on_custom_period(self):
        """Open dialog to set a custom time span or date range."""
        from PyQt6.QtWidgets import QDialog, QRadioButton, QButtonGroup, QSpinBox, QDateEdit
        from PyQt6.QtCore import QDate

        dlg = QDialog(self)
        dlg.setWindowTitle("Custom Time Range")
        dlg.setMinimumWidth(320)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(8)

        group = QButtonGroup(dlg)
        radio_span = QRadioButton("Last N days")
        radio_range = QRadioButton("Date range")
        group.addButton(radio_span, 0)
        group.addButton(radio_range, 1)
        radio_span.setChecked(True)

        # Span option
        span_row = QHBoxLayout()
        span_row.addWidget(radio_span)
        span_spin = QSpinBox()
        span_spin.setRange(1, 3650)
        span_spin.setValue(14)
        span_spin.setSuffix(" days")
        span_row.addWidget(span_spin)
        span_row.addStretch()
        layout.addLayout(span_row)

        # Range option
        range_row = QHBoxLayout()
        range_row.addWidget(radio_range)
        range_row.addWidget(QLabel("From:"))
        from_date = QDateEdit()
        from_date.setCalendarPopup(True)
        from_date.setDate(QDate.currentDate().addMonths(-1))
        range_row.addWidget(from_date)
        range_row.addWidget(QLabel("To:"))
        to_date = QDateEdit()
        to_date.setCalendarPopup(True)
        to_date.setDate(QDate.currentDate())
        range_row.addWidget(to_date)
        layout.addLayout(range_row)

        def _toggle(btn_id, checked):
            if not checked:
                return
            span_spin.setEnabled(btn_id == 0)
            from_date.setEnabled(btn_id == 1)
            to_date.setEnabled(btn_id == 1)

        group.idToggled.connect(_toggle)
        _toggle(0, True)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel_btn)
        ok_btn = QPushButton("OK")
        ok_btn.setObjectName("accentButton")
        ok_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

        dlg.setStyleSheet(f"QDialog {{ background-color: {SECONDARY}; }}")

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        import time as _time
        now_ts = int(_time.time())

        if radio_span.isChecked():
            days = span_spin.value()
            from_ts = now_ts - days * 86400
            self._dash_custom_range = (from_ts, now_ts)
        else:
            fd = from_date.date()
            td = to_date.date()
            from_dt = datetime(fd.year(), fd.month(), fd.day(), tzinfo=timezone.utc)
            to_dt = datetime(td.year(), td.month(), td.day(), 23, 59, 59, tzinfo=timezone.utc)
            self._dash_custom_range = (int(from_dt.timestamp()), int(to_dt.timestamp()))

        self._dash_period_idx = -1
        self._update_dash_period_buttons()
        self._refresh_dashboard()

    def _on_add_goal(self):
        from ..dialogs.goal_dialog import GoalDialog

        prof_levels = {}
        if self._manager.skill_values and self._manager.professions:
            prof_levels = calculate_all_profession_levels(
                self._manager.skill_values,
                self._manager.professions,
                self._manager.skill_metadata,
            )

        dlg = GoalDialog(
            skill_metadata=self._manager.skill_metadata,
            professions=self._manager.professions,
            skill_values=self._manager.skill_values,
            profession_levels=prof_levels,
            rank_thresholds=self._rank_thresholds,
            parent=self,
        )
        if dlg.exec() and self._db:
            goal = dlg.get_goal()
            if goal:
                self._db.add_goal(**goal)
                self._refresh_dashboard()

    def _on_edit_goal(self, goal_id: int):
        from ..dialogs.goal_dialog import GoalDialog

        goal = next((g for g in self._active_goals if g["id"] == goal_id), None)
        if not goal:
            return

        prof_levels = {}
        if self._manager.skill_values and self._manager.professions:
            prof_levels = calculate_all_profession_levels(
                self._manager.skill_values,
                self._manager.professions,
                self._manager.skill_metadata,
            )

        dlg = GoalDialog(
            skill_metadata=self._manager.skill_metadata,
            professions=self._manager.professions,
            skill_values=self._manager.skill_values,
            profession_levels=prof_levels,
            rank_thresholds=self._rank_thresholds,
            existing_goal=goal,
            parent=self,
        )
        if dlg.exec() and self._db:
            updated = dlg.get_goal()
            if updated:
                self._db.update_goal(
                    goal_id,
                    target_value=updated["target_value"],
                    start_value=updated["start_value"],
                )
                self._refresh_dashboard()

    def _on_delete_goal(self, goal_id: int):
        if self._db:
            self._db.delete_goal(goal_id)
            self._refresh_dashboard()

    def _refresh_rollups_bg(self):
        """Refresh rollup tables in background thread, then refresh dashboard if active."""
        if not self._db:
            return

        def _do_rollup():
            self._db.refresh_skill_rollups()
            if self._tabs.currentIndex() == TAB_DASHBOARD:
                QTimer.singleShot(0, self._refresh_dashboard)

        threading.Thread(
            target=_do_rollup, daemon=True, name="skills-rollup",
        ).start()

    def _refresh_dashboard(self):
        """Kick off background data load for the dashboard."""
        if not self._db:
            self._dash_onboarding.show()
            return
        self._dash_loading.show()
        threading.Thread(
            target=self._load_dashboard_bg, daemon=True,
            name="skills-dashboard",
        ).start()

    def _load_dashboard_bg(self):
        """Background: refresh rollups, load goals, load top gains + timeseries."""
        import time as _time

        self._db.refresh_skill_rollups()
        goals = self._db.get_active_goals()

        now_ts = int(_time.time())
        if self._dash_custom_range is not None:
            from_ts, to_ts = self._dash_custom_range
        else:
            days = TIME_PERIODS[self._dash_period_idx][1]
            from_ts = now_ts - int(days * 86400) if days > 0 else 0
            to_ts = now_ts

        top_gains = self._db.get_top_gaining_skills(from_ts, to_ts, limit=10)

        # Always load top-gains timeseries (for toggle)
        top_timeseries = []
        if top_gains:
            top_ids = [g["skill_id"] for g in top_gains[:5]]
            top_timeseries = self._db.get_skill_gains_timeseries(
                top_ids, from_ts, to_ts,
            )

        # Load goal-specific timeseries if goals exist
        goal_timeseries = []
        if goals:
            nm = name_to_id_map()
            goal_skill_ids = set()
            for g in goals:
                if g["goal_type"] == "skill_points":
                    sid = nm.get(g["target_name"])
                    if sid is not None:
                        goal_skill_ids.add(sid)
                elif g["goal_type"] == "profession_level":
                    prof = next(
                        (p for p in self._manager.professions
                         if p["Name"] == g["target_name"]), None
                    )
                    if prof:
                        for sk in prof.get("Skills", []):
                            sid = nm.get(sk["Name"])
                            if sid is not None:
                                goal_skill_ids.add(sid)
            if goal_skill_ids:
                goal_timeseries = self._db.get_skill_gains_timeseries(
                    list(goal_skill_ids), from_ts, to_ts,
                )

        # Load custom timeseries if user has picked skills/professions
        custom_timeseries = []
        custom_ids = self._get_custom_skill_ids()
        if custom_ids:
            custom_timeseries = self._db.get_skill_gains_timeseries(
                custom_ids, from_ts, to_ts,
            )

        # Collect baseline skill values (current scan values by skill_id)
        nm = name_to_id_map()
        skill_values = self._manager.skill_values or {}
        baselines: dict[int, float] = {}
        for name, val in skill_values.items():
            sid = nm.get(name)
            if sid is not None:
                baselines[sid] = val

        # Load pre-scan gains: gains before the first scan are already baked
        # into the scan values.  Store them so the chart can compute what
        # skill values were *before* those gains occurred.
        baseline_ts = self._db.get_last_scan_timestamp()
        pre_scan_gains: dict[int, float] = {}
        if baseline_ts and baseline_ts > 0:
            pre_scan_gains = self._db.get_skill_gains_before(baseline_ts)

        QTimer.singleShot(
            0, partial(
                self._on_dashboard_loaded,
                goals, top_gains, goal_timeseries, top_timeseries,
                custom_timeseries, baselines, pre_scan_gains,
            )
        )

    def _on_dashboard_loaded(self, goals, top_gains,
                             goal_timeseries, top_timeseries,
                             custom_timeseries, baselines, pre_scan_gains):
        """Main thread: populate dashboard widgets."""
        self._dash_loading.hide()
        self._active_goals = goals
        self._dash_loaded = True
        self._dash_last_top_gains = top_gains
        self._dash_last_top_timeseries = top_timeseries
        self._dash_last_goal_timeseries = goal_timeseries
        self._dash_last_custom_timeseries = custom_timeseries
        self._dash_last_baselines = baselines

        # Merge accumulated live gains into baselines so the chart Y-axis
        # stays correct (baselines from DB are scan-only values).
        if self._skill_gains:
            nm = name_to_id_map()
            for name, gain in self._skill_gains.items():
                sid = nm.get(name)
                if sid is not None:
                    self._dash_last_baselines[sid] = (
                        self._dash_last_baselines.get(sid, 0) + gain
                    )

        # Store pre-scan gains (id-based → name-based)
        id_names = id_to_name_map()
        self._pre_scan_gains = {}
        for sid, total in pre_scan_gains.items():
            name = id_names.get(sid)
            if name:
                self._pre_scan_gains[name] = total

        has_goals = bool(goals)
        has_data = bool(self._manager.skill_values) or bool(top_gains)

        # Show/hide view toggle — visible when more than one view is available
        has_custom = self._has_custom_picks
        modes_available = sum([has_goals, True, has_custom])  # top_gains always available
        if modes_available > 1 and has_data:
            self._dash_view_combo.show()
        else:
            self._dash_view_combo.hide()
            if has_goals:
                self._dash_view_mode = "goals"
            elif not has_data:
                self._dash_view_mode = "top_gains"
        self._update_view_combo()

        self._apply_dashboard_view()

        # Re-apply accumulated live gains so cards don't visually reset
        if self._skill_gains:
            self._refresh_dashboard_live()

    def _apply_dashboard_view(self):
        """Show goals, top-gains, or custom view based on current mode."""
        # Hide everything first
        self._dash_goals_container.hide()
        self._dash_chart.hide()
        self._dash_gains_label.hide()
        self._dash_gains_table.hide()
        self._dash_onboarding.hide()
        self._dash_graph_mode_btn.hide()
        self._dash_pick_skills_btn.hide()

        has_goals = bool(self._active_goals)
        has_data = bool(self._manager.skill_values) or bool(self._dash_last_top_gains)

        if self._dash_view_mode == "goals" and has_goals:
            self._show_dashboard_goals(
                self._active_goals, self._dash_last_goal_timeseries,
            )
            # Show graph mode toggle if any goal maps to professions
            has_prof_view = any(
                g["goal_type"] == "profession_level" for g in self._active_goals
            ) or (
                self._manager.professions and any(
                    g["goal_type"] != "profession_level"
                    and any(
                        any(sk["Name"] == g["target_name"]
                            for sk in p.get("Skills", []))
                        for p in self._manager.professions
                    )
                    for g in self._active_goals
                )
            )
            if has_prof_view:
                self._dash_graph_mode_btn.show()
        elif self._dash_view_mode == "custom" and self._has_custom_picks:
            self._show_dashboard_custom(self._dash_last_custom_timeseries)
            self._dash_pick_skills_btn.show()
        elif has_data:
            self._show_dashboard_top_gains(
                self._dash_last_top_gains, self._dash_last_top_timeseries,
            )
            self._dash_pick_skills_btn.show()
        else:
            self._dash_onboarding.show()

    _VIEW_MODE_LABELS = {
        "goals": "Goals",
        "top_gains": "Top",
        "custom": "Custom",
    }

    def _on_dash_view_changed(self, index: int):
        """Handle view mode dropdown change."""
        mode = self._dash_view_combo.itemData(index)
        if mode is None or mode == self._dash_view_mode:
            return
        self._dash_view_mode = mode
        self._apply_dashboard_view()

    def _update_view_combo(self):
        """Rebuild the view mode dropdown items."""
        has_goals = bool(self._active_goals)
        has_custom = self._has_custom_picks
        modes = []
        if has_goals:
            modes.append("goals")
        modes.append("top_gains")
        if has_custom:
            modes.append("custom")

        self._dash_view_combo.blockSignals(True)
        self._dash_view_combo.clear()
        for mode in modes:
            self._dash_view_combo.addItem(
                self._VIEW_MODE_LABELS.get(mode, mode), mode,
            )
        # Select current mode
        for i in range(self._dash_view_combo.count()):
            if self._dash_view_combo.itemData(i) == self._dash_view_mode:
                self._dash_view_combo.setCurrentIndex(i)
                break
        self._dash_view_combo.blockSignals(False)

    _GOAL_CARD_MIN_W = 280
    _GOAL_CARD_MAX_W = 500
    _GOAL_MAX_ROWS = 2  # max rows of cards visible per page

    def _show_dashboard_goals(self, goals, timeseries):
        """Show goal progress cards (grid, paginated) and chart."""
        # Clear old contents
        while self._dash_goals_layout.count():
            item = self._dash_goals_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

        prof_levels = {}
        if self._manager.skill_values and self._manager.professions:
            prof_levels = calculate_all_profession_levels(
                self._manager.skill_values,
                self._manager.professions,
                self._manager.skill_metadata,
            )

        # Compute how many cards fit per row
        avail_w = self._dash_goals_container.width() or 800
        cols = max(1, avail_w // (self._GOAL_CARD_MIN_W + 6))
        per_page = cols * self._GOAL_MAX_ROWS

        # Clamp page index
        total_pages = max(1, (len(goals) + per_page - 1) // per_page)
        self._goal_page_idx = max(0, min(self._goal_page_idx, total_pages - 1))
        start_idx = self._goal_page_idx * per_page
        page_goals = goals[start_idx:start_idx + per_page]

        # Lay out cards in rows
        row_layout: QHBoxLayout | None = None
        for i, goal in enumerate(page_goals):
            if i % cols == 0:
                row_layout = QHBoxLayout()
                row_layout.setSpacing(6)
                self._dash_goals_layout.addLayout(row_layout)

            visible = goal["id"] not in self._hidden_goal_ids
            card = _GoalProgressCard(
                goal,
                self._manager.skill_values,
                prof_levels,
                visible=visible,
                parent=self._dash_goals_container,
            )
            card.setMinimumWidth(self._GOAL_CARD_MIN_W)
            card.setMaximumWidth(self._GOAL_CARD_MAX_W)
            card.edit_clicked.connect(self._on_edit_goal)
            card.delete_clicked.connect(self._on_delete_goal)
            card.visibility_toggled.connect(self._on_goal_visibility_toggled)
            row_layout.addWidget(card)

        # Push cards left in every row
        if row_layout is not None:
            row_layout.addStretch()

        # Pagination row (only if >1 page)
        if total_pages > 1:
            page_row = QHBoxLayout()
            page_row.addStretch()
            prev_btn = QPushButton("<")
            prev_btn.setFixedSize(28, 22)
            prev_btn.setEnabled(self._goal_page_idx > 0)
            prev_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            prev_btn.clicked.connect(lambda: self._change_goal_page(-1))
            page_row.addWidget(prev_btn)
            page_label = QLabel(f"Page {self._goal_page_idx + 1}/{total_pages}")
            page_label.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED};")
            page_row.addWidget(page_label)
            next_btn = QPushButton(">")
            next_btn.setFixedSize(28, 22)
            next_btn.setEnabled(self._goal_page_idx < total_pages - 1)
            next_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            next_btn.clicked.connect(lambda: self._change_goal_page(1))
            page_row.addWidget(next_btn)
            page_row.addStretch()
            self._dash_goals_layout.addLayout(page_row)

        self._dash_goals_container.show()

        # Build chart from timeseries (filtered by visibility)
        self._populate_goal_chart(timeseries)

    def _change_goal_page(self, delta: int):
        """Navigate goal pages without reloading data."""
        self._goal_page_idx += delta
        self._show_dashboard_goals(
            self._active_goals, self._dash_last_goal_timeseries,
        )

    def _on_goal_visibility_toggled(self, goal_id: int, visible: bool):
        """Handle eye toggle on a goal card."""
        if visible:
            self._hidden_goal_ids.discard(goal_id)
        else:
            self._hidden_goal_ids.add(goal_id)
        # Re-populate chart with filtered timeseries
        self._populate_goal_chart(self._dash_last_goal_timeseries)

    def _show_dashboard_top_gains(self, top_gains, timeseries):
        """Show top gaining skills table and chart."""
        id_names = id_to_name_map()
        period_label = (
            "Custom" if self._dash_period_idx == -1
            else TIME_PERIODS[self._dash_period_idx][0]
        )
        self._dash_gains_label.setText(f"Top Gaining Skills ({period_label})")
        self._dash_gains_label.show()

        # Build name → category lookup for rank exclusion
        name_to_cat = {s["Name"]: s.get("Category", "") for s in (self._manager.skill_metadata or [])}

        # Populate table
        self._dash_gains_table.setUpdatesEnabled(False)
        try:
            self._dash_gains_table.setRowCount(len(top_gains))
            for i, entry in enumerate(top_gains):
                name = id_names.get(entry["skill_id"], f"ID {entry['skill_id']}")
                current = self._manager.skill_values.get(name, 0)
                rank, _ = self._get_rank_and_progress(current, name_to_cat.get(name))

                self._dash_gains_table.setItem(i, 0, QTableWidgetItem(name))
                gain_item = NumericTableWidgetItem(
                    f"+{entry['total_amount']:.2f}", entry["total_amount"]
                )
                gain_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                gain_item.setForeground(QColor(SUCCESS))
                self._dash_gains_table.setItem(i, 1, gain_item)
                cur_item = NumericTableWidgetItem(f"{current:,.2f}", current)
                cur_item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self._dash_gains_table.setItem(i, 2, cur_item)
                self._dash_gains_table.setItem(i, 3, QTableWidgetItem(rank))
        finally:
            self._dash_gains_table.setUpdatesEnabled(True)

        self._dash_gains_table.show()

        # Build chart from timeseries
        self._populate_chart(timeseries)

    @property
    def _has_custom_picks(self) -> bool:
        return bool(self._dash_custom_skill_ids) or bool(self._dash_custom_prof_names)

    def _get_custom_skill_ids(self) -> list[int]:
        """Resolve effective skill IDs for the current custom pick."""
        if self._dash_custom_mode == "professions" and self._dash_custom_prof_names:
            nm = name_to_id_map()
            ids: set[int] = set()
            for prof_name in self._dash_custom_prof_names:
                prof = next(
                    (p for p in self._manager.professions
                     if p["Name"] == prof_name), None,
                )
                if prof:
                    for sk in prof.get("Skills", []):
                        sid = nm.get(sk["Name"])
                        if sid is not None:
                            ids.add(sid)
            return list(ids)
        return list(self._dash_custom_skill_ids)

    def _show_dashboard_custom(self, timeseries):
        """Show chart with user-picked custom skills or professions."""
        if self._dash_custom_mode == "professions":
            self._populate_custom_profession_chart(timeseries)
        else:
            self._populate_chart(timeseries)

    def _on_pick_skills(self):
        """Open skill/profession picker dialog and switch to custom view."""
        from ..dialogs.skill_picker_dialog import SkillPickerDialog

        top_ids = [g["skill_id"] for g in self._dash_last_top_gains[:10]]

        prof_levels: dict[str, float] = {}
        if self._manager.skill_values and self._manager.professions:
            prof_levels = calculate_all_profession_levels(
                self._manager.skill_values,
                self._manager.professions,
                self._manager.skill_metadata,
            )

        dlg = SkillPickerDialog(
            skill_metadata=self._manager.skill_metadata or [],
            professions=self._manager.professions or [],
            skill_values=self._manager.skill_values or {},
            profession_levels=prof_levels,
            top_gaining_skill_ids=top_ids,
            preselected_ids=self._dash_custom_skill_ids or None,
            preselected_prof_names=self._dash_custom_prof_names or None,
            initial_mode=self._dash_custom_mode,
            parent=self,
        )
        if dlg.exec():
            result = dlg.get_result()
            if result is None:
                return
            if result.mode == "professions" and result.profession_names:
                self._dash_custom_mode = "professions"
                self._dash_custom_prof_names = result.profession_names
                self._dash_custom_skill_ids = []
                self._dash_view_mode = "custom"
                self._load_custom_timeseries()
            elif result.mode == "skills" and result.skill_ids:
                self._dash_custom_mode = "skills"
                self._dash_custom_skill_ids = result.skill_ids
                self._dash_custom_prof_names = []
                self._dash_view_mode = "custom"
                self._load_custom_timeseries()
            else:
                # Cleared selection — go back to top_gains
                self._dash_custom_skill_ids = []
                self._dash_custom_prof_names = []
                if self._dash_view_mode == "custom":
                    self._dash_view_mode = "top_gains"
                self._update_view_combo()
                self._apply_dashboard_view()

    def _load_custom_timeseries(self):
        """Load timeseries for custom-picked skills/professions in background."""
        import time as _time

        if not self._db or not self._has_custom_picks:
            return

        skill_ids = self._get_custom_skill_ids()
        if not skill_ids:
            return
        now_ts = int(_time.time())
        if self._dash_custom_range is not None:
            from_ts, to_ts = self._dash_custom_range
        else:
            days = TIME_PERIODS[self._dash_period_idx][1]
            from_ts = now_ts - int(days * 86400) if days > 0 else 0
            to_ts = now_ts

        def _load():
            self._db.refresh_skill_rollups()
            ts_data = self._db.get_skill_gains_timeseries(skill_ids, from_ts, to_ts)
            QTimer.singleShot(0, partial(self._on_custom_timeseries_loaded, ts_data))

        threading.Thread(target=_load, daemon=True, name="custom-chart").start()

    def _on_custom_timeseries_loaded(self, timeseries):
        """Handle loaded custom timeseries data."""
        self._dash_last_custom_timeseries = timeseries
        self._update_view_combo()
        # Update view dropdown
        has_goals = bool(self._active_goals)
        has_custom = self._has_custom_picks
        modes_available = sum([has_goals, True, has_custom])
        if modes_available > 1:
            self._dash_view_combo.show()
        self._update_view_combo()
        self._apply_dashboard_view()

    def _populate_chart(self, timeseries):
        """Build ChartSeries from timeseries data with absolute skill values.

        Uses baselines (current skill values) to compute the correct Y-axis:
        baseline_at_start = current_value - total_gains_in_period, then
        each point = baseline_at_start + cumulative_gains_up_to_that_point.
        """
        if not timeseries:
            self._dash_chart.clear()
            return

        import time as _time
        id_names = id_to_name_map()
        baselines = self._dash_last_baselines
        now_ts = int(_time.time())

        # Group by skill_id and sort by timestamp
        by_skill: dict[int, list[tuple[int, float]]] = {}
        for row in timeseries:
            sid = row["skill_id"]
            by_skill.setdefault(sid, []).append((row["ts"], row["amount"]))

        series_list = []
        for i, (sid, data) in enumerate(by_skill.items()):
            data.sort(key=lambda p: p[0])

            # Total gain in this period
            total_gain = sum(amt for _, amt in data)

            # Current value is the most recent known value
            current_value = baselines.get(sid, 0)

            # Value at start of chart = current - total gain in period
            start_value = current_value - total_gain

            # Build absolute value series (cumulative sum + start_value)
            abs_data = []
            running = start_value
            for ts, amt in data:
                running += amt
                abs_data.append((ts, running))

            # Extend to current time (hold last value)
            if abs_data and abs_data[-1][0] < now_ts:
                abs_data.append((now_ts, abs_data[-1][1]))

            name = id_names.get(sid, f"Skill {sid}")
            color = CHART_COLORS[i % len(CHART_COLORS)]
            series_list.append(ChartSeries(name=name, color=color, data=abs_data))

        self._dash_chart.set_smooth(True)
        self._dash_chart.set_cumulative(False)  # Already absolute values
        self._dash_chart.set_data(series_list)
        self._dash_chart.show()

    def _populate_goal_chart(self, timeseries):
        """Populate chart filtering by hidden goals and applying graph mode."""
        # Filter out hidden goals' skill_ids
        filtered = timeseries
        if self._hidden_goal_ids:
            nm = name_to_id_map()
            hidden_sids: set[int] = set()
            for g in self._active_goals:
                if g["id"] not in self._hidden_goal_ids:
                    continue
                if g["goal_type"] == "profession_level":
                    prof = next(
                        (p for p in self._manager.professions if p["Name"] == g["target_name"]),
                        None,
                    )
                    if prof:
                        for sk in prof.get("Skills", []):
                            sid = nm.get(sk["Name"])
                            if sid is not None:
                                hidden_sids.add(sid)
                else:
                    sid = nm.get(g["target_name"])
                    if sid is not None:
                        hidden_sids.add(sid)
            filtered = [r for r in timeseries if r["skill_id"] not in hidden_sids]

        if self._dash_graph_mode == "professions":
            self._populate_profession_chart(filtered)
        else:
            self._populate_chart(filtered)

    def _on_graph_mode_toggle(self):
        """Toggle between skills and professions chart modes."""
        if self._dash_graph_mode == "skills":
            self._dash_graph_mode = "professions"
            self._dash_graph_mode_btn.setText("Skills")
        else:
            self._dash_graph_mode = "skills"
            self._dash_graph_mode_btn.setText("Professions")
        self._populate_goal_chart(self._dash_last_goal_timeseries)

    def _populate_profession_chart(self, timeseries):
        """Build chart with one line per profession goal."""
        if not timeseries:
            self._dash_chart.clear()
            return

        # Collect professions to chart: explicit profession goals + professions
        # that contain skills from skill-type goals
        prof_names_seen: set[str] = set()
        prof_list: list[dict] = []
        for g in self._active_goals:
            if g["id"] in self._hidden_goal_ids:
                continue
            if g["goal_type"] == "profession_level":
                prof = next(
                    (p for p in self._manager.professions
                     if p["Name"] == g["target_name"]),
                    None,
                )
                if prof and prof["Name"] not in prof_names_seen:
                    prof_names_seen.add(prof["Name"])
                    prof_list.append(prof)
            else:
                # Skill goal — find all professions this skill contributes to
                skill_name = g["target_name"]
                for p in self._manager.professions:
                    if p["Name"] in prof_names_seen:
                        continue
                    if any(sk["Name"] == skill_name
                           for sk in p.get("Skills", [])):
                        prof_names_seen.add(p["Name"])
                        prof_list.append(p)

        if not prof_list:
            self._populate_chart(timeseries)
            return

        series_list = self._build_profession_series(timeseries, prof_list)
        if not series_list:
            self._dash_chart.clear()
            return
        self._dash_chart.set_smooth(True)
        self._dash_chart.set_cumulative(False)
        self._dash_chart.set_data(series_list)
        self._dash_chart.show()

    def _populate_custom_profession_chart(self, timeseries):
        """Build chart with one line per user-picked profession."""
        if not timeseries:
            self._dash_chart.clear()
            return
        target_names = set(self._dash_custom_prof_names)
        prof_list = [
            p for p in self._manager.professions
            if p["Name"] in target_names
        ]
        if not prof_list:
            self._dash_chart.clear()
            return
        series_list = self._build_profession_series(timeseries, prof_list)
        if not series_list:
            self._dash_chart.clear()
            return
        self._dash_chart.set_smooth(True)
        self._dash_chart.set_cumulative(False)
        self._dash_chart.set_data(series_list)
        self._dash_chart.show()

    def _build_profession_series(
        self, timeseries: list[dict], prof_list: list[dict],
    ) -> list[ChartSeries]:
        """Build ChartSeries for profession level lines from timeseries data."""
        import time as _time
        id_names = id_to_name_map()
        now_ts = int(_time.time())
        skill_values = self._manager.skill_values or {}
        attr_skills = build_attribute_skill_set(self._manager.skill_metadata)

        # Group timeseries by skill_id
        by_skill: dict[int, list[tuple[int, float]]] = {}
        for row in timeseries:
            sid = row["skill_id"]
            by_skill.setdefault(sid, []).append((row["ts"], row["amount"]))
        for sid in by_skill:
            by_skill[sid].sort(key=lambda p: p[0])

        # Total gain per skill for baseline computation
        total_gains = {sid: sum(a for _, a in data) for sid, data in by_skill.items()}

        # Collect all unique timestamps
        all_ts = sorted({ts for data in by_skill.values() for ts, _ in data})
        if not all_ts:
            return []

        # Base skill values at start of period
        base_values = dict(skill_values)
        for sid, tg in total_gains.items():
            sk_name = id_names.get(sid)
            if sk_name:
                base_values[sk_name] = skill_values.get(sk_name, 0) - tg

        # Build cumulative gains per skill over time
        cumulative_by_ts: list[dict[int, float]] = []
        cumulative: dict[int, float] = {}
        for ts in all_ts:
            for sid, data in by_skill.items():
                for t, amt in data:
                    if t == ts:
                        cumulative[sid] = cumulative.get(sid, 0) + amt
            cumulative_by_ts.append(dict(cumulative))

        series_list = []
        for i, prof in enumerate(prof_list):
            prof_points = []
            for ts_idx, ts in enumerate(all_ts):
                current_values = dict(base_values)
                for sid, cum_amt in cumulative_by_ts[ts_idx].items():
                    sk_name = id_names.get(sid)
                    if sk_name:
                        current_values[sk_name] = base_values.get(sk_name, 0) + cum_amt
                level = calculate_profession_level(
                    current_values, prof.get("Skills", []), attr_skills
                )
                prof_points.append((ts, level))

            if prof_points and prof_points[-1][0] < now_ts:
                prof_points.append((now_ts, prof_points[-1][1]))

            color = CHART_COLORS[i % len(CHART_COLORS)]
            series_list.append(ChartSeries(
                name=prof["Name"], color=color, data=prof_points,
            ))
        return series_list

    def _check_goal_completion(self):
        """Check if any active goals have been reached and mark them complete."""
        if not self._db:
            return
        goals = self._db.get_active_goals()
        if not goals:
            return

        prof_levels = {}
        if self._manager.skill_values and self._manager.professions:
            prof_levels = calculate_all_profession_levels(
                self._manager.skill_values,
                self._manager.professions,
                self._manager.skill_metadata,
            )

        for goal in goals:
            if goal["goal_type"] == "skill_points":
                current = self._manager.skill_values.get(goal["target_name"], 0)
            else:
                current = prof_levels.get(goal["target_name"], 0)
            if current >= goal["target_value"]:
                self._db.complete_goal(goal["id"])

    def show_profession_chart(self, profession_name: str):
        """Switch to dashboard and show a chart for a specific profession's skills."""
        prof = next(
            (p for p in self._manager.professions if p["Name"] == profession_name),
            None,
        )
        if not prof or not self._db:
            return

        # Switch to dashboard
        self._tabs.setCurrentIndex(TAB_DASHBOARD)

        # Load timeseries for the profession's skills
        import time as _time
        nm = name_to_id_map()
        skill_ids = []
        for sk in prof.get("Skills", []):
            sid = nm.get(sk["Name"])
            if sid is not None:
                skill_ids.append(sid)

        if not skill_ids:
            return

        days = TIME_PERIODS[self._dash_period_idx][1]
        now_ts = int(_time.time())
        from_ts = now_ts - (days * 86400) if days > 0 else 0

        def _load():
            self._db.refresh_skill_rollups()
            ts_data = self._db.get_skill_gains_timeseries(skill_ids, from_ts, now_ts)
            QTimer.singleShot(0, partial(self._on_profession_chart_loaded, ts_data, profession_name))

        threading.Thread(target=_load, daemon=True, name="prof-chart").start()

    def _on_profession_chart_loaded(self, timeseries, profession_name):
        """Populate chart with profession skill data using absolute values."""
        # Hide non-chart dashboard widgets
        self._dash_goals_container.hide()
        self._dash_gains_label.hide()
        self._dash_gains_table.hide()
        self._dash_onboarding.hide()

        if not timeseries:
            self._dash_chart.clear()
            return

        import time as _time
        id_names = id_to_name_map()
        nm = name_to_id_map()
        now_ts = int(_time.time())
        skill_values = self._manager.skill_values or {}

        # Group by skill_id
        by_skill: dict[int, list[tuple[int, float]]] = {}
        for row in timeseries:
            sid = row["skill_id"]
            by_skill.setdefault(sid, []).append((row["ts"], row["amount"]))

        # Build absolute-value series for each skill
        series_list = []
        for i, (sid, data) in enumerate(by_skill.items()):
            data.sort(key=lambda p: p[0])
            total_gain = sum(amt for _, amt in data)
            sk_name = id_names.get(sid, "")
            current_value = skill_values.get(sk_name, 0)
            start_value = current_value - total_gain

            abs_data = []
            running = start_value
            for ts, amt in data:
                running += amt
                abs_data.append((ts, running))
            if abs_data and abs_data[-1][0] < now_ts:
                abs_data.append((now_ts, abs_data[-1][1]))

            name = id_names.get(sid, f"Skill {sid}")
            color = CHART_COLORS[i % len(CHART_COLORS)]
            series_list.append(ChartSeries(name=name, color=color, data=abs_data))

        # Add a profession level series
        prof = next(
            (p for p in self._manager.professions if p["Name"] == profession_name),
            None,
        )
        if prof and skill_values:
            attr_skills = build_attribute_skill_set(self._manager.skill_metadata)

            # Collect all unique timestamps, sorted
            all_ts = sorted({ts for s_data in by_skill.values() for ts, _ in s_data})

            # Build cumulative gains per skill_id
            cumulative_gains: dict[int, float] = {}
            total_gains: dict[int, float] = {
                sid: sum(amt for _, amt in s_data)
                for sid, s_data in by_skill.items()
            }
            # Start values: current - total gain
            base_values = dict(skill_values)
            for sid, tg in total_gains.items():
                sk_name = id_names.get(sid)
                if sk_name:
                    base_values[sk_name] = skill_values.get(sk_name, 0) - tg

            prof_points = []
            for ts in all_ts:
                for sid, s_data in by_skill.items():
                    for t, amt in s_data:
                        if t == ts:
                            cumulative_gains[sid] = cumulative_gains.get(sid, 0) + amt

                current_values = dict(base_values)
                for sid, cum_amt in cumulative_gains.items():
                    sk_name = id_names.get(sid)
                    if sk_name:
                        current_values[sk_name] = base_values.get(sk_name, 0) + cum_amt

                level = calculate_profession_level(
                    current_values, prof.get("Skills", []), attr_skills
                )
                prof_points.append((ts, level))

            if prof_points:
                if prof_points[-1][0] < now_ts:
                    prof_points.append((now_ts, prof_points[-1][1]))
                series_list.append(ChartSeries(
                    name=profession_name,
                    color=ACCENT,
                    data=prof_points,
                ))

        self._dash_chart.set_cumulative(False)
        self._dash_chart.set_data(series_list)
        self._dash_chart.show()

    # ── Scanning Tab ──────────────────────────────────────────────────────

    def _trigger_manual_scan(self):
        """Trigger a manual OCR scan via event bus."""
        if getattr(self._config, "ocr_auto_scan_enabled", True):
            QMessageBox.information(
                self, "Manual Scan",
                "Disable automated scanning first to run manual scans.",
            )
            return
        if self._event_bus:
            from ...core.constants import EVENT_OCR_MANUAL_TRIGGER
            self._event_bus.publish(EVENT_OCR_MANUAL_TRIGGER, None)
        self._scan_results_group.setTitle("Scan Results (scanning...)")
        self._manual_scan_btn.setEnabled(False)

    def _on_auto_scan_toggled(self, checked: bool):
        """Enable/disable continuous OCR scanning and persist the setting."""
        if self._config:
            self._config.ocr_auto_scan_enabled = checked
            from ...core.config import save_config
            save_config(self._config, self._config_path)
        self._manual_scan_btn.setEnabled(not checked)
        if self._event_bus:
            from ...core.constants import EVENT_CONFIG_CHANGED
            self._event_bus.publish(EVENT_CONFIG_CHANGED, self._config)

    def _on_debug_overlay_toggled(self, checked: bool):
        """Toggle the scan overlay debug mode."""
        if self._config:
            self._config.scan_overlay_debug = checked
            from ...core.config import save_config
            save_config(self._config, self._config_path)
        # Publish via EventBus so scan_highlight_overlay receives it
        # (the signal bridge is one-way: EventBus→Qt only)
        if self._event_bus:
            from ...core.constants import EVENT_CONFIG_CHANGED
            self._event_bus.publish(EVENT_CONFIG_CHANGED, self._config)

    def _on_config_changed(self, config):
        """Sync debug overlay checkbox when config changes externally (e.g. F3)."""
        if config and hasattr(config, "scan_overlay_debug"):
            self._debug_overlay_check.blockSignals(True)
            self._debug_overlay_check.setChecked(config.scan_overlay_debug)
            self._debug_overlay_check.blockSignals(False)
        if config and hasattr(config, "ocr_auto_scan_enabled"):
            self._auto_scan_check.blockSignals(True)
            self._auto_scan_check.setChecked(config.ocr_auto_scan_enabled)
            self._auto_scan_check.blockSignals(False)
            self._manual_scan_btn.setEnabled(not config.ocr_auto_scan_enabled)

    def _on_ocr_progress(self, data):
        if hasattr(data, "total_found"):
            total_expected = getattr(data, "total_expected", 165)
            self._scan_results_group.setTitle(
                f"Scan Results ({data.total_found}/{total_expected} skills)"
            )

    def _on_skill_scanned(self, reading):
        """Handle a single skill being scanned — add or update in the table."""
        self._suppress_next_scan_complete = False
        sorting_enabled = self._scan_results_table.isSortingEnabled()
        header = self._scan_results_table.horizontalHeader()
        sort_col = header.sortIndicatorSection()
        sort_order = header.sortIndicatorOrder()
        if sorting_enabled:
            self._scan_results_table.setSortingEnabled(False)

        name_item = self._scan_skill_rows.get(reading.skill_name)
        if name_item is not None:
            row = name_item.row()
        else:
            row = self._scan_results_table.rowCount()
            self._scan_results_table.setRowCount(row + 1)
            name_item = QTableWidgetItem(reading.skill_name)
            self._scan_results_table.setItem(row, 0, name_item)
            self._scan_skill_rows[reading.skill_name] = name_item

        self._scan_results_table.setItem(row, 1, QTableWidgetItem(reading.rank))
        threshold_item = NumericTableWidgetItem(str(reading.rank_threshold), reading.rank_threshold)
        threshold_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._scan_results_table.setItem(row, 2, threshold_item)
        points_item = NumericTableWidgetItem(f"{reading.current_points:.2f}", reading.current_points)
        points_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._scan_results_table.setItem(row, 3, points_item)

        self._scan_skill_warnings[reading.skill_name] = bool(reading.is_mismatch)
        self._scan_warning_count = sum(1 for warned in self._scan_skill_warnings.values() if warned)

        warning_color = QColor(245, 158, 11)
        default_color = self.palette().color(self.foregroundRole())
        row_color = warning_color if reading.is_mismatch else default_color
        for col in range(4):
            item = self._scan_results_table.item(row, col)
            if item:
                item.setForeground(row_color)

        if sorting_enabled:
            self._scan_results_table.setSortingEnabled(True)
            if sort_col >= 0:
                self._scan_results_table.sortItems(sort_col, sort_order)

        # Update group title with count
        count = len(self._scan_skill_rows)
        self._scan_results_group.setTitle(f"Scan Results ({count} skills read)")
        self._scan_info_label.setText(
            f"{count} read, {self._scan_warning_count} warnings"
        )

        # Update skill value in the manager for live card refresh
        self._manager._skill_values[reading.skill_name] = reading.current_points

    def clear_scan_results(self):
        """Clear the Scanning tab result table and counters."""
        self._scan_results_table.setRowCount(0)
        self._scan_skill_rows.clear()
        self._scan_skill_warnings.clear()
        self._scan_warning_count = 0
        self._suppress_next_scan_complete = True
        self._scan_results_group.setTitle("Scan Results")
        self._scan_info_label.setText("")

    def _on_ocr_page_changed(self, _data):
        """Page changed — keep accumulating (don't clear)."""
        pass

    def _on_ocr_complete(self, result):
        self._last_scan_result = result
        self._manual_scan_btn.setEnabled(
            not getattr(self._config, "ocr_auto_scan_enabled", True)
        )

        if self._suppress_next_scan_complete:
            self._suppress_next_scan_complete = False
            return

        # Table is already populated by _on_skill_scanned — just update counts
        self._scan_results_group.setTitle(
            f"Scan Results ({result.total_found}/{result.total_expected} skills)"
        )
        self._scan_info_label.setText(
            f"{result.total_found}/{result.total_expected} read,"
            f" {self._scan_warning_count} warnings"
        )

        # Reset gains baseline — scan is the new reference point
        self._skill_gains.clear()
        self._gains_loaded = False

        # Refresh displays with accumulated values
        if self._scan_skill_rows:
            self._refresh_skills_display()
            self._refresh_prof_display()

    # ── Import / Export ─────────────────────────────────────────────────

    _EXPORT_FILTER = (
        "CSV files (*.csv);;TSV files (*.tsv);;JSON files (*.json);;All files (*)"
    )
    _IMPORT_FILTER = (
        "Skill files (*.csv *.tsv *.json);;CSV files (*.csv);;TSV files (*.tsv)"
        ";;JSON files (*.json);;All files (*)"
    )

    def _get_export_timestamp(self) -> str:
        """Get ISO timestamp for export: last scan time or current UTC."""
        ts = self._db.get_last_scan_timestamp() if self._db else None
        if ts is not None:
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        return datetime.now(tz=timezone.utc).isoformat()

    def _on_export_skills(self):
        values = self._manager.get_all_values()
        if not values:
            QMessageBox.information(self, "Export Skills", "No skill data to export.")
            return

        path, chosen = QFileDialog.getSaveFileName(
            self, "Export Skills", "skills", self._EXPORT_FILTER,
        )
        if not path:
            return

        ext = Path(path).suffix.lower()
        exported_at = self._get_export_timestamp()
        try:
            if ext == ".json":
                text = json.dumps(
                    {
                        "exported_at": exported_at,
                        "skills": {k: v for k, v in sorted(values.items())},
                    },
                    indent=2,
                )
            elif ext == ".tsv":
                buf = io.StringIO()
                buf.write(f"# Exported: {exported_at}\n")
                writer = csv.writer(buf, delimiter="\t")
                writer.writerow(["Skill", "Value"])
                for name, val in sorted(values.items()):
                    writer.writerow([name, val])
                text = buf.getvalue()
            else:  # default csv
                buf = io.StringIO()
                buf.write(f"# Exported: {exported_at}\n")
                writer = csv.writer(buf)
                writer.writerow(["Skill", "Value"])
                for name, val in sorted(values.items()):
                    writer.writerow([name, val])
                text = buf.getvalue()
            Path(path).write_text(text, encoding="utf-8")
            QMessageBox.information(
                self, "Export Skills",
                f"Exported {len(values)} skills to {Path(path).name}",
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def _on_import_skills(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Skills", "", self._IMPORT_FILTER,
        )
        if not path:
            return

        ext = Path(path).suffix.lower()
        try:
            raw = Path(path).read_text(encoding="utf-8")
            imported: dict[str, float] = {}
            file_timestamp: str | None = None

            if ext == ".json":
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError("JSON must be an object mapping skill names to values")
                # Support wrapped format: {exported_at, skills}
                if "skills" in data and isinstance(data["skills"], dict):
                    file_timestamp = data.get("exported_at")
                    data = data["skills"]
                for k, v in data.items():
                    if k == "exported_at":
                        continue
                    imported[str(k)] = float(v)
            elif ext in (".csv", ".tsv"):
                delimiter = "\t" if ext == ".tsv" else ","
                lines = raw.splitlines(True)
                # Check for timestamp comment header
                start_idx = 0
                if lines and lines[0].startswith("# Exported:"):
                    file_timestamp = lines[0].split(":", 1)[1].strip()
                    start_idx = 1
                content = "".join(lines[start_idx:])
                reader = csv.reader(io.StringIO(content), delimiter=delimiter)
                header = next(reader, None)
                if not header or len(header) < 2:
                    raise ValueError("File must have at least two columns (Skill, Value)")
                for row in reader:
                    if len(row) >= 2 and row[0].strip() and row[1].strip():
                        imported[row[0].strip()] = float(row[1].strip())
            else:
                raise ValueError(f"Unsupported file type: {ext}")

            if not imported:
                QMessageBox.warning(self, "Import Skills", "No valid skills found in file.")
                return

            # If no timestamp in file, ask the user
            imported_at = file_timestamp
            if not imported_at:
                imported_at = self._ask_import_timestamp()
                if imported_at is None:
                    return  # User cancelled

            # Confirm before overwriting
            answer = QMessageBox.question(
                self, "Import Skills",
                f"Import {len(imported)} skills from {Path(path).name}?\n\n"
                "This will overwrite current values for matching skills.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

            synced = self._manager.apply_imported_values(
                imported, imported_at=imported_at,
            )

            # Reset gains baseline — import is the new reference point
            self._skill_gains.clear()
            self._gains_loaded = False

            # Refresh all displays
            self._refresh_skills_display()
            self._refresh_prof_display()

            if self._manager._nexus_client and not synced:
                QMessageBox.warning(
                    self, "Import Skills",
                    f"Imported {len(imported)} skills from {Path(path).name}.\n\n"
                    "Saved locally, but remote sync failed.",
                )
            else:
                QMessageBox.information(
                    self, "Import Skills",
                    f"Imported {len(imported)} skills from {Path(path).name}",
                )
        except (ValueError, json.JSONDecodeError) as e:
            QMessageBox.critical(self, "Import Failed", f"Invalid file format:\n{e}")
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", str(e))

    def _ask_import_timestamp(self) -> str | None:
        """Ask the user for a timestamp when import file has none.

        Returns ISO timestamp string, or None if cancelled.
        """
        from PyQt6.QtWidgets import (
            QDialog, QDialogButtonBox, QRadioButton, QButtonGroup, QDateEdit,
        )
        from PyQt6.QtCore import QDate

        dlg = QDialog(self)
        dlg.setWindowTitle("Import Timestamp")
        dlg.setMinimumWidth(340)
        layout = QVBoxLayout(dlg)

        layout.addWidget(QLabel("This file has no timestamp.\nWhen were these skills recorded?"))

        group = QButtonGroup(dlg)
        radio_now = QRadioButton("Use current time (this is a fresh scan)")
        radio_date = QRadioButton("Enter date:")
        group.addButton(radio_now, 0)
        group.addButton(radio_date, 1)
        radio_now.setChecked(True)
        layout.addWidget(radio_now)

        date_row = QHBoxLayout()
        date_row.addWidget(radio_date)
        date_edit = QDateEdit()
        date_edit.setDate(QDate.currentDate())
        date_edit.setCalendarPopup(True)
        date_edit.setEnabled(False)
        date_row.addWidget(date_edit)
        layout.addLayout(date_row)

        radio_date.toggled.connect(date_edit.setEnabled)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None

        if group.checkedId() == 0:
            return datetime.now(tz=timezone.utc).isoformat()
        else:
            qdate = date_edit.date()
            dt = datetime(qdate.year(), qdate.month(), qdate.day(), tzinfo=timezone.utc)
            return dt.isoformat()

    # ── Auth ──────────────────────────────────────────────────────────────

    def _on_auth_changed(self, state):
        if not state.authenticated:
            # Reset sync flag so skills re-sync on next login
            self._synced = False
            return
        if not self._synced:
            # Sync skills on first auth (or re-auth after logout)
            threading.Thread(target=self._sync_on_auth, daemon=True, name="skills-sync").start()

    def _sync_on_auth(self):
        self._synced = self._manager.sync_from_nexus()
        if not self._synced:
            self._manager.load_from_local()
        QTimer.singleShot(0, self._on_data_loaded)

    # ── Live Skill Gains ─────────────────────────────────────────────────

    def _on_skill_gain(self, event):
        """Handle a live skill gain event — update the accumulated gains dict."""
        import time as _time
        name = event.skill_name
        self._skill_gains[name] = self._skill_gains.get(name, 0) + event.amount

        # Append to in-memory dashboard timeseries for live chart updates
        nm = name_to_id_map()
        sid = nm.get(name)
        if sid is not None and self._dash_loaded:
            now_ts = int(_time.time())
            entry = {"ts": now_ts, "skill_id": sid, "amount": event.amount}
            self._dash_last_goal_timeseries.append(entry)
            self._dash_last_top_timeseries.append(entry)
            self._dash_last_custom_timeseries.append(entry)
            # Update baseline (current scan value)
            self._dash_last_baselines[sid] = self._dash_last_baselines.get(sid, 0) + event.amount

        if not self._gain_refresh_pending:
            self._gain_refresh_pending = True
            QTimer.singleShot(500, self._flush_gain_refresh)

    def _flush_gain_refresh(self):
        self._gain_refresh_pending = False
        current_tab = self._tabs.currentIndex()
        if current_tab == TAB_SKILLS:
            self._refresh_skills_display()
        if current_tab == TAB_DASHBOARD and self._dash_loaded:
            self._refresh_dashboard_live()

    def _refresh_dashboard_live(self):
        """Lightweight dashboard update — no DB queries, just UI refresh."""
        # Update goal progress cards in-place
        skill_values = self._manager.skill_values or {}
        # Merge live gains into a working copy
        live_values = dict(skill_values)
        for name, gain in self._skill_gains.items():
            live_values[name] = live_values.get(name, 0) + gain

        prof_levels = {}
        if live_values and self._manager.professions:
            prof_levels = calculate_all_profession_levels(
                live_values,
                self._manager.professions,
                self._manager.skill_metadata,
            )

        # Cards are inside nested HBoxLayouts — walk both levels
        for i in range(self._dash_goals_layout.count()):
            item = self._dash_goals_layout.itemAt(i)
            sub = item.layout() if item else None
            if sub is not None:
                for j in range(sub.count()):
                    widget = sub.itemAt(j).widget() if sub.itemAt(j) else None
                    if isinstance(widget, _GoalProgressCard):
                        widget.update_progress(live_values, prof_levels)

        # Refresh chart with updated timeseries
        if self._dash_view_mode == "goals":
            self._populate_goal_chart(self._dash_last_goal_timeseries)
        elif self._dash_view_mode == "custom":
            self._show_dashboard_custom(self._dash_last_custom_timeseries)
        else:
            self._populate_chart(self._dash_last_top_timeseries)

        # Update top gains table current values if visible
        if self._dash_gains_table.isVisible():
            id_names = id_to_name_map()
            name_to_cat = {s["Name"]: s.get("Category", "") for s in (self._manager.skill_metadata or [])}
            for i in range(self._dash_gains_table.rowCount()):
                name_item = self._dash_gains_table.item(i, 0)
                if not name_item:
                    continue
                name = name_item.text()
                current = live_values.get(name, 0)
                cur_item = self._dash_gains_table.item(i, 2)
                if cur_item:
                    cur_item.setText(f"{current:,.2f}")

    # ── Resize ────────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        # Deferred grids couldn't lay out while the page was hidden in the
        # stacked widget (viewport width was 0).  Flush them now with a
        # single-shot so Qt finishes geometry first.
        if self._skills_grid_deferred or self._prof_grid_deferred:
            QTimer.singleShot(0, self._flush_deferred_grids)

    def _flush_deferred_grids(self):
        if self._skills_grid_deferred:
            self._refresh_skills_display()
        if self._prof_grid_deferred:
            self._refresh_prof_display()

    def _on_tab_changed(self, index):
        """Re-flow grid when switching tabs only if column count changed."""
        if index == TAB_DASHBOARD and not self._dash_loaded:
            self._refresh_dashboard()
        elif index == TAB_SKILLS and self._skills_view_mode == "grid":
            # Defer so Qt finishes layout and the viewport has real dimensions
            QTimer.singleShot(0, self._check_skills_grid_refresh)
        elif index == TAB_PROFESSIONS and self._prof_view_mode == "grid":
            QTimer.singleShot(0, self._check_prof_grid_refresh)
        self._emit_nav()

    def _check_skills_grid_refresh(self):
        if self._tabs.currentIndex() != TAB_SKILLS:
            return
        available = self._skills_scroll.viewport().width() - 20
        if available > 0:
            cols = max(1, available // (CARD_MIN_WIDTH + 6))
            if self._skills_grid_deferred or cols != self._skills_grid_cols:
                self._refresh_skills_display()

    def _check_prof_grid_refresh(self):
        if self._tabs.currentIndex() != TAB_PROFESSIONS:
            return
        available = self._prof_scroll.viewport().width() - 20
        if available > 0:
            cols = max(1, available // (CARD_MIN_WIDTH + 6))
            if self._prof_grid_deferred or cols != self._prof_grid_cols:
                self._refresh_prof_display()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_timer.start()

    def _on_resize_settled(self):
        """Handle resize after debounce — rebuild grid if layout changed."""
        if self._skills_view_mode == "grid" and self._tabs.currentIndex() == TAB_SKILLS:
            available = self._skills_scroll.viewport().width() - 20
            if available <= 0:
                return
            if self._skills_grid_deferred:
                self._refresh_skills_display()
            else:
                cols = max(1, available // (CARD_MIN_WIDTH + 6))
                card_w = min(CARD_MAX_WIDTH, max(CARD_MIN_WIDTH,
                             (available - (cols - 1) * 6) // cols))
                if cols != self._skills_grid_cols or card_w != self._skills_vgrid_card_w:
                    self._refresh_skills_display()
                elif self._skills_vgrid_rows:
                    self._render_visible_skill_cards()
        elif self._prof_view_mode == "grid" and self._tabs.currentIndex() == TAB_PROFESSIONS:
            available = self._prof_scroll.viewport().width() - 20
            if available <= 0:
                return
            if self._prof_grid_deferred:
                self._refresh_prof_display()
            else:
                cols = max(1, available // (CARD_MIN_WIDTH + 6))
                card_w = min(CARD_MAX_WIDTH, max(CARD_MIN_WIDTH,
                             (available - (cols - 1) * 6) // cols))
                if cols != self._prof_grid_cols or card_w != self._prof_vgrid_card_w:
                    self._refresh_prof_display()
                elif self._prof_vgrid_rows:
                    self._render_visible_prof_cards()
