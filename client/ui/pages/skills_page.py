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
    QGridLayout, QSizePolicy, QFileDialog, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QCursor
from PyQt6.QtWidgets import QGraphicsOpacityEffect

from ...skills.calculations import (
    calculate_all_profession_levels, build_attribute_skill_set,
)
from ...skills.badges import get_skill_badges, Badge
from ...core.logger import get_logger
from ...skills.sync import SkillDataManager
from ..theme import (
    SECONDARY, BORDER, BORDER_HOVER, TEXT_MUTED,
    SUCCESS, SUCCESS_BG, WARNING, WARNING_BG,
    ACCENT, ACCENT_LIGHT,
)


log = get_logger("SkillsPage")

# ── Constants ──────────────────────────────────────────────────────────────
CARD_MIN_WIDTH = 180
CARD_MAX_WIDTH = 260

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
    ("1w", 7),
    ("1m", 30),
    ("3m", 90),
    ("6m", 180),
    ("1y", 365),
    ("All", 0),
]


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
        self.setStyleSheet(f"""
            SkillCard {{
                background-color: {SECONDARY};
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
            SkillCard:hover {{
                border-color: {BORDER_HOVER};
            }}
        """)
        if dimmed:
            effect = QGraphicsOpacityEffect(self)
            effect.setOpacity(0.35)
            self.setGraphicsEffect(effect)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 14)
        layout.setSpacing(4)

        # Row 1: Name + Badges (top-right)
        top_row = QHBoxLayout()
        top_row.setSpacing(4)
        name_label = QLabel(skill_name)
        name_label.setStyleSheet("font-weight: bold; font-size: 11px; background: transparent; border: none;")
        name_label.setWordWrap(True)
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
        rank_label.setStyleSheet(f"font-size: 10px; color: {TEXT_MUTED}; background: transparent; border: none;")
        info_row.addWidget(rank_label)
        if weight is not None:
            weight_label = QLabel(f"{weight}%")
            weight_label.setStyleSheet(f"font-size: 9px; color: {ACCENT}; background: transparent; border: none;")
            info_row.addWidget(weight_label)
        info_row.addStretch()

        self._points_label = QLabel(f"{points:.2f}")
        self._points_label.setStyleSheet("font-size: 10px; background: transparent; border: none;")
        info_row.addWidget(self._points_label)

        if gain > 0.001:
            gain_label = QLabel(f"+{gain:.4f}")
            gain_label.setStyleSheet(
                f"font-size: 9px; color: {SUCCESS}; background: transparent; border: none;"
            )
            info_row.addWidget(gain_label)

        self._edit_input = QDoubleSpinBox()
        self._edit_input.setDecimals(2)
        self._edit_input.setMaximum(999999)
        self._edit_input.setMinimumWidth(80)
        self._edit_input.setVisible(False)
        self._edit_input.editingFinished.connect(self._finish_edit)
        info_row.addWidget(self._edit_input)

        layout.addLayout(info_row)

        # Row 3: Progress bar
        bar = QProgressBar()
        bar.setMaximum(1000)
        bar.setValue(int(progress * 10))
        bar.setTextVisible(False)
        bar.setFixedHeight(6)
        layout.addWidget(bar)

    @staticmethod
    def _badge_style(badge: Badge) -> str:
        """Build QSS for a badge label based on type and level."""
        type_styles = BADGE_STYLES.get(badge.badge_type, {})
        bg, fg, border = type_styles.get(badge.level, ("#666", "#fff", None))
        parts = [
            f"background-color: {bg};",
            f"color: {fg};",
            "font-size: 9px;",
            "font-weight: 600;",
            "padding: 1px 4px;",
            "border-radius: 3px;",
        ]
        if border:
            parts.append(f"border: 1px solid {border};")
        else:
            parts.append("border: none;")
        return " ".join(parts)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._skill_name)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_edit()
        super().mouseDoubleClickEvent(event)

    def _start_edit(self):
        if self._editing:
            return
        self._editing = True
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
        self.setStyleSheet(f"""
            ProfessionCard {{
                background-color: {SECONDARY};
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
            ProfessionCard:hover {{
                border-color: {BORDER_HOVER};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 14)
        layout.setSpacing(4)

        # Row 1: Name
        name_label = QLabel(prof_name)
        name_label.setStyleSheet(
            "font-weight: bold; font-size: 11px; background: transparent; border: none;"
        )
        name_label.setWordWrap(True)
        layout.addWidget(name_label)

        # Row 2: "Level N" + weight + level value
        info_row = QHBoxLayout()
        info_row.setSpacing(4)
        level_int = int(level)
        rank_label = QLabel(f"Level {level_int}")
        rank_label.setStyleSheet(
            f"font-size: 10px; color: {TEXT_MUTED}; background: transparent; border: none;"
        )
        info_row.addWidget(rank_label)
        if weight is not None:
            weight_label = QLabel(f"{weight}%")
            weight_label.setStyleSheet(f"font-size: 9px; color: {ACCENT}; background: transparent; border: none;")
            info_row.addWidget(weight_label)
        info_row.addStretch()
        level_label = QLabel(f"{level:.2f}")
        level_label.setStyleSheet(
            "font-size: 10px; background: transparent; border: none;"
        )
        info_row.addWidget(level_label)
        layout.addLayout(info_row)

        # Row 3: Progress bar (fractional part of level)
        bar = QProgressBar()
        bar.setMaximum(1000)
        bar.setValue(int((level - level_int) * 1000))
        bar.setTextVisible(False)
        bar.setFixedHeight(6)
        layout.addWidget(bar)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._prof_name)
        super().mousePressEvent(event)


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
        self._manager = SkillDataManager(data_client, nexus_client)

        # View state
        self._skills_view_mode = "grid"     # "grid" or "list"
        self._prof_view_mode = "grid"
        self._skill_filter_profession = None  # filter skills by profession name
        self._prof_filter_skill = None        # filter professions by skill name
        self._last_scan_result = None
        self._synced = False

        # Skill gains since last baseline (scan/import)
        self._skill_gains: dict[str, float] = {}  # {skill_name: accumulated_gain}
        self._gain_refresh_pending = False

        # Rank lookup (loaded lazily)
        self._rank_thresholds: list[dict] = []

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
        self._build_skills_tab()
        self._build_professions_tab()
        self._build_progression_tab()
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

        # Initial data load (deferred)
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

        # Grid view (in scroll area)
        self._skills_scroll = QScrollArea()
        self._skills_scroll.setWidgetResizable(True)
        self._skills_grid_container = QWidget()
        self._skills_grid_layout = QGridLayout(self._skills_grid_container)
        self._skills_grid_layout.setSpacing(6)
        self._skills_grid_layout.setContentsMargins(0, 0, 0, 12)
        self._skills_loading_label = QLabel("Loading...")
        self._skills_loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._skills_loading_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        self._skills_grid_layout.addWidget(self._skills_loading_label, 0, 0)
        self._skills_scroll.setWidget(self._skills_grid_container)
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

        # Grid view
        self._prof_scroll = QScrollArea()
        self._prof_scroll.setWidgetResizable(True)
        self._prof_grid_container = QWidget()
        self._prof_grid_layout = QGridLayout(self._prof_grid_container)
        self._prof_grid_layout.setSpacing(6)
        self._prof_grid_layout.setContentsMargins(0, 0, 0, 12)
        self._prof_loading_label = QLabel("Loading...")
        self._prof_loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._prof_loading_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        self._prof_grid_layout.addWidget(self._prof_loading_label, 0, 0)
        self._prof_scroll.setWidget(self._prof_grid_container)
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

    def _build_progression_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)

        # Controls
        controls = QHBoxLayout()

        controls.addWidget(QLabel("Period:"))
        self._prog_period = QComboBox()
        for label, _ in TIME_PERIODS:
            self._prog_period.addItem(label)
        self._prog_period.setCurrentText("3m")
        controls.addWidget(self._prog_period)

        controls.addWidget(QLabel("Skill:"))
        self._prog_skill_picker = QComboBox()
        self._prog_skill_picker.setEditable(True)
        self._prog_skill_picker.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._prog_skill_picker.addItem("All")
        controls.addWidget(self._prog_skill_picker)

        self._prog_fetch_btn = QPushButton("Load History")
        self._prog_fetch_btn.clicked.connect(self._load_progression)
        controls.addWidget(self._prog_fetch_btn)

        controls.addStretch()
        layout.addLayout(controls)

        # Stats summary
        self._prog_stats_label = QLabel("Select a skill and time period, then click Load History.")
        layout.addWidget(self._prog_stats_label)

        # History table (simple table view since we don't have pyqtgraph guaranteed)
        self._prog_table = QTableWidget()
        self._prog_table.setColumnCount(3)
        self._prog_table.setHorizontalHeaderLabels(["Date", "Skill", "Value"])
        self._prog_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._prog_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._prog_table)

        self._tabs.addTab(tab, "Progression")

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
        self._scan_warning_count = 0
        self._scan_skill_rows: dict[str, int] = {}  # skill_name → row index
        results_layout.addWidget(self._scan_results_table)

        layout.addWidget(self._scan_results_group)

        self._tabs.addTab(tab, "Scanning")

    # ── Data Loading ──────────────────────────────────────────────────────

    def _initial_load(self):
        """Load metadata and sync skills on startup."""
        threading.Thread(target=self._load_data_bg, daemon=True).start()

    def _load_data_bg(self):
        self._manager.refresh_metadata()
        self._load_rank_thresholds()

        if self._oauth.is_authenticated():
            self._manager.sync_from_nexus()
            self._synced = True

        self._load_gains_from_db()

        # Update UI on main thread
        QTimer.singleShot(0, self._on_data_loaded)

    def _load_gains_from_db(self):
        """Load accumulated gains since last scan baseline from the local DB."""
        if not self._db:
            return
        from ...skills.skill_ids import id_to_name_map

        baseline_ts = self._db.get_last_scan_timestamp() or 0
        gains_by_id = self._db.get_skill_gains_since(baseline_ts)
        id_names = id_to_name_map()

        self._skill_gains = {}
        for skill_id, total in gains_by_id.items():
            name = id_names.get(skill_id)
            if name:
                self._skill_gains[name] = total

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

    def _get_rank_and_progress(self, points: float) -> tuple[str, float]:
        """Get rank name and progress % for a given skill point value."""
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

    def _on_data_loaded(self):
        """Called on main thread after background data load."""
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

        # Populate progression skill picker
        self._prog_skill_picker.blockSignals(True)
        self._prog_skill_picker.clear()
        self._prog_skill_picker.addItem("All")
        for s in sorted(meta, key=lambda x: x.get("Name", "")):
            if not s.get("IsHidden"):
                self._prog_skill_picker.addItem(s["Name"])
        self._prog_skill_picker.blockSignals(False)

        # Refresh displays
        self._refresh_skills_display()
        self._refresh_prof_display()

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

    def _get_filtered_skills(self) -> list[dict]:
        """Get skill metadata filtered and sorted for display."""
        meta = self._manager.skill_metadata
        values = self._manager.skill_values
        attr_skills = build_attribute_skill_set(meta)

        # Filter by profession: include any skill that lists the profession
        # (hidden skills are kept — they render dimmed when 0 points)
        if self._skill_filter_profession:
            pname = self._skill_filter_profession
            meta = [
                s for s in meta
                if any(p.get("Name") == pname
                       for p in s.get("Professions", []))
            ]
        else:
            meta = [s for s in meta if not s.get("IsHidden")]

        # Sort
        sort_idx = self._skills_sort.currentIndex()
        if sort_idx == 0:  # Category
            meta.sort(key=lambda s: (s.get("Category") or "", s["Name"]))
        elif sort_idx == 1:  # Level
            meta.sort(key=lambda s: values.get(s["Name"], 0), reverse=True)
        elif sort_idx == 2:  # HP Contribution
            meta.sort(key=lambda s: s.get("HPIncrease") or 9999)
        elif sort_idx == 3:  # Eva/Dod/Jam
            def defense_sort(s):
                for p in s.get("Professions", []):
                    if p.get("Name") in ("Evader", "Dodger", "Jammer"):
                        return -(p.get("Weight") or 0)
                return 0
            meta.sort(key=defense_sort)
        elif sort_idx == 4:  # Looter
            def looter_sort(s):
                for p in s.get("Professions", []):
                    if p.get("Name", "").endswith("Looter"):
                        return -(p.get("Weight") or 0)
                return 0
            meta.sort(key=looter_sort)
        elif sort_idx == 5:  # Gain
            meta.sort(key=lambda s: self._skill_gains.get(s["Name"], 0), reverse=True)

        return meta

    def _refresh_skills_display(self):
        meta = self._get_filtered_skills()
        values = self._manager.skill_values
        all_meta = self._manager.skill_metadata

        if self._skills_view_mode == "grid":
            self._populate_skills_grid(meta, values, all_meta)
        else:
            self._populate_skills_table(meta, values, all_meta)

    def _populate_skills_grid(self, skills: list[dict], values: dict,
                              all_meta: list[dict]):
        # Clear old cards
        while self._skills_grid_layout.count():
            item = self._skills_grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._skills_grid_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        if not skills:
            lbl = QLabel("No skills to display. Login to sync your skills.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._skills_grid_layout.addWidget(lbl, 0, 0)
            return

        # Calculate columns based on scroll area width
        available = self._skills_scroll.viewport().width() - 20
        cols = max(1, available // (CARD_MIN_WIDTH + 6))

        sort_by_category = self._skills_sort.currentIndex() == 0
        current_category = None
        grid_row = 0
        col_idx = 0

        for skill in skills:
            # Insert category header when category changes
            if sort_by_category:
                cat = skill.get("Category") or "Uncategorized"
                if cat != current_category:
                    current_category = cat
                    if col_idx > 0:
                        grid_row += 1
                        col_idx = 0
                    header = QLabel(cat)
                    header.setStyleSheet(
                        f"font-weight: bold; font-size: 13px; color: {TEXT_MUTED}; "
                        f"border-bottom: 1px solid {BORDER}; padding: 6px 0 2px 0; "
                        f"background: transparent;"
                    )
                    self._skills_grid_layout.addWidget(
                        header, grid_row, 0, 1, cols,
                    )
                    grid_row += 1

            name = skill["Name"]
            points = values.get(name, 0)
            rank, progress = self._get_rank_and_progress(points)
            badges = get_skill_badges(name, all_meta)

            # Look up weight when filtering by profession or skill
            weight = None
            if self._skill_filter_profession:
                for p in skill.get("Professions", []):
                    if p.get("Name") == self._skill_filter_profession:
                        weight = p.get("Weight", 0)
                        break

            gain = self._skill_gains.get(name, 0.0)
            card = SkillCard(name, points, rank, progress, badges,
                            dimmed=(points == 0 and gain < 0.001),
                            weight=weight, gain=gain)
            card.clicked.connect(self._on_skill_card_clicked)
            card.value_edited.connect(self._on_skill_value_edited)

            self._skills_grid_layout.addWidget(
                card, grid_row, col_idx,
                alignment=Qt.AlignmentFlag.AlignTop,
            )
            col_idx += 1
            if col_idx >= cols:
                col_idx = 0
                grid_row += 1

    def _populate_skills_table(self, skills: list[dict], values: dict,
                               all_meta: list[dict]):
        self._skills_table.setRowCount(len(skills))
        for i, skill in enumerate(skills):
            name = skill["Name"]
            points = values.get(name, 0)
            rank, progress = self._get_rank_and_progress(points)
            badges = get_skill_badges(name, all_meta)
            hp_inc = skill.get("HPIncrease") or 0

            gain = self._skill_gains.get(name, 0.0)
            dimmed = points == 0 and gain < 0.001
            fg = Qt.GlobalColor.gray if dimmed else None

            items = []
            items.append(QTableWidgetItem(name))
            items.append(QTableWidgetItem(skill.get("Category") or ""))
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
            daemon=True,
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
            self._tabs.setCurrentIndex(1)  # Professions tab
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

    def _get_filtered_professions(self) -> list[dict]:
        profs = self._manager.professions
        values = self._manager.skill_values
        meta = self._manager.skill_metadata
        levels = calculate_all_profession_levels(values, profs, meta)

        # Filter by skill
        if self._prof_filter_skill:
            profs = [
                p for p in profs
                if any(
                    s.get("Name") == self._prof_filter_skill
                    for s in p.get("Skills", [])
                )
            ]

        # Annotate with level
        result = []
        for p in profs:
            level = levels.get(p["Name"], 0)
            result.append({**p, "_level": level})

        # Sort
        sort_idx = self._prof_sort.currentIndex()
        if sort_idx == 0:  # Category
            result.sort(key=lambda p: (p.get("Category") or "", p["Name"]))
        elif sort_idx == 1:  # Level
            result.sort(key=lambda p: p["_level"], reverse=True)
        elif sort_idx == 2:  # Skill Count
            result.sort(key=lambda p: len(p.get("Skills", [])), reverse=True)

        return result

    def _refresh_prof_display(self):
        profs = self._get_filtered_professions()
        if self._prof_view_mode == "grid":
            self._populate_prof_grid(profs)
        else:
            self._populate_prof_table(profs)

    def _populate_prof_grid(self, profs: list[dict]):
        while self._prof_grid_layout.count():
            item = self._prof_grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._prof_grid_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        if not profs:
            lbl = QLabel("No professions to display.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._prof_grid_layout.addWidget(lbl, 0, 0)
            return

        available = self._prof_scroll.viewport().width() - 20
        cols = max(1, available // (CARD_MIN_WIDTH + 6))

        sort_by_category = self._prof_sort.currentIndex() == 0
        current_category = None
        grid_row = 0
        col_idx = 0

        for prof in profs:
            # Insert category header when category changes
            if sort_by_category:
                cat = prof.get("Category") or "Uncategorized"
                if cat != current_category:
                    current_category = cat
                    if col_idx > 0:
                        grid_row += 1
                        col_idx = 0
                    header = QLabel(cat)
                    header.setStyleSheet(
                        f"font-weight: bold; font-size: 13px; color: {TEXT_MUTED}; "
                        f"border-bottom: 1px solid {BORDER}; padding: 6px 0 2px 0; "
                        f"background: transparent;"
                    )
                    self._prof_grid_layout.addWidget(
                        header, grid_row, 0, 1, cols,
                    )
                    grid_row += 1

            # Look up weight when filtering by skill
            weight = None
            if self._prof_filter_skill:
                for s in prof.get("Skills", []):
                    if s.get("Name") == self._prof_filter_skill:
                        weight = s.get("Weight", 0)
                        break

            card = ProfessionCard(
                prof["Name"],
                prof["_level"],
                len(prof.get("Skills", [])),
                weight=weight,
            )
            card.clicked.connect(self._on_prof_card_clicked)
            self._prof_grid_layout.addWidget(
                card, grid_row, col_idx,
                alignment=Qt.AlignmentFlag.AlignTop,
            )
            col_idx += 1
            if col_idx >= cols:
                col_idx = 0
                grid_row += 1

    def _populate_prof_table(self, profs: list[dict]):
        self._prof_table.setRowCount(len(profs))
        for i, prof in enumerate(profs):
            self._prof_table.setItem(i, 0, QTableWidgetItem(prof["Name"]))
            self._prof_table.setItem(i, 1, QTableWidgetItem(prof.get("Category") or ""))

            level_item = QTableWidgetItem(f"{prof['_level']:.2f}")
            level_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._prof_table.setItem(i, 2, level_item)

            count_item = QTableWidgetItem(str(len(prof.get("Skills", []))))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._prof_table.setItem(i, 3, count_item)

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
            self._tabs.setCurrentIndex(0)  # Skills tab
        finally:
            self._applying_sub_state = False
        self._emit_nav()

    # ── Progression Tab ───────────────────────────────────────────────────

    def _load_progression(self):
        skill_name = self._prog_skill_picker.currentText()
        if skill_name == "All":
            skill_names = None
        else:
            skill_names = [skill_name]

        # Determine date range
        period_text = self._prog_period.currentText()
        days = dict(TIME_PERIODS).get(period_text, 0)
        from_date = None
        if days > 0:
            from_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        self._prog_fetch_btn.setEnabled(False)
        self._prog_stats_label.setText("Loading...")

        threading.Thread(
            target=self._fetch_progression_bg,
            args=(skill_names, from_date),
            daemon=True,
        ).start()

    def _fetch_progression_bg(self, skill_names, from_date):
        history = self._manager.get_skill_history(
            skill_names=skill_names, from_date=from_date
        )
        QTimer.singleShot(0, partial(self._on_progression_loaded, history))

    def _on_progression_loaded(self, history):
        self._prog_fetch_btn.setEnabled(True)

        if not history:
            self._prog_stats_label.setText("No history data found.")
            self._prog_table.setRowCount(0)
            return

        # Populate table
        self._prog_table.setRowCount(len(history))
        for i, entry in enumerate(history):
            date_str = entry.get("imported_at", "")
            if "T" in date_str:
                date_str = date_str[:19].replace("T", " ")
            self._prog_table.setItem(i, 0, QTableWidgetItem(date_str))
            self._prog_table.setItem(i, 1, QTableWidgetItem(entry.get("skill_name", "")))
            val = float(entry.get("new_value", 0))
            val_item = QTableWidgetItem(f"{val:.2f}")
            val_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._prog_table.setItem(i, 2, val_item)

        # Stats
        skills_in_data = set(e.get("skill_name") for e in history)
        self._prog_stats_label.setText(
            f"Loaded {len(history)} records across {len(skills_in_data)} skills."
        )

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
        # Deduplicate: update existing row if skill already scanned
        if reading.skill_name in self._scan_skill_rows:
            row = self._scan_skill_rows[reading.skill_name]
        else:
            row = self._scan_results_table.rowCount()
            self._scan_results_table.setRowCount(row + 1)
            self._scan_skill_rows[reading.skill_name] = row

        self._scan_results_table.setItem(
            row, 0, QTableWidgetItem(reading.skill_name)
        )
        self._scan_results_table.setItem(row, 1, QTableWidgetItem(reading.rank))
        self._scan_results_table.setItem(
            row, 2, QTableWidgetItem(str(reading.rank_threshold))
        )
        self._scan_results_table.setItem(
            row, 3, QTableWidgetItem(f"{reading.current_points:.2f}")
        )

        # Highlight mismatch rows in amber
        if reading.is_mismatch:
            from PyQt6.QtGui import QColor
            warning = QColor(245, 158, 11)
            for col in range(4):
                item = self._scan_results_table.item(row, col)
                if item:
                    item.setForeground(warning)
            self._scan_warning_count += 1

        self._scan_results_table.scrollToBottom()

        # Update group title with count
        count = len(self._scan_skill_rows)
        self._scan_results_group.setTitle(f"Scan Results ({count} skills read)")
        self._scan_info_label.setText(
            f"{count} read, {self._scan_warning_count} warnings"
        )

        # Update skill value in the manager for live card refresh
        self._manager._skill_values[reading.skill_name] = reading.current_points

    def _on_ocr_page_changed(self, _data):
        """Page changed — keep accumulating (don't clear)."""
        pass

    def _on_ocr_complete(self, result):
        self._last_scan_result = result
        self._manual_scan_btn.setEnabled(
            not getattr(self._config, "ocr_auto_scan_enabled", True)
        )

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
        try:
            if ext == ".json":
                text = json.dumps(
                    {k: v for k, v in sorted(values.items())},
                    indent=2,
                )
            elif ext == ".tsv":
                buf = io.StringIO()
                writer = csv.writer(buf, delimiter="\t")
                writer.writerow(["Skill", "Value"])
                for name, val in sorted(values.items()):
                    writer.writerow([name, val])
                text = buf.getvalue()
            else:  # default csv
                buf = io.StringIO()
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

            if ext == ".json":
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ValueError("JSON must be an object mapping skill names to values")
                for k, v in data.items():
                    imported[str(k)] = float(v)
            elif ext in (".csv", ".tsv"):
                delimiter = "\t" if ext == ".tsv" else ","
                reader = csv.reader(io.StringIO(raw), delimiter=delimiter)
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

            # Confirm before overwriting
            answer = QMessageBox.question(
                self, "Import Skills",
                f"Import {len(imported)} skills from {Path(path).name}?\n\n"
                "This will overwrite current values for matching skills.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

            # Apply values through the manager
            for name, val in imported.items():
                self._manager._skill_values[name] = val

            # Upload if connected
            if self._manager._nexus_client:
                try:
                    self._manager._nexus_client.upload_skills(
                        self._manager._skill_values, track_import=True,
                    )
                except Exception as e:
                    log.error("Failed to upload imported skills: %s", e)

            # Reset gains baseline — import is the new reference point
            self._skill_gains.clear()

            # Refresh all displays
            self._refresh_skills_display()
            self._refresh_prof_display()

            QMessageBox.information(
                self, "Import Skills",
                f"Imported {len(imported)} skills from {Path(path).name}",
            )
        except (ValueError, json.JSONDecodeError) as e:
            QMessageBox.critical(self, "Import Failed", f"Invalid file format:\n{e}")
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", str(e))

    # ── Auth ──────────────────────────────────────────────────────────────

    def _on_auth_changed(self, state):
        if state.authenticated and not self._synced:
            # Sync skills on first auth
            threading.Thread(target=self._sync_on_auth, daemon=True).start()

    def _sync_on_auth(self):
        self._manager.sync_from_nexus()
        self._synced = True
        QTimer.singleShot(0, self._on_data_loaded)

    # ── Live Skill Gains ─────────────────────────────────────────────────

    def _on_skill_gain(self, event):
        """Handle a live skill gain event — update the accumulated gains dict."""
        name = event.skill_name
        self._skill_gains[name] = self._skill_gains.get(name, 0) + event.amount
        if not self._gain_refresh_pending:
            self._gain_refresh_pending = True
            QTimer.singleShot(500, self._flush_gain_refresh)

    def _flush_gain_refresh(self):
        self._gain_refresh_pending = False
        if self._tabs.currentIndex() == 0:
            self._refresh_skills_display()

    # ── Resize ────────────────────────────────────────────────────────────

    def _on_tab_changed(self, index):
        """Re-flow grid when switching tabs (viewport width may differ)."""
        if index == 0 and self._skills_view_mode == "grid":
            self._refresh_skills_display()
        elif index == 1 and self._prof_view_mode == "grid":
            self._refresh_prof_display()
        self._emit_nav()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Re-flow grid on resize
        if self._skills_view_mode == "grid" and self._tabs.currentIndex() == 0:
            self._refresh_skills_display()
        elif self._prof_view_mode == "grid" and self._tabs.currentIndex() == 1:
            self._refresh_prof_display()
