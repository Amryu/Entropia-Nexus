"""Skills page — 6-tab interface for skill management, progression, and optimization."""

import threading
from datetime import datetime, timedelta, timezone
from functools import partial

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QScrollArea, QComboBox, QCheckBox,
    QProgressBar, QLineEdit, QDoubleSpinBox, QFrame,
    QGridLayout, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QCursor

from ...skills.calculations import (
    calculate_profession_level, calculate_all_profession_levels,
    calculate_hp, build_attribute_skill_set,
    find_cheapest_profession_path, find_cheapest_hp_path,
)
from ...skills.badges import get_skill_badges, Badge
from ...skills.sync import SkillDataManager
from ..theme import (
    SECONDARY, BORDER, BORDER_HOVER, TEXT_MUTED,
    SUCCESS, SUCCESS_BG, WARNING, WARNING_BG,
    ACCENT, ACCENT_LIGHT,
)


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
                 progress: float, badges: list[Badge], parent=None):
        super().__init__(parent)
        self._skill_name = skill_name
        self._points = points
        self._editing = False

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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

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

        # Row 2: Rank + Points
        info_row = QHBoxLayout()
        info_row.setSpacing(4)
        rank_label = QLabel(rank)
        rank_label.setStyleSheet(f"font-size: 10px; color: {TEXT_MUTED}; background: transparent; border: none;")
        info_row.addWidget(rank_label)
        info_row.addStretch()

        self._points_label = QLabel(f"{points:.4f}")
        self._points_label.setStyleSheet("font-size: 10px; background: transparent; border: none;")
        info_row.addWidget(self._points_label)

        self._edit_input = QDoubleSpinBox()
        self._edit_input.setDecimals(4)
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
            "text-transform: uppercase;",
        ]
        if border:
            parts.append(f"border: 1px solid {border};")
        else:
            parts.append("border: none;")
        # Low-level badges get reduced opacity effect via muted text
        if badge.level == "low":
            parts.append("opacity: 0.7;")
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
            self._points_label.setText(f"{new_val:.4f}")
            self.value_edited.emit(self._skill_name, new_val)


class ProfessionCard(QFrame):
    """Compact profession card for grid view — matches SkillCard layout."""

    clicked = pyqtSignal(str)

    def __init__(self, prof_name: str, level: float, skill_count: int,
                 category: str = "", parent=None):
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
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        # Row 1: Name
        name_label = QLabel(prof_name)
        name_label.setStyleSheet(
            "font-weight: bold; font-size: 11px; background: transparent; border: none;"
        )
        name_label.setWordWrap(True)
        layout.addWidget(name_label)

        # Row 2: "Level N" (left) + level value (right)
        info_row = QHBoxLayout()
        info_row.setSpacing(4)
        level_int = int(level)
        rank_label = QLabel(f"Level {level_int}")
        rank_label.setStyleSheet(
            f"font-size: 10px; color: {TEXT_MUTED}; background: transparent; border: none;"
        )
        info_row.addWidget(rank_label)
        info_row.addStretch()
        level_label = QLabel(f"{level:.4f}")
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

    def __init__(self, *, signals, oauth, nexus_client, data_client=None):
        super().__init__()
        self._signals = signals
        self._oauth = oauth
        self._nexus_client = nexus_client
        self._data_client = data_client

        # Data manager
        self._manager = SkillDataManager(data_client, nexus_client)

        # View state
        self._skills_view_mode = "grid"     # "grid" or "list"
        self._prof_view_mode = "grid"
        self._skill_filter_profession = None  # filter skills by profession name
        self._prof_filter_skill = None        # filter professions by skill name
        self._last_scan_result = None
        self._synced = False

        # Rank lookup (loaded lazily)
        self._rank_thresholds: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Tab widget (no page header)
        self._tabs = QTabWidget()
        self._build_skills_tab()
        self._build_professions_tab()
        self._build_progression_tab()
        self._build_analytics_tab()
        self._build_optimizer_tab()
        self._build_scanning_tab()
        layout.addWidget(self._tabs)

        # Connect signals
        signals.ocr_progress.connect(self._on_ocr_progress)
        signals.ocr_complete.connect(self._on_ocr_complete)
        signals.skills_uploaded.connect(self._on_upload_success)
        signals.skills_upload_failed.connect(self._on_upload_failed)
        signals.auth_state_changed.connect(self._on_auth_changed)

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
                                    "Evader/Dodger/Jammer", "Looter"])
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
        self._skills_loading_label = QLabel("Loading...")
        self._skills_loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._skills_loading_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        self._skills_grid_layout.addWidget(self._skills_loading_label, 0, 0)
        self._skills_scroll.setWidget(self._skills_grid_container)
        layout.addWidget(self._skills_scroll)

        # List view (table, hidden by default)
        self._skills_table = QTableWidget()
        self._skills_table.setColumnCount(6)
        self._skills_table.setHorizontalHeaderLabels(
            ["Name", "Category", "Level", "Points", "HP", "Badges"]
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
        self._prof_view_toggle.setFixedWidth(80)
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

        # Mode selector
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Target:"))
        self._opt_mode = QComboBox()
        self._opt_mode.addItems(["Profession Level", "HP"])
        self._opt_mode.currentIndexChanged.connect(self._on_opt_mode_changed)
        mode_row.addWidget(self._opt_mode)

        # Profession selector (for profession mode)
        self._opt_prof_label = QLabel("Profession:")
        mode_row.addWidget(self._opt_prof_label)
        self._opt_prof_combo = QComboBox()
        self._opt_prof_combo.setMinimumWidth(150)
        mode_row.addWidget(self._opt_prof_combo)

        mode_row.addWidget(QLabel("Current:"))
        self._opt_current = QLabel("-")
        self._opt_current.setMinimumWidth(60)
        mode_row.addWidget(self._opt_current)

        mode_row.addWidget(QLabel("Target:"))
        self._opt_target = QDoubleSpinBox()
        self._opt_target.setDecimals(4)
        self._opt_target.setMaximum(999999)
        self._opt_target.setMinimumWidth(80)
        mode_row.addWidget(self._opt_target)

        self._opt_calc_btn = QPushButton("Calculate")
        self._opt_calc_btn.clicked.connect(self._run_optimizer)
        mode_row.addWidget(self._opt_calc_btn)

        mode_row.addStretch()
        layout.addLayout(mode_row)

        # Results
        self._opt_total_label = QLabel("")
        self._opt_total_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        layout.addWidget(self._opt_total_label)

        self._opt_table = QTableWidget()
        self._opt_table.setColumnCount(6)
        self._opt_table.setHorizontalHeaderLabels(
            ["Skill", "Current", "Added", "Method", "Cost (PED)", "Gain"]
        )
        self._opt_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._opt_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._opt_table)

        self._tabs.addTab(tab, "Optimizer")

    def _build_scanning_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(4, 4, 4, 4)

        # Auto-scan toggle
        scan_group = QGroupBox("Scan Settings")
        scan_layout = QVBoxLayout(scan_group)

        self._auto_scan_check = QCheckBox("Enable automated scanning (F7 hotkey)")
        self._auto_scan_check.setChecked(True)
        scan_layout.addWidget(self._auto_scan_check)

        btn_row = QHBoxLayout()
        self._manual_scan_btn = QPushButton("Run Manual Scan")
        self._manual_scan_btn.clicked.connect(self._trigger_manual_scan)
        btn_row.addWidget(self._manual_scan_btn)
        btn_row.addStretch()
        scan_layout.addLayout(btn_row)

        layout.addWidget(scan_group)

        # Progress
        progress_group = QGroupBox("Scan Progress")
        progress_layout = QVBoxLayout(progress_group)

        self._scan_progress_bar = QProgressBar()
        self._scan_progress_bar.setMaximum(165)
        progress_layout.addWidget(self._scan_progress_bar)

        self._scan_progress_label = QLabel("Waiting for scan...")
        progress_layout.addWidget(self._scan_progress_label)

        layout.addWidget(progress_group)

        # Upload section
        upload_group = QGroupBox("Upload to Entropia Nexus")
        upload_layout = QVBoxLayout(upload_group)

        self._upload_status = QLabel("Scan skills first, then upload.")
        upload_layout.addWidget(self._upload_status)

        upload_btn_row = QHBoxLayout()
        self._upload_btn = QPushButton("Upload Skills")
        self._upload_btn.setEnabled(False)
        self._upload_btn.clicked.connect(self._on_upload)
        upload_btn_row.addWidget(self._upload_btn)
        upload_btn_row.addStretch()
        upload_layout.addLayout(upload_btn_row)

        layout.addWidget(upload_group)

        # Last scan results table
        results_group = QGroupBox("Last Scan Results")
        results_layout = QVBoxLayout(results_group)

        self._scan_results_table = QTableWidget()
        self._scan_results_table.setColumnCount(4)
        self._scan_results_table.setHorizontalHeaderLabels(
            ["Skill", "Rank", "Points", "Progress"]
        )
        self._scan_results_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._scan_results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        results_layout.addWidget(self._scan_results_table)

        layout.addWidget(results_group)

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

        # Update UI on main thread
        QTimer.singleShot(0, self._on_data_loaded)

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

        # Populate optimizer profession list
        self._opt_prof_combo.blockSignals(True)
        self._opt_prof_combo.clear()
        for p in sorted(profs, key=lambda x: x.get("Name", "")):
            self._opt_prof_combo.addItem(p["Name"])
        self._opt_prof_combo.blockSignals(False)

        # Refresh displays
        self._refresh_skills_display()
        self._refresh_prof_display()
        self._update_optimizer_current()

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

        # Filter by profession
        if self._skill_filter_profession:
            prof_skills = set()
            for prof in self._manager.professions:
                if prof["Name"] == self._skill_filter_profession:
                    for sk in prof.get("Skills", []):
                        prof_skills.add(sk.get("Name", ""))
                    break
            meta = [s for s in meta if s["Name"] in prof_skills]

        # Filter hidden
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

            card = SkillCard(name, points, rank, progress, badges)
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

            self._skills_table.setItem(i, 0, QTableWidgetItem(name))
            self._skills_table.setItem(i, 1, QTableWidgetItem(skill.get("Category") or ""))

            rank_item = QTableWidgetItem(rank)
            self._skills_table.setItem(i, 2, rank_item)

            pts_item = QTableWidgetItem(f"{points:.4f}")
            pts_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._skills_table.setItem(i, 3, pts_item)

            hp_text = str(hp_inc) if hp_inc > 0 else ""
            self._skills_table.setItem(i, 4, QTableWidgetItem(hp_text))

            badge_text = " ".join(b.label for b in badges)
            self._skills_table.setItem(i, 5, QTableWidgetItem(badge_text))

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

    def _navigate_to_professions_for_skill(self, skill_name: str):
        """Switch to Professions tab filtered by a skill."""
        self._prof_filter_skill = skill_name
        self._prof_skill_filter.setCurrentText(skill_name)
        self._tabs.setCurrentIndex(1)  # Professions tab

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

            card = ProfessionCard(
                prof["Name"],
                prof["_level"],
                len(prof.get("Skills", [])),
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

            level_item = QTableWidgetItem(f"{prof['_level']:.4f}")
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
        self._skill_filter_profession = prof_name
        self._skills_prof_filter.setCurrentText(prof_name)
        self._tabs.setCurrentIndex(0)  # Skills tab

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
            val = entry.get("new_value", 0)
            val_item = QTableWidgetItem(f"{val:.4f}")
            val_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._prog_table.setItem(i, 2, val_item)

        # Stats
        skills_in_data = set(e.get("skill_name") for e in history)
        self._prog_stats_label.setText(
            f"Loaded {len(history)} records across {len(skills_in_data)} skills."
        )

    # ── Optimizer Tab ─────────────────────────────────────────────────────

    def _on_opt_mode_changed(self, idx):
        is_prof = idx == 0
        self._opt_prof_label.setVisible(is_prof)
        self._opt_prof_combo.setVisible(is_prof)
        self._update_optimizer_current()

    def _update_optimizer_current(self):
        values = self._manager.skill_values
        meta = self._manager.skill_metadata
        profs = self._manager.professions

        if self._opt_mode.currentIndex() == 0:
            # Profession mode
            prof_name = self._opt_prof_combo.currentText()
            if prof_name:
                levels = calculate_all_profession_levels(values, profs, meta)
                current = levels.get(prof_name, 0)
                self._opt_current.setText(f"{current:.4f}")
            else:
                self._opt_current.setText("-")
        else:
            # HP mode
            hp = calculate_hp(values, meta)
            self._opt_current.setText(f"{hp:.1f}")

    def _run_optimizer(self):
        values = self._manager.skill_values
        meta = self._manager.skill_metadata
        profs = self._manager.professions
        attr_skills = build_attribute_skill_set(meta)

        if self._opt_mode.currentIndex() == 0:
            # Profession path
            prof_name = self._opt_prof_combo.currentText()
            prof = None
            for p in profs:
                if p["Name"] == prof_name:
                    prof = p
                    break
            if not prof:
                return

            levels = calculate_all_profession_levels(values, profs, meta)
            current_level = levels.get(prof_name, 0)
            target_level = self._opt_target.value()

            result = find_cheapest_profession_path(
                values, prof.get("Skills", []),
                current_level, target_level,
                attribute_skills=attr_skills,
            )
            gain_key = "levelGain"
        else:
            # HP path
            current_hp = calculate_hp(values, meta)
            target_hp = self._opt_target.value()

            result = find_cheapest_hp_path(
                values, meta, current_hp, target_hp,
            )
            gain_key = "hpGain"

        # Display results
        allocs = result.get("allocations", [])
        total_cost = result.get("totalCost", 0)
        feasible = result.get("feasible", False)

        status = f"Total cost: {total_cost:.2f} PED"
        if not feasible:
            status += " (may not be fully achievable)"
        self._opt_total_label.setText(status)

        self._opt_table.setRowCount(len(allocs))
        for i, alloc in enumerate(allocs):
            self._opt_table.setItem(i, 0, QTableWidgetItem(alloc.get("skill", "")))

            cur_item = QTableWidgetItem(f"{alloc.get('currentPoints', 0):.4f}")
            cur_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._opt_table.setItem(i, 1, cur_item)

            add_item = QTableWidgetItem(f"{alloc.get('addedPoints', 0):.4f}")
            add_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._opt_table.setItem(i, 2, add_item)

            self._opt_table.setItem(i, 3, QTableWidgetItem(alloc.get("method", "")))

            cost_item = QTableWidgetItem(f"{alloc.get('cost', 0):.2f}")
            cost_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._opt_table.setItem(i, 4, cost_item)

            gain = alloc.get(gain_key, 0)
            gain_item = QTableWidgetItem(f"{gain:.4f}")
            gain_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._opt_table.setItem(i, 5, gain_item)

    # ── Scanning Tab ──────────────────────────────────────────────────────

    def _trigger_manual_scan(self):
        """Trigger a manual OCR scan via event bus."""
        from ...core.constants import EVENT_OCR_OVERLAYS_SHOW
        if hasattr(self._signals, 'trigger_ocr_scan'):
            self._signals.trigger_ocr_scan.emit()
        self._scan_progress_label.setText("Manual scan triggered...")
        self._manual_scan_btn.setEnabled(False)

    def _on_ocr_progress(self, data):
        if hasattr(data, "total_found"):
            self._scan_progress_bar.setValue(data.total_found)
            total_expected = getattr(data, "total_expected", 165)
            self._scan_progress_label.setText(
                f"Found {data.total_found}/{total_expected} skills"
            )

    def _on_ocr_complete(self, result):
        self._last_scan_result = result
        self._scan_progress_label.setText(
            f"Scan complete: {result.total_found}/{result.total_expected} skills"
        )
        self._scan_progress_bar.setValue(result.total_found)
        self._manual_scan_btn.setEnabled(True)

        # Populate scan results table
        skills = result.skills if hasattr(result, "skills") else []
        self._scan_results_table.setRowCount(len(skills))
        for i, skill in enumerate(skills):
            self._scan_results_table.setItem(
                i, 0, QTableWidgetItem(skill.skill_name)
            )
            self._scan_results_table.setItem(i, 1, QTableWidgetItem(skill.rank))
            self._scan_results_table.setItem(
                i, 2, QTableWidgetItem(f"{skill.current_points:.2f}")
            )
            self._scan_results_table.setItem(
                i, 3, QTableWidgetItem(f"{skill.progress_percent:.1f}%")
            )

        # Enable upload if authenticated
        self._upload_btn.setEnabled(self._oauth.is_authenticated())
        self._upload_status.setText(
            "Ready to upload." if self._oauth.is_authenticated()
            else "Login required to upload."
        )

        # Also update skill values from scan
        if skills:
            for skill in skills:
                self._manager._skill_values[skill.skill_name] = skill.current_points
            self._refresh_skills_display()
            self._refresh_prof_display()
            self._update_optimizer_current()

    def _on_upload(self):
        if not self._last_scan_result or not self._oauth.is_authenticated():
            return

        self._upload_btn.setEnabled(False)
        self._upload_status.setText("Uploading...")

        skills = {
            s.skill_name: s.current_points
            for s in self._last_scan_result.skills
        }

        threading.Thread(
            target=self._do_upload, args=(skills,), daemon=True
        ).start()

    def _do_upload(self, skills):
        result = self._nexus_client.upload_skills(skills)
        if result:
            QTimer.singleShot(0, partial(self._on_upload_success, result))
        else:
            QTimer.singleShot(0, partial(self._on_upload_failed, "Upload failed"))

    def _on_upload_success(self, result):
        self._upload_status.setText("Upload successful!")
        self._upload_btn.setEnabled(True)

    def _on_upload_failed(self, error):
        self._upload_status.setText(f"Upload failed: {error}")
        self._upload_btn.setEnabled(True)

    # ── Auth ──────────────────────────────────────────────────────────────

    def _on_auth_changed(self, state):
        if state.authenticated and not self._synced:
            # Sync skills on first auth
            threading.Thread(target=self._sync_on_auth, daemon=True).start()

        if self._last_scan_result:
            self._upload_btn.setEnabled(state.authenticated)
            self._upload_status.setText(
                "Ready to upload." if state.authenticated
                else "Login required to upload."
            )

    def _sync_on_auth(self):
        self._manager.sync_from_nexus()
        self._synced = True
        QTimer.singleShot(0, self._on_data_loaded)

    # ── Resize ────────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Re-flow grid on resize
        if self._skills_view_mode == "grid" and self._tabs.currentIndex() == 0:
            self._refresh_skills_display()
        elif self._prof_view_mode == "grid" and self._tabs.currentIndex() == 1:
            self._refresh_prof_display()
