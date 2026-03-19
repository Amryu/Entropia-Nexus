"""Tracker page — track recurring missions, events, and activity."""

from __future__ import annotations

import re
import threading
import time
from datetime import datetime, timezone, timedelta

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QDialog, QLineEdit, QComboBox, QCheckBox,
    QAbstractItemView, QSpinBox, QApplication,
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import QColor

from ..icons import svg_icon, BELL, COPY, ARROW_UP, ARROW_DOWN, PENCIL
from ..theme import (
    PRIMARY, SECONDARY, HOVER, TEXT, TEXT_MUTED, ACCENT, ACCENT_HOVER,
    BORDER, SUCCESS, ERROR, WARNING, DISABLED,
)
from ...core.constants import EVENT_TRACKER_DAILY_READY, EVENT_TRACKER_EVENT_REMINDER
from ...core.logger import get_logger

log = get_logger("Tracker")

# ---------------------------------------------------------------------------
# Interval utilities
# ---------------------------------------------------------------------------

_DAY_RE = re.compile(r"(\d+)\s*days?", re.IGNORECASE)
_HOUR_RE = re.compile(r"(\d+)\s*hours?", re.IGNORECASE)
_MIN_RE = re.compile(r"(\d+)\s*minutes?", re.IGNORECASE)
_TIME_RE = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})")

MS_24H = 86_400_000

# Waypoint regex: /wp [Planet, Long, Lat, Alt, Name] — all parts optional
_WP_RE = re.compile(
    r"(?:/wp\s*)?\[?\s*([^,]+?)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,"
    r"\s*([\d.]+)\s*,\s*(.+?)\s*\]?\s*$",
    re.IGNORECASE,
)


def _parse_waypoint(raw: str) -> tuple[dict | None, str]:
    """Parse a waypoint string into (start_location dict, planet) or (None, '')."""
    if not raw:
        return None, ""
    m = _WP_RE.match(raw.strip())
    if m:
        return {
            "longitude": float(m.group(2)),
            "latitude": float(m.group(3)),
            "altitude": float(m.group(4)),
            "name": m.group(5).strip(),
        }, m.group(1).strip()
    return None, ""


def _normalize_waypoint_input(raw: str) -> str:
    """Strip /wp prefix and brackets from user input for clean storage."""
    s = raw.strip()
    if s.lower().startswith("/wp"):
        s = s[3:].strip()
    s = s.strip("[]").strip()
    return s


def _waypoint_copy_string(m: dict) -> str | None:
    """Build a /wp string for clipboard from a mission/custom daily dict."""
    loc = m.get("start_location")
    if loc and loc.get("longitude") is not None:
        planet = m.get("planet", "?")
        return (
            f"/wp [{planet}, {loc['longitude']:.0f}, {loc['latitude']:.0f},"
            f" {loc.get('altitude', 100):.0f}, {loc.get('name') or m.get('name', '?')}]"
        )
    # Fallback: raw waypoint string for custom dailies
    wp = m.get("waypoint", "")
    if wp:
        if wp.lower().startswith("/wp"):
            return wp
        return f"/wp [{wp}]"
    return None


def _normalize_interval(value) -> str:
    """Normalize a cooldown duration (dict or string) to an interval string."""
    if not value:
        return ""
    if isinstance(value, dict):
        parts = []
        if value.get("days"):
            parts.append(f"{value['days']} days")
        if value.get("hours"):
            parts.append(f"{value['hours']} hours")
        if value.get("minutes"):
            parts.append(f"{value['minutes']} minutes")
        if value.get("seconds"):
            parts.append(f"{value['seconds']} seconds")
        return " ".join(parts) if parts else "1 day"
    return str(value)


def interval_to_ms(interval) -> int:
    """Parse a PostgreSQL INTERVAL (string or dict) to milliseconds."""
    if not interval:
        return 0
    s = _normalize_interval(interval)
    total = 0
    m = _DAY_RE.search(s)
    if m:
        total += int(m.group(1)) * 86_400_000
    m = _HOUR_RE.search(s)
    if m:
        total += int(m.group(1)) * 3_600_000
    m = _MIN_RE.search(s)
    if m:
        total += int(m.group(1)) * 60_000
    m = _TIME_RE.search(s)
    if m:
        total += int(m.group(1)) * 3_600_000
        total += int(m.group(2)) * 60_000
        total += int(m.group(3)) * 1_000
    return total or MS_24H  # default 24h


def format_countdown(ms: int) -> str:
    """Format milliseconds as a human-readable countdown."""
    if ms <= 0:
        return "Ready"
    secs = ms // 1000
    d, secs = divmod(secs, 86400)
    h, secs = divmod(secs, 3600)
    m, s = divmod(secs, 60)
    if d:
        return f"{d}d {h}h {m}m"
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def format_cooldown_label(interval) -> str:
    """Short label for a cooldown duration."""
    if not interval:
        return "?"
    s = _normalize_interval(interval)
    parts = []
    m = _DAY_RE.search(s)
    if m:
        parts.append(f"{m.group(1)}d")
    m = _HOUR_RE.search(s)
    if m:
        parts.append(f"{m.group(1)}h")
    m = _MIN_RE.search(s)
    if m:
        parts.append(f"{m.group(1)}m")
    if parts:
        return " ".join(parts)
    m = _TIME_RE.search(s)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        return f"{h}h {mn}m" if h else f"{mn}m"
    return s


# ---------------------------------------------------------------------------
# Tab / table styles
# ---------------------------------------------------------------------------

_TAB_LABELS = ["Dailies", "Events", "Hunting", "Mining", "Crafting"]
_COMING_SOON_TABS = {3, 4}  # Mining, Crafting

_TABLE_STYLE = f"""
    QTableWidget {{
        background: {PRIMARY}; color: {TEXT}; border: 1px solid {BORDER};
        border-radius: 4px; gridline-color: transparent;
    }}
    QTableWidget::item {{ padding: 4px 8px; border-bottom: 1px solid {BORDER}; }}
    QHeaderView::section {{
        background: {SECONDARY}; color: {TEXT_MUTED}; border: none;
        padding: 4px 8px; font-size: 11px; font-weight: bold;
    }}
"""


def _tab_style(active=False):
    if active:
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {ACCENT};
                border-width: 0px 0px 2px 0px;
                border-style: solid;
                border-color: {ACCENT};
                padding: 0px 16px;
                font-size: 13px;
                font-weight: bold;
            }}
        """
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {TEXT_MUTED};
            border-width: 0px 0px 2px 0px;
            border-style: solid;
            border-color: transparent;
            padding: 0px 16px;
            font-size: 13px;
        }}
        QPushButton:hover {{ color: {TEXT}; }}
    """


# ---------------------------------------------------------------------------
# Column indices for missions table
# ---------------------------------------------------------------------------

COL_NAME = 0
COL_PLANET = 1
COL_COOLDOWN = 2
COL_STARTS_ON = 3
COL_STATUS = 4
COL_ACTIONS = 5
_MISSION_HEADERS = ["Mission", "Planet", "Cooldown", "Starts On", "Status", ""]


# ---------------------------------------------------------------------------
# Tracker Page
# ---------------------------------------------------------------------------

class TrackerPage(QWidget):
    navigation_changed = pyqtSignal(object)

    def __init__(self, *, signals, config, config_path, data_client, event_bus, oauth, db):
        super().__init__()
        self._signals = signals
        self._config = config
        self._config_path = config_path
        self._data_client = data_client
        self._event_bus = event_bus
        self._db = db
        self._authenticated = oauth.auth_state.authenticated

        # One-time migration: config → database
        self._migrate_config_to_db()

        # In-memory mission list (loaded from DB) — includes both API missions and custom dailies
        custom = self._db.get_custom_dailies()
        # Parse waypoints into start_location for custom dailies
        for cd in custom:
            loc, planet = _parse_waypoint(cd.get("waypoint", ""))
            cd["start_location"] = loc
            cd["planet"] = planet or ""
        self._tracked_missions: list[dict] = self._db.get_tracked_missions() + custom

        # Track auth state for submit button
        signals.auth_state_changed.connect(self._on_auth_changed)

        # Debounced DB save
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self._persist)

        # Cooldown tick (1 second)
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._on_tick)

        # Notification grouping
        self._notified_ready: set[int] = set()
        self._notified_pre: set[int] = set()
        self._pending_group: list[dict] = []
        self._group_timer = QTimer(self)
        self._group_timer.setSingleShot(True)
        self._group_timer.setInterval(5000)
        self._group_timer.timeout.connect(self._flush_group)

        # Cached API data
        self._all_missions: list[dict] = []
        self._planets: list[str] = []
        self._events_upcoming: list[dict] = []
        self._events_past: list[dict] = []

        self._build_ui()
        self._load_data_async()
        self._tick_timer.start()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Tab bar
        tab_bar = QWidget()
        tab_bar.setFixedHeight(40)
        tab_bar.setStyleSheet(
            f"background-color: {PRIMARY};"
            f" border-width: 0px 0px 1px 0px;"
            f" border-style: solid;"
            f" border-color: {BORDER};"
        )
        tab_layout = QHBoxLayout(tab_bar)
        tab_layout.setContentsMargins(16, 0, 16, 0)
        tab_layout.setSpacing(0)

        self._tab_buttons: list[QPushButton] = []
        self._active_tab = 0
        for i, label in enumerate(_TAB_LABELS):
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(40)
            btn.clicked.connect(lambda _, idx=i: self._switch_tab(idx))
            tab_layout.addWidget(btn)
            self._tab_buttons.append(btn)
        tab_layout.addStretch()
        root.addWidget(tab_bar)

        # Sub-pages
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_dailies_page())    # 0: Dailies
        self._stack.addWidget(self._build_events_page())     # 1: Events
        self._stack.addWidget(self._build_hunting_page())    # 2: Hunting
        for i in sorted(_COMING_SOON_TABS):
            self._stack.addWidget(self._build_coming_soon_page(_TAB_LABELS[i]))
        root.addWidget(self._stack)

        self._switch_tab(0)

    def _switch_tab(self, index: int):
        self._active_tab = index
        self._stack.setCurrentIndex(index)
        for i, btn in enumerate(self._tab_buttons):
            btn.setStyleSheet(_tab_style(i == index))

    # --- Dailies sub-page ---

    def _build_dailies_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(8)

        header = QHBoxLayout()
        lbl = QLabel("Tracked Missions")
        lbl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {TEXT}; border: none;")
        header.addWidget(lbl)
        header.addStretch()
        add_btn = QPushButton("+ Add Mission")
        add_btn.setFixedHeight(28)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: #fff; border: none;
                border-radius: 4px; padding: 4px 12px; font-size: 12px;
            }}
            QPushButton:hover {{ background: {ACCENT_HOVER}; }}
        """)
        add_btn.clicked.connect(self._open_mission_picker)
        header.addWidget(add_btn)

        custom_btn = QPushButton("+ Custom Daily")
        custom_btn.setFixedHeight(28)
        custom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        custom_btn.setStyleSheet(f"""
            QPushButton {{
                background: {SECONDARY}; color: {TEXT}; border: 1px solid {BORDER};
                border-radius: 4px; padding: 4px 12px; font-size: 12px;
            }}
            QPushButton:hover {{ background: {HOVER}; }}
        """)
        custom_btn.clicked.connect(self._open_custom_daily_dialog)
        header.addWidget(custom_btn)
        layout.addLayout(header)

        self._missions_table = QTableWidget(0, len(_MISSION_HEADERS))
        self._missions_table.setHorizontalHeaderLabels(_MISSION_HEADERS)
        self._missions_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._missions_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._missions_table.verticalHeader().setVisible(False)
        self._missions_table.setShowGrid(False)
        self._missions_table.setStyleSheet(_TABLE_STYLE)
        hdr = self._missions_table.horizontalHeader()
        hdr.setStretchLastSection(False)
        hdr.setMinimumSectionSize(100)
        hdr.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        for col, width in (
            (COL_PLANET, 100),
            (COL_COOLDOWN, 80),
            (COL_STARTS_ON, 100),
            (COL_STATUS, 80),
            (COL_ACTIONS, 280),
        ):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            hdr.resizeSection(col, width)
        layout.addWidget(self._missions_table)

        self._refresh_missions_table()
        return page

    # --- Events sub-page ---

    def _build_events_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(8)

        header = QHBoxLayout()
        self._events_label = QLabel("Loading events...")
        self._events_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px; border: none;")
        header.addWidget(self._events_label)
        header.addStretch()

        self._submit_event_btn = QPushButton("Submit Event")
        self._submit_event_btn.setFixedHeight(28)
        self._submit_event_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._submit_event_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: #fff; border: none;
                border-radius: 4px; padding: 4px 12px; font-size: 12px;
            }}
            QPushButton:hover {{ background: {ACCENT_HOVER}; }}
            QPushButton:disabled {{ background: {SECONDARY}; color: {TEXT_MUTED}; }}
        """)
        self._submit_event_btn.setEnabled(self._authenticated)
        self._submit_event_btn.setToolTip(
            "Submit a new event" if self._authenticated
            else "Log in to submit events"
        )
        self._submit_event_btn.clicked.connect(self._open_submit_event)
        header.addWidget(self._submit_event_btn)
        layout.addLayout(header)

        self._events_table = QTableWidget(0, 5)
        self._events_table.setHorizontalHeaderLabels(["Event", "Date", "Location", "Status", ""])
        self._events_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._events_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._events_table.verticalHeader().setVisible(False)
        self._events_table.setShowGrid(False)
        self._events_table.setStyleSheet(_TABLE_STYLE)
        ehdr = self._events_table.horizontalHeader()
        ehdr.setStretchLastSection(False)
        ehdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        ehdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        ehdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        ehdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        ehdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        ehdr.resizeSection(4, 100)
        layout.addWidget(self._events_table)

        return page

    # --- Hunting sub-page ---

    def _build_hunting_page(self):
        from PyQt6.QtWidgets import (
            QTextEdit, QSplitter, QTreeWidget, QTreeWidgetItem, QScrollArea,
        )
        from PyQt6.QtGui import QFont

        page = QWidget()
        outer = QHBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Left sidebar: session tree ──────────────────────────────
        sidebar = QWidget()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet(
            f"background: {SECONDARY};"
            f"border-right: 1px solid {BORDER};"
        )
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(0, 8, 0, 8)
        sb_layout.setSpacing(4)

        # "Live" button
        self._hunt_live_btn = QPushButton("  Live")
        self._hunt_live_btn.setFixedHeight(32)
        self._hunt_live_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hunt_live_btn.setCheckable(True)
        self._hunt_live_btn.setChecked(True)
        self._hunt_live_btn.setStyleSheet(self._tree_btn_style(True))
        self._hunt_live_btn.clicked.connect(self._hunt_show_live)
        sb_layout.addWidget(self._hunt_live_btn)

        # Separator
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER};")
        sb_layout.addWidget(sep)

        # Session tree
        self._hunt_tree = QTreeWidget()
        self._hunt_tree.setHeaderHidden(True)
        self._hunt_tree.setIndentation(14)
        self._hunt_tree.setStyleSheet(
            f"QTreeWidget {{"
            f"  background: {SECONDARY}; color: {TEXT};"
            f"  border: none; font-size: 11px;"
            f"}}"
            f"QTreeWidget::item {{"
            f"  padding: 3px 4px; border: none;"
            f"}}"
            f"QTreeWidget::item:hover {{"
            f"  background: {HOVER};"
            f"}}"
            f"QTreeWidget::item:selected {{"
            f"  background: {HOVER}; color: {ACCENT};"
            f"}}"
        )
        self._hunt_tree.itemClicked.connect(self._on_hunt_tree_clicked)
        sb_layout.addWidget(self._hunt_tree, 1)

        outer.addWidget(sidebar)

        # ── Right content area ──────────────────────────────────────
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 12, 16, 12)
        content_layout.setSpacing(8)

        # Header row: title + timer + status
        header = QHBoxLayout()
        title = QLabel("Hunting Tracker")
        title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {TEXT}; border: none;")
        header.addWidget(title)
        header.addStretch()

        self._hunt_timer_label = QLabel("00:00:00")
        self._hunt_timer_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 13px; font-family: Consolas; border: none;"
        )
        header.addWidget(self._hunt_timer_label)

        self._hunt_status_label = QLabel("No active session")
        self._hunt_status_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; border: none; margin-left: 12px;")
        header.addWidget(self._hunt_status_label)

        configure_btn = QPushButton("Configure...")
        configure_btn.setFixedHeight(28)
        configure_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        configure_btn.setStyleSheet(
            f"QPushButton {{ background: {ACCENT}; color: #fff; border: none;"
            f"  border-radius: 4px; padding: 4px 12px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {ACCENT_HOVER}; }}"
        )
        configure_btn.clicked.connect(self._open_hunt_config)
        header.addWidget(configure_btn)
        content_layout.addLayout(header)

        # Summary bar
        summary_bar = QWidget()
        summary_bar.setStyleSheet(
            f"background: {SECONDARY}; border: 1px solid {BORDER}; border-radius: 4px;"
        )
        summary_layout = QHBoxLayout(summary_bar)
        summary_layout.setContentsMargins(12, 8, 12, 8)
        summary_layout.setSpacing(16)

        self._hunt_kills_label = self._stat_label("Kills", "0")
        self._hunt_cost_label = self._stat_label("Cost", "0.00")
        self._hunt_loot_label = self._stat_label("Loot", "0.00")
        self._hunt_return_label = self._stat_label("Return", "—")
        summary_layout.addWidget(self._hunt_kills_label)
        summary_layout.addWidget(self._hunt_cost_label)
        summary_layout.addWidget(self._hunt_loot_label)
        summary_layout.addWidget(self._hunt_return_label)
        summary_layout.addStretch()
        content_layout.addWidget(summary_bar)

        # View toggle: Event Log ↔ Hunt Log
        self._log_mode = "event"  # "event" or "hunt"
        self._log_toggle_btn = QPushButton("Hunt Log")
        self._log_toggle_btn.setFixedHeight(28)
        self._log_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._log_toggle_btn.setStyleSheet(
            f"QPushButton {{ background: {SECONDARY}; color: {TEXT};"
            f"  border: 1px solid {BORDER}; border-radius: 4px;"
            f"  padding: 4px 12px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {HOVER}; }}"
        )
        self._log_toggle_btn.clicked.connect(self._toggle_log_mode)
        content_layout.addWidget(self._log_toggle_btn)

        # Stacked widget for Event Log / Hunt Log
        self._log_stack = QStackedWidget()

        # Page 0: Event Log (real-time tracking log)
        self._hunt_log = QTextEdit()
        self._hunt_log.setReadOnly(True)
        self._hunt_log.setFont(QFont("Consolas", 9))
        self._hunt_log.setStyleSheet(
            f"QTextEdit {{"
            f"  background: {PRIMARY}; color: {TEXT};"
            f"  border: 1px solid {BORDER}; border-radius: 4px;"
            f"  padding: 8px;"
            f"}}"
        )
        self._hunt_log.setPlaceholderText(
            "Tracking log will appear here when a hunting session is active.\n"
            "Start hunting in-game to see real-time combat events, tool attribution, "
            "and encounter tracking."
        )
        self._log_stack.addWidget(self._hunt_log)

        # Page 1: Hunt Log (structured encounter/loadout history)
        from PyQt6.QtWidgets import QScrollArea, QListWidget
        hunt_log_container = QWidget()
        hunt_log_layout = QVBoxLayout(hunt_log_container)
        hunt_log_layout.setContentsMargins(0, 0, 0, 0)
        hunt_log_layout.setSpacing(4)

        self._hunt_log_list = QListWidget()
        self._hunt_log_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._hunt_log_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._hunt_log_list.setStyleSheet(
            f"QListWidget {{"
            f"  background: {PRIMARY}; color: {TEXT};"
            f"  border: 1px solid {BORDER}; border-radius: 4px;"
            f"  font-size: 11px;"
            f"}}"
            f"QListWidget::item {{"
            f"  padding: 4px 8px; border-bottom: 1px solid {BORDER};"
            f"}}"
            f"QListWidget::item:selected {{"
            f"  background: {HOVER};"
            f"}}"
        )
        hunt_log_layout.addWidget(self._hunt_log_list, 1)

        # Insert buttons row
        insert_row = QHBoxLayout()
        insert_row.setSpacing(6)

        add_separator_btn = QPushButton("+ Hunt Separator")
        add_separator_btn.setFixedHeight(26)
        add_separator_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_separator_btn.setStyleSheet(
            f"QPushButton {{ background: {SECONDARY}; color: {TEXT_MUTED};"
            f"  border: 1px solid {BORDER}; border-radius: 4px;"
            f"  padding: 2px 10px; font-size: 11px; }}"
            f"QPushButton:hover {{ background: {HOVER}; color: {TEXT}; }}"
        )
        add_separator_btn.clicked.connect(self._add_hunt_separator)
        insert_row.addWidget(add_separator_btn)

        add_loadout_btn = QPushButton("+ Loadout Update")
        add_loadout_btn.setFixedHeight(26)
        add_loadout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_loadout_btn.setStyleSheet(
            f"QPushButton {{ background: {SECONDARY}; color: {TEXT_MUTED};"
            f"  border: 1px solid {BORDER}; border-radius: 4px;"
            f"  padding: 2px 10px; font-size: 11px; }}"
            f"QPushButton:hover {{ background: {HOVER}; color: {TEXT}; }}"
        )
        add_loadout_btn.clicked.connect(self._add_loadout_update)
        insert_row.addWidget(add_loadout_btn)

        delete_btn = QPushButton("Delete Selected")
        delete_btn.setFixedHeight(26)
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setStyleSheet(
            f"QPushButton {{ background: {SECONDARY}; color: {TEXT_MUTED};"
            f"  border: 1px solid {BORDER}; border-radius: 4px;"
            f"  padding: 2px 10px; font-size: 11px; }}"
            f"QPushButton:hover {{ background: {HOVER}; color: {ERROR}; }}"
        )
        delete_btn.clicked.connect(self._delete_hunt_log_item)
        insert_row.addWidget(delete_btn)

        insert_row.addStretch()
        hunt_log_layout.addLayout(insert_row)

        self._log_stack.addWidget(hunt_log_container)
        content_layout.addWidget(self._log_stack, 1)

        # Alive encounters bar (bottom)
        self._encounters_bar = QWidget()
        self._encounters_bar.setStyleSheet(
            f"background: {SECONDARY}; border: 1px solid {BORDER}; border-radius: 4px;"
        )
        self._encounters_bar_layout = QHBoxLayout(self._encounters_bar)
        self._encounters_bar_layout.setContentsMargins(8, 6, 8, 6)
        self._encounters_bar_layout.setSpacing(12)
        enc_title = QLabel("Encounters:")
        enc_title.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px; font-weight: bold; border: none;")
        self._encounters_bar_layout.addWidget(enc_title)
        self._encounters_bar_layout.addStretch()
        self._encounters_bar.hide()  # Hidden until encounters exist
        content_layout.addWidget(self._encounters_bar)

        # Clear button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        clear_btn = QPushButton("Clear Log")
        clear_btn.setFixedHeight(28)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet(
            f"QPushButton {{ background: {SECONDARY}; color: {TEXT_MUTED};"
            f"  border: 1px solid {BORDER}; border-radius: 4px;"
            f"  padding: 4px 12px; font-size: 12px; }}"
            f"QPushButton:hover {{ background: {HOVER}; }}"
        )
        clear_btn.clicked.connect(self._hunt_log.clear)
        btn_row.addWidget(clear_btn)
        content_layout.addLayout(btn_row)

        outer.addWidget(content, 1)

        # ── Session timer ───────────────────────────────────────────
        self._hunt_session_start: datetime | None = None
        self._hunt_timer = QTimer(self)
        self._hunt_timer.setInterval(1000)
        self._hunt_timer.timeout.connect(self._update_hunt_timer)

        # ── Connect signals ─────────────────────────────────────────
        self._signals.tracking_log.connect(self._on_tracking_log)
        self._signals.hunt_session_updated.connect(self._on_hunt_session_updated)
        self._signals.hunt_session_started.connect(self._on_hunt_session_started)
        self._signals.hunt_session_stopped.connect(self._on_hunt_session_stopped)

        # Load historical sessions into tree
        self._hunt_refresh_tree()

        return page

    def _tree_btn_style(self, active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ background: {HOVER}; color: {ACCENT};"
                f"  border: none; font-weight: bold; font-size: 12px;"
                f"  text-align: left; padding: 4px 12px; }}"
            )
        return (
            f"QPushButton {{ background: transparent; color: {TEXT};"
            f"  border: none; font-size: 12px;"
            f"  text-align: left; padding: 4px 12px; }}"
            f"QPushButton:hover {{ background: {HOVER}; }}"
        )

    @staticmethod
    def _return_str(cost: float, loot: float) -> str:
        """Format return % with color."""
        if cost <= 0:
            return ""
        ret = loot / cost * 100
        color = "#4ec9b0" if ret >= 100 else "#f44747"
        return f"  ({ret:.0f}%)"

    def _hunt_refresh_tree(self):
        """Populate the session tree from DB."""
        from PyQt6.QtWidgets import QTreeWidgetItem

        self._hunt_tree.clear()
        sessions = self._db.get_recent_sessions(limit=100)

        # Group by month
        months: dict[str, list[dict]] = {}
        for s in sessions:
            start = s.get("start_time", "")
            month_key = start[:7] if len(start) >= 7 else "Unknown"  # YYYY-MM
            months.setdefault(month_key, []).append(s)

        for month_key in sorted(months.keys(), reverse=True):
            month_sessions = months[month_key]
            # Month node
            month_cost = sum(s.get("total_cost", 0) for s in month_sessions)
            month_loot = sum(s.get("total_loot", 0) for s in month_sessions)
            month_kills = sum(s.get("kills", 0) for s in month_sessions)
            month_label = month_key
            try:
                dt = datetime.strptime(month_key, "%Y-%m")
                month_label = dt.strftime("%B %Y")
            except ValueError:
                pass
            ret_str = self._return_str(month_cost, month_loot)
            month_item = QTreeWidgetItem([f"{month_label}{ret_str}"])
            month_item.setToolTip(0, f"{month_kills} kills, {month_cost:.2f} cost, {month_loot:.2f} loot")

            for s in month_sessions:
                start = s.get("start_time", "")
                s_cost = s.get("total_cost", 0)
                s_loot = s.get("total_loot", 0)
                s_kills = s.get("kills", 0)
                # Format: "19 Mar 14:30  (85%)"
                try:
                    dt = datetime.fromisoformat(start)
                    date_str = dt.strftime("%d %b %H:%M")
                except (ValueError, TypeError):
                    date_str = start[:16]
                ret_str = self._return_str(s_cost, s_loot)
                session_item = QTreeWidgetItem([f"{date_str}{ret_str}"])
                session_item.setData(0, Qt.ItemDataRole.UserRole, s.get("id"))
                session_item.setToolTip(0, f"{s_kills} kills, {s_cost:.2f} cost, {s_loot:.2f} loot")

                # Load hunts for this session
                hunts = self._db.get_session_hunts_with_stats(s.get("id", ""))
                for h in hunts:
                    h_cost = h.get("total_cost", 0)
                    h_loot = h.get("total_loot", 0)
                    h_kills = h.get("kills", 0)
                    mob = h.get("primary_mob") or "Mixed"
                    ret_str = self._return_str(h_cost, h_loot)
                    hunt_item = QTreeWidgetItem([f"{mob}{ret_str}"])
                    hunt_item.setData(0, Qt.ItemDataRole.UserRole, h.get("id"))
                    hunt_item.setData(0, Qt.ItemDataRole.UserRole + 1, "hunt")
                    hunt_item.setToolTip(0, f"{h_kills} kills, {h_cost:.2f} cost, {h_loot:.2f} loot")
                    session_item.addChild(hunt_item)

                month_item.addChild(session_item)

            self._hunt_tree.addTopLevelItem(month_item)

    def _on_hunt_tree_clicked(self, item, column):
        """Handle tree item click — switch to historical view (placeholder)."""
        self._hunt_live_btn.setChecked(False)
        self._hunt_live_btn.setStyleSheet(self._tree_btn_style(False))
        # For now, just show info in the log
        node_id = item.data(0, Qt.ItemDataRole.UserRole)
        if node_id:
            self._hunt_log.setPlaceholderText(f"Historical view for {item.text(0)} — coming soon")

    def _hunt_show_live(self):
        """Switch back to live view."""
        self._hunt_live_btn.setChecked(True)
        self._hunt_live_btn.setStyleSheet(self._tree_btn_style(True))
        self._hunt_tree.clearSelection()
        self._hunt_log.setPlaceholderText(
            "Tracking log will appear here when a hunting session is active.\n"
            "Start hunting in-game to see real-time combat events."
        )

    def _stat_label(self, title: str, value: str) -> QLabel:
        """Create a small stat label for the summary bar."""
        lbl = QLabel(f"<span style='color:{TEXT_MUTED};font-size:10px;'>{title}</span>"
                     f"<br><span style='font-size:13px;font-weight:bold;'>{value}</span>")
        lbl.setStyleSheet(f"color: {TEXT}; border: none;")
        return lbl

    def _update_stat_label(self, label: QLabel, title: str, value: str):
        label.setText(
            f"<span style='color:{TEXT_MUTED};font-size:10px;'>{title}</span>"
            f"<br><span style='font-size:13px;font-weight:bold;'>{value}</span>"
        )

    # Category → color mapping for log entries
    _LOG_COLORS = {
        "combat": "#d4d4d4",   # light gray
        "loot": "#4ec9b0",     # teal
        "death": "#f44747",    # red
        "global": "#dcdcaa",   # gold
        "ocr": "#569cd6",      # blue
        "tool": "#c586c0",     # purple
        "encounter": "#ce9178",  # orange
        "session": "#6a9955",  # green
    }

    def _on_tracking_log(self, entry):
        """Append a tracking log entry to the hunt log."""
        if not isinstance(entry, dict):
            return
        time_str = entry.get("time", "")[11:23]  # HH:MM:SS.mmm
        category = entry.get("category", "")
        message = entry.get("message", "")
        color = self._LOG_COLORS.get(category, TEXT)
        tag = category.upper().ljust(9)

        line = (
            f"<span style='color:{TEXT_MUTED}'>{time_str}</span> "
            f"<span style='color:{color};font-weight:bold'>{tag}</span> "
            f"<span style='color:{color}'>{message}</span>"
        )
        self._hunt_log.append(line)

        # Auto-scroll to bottom
        cursor = self._hunt_log.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._hunt_log.setTextCursor(cursor)

    def _update_hunt_timer(self):
        """Update the session elapsed time display."""
        if not self._hunt_session_start:
            return
        elapsed = datetime.utcnow() - self._hunt_session_start
        total_secs = int(elapsed.total_seconds())
        h, rem = divmod(total_secs, 3600)
        m, s = divmod(rem, 60)
        self._hunt_timer_label.setText(f"{h:02d}:{m:02d}:{s:02d}")

    def _on_hunt_session_started(self, data):
        """Handle session start — start timer, update status."""
        self._hunt_session_start = datetime.utcnow()
        self._hunt_timer.start()
        self._hunt_timer_label.setText("00:00:00")
        self._hunt_status_label.setText("Session active")

    def _on_hunt_session_updated(self, data):
        """Update the summary bar with session stats."""
        if not isinstance(data, dict):
            return
        kills = data.get("kills", 0)
        cost = data.get("total_cost", 0)
        loot = data.get("loot_total", 0)
        ret = (loot / cost * 100) if cost > 0 else 0

        self._update_stat_label(self._hunt_kills_label, "Kills", str(kills))
        self._update_stat_label(self._hunt_cost_label, "Cost", f"{cost:.2f}")
        self._update_stat_label(self._hunt_loot_label, "Loot", f"{loot:.2f}")

        if cost > 0:
            ret_color = "#4ec9b0" if ret >= 100 else "#f44747"
            self._update_stat_label(
                self._hunt_return_label, "Return",
                f"<span style='color:{ret_color}'>{ret:.1f}%</span>",
            )
        else:
            self._update_stat_label(self._hunt_return_label, "Return", "—")

        self._hunt_status_label.setText(
            f"Session active — {kills} kills, {data.get('hunt_count', 0)} hunts"
        )

        # Rebuild encounters bar
        alive = data.get("alive_encounters", [])
        self._rebuild_encounters_bar(alive)

        # Store data for hunt log rebuilds
        self._last_hunt_data = data

        # Refresh hunt log if visible
        if self._log_mode == "hunt":
            self._rebuild_hunt_log()

    def _rebuild_encounters_bar(self, alive: list[dict]):
        """Rebuild the encounters bar from alive encounters list."""
        # Clear existing encounter labels (keep the title label at index 0 and stretch)
        while self._encounters_bar_layout.count() > 2:
            item = self._encounters_bar_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        if not alive:
            self._encounters_bar.hide()
            return

        self._encounters_bar.show()
        for enc in alive:
            is_active = enc.get("is_active", False)
            mob = enc.get("mob_name", "?")
            dmg = enc.get("damage_dealt", 0)
            color = ACCENT if is_active else TEXT_MUTED
            indicator = "\u25cf" if is_active else "\u25cb"  # ● / ○

            lbl = QLabel(
                f"<span style='color:{color}'>{indicator} {mob}</span>"
                f"  <span style='color:{TEXT_MUTED};font-size:9px'>{dmg:.0f} dmg</span>"
            )
            lbl.setStyleSheet(f"font-size: 11px; border: none;")
            # Insert before the stretch
            self._encounters_bar_layout.insertWidget(
                self._encounters_bar_layout.count() - 1, lbl
            )

    def _toggle_log_mode(self):
        """Toggle between Event Log and Hunt Log views."""
        if self._log_mode == "event":
            self._log_mode = "hunt"
            self._log_stack.setCurrentIndex(1)
            self._log_toggle_btn.setText("Event Log")
            self._rebuild_hunt_log()
        else:
            self._log_mode = "event"
            self._log_stack.setCurrentIndex(0)
            self._log_toggle_btn.setText("Hunt Log")

    # -- Hunt Log (structured encounter + loadout history) --------------------

    _HUNT_LOG_ICONS = {
        "encounter": ("\u2694", "#d4d4d4"),      # ⚔ gray
        "hunt_separator": ("\u2500\u2500\u2500", ACCENT),  # ─── blue
        "initial": ("\u25c6", "#6a9955"),         # ◆ green
        "edit": ("\u270e", ACCENT),               # ✎ blue
        "enhancer_break": ("\u2717", "#f44747"),  # ✗ red
        "enhancer_adjust": ("\u2699", "#dcdcaa"), # ⚙ gold
        "tool_detected": ("\u2795", "#4ec9b0"),   # + teal
    }

    def _rebuild_hunt_log(self):
        """Rebuild the Hunt Log from session data."""
        from PyQt6.QtWidgets import QListWidgetItem

        self._hunt_log_list.clear()
        if not hasattr(self, '_last_hunt_data'):
            return

        data = self._last_hunt_data
        loadout_events = data.get("loadout_events", [])

        # Build a merged timeline: encounters (from session.encounters via DB)
        # + loadout events, sorted by timestamp
        timeline = []

        # Add loadout events
        for evt in loadout_events:
            ts = evt.get("timestamp", "")
            timeline.append({
                "timestamp": ts,
                "type": evt.get("event_type", ""),
                "text": evt.get("description", ""),
                "cost": evt.get("cost_per_shot"),
                "db_id": evt.get("id"),
                "draggable": evt.get("event_type") in ("hunt_separator", "edit", "enhancer_adjust"),
            })

        # Sort by timestamp
        timeline.sort(key=lambda x: x.get("timestamp", ""))

        for entry in timeline:
            etype = entry["type"]
            ts = entry.get("timestamp", "")
            time_str = ts[11:19] if len(ts) >= 19 else ts
            icon, color = self._HUNT_LOG_ICONS.get(etype, ("\u2022", TEXT_MUTED))
            text = entry.get("text", "")
            cost = entry.get("cost")
            cost_str = f"  [{cost:.4f} PED/shot]" if cost else ""

            if etype == "hunt_separator":
                display = f"{'─' * 10}  Hunt boundary  {'─' * 10}"
            else:
                display = f"{time_str}  {icon} {text}{cost_str}"

            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, entry.get("db_id"))
            item.setData(Qt.ItemDataRole.UserRole + 1, etype)

            # Only separators and loadout updates are draggable
            if entry.get("draggable"):
                item.setFlags(
                    item.flags() | Qt.ItemFlag.ItemIsDragEnabled
                )
            else:
                item.setFlags(
                    item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled
                )

            self._hunt_log_list.addItem(item)

    def _add_hunt_separator(self):
        """Insert a hunt separator at the current selection point."""
        row = self._hunt_log_list.currentRow()
        if row < 0:
            row = self._hunt_log_list.count()

        # Persist to DB
        from datetime import datetime
        self._db.insert_loadout_event(
            session_id=self._last_hunt_data.get("session_id", "") if hasattr(self, '_last_hunt_data') else "",
            timestamp=datetime.utcnow().isoformat(),
            event_type="hunt_separator",
            description="Hunt boundary",
        )
        self._rebuild_hunt_log()

    def _add_loadout_update(self):
        """Insert a manual loadout update at the current selection point."""
        from ..dialogs.hunt_config_dialog import HuntConfigDialog
        dlg = HuntConfigDialog(
            config=self._config,
            db=self._db,
            event_bus=self._event_bus,
            parent=self,
        )
        dlg.exec()
        self._rebuild_hunt_log()

    def _delete_hunt_log_item(self):
        """Delete the selected hunt log item."""
        item = self._hunt_log_list.currentItem()
        if not item:
            return
        db_id = item.data(Qt.ItemDataRole.UserRole)
        etype = item.data(Qt.ItemDataRole.UserRole + 1)

        # Only allow deleting user-created items
        if etype in ("hunt_separator", "edit", "enhancer_adjust", "tool_detected", "initial") and db_id:
            self._db.delete_loadout_event(db_id)
            self._rebuild_hunt_log()

    def _on_hunt_session_stopped(self, _data):
        self._hunt_timer.stop()
        self._hunt_status_label.setText("No active session")
        self._encounters_bar.hide()
        # Refresh tree to include the just-ended session
        self._hunt_refresh_tree()

    def _open_hunt_config(self):
        """Open the hunt configuration dialog."""
        from ..dialogs.hunt_config_dialog import HuntConfigDialog
        dlg = HuntConfigDialog(
            config=self._config,
            db=self._db,
            event_bus=self._event_bus,
            parent=self,
        )
        dlg.exec()

    # --- Coming soon sub-page ---

    def _build_coming_soon_page(self, title: str):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.addStretch()
        lbl = QLabel(f"{title}\nComing Soon")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 16px; border: none;")
        layout.addWidget(lbl)
        layout.addStretch()
        return page

    # ------------------------------------------------------------------
    # Auth state
    # ------------------------------------------------------------------

    def _on_auth_changed(self, state):
        self._authenticated = state.authenticated
        if hasattr(self, "_submit_event_btn"):
            self._submit_event_btn.setEnabled(self._authenticated)
            self._submit_event_btn.setToolTip(
                "Submit a new event" if self._authenticated
                else "Log in to submit events"
            )

    def _open_submit_event(self):
        import webbrowser
        webbrowser.open(f"{self._config.nexus_base_url}/events/submit")

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_data_async(self):
        threading.Thread(target=self._fetch_data, daemon=True, name="tracker-fetch").start()

    def _fetch_data(self):
        try:
            missions = self._data_client.get_missions() or []
            self._all_missions = [
                m for m in missions
                if (m.get("Properties") or {}).get("Type") == "Recurring"
            ]
            # Extract unique planet names
            planet_set = set()
            for m in self._all_missions:
                p = (m.get("Planet") or {}).get("Name")
                if p:
                    planet_set.add(p)
            self._planets = sorted(planet_set)
        except Exception as e:
            log.warning("Failed to fetch missions: %s", e)

        try:
            data = self._data_client.get_events(include_past=True, past_limit=20)
            if isinstance(data, dict):
                self._events_upcoming = data.get("upcoming") or []
                self._events_past = data.get("past") or []
            else:
                # Fallback for old API response (flat list)
                self._events_upcoming = data if isinstance(data, list) else []
                self._events_past = []
        except Exception as e:
            log.warning("Failed to fetch events: %s", e)

        # Schedule UI update on main thread
        QTimer.singleShot(0, self._on_data_loaded)

    def _on_data_loaded(self):
        self._refresh_events_table()

    # ------------------------------------------------------------------
    # Missions table
    # ------------------------------------------------------------------

    def _refresh_missions_table(self):
        tracked = self._tracked_missions or []
        now_ms = int(time.time() * 1000)

        # Compute remaining time for each
        entries = []
        for m in tracked:
            started = m.get("cooldown_started_at")
            if started:
                try:
                    started_ms = int(datetime.fromisoformat(started).timestamp() * 1000)
                except (ValueError, TypeError):
                    started_ms = 0
                cd_ms = m.get("cooldown_ms", MS_24H)
                remaining = max(0, cd_ms - (now_ms - started_ms))
            else:
                remaining = -1  # not started
            entries.append((m, remaining))

        # Sort: on-cooldown (asc), ready+idle by order, disabled at bottom
        def sort_key(pair):
            m, r = pair
            if m.get("is_custom") and not m.get("enabled", True):
                return (2, m.get("order", 0))
            if r > 0:
                return (0, r)
            return (1, m.get("order", 0))

        def reorder_group(pair):
            m, r = pair
            if m.get("is_custom") and not m.get("enabled", True):
                return 2  # disabled — no arrows shown
            if r > 0:
                return 0  # on-cooldown — position driven by timer
            return 1      # ready or idle (enabled) — reorderable

        entries.sort(key=sort_key)

        self._missions_table.setUpdatesEnabled(False)
        try:
            self.__populate_missions_rows(entries, reorder_group)
        finally:
            self._missions_table.setUpdatesEnabled(True)

    def __populate_missions_rows(self, entries, reorder_group=None):
        num_entries = len(entries)
        self._missions_table.setRowCount(num_entries)
        icon_size = QSize(14, 14)
        for row, (m, remaining) in enumerate(entries):
            mid = m.get("id")
            name = m.get("name", "?")
            is_custom = m.get("is_custom", False)
            is_disabled = is_custom and not m.get("enabled", True)
            text_color = DISABLED if is_disabled else TEXT

            # Name — cell widget with badges and optional checkbox
            needs_widget = is_custom or m.get("has_expiry")
            if needs_widget:
                name_w = QWidget()
                name_w.setStyleSheet("background: transparent;")
                nl = QHBoxLayout(name_w)
                nl.setContentsMargins(4, 0, 0, 0)
                nl.setSpacing(6)

                if is_custom:
                    cb = QCheckBox()
                    cb.setChecked(m.get("enabled", True))
                    cb.setToolTip("Enable / disable this custom daily")
                    cb.stateChanged.connect(
                        lambda state, i=mid: self._toggle_custom_enabled(i, state != 0)
                    )
                    nl.addWidget(cb)

                name_lbl = QLabel(name)
                name_lbl.setStyleSheet(
                    f"color: {text_color}; font-size: 12px; background: transparent;"
                )
                nl.addWidget(name_lbl)

                if is_custom:
                    badge = QLabel("Custom")
                    badge.setStyleSheet(
                        f"color: {ACCENT if not is_disabled else DISABLED};"
                        f" font-size: 9px; font-weight: bold;"
                        f" border: 1px solid {ACCENT if not is_disabled else DISABLED};"
                        f" border-radius: 3px;"
                        " padding: 1px 3px; background: transparent;"
                    )
                    nl.addWidget(badge)

                if m.get("has_expiry"):
                    badge_24h = QLabel("24h")
                    badge_24h.setToolTip("Expires 24h after accept")
                    badge_24h.setStyleSheet(
                        f"color: {WARNING}; font-size: 9px; font-weight: bold;"
                        f" border: 1px solid {WARNING}; border-radius: 3px;"
                        " padding: 1px 3px; background: transparent;"
                    )
                    nl.addWidget(badge_24h)

                nl.addStretch()
                name_w.setProperty("mission_id", mid)
                self._missions_table.setCellWidget(row, COL_NAME, name_w)
                name_item = QTableWidgetItem()
                name_item.setData(Qt.ItemDataRole.UserRole, mid)
                self._missions_table.setItem(row, COL_NAME, name_item)
            else:
                self._missions_table.removeCellWidget(row, COL_NAME)
                name_item = QTableWidgetItem(name)
                name_item.setData(Qt.ItemDataRole.UserRole, mid)
                self._missions_table.setItem(row, COL_NAME, name_item)

            # Planet
            planet_item = QTableWidgetItem(m.get("planet", "") or "—")
            if is_disabled:
                planet_item.setForeground(QColor(DISABLED))
            self._missions_table.setItem(row, COL_PLANET, planet_item)

            # Cooldown duration
            cd_item = QTableWidgetItem(format_cooldown_label(m.get("cooldown_duration")))
            if is_disabled:
                cd_item.setForeground(QColor(DISABLED))
            self._missions_table.setItem(row, COL_COOLDOWN, cd_item)

            # Starts on
            starts_item = QTableWidgetItem(m.get("cooldown_starts_on", "Completion"))
            if is_disabled:
                starts_item.setForeground(QColor(DISABLED))
            self._missions_table.setItem(row, COL_STARTS_ON, starts_item)

            # Status
            status_item = QTableWidgetItem()
            if is_disabled:
                status_item.setText("Disabled")
                status_item.setForeground(QColor(DISABLED))
            elif remaining > 0:
                status_item.setText(format_countdown(remaining))
                status_item.setForeground(QColor(TEXT_MUTED))
            elif remaining == 0:
                status_item.setText("Ready")
                status_item.setForeground(QColor(SUCCESS))
            else:
                status_item.setText("—")
                status_item.setForeground(QColor(TEXT_MUTED))
            self._missions_table.setItem(row, COL_STATUS, status_item)

            # Actions widget
            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(2, 2, 2, 2)
            actions_layout.setSpacing(2)

            if is_disabled:
                # Disabled custom daily — only Edit and Remove
                pass
            elif remaining > 0:
                reset_btn = QPushButton("Reset")
                reset_btn.setFixedSize(50, 22)
                reset_btn.setStyleSheet(self._small_btn_style())
                reset_btn.setProperty("armed", False)
                reset_btn.clicked.connect(
                    lambda _, i=mid, b=reset_btn: self._on_reset_clicked(b, i)
                )
                actions_layout.addWidget(reset_btn)

                snooze_btn = QPushButton("Snooze")
                snooze_btn.setFixedSize(50, 22)
                snooze_btn.setToolTip("Snooze notification 30 min")
                snooze_btn.setStyleSheet(self._small_btn_style())
                snooze_btn.clicked.connect(lambda _, i=mid: self._snooze(i))
                actions_layout.addWidget(snooze_btn)
            else:
                start_btn = QPushButton("Start")
                start_btn.setFixedSize(50, 22)
                start_btn.setStyleSheet(self._small_btn_style(accent=True))
                start_btn.clicked.connect(lambda _, i=mid: self._start_cooldown(i))
                actions_layout.addWidget(start_btn)

            # Reorder arrows: only for enabled, non-cooldown items
            # (disabled items have no arrows; cooldown items sort by time)
            my_group = reorder_group(entries[row]) if reorder_group else None
            can_reorder = not is_disabled and remaining <= 0 and my_group is not None

            if can_reorder:
                # Up arrow — only if previous neighbor is in the same group
                prev_mid = None
                if row > 0 and reorder_group(entries[row - 1]) == my_group:
                    prev_mid = entries[row - 1][0].get("id")
                up_btn = QPushButton()
                up_btn.setFixedSize(22, 22)
                up_btn.setIconSize(icon_size)
                up_btn.setIcon(svg_icon(ARROW_UP, TEXT_MUTED, 14))
                up_btn.setToolTip("Move up")
                up_btn.setStyleSheet(self._small_btn_style())
                up_btn.setEnabled(prev_mid is not None)
                up_btn.clicked.connect(lambda _, a=mid, b=prev_mid: self._swap_mission_order(a, b))
                actions_layout.addWidget(up_btn)

                # Down arrow — only if next neighbor is in the same group
                next_mid = None
                if row < num_entries - 1 and reorder_group(entries[row + 1]) == my_group:
                    next_mid = entries[row + 1][0].get("id")
                down_btn = QPushButton()
                down_btn.setFixedSize(22, 22)
                down_btn.setIconSize(icon_size)
                down_btn.setIcon(svg_icon(ARROW_DOWN, TEXT_MUTED, 14))
                down_btn.setToolTip("Move down")
                down_btn.setStyleSheet(self._small_btn_style())
                down_btn.setEnabled(next_mid is not None)
                down_btn.clicked.connect(lambda _, a=mid, b=next_mid: self._swap_mission_order(a, b))
                actions_layout.addWidget(down_btn)

            if not is_disabled:
                # Bell — notification settings
                bell_btn = QPushButton()
                bell_btn.setFixedSize(22, 22)
                bell_btn.setIconSize(icon_size)
                bell_btn.setIcon(svg_icon(BELL, TEXT_MUTED, 14))
                bell_btn.setToolTip("Notification settings")
                bell_btn.setStyleSheet(self._small_btn_style())
                bell_btn.clicked.connect(lambda _, i=mid: self._open_mission_settings(i))
                actions_layout.addWidget(bell_btn)

                # Copy waypoint
                wp_btn = QPushButton()
                wp_btn.setFixedSize(22, 22)
                wp_btn.setIconSize(icon_size)
                wp_str = _waypoint_copy_string(m)
                if wp_str:
                    wp_btn.setIcon(svg_icon(COPY, TEXT_MUTED, 14))
                    wp_btn.setToolTip(wp_str)
                    wp_btn.setStyleSheet(self._small_btn_style())
                    wp_btn.clicked.connect(lambda _, s=wp_str: self._copy_waypoint(s))
                else:
                    wp_btn.setIcon(svg_icon(COPY, TEXT_MUTED, 14))
                    wp_btn.setToolTip("No waypoint")
                    wp_btn.setStyleSheet(self._small_btn_style())
                    wp_btn.setEnabled(False)
                actions_layout.addWidget(wp_btn)

            # Edit button (custom dailies only)
            if is_custom:
                edit_btn = QPushButton()
                edit_btn.setFixedSize(22, 22)
                edit_btn.setIconSize(icon_size)
                edit_btn.setIcon(svg_icon(PENCIL, TEXT_MUTED, 14))
                edit_btn.setToolTip("Edit custom daily")
                edit_btn.setStyleSheet(self._small_btn_style())
                edit_btn.clicked.connect(lambda _, i=mid: self._edit_custom_daily(i))
                actions_layout.addWidget(edit_btn)

            # Remove
            rm_btn = QPushButton("x")
            rm_btn.setFixedSize(22, 22)
            rm_btn.setToolTip("Remove")
            rm_btn.setStyleSheet(self._small_btn_style(danger=True))
            rm_btn.clicked.connect(lambda _, i=mid: self._remove_mission(i))
            actions_layout.addWidget(rm_btn)

            actions_layout.addStretch()
            self._missions_table.setCellWidget(row, COL_ACTIONS, actions)
            self._missions_table.setRowHeight(row, 36)

    def _copy_waypoint(self, wp_str: str):
        QApplication.clipboard().setText(wp_str)

    def _small_btn_style(self, *, accent=False, danger=False):
        bg = "transparent"
        fg = TEXT_MUTED
        border = BORDER
        hover_bg = HOVER
        if accent:
            bg = ACCENT
            fg = "#fff"
            border = ACCENT
            hover_bg = ACCENT_HOVER
        if danger:
            fg = ERROR
            border = ERROR
        return f"""
            QPushButton {{
                background: {bg}; color: {fg}; border: 1px solid {border};
                border-radius: 3px; font-size: 11px; padding: 0px;
            }}
            QPushButton:hover {{ background: {hover_bg}; }}
        """

    # ------------------------------------------------------------------
    # Events table
    # ------------------------------------------------------------------

    def _classify_event(self, ev, now):
        """Return (category, sort_key) for an event.

        Categories: 'active' (started, not ended), 'upcoming', 'past'.
        """
        start_dt = end_dt = None
        try:
            s = ev.get("start_date", "")
            start_dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
        try:
            e = ev.get("end_date") or ""
            if e:
                end_dt = datetime.fromisoformat(e.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

        if start_dt and start_dt <= now:
            if end_dt and end_dt >= now:
                # Active — sort by soonest to end first
                return "active", end_dt
            if end_dt and end_dt < now:
                # Past (has end_date that already passed)
                return "past", end_dt
            if not end_dt:
                # Started, no end date — treat as active for 1 day
                if now - start_dt < timedelta(days=1):
                    return "active", start_dt
                return "past", start_dt
        if start_dt and start_dt > now:
            return "upcoming", start_dt
        return "upcoming", now

    def _refresh_events_table(self):
        upcoming = self._events_upcoming or []
        past_raw = self._events_past or []
        if not upcoming and not past_raw:
            self._events_label.setText("No events.")
            self._events_table.setRowCount(0)
            return

        now = datetime.now(timezone.utc)
        reminded_ids = {r["event_id"] for r in (self._config.tracker_event_reminders or [])}

        # Classify upcoming into active vs upcoming
        active: list[tuple] = []
        future: list[tuple] = []
        for ev in upcoming:
            cat, key = self._classify_event(ev, now)
            if cat == "active":
                active.append((ev, key))
            else:
                future.append((ev, key))

        # Past events — sort by end_date (or start_date) descending
        past: list[tuple] = []
        for ev in past_raw:
            _, key = self._classify_event(ev, now)
            past.append((ev, key))

        # Sort each group
        active.sort(key=lambda t: t[1])           # soonest to end first
        future.sort(key=lambda t: t[1])            # soonest start first
        past.sort(key=lambda t: t[1], reverse=True)  # most recent first

        ordered = (
            [(ev, "Active") for ev, _ in active]
            + [(ev, "Upcoming") for ev, _ in future]
            + [(ev, "Past") for ev, _ in past]
        )

        counts = []
        if active:
            counts.append(f"{len(active)} active")
        if future:
            counts.append(f"{len(future)} upcoming")
        if past:
            counts.append(f"{len(past)} past")
        self._events_label.setText(", ".join(counts).capitalize() + f" event{'s' if len(ordered) != 1 else ''}")

        self._events_table.setUpdatesEnabled(False)
        try:
            self.__populate_events_rows(ordered, now, reminded_ids)
        finally:
            self._events_table.setUpdatesEnabled(True)

    def __populate_events_rows(self, ordered, now, reminded_ids):
        self._events_table.setRowCount(len(ordered))
        for row, (ev, status) in enumerate(ordered):
            eid = ev.get("id")

            # Title
            title_text = ev.get("title", "?")
            if ev.get("type") == "official":
                title_text += "  [Official]"
            title_item = QTableWidgetItem(title_text)
            title_item.setData(Qt.ItemDataRole.UserRole, eid)
            if status == "Past":
                title_item.setForeground(QColor(TEXT_MUTED))
            self._events_table.setItem(row, 0, title_item)

            # Date
            start_str = ev.get("start_date", "")
            try:
                start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                date_text = start_dt.strftime("%b %d, %Y  %H:%M")
                if status == "Upcoming":
                    delta = start_dt - now
                    hours = int(delta.total_seconds() // 3600)
                    days = hours // 24
                    if days > 0:
                        date_text += f"  (in {days}d {hours % 24}h)"
                    elif hours > 0:
                        date_text += f"  (in {hours}h)"
                    else:
                        mins = max(0, int(delta.total_seconds() // 60))
                        date_text += f"  (in {mins}m)"
                elif status == "Active":
                    date_text += "  (now)"
            except (ValueError, TypeError):
                date_text = start_str
            date_item = QTableWidgetItem(date_text)
            if status == "Past":
                date_item.setForeground(QColor(TEXT_MUTED))
            self._events_table.setItem(row, 1, date_item)

            # Location
            loc_item = QTableWidgetItem(ev.get("location") or "—")
            if status == "Past":
                loc_item.setForeground(QColor(TEXT_MUTED))
            self._events_table.setItem(row, 2, loc_item)

            # Status
            status_item = QTableWidgetItem(status)
            if status == "Active":
                status_item.setForeground(QColor(SUCCESS))
            elif status == "Past":
                status_item.setForeground(QColor(TEXT_MUTED))
            else:
                status_item.setForeground(QColor(ACCENT))
            self._events_table.setItem(row, 3, status_item)

            # Remind button (only for upcoming/active)
            remind_widget = QWidget()
            remind_layout = QHBoxLayout(remind_widget)
            remind_layout.setContentsMargins(2, 2, 2, 2)
            if status != "Past":
                remind_btn = QPushButton("Reminded" if eid in reminded_ids else "Remind me")
                remind_btn.setFixedHeight(22)
                if eid in reminded_ids:
                    remind_btn.setStyleSheet(self._small_btn_style(accent=True))
                else:
                    remind_btn.setStyleSheet(self._small_btn_style())
                remind_btn.clicked.connect(lambda _, i=eid, e=ev: self._toggle_event_reminder(i, e))
                remind_layout.addWidget(remind_btn)
            self._events_table.setCellWidget(row, 4, remind_widget)
            self._events_table.setRowHeight(row, 36)

    # ------------------------------------------------------------------
    # Mission actions
    # ------------------------------------------------------------------

    def _start_cooldown(self, mission_id: int):
        for m in self._tracked_missions:
            if m["id"] == mission_id:
                m["cooldown_started_at"] = datetime.now(timezone.utc).isoformat()
                break
        # Reset notification state for this mission
        self._notified_ready.discard(mission_id)
        self._notified_pre.discard(mission_id)
        self._schedule_save()
        self._refresh_missions_table()

    def _on_reset_clicked(self, btn: QPushButton, mission_id: int):
        """Two-stage reset: first click arms (turns red), second click confirms."""
        if btn.property("armed"):
            self._reset_cooldown(mission_id)
            return
        btn.setProperty("armed", True)
        btn.setText("Sure?")
        btn.setStyleSheet(self._small_btn_style(danger=True))
        # Disarm after 10 seconds
        QTimer.singleShot(10_000, lambda: self._disarm_reset(btn))

    def _disarm_reset(self, btn: QPushButton):
        """Revert armed reset button back to normal state."""
        try:
            if btn.property("armed"):
                btn.setProperty("armed", False)
                btn.setText("Reset")
                btn.setStyleSheet(self._small_btn_style())
        except RuntimeError:
            pass  # widget was deleted

    def _reset_cooldown(self, mission_id: int):
        for m in self._tracked_missions:
            if m["id"] == mission_id:
                m["cooldown_started_at"] = None
                break
        self._notified_ready.discard(mission_id)
        self._notified_pre.discard(mission_id)
        self._schedule_save()
        self._refresh_missions_table()

    def _remove_mission(self, mission_id: int):
        self._tracked_missions = [
            m for m in self._tracked_missions if m["id"] != mission_id
        ]
        self._schedule_save()
        self._refresh_missions_table()

    def _swap_mission_order(self, id_a: int, id_b: int | None):
        """Swap the order fields of two missions (by displayed neighbor IDs)."""
        if id_b is None:
            return
        missions = self._tracked_missions or []
        m_a = m_b = None
        idx_a = idx_b = -1
        for i, m in enumerate(missions):
            if m["id"] == id_a:
                m_a, idx_a = m, i
            elif m["id"] == id_b:
                m_b, idx_b = m, i
        if m_a is None or m_b is None:
            return
        m_a["order"], m_b["order"] = m_b["order"], m_a["order"]
        # Also swap list positions so order is stable
        missions[idx_a], missions[idx_b] = missions[idx_b], missions[idx_a]
        self._schedule_save()
        self._refresh_missions_table()

    def _snooze(self, mission_id: int):
        # Suppress notifications for 30 min by marking as notified
        self._notified_ready.add(mission_id)
        self._notified_pre.add(mission_id)
        # Schedule un-snooze
        QTimer.singleShot(30 * 60_000, lambda: self._un_snooze(mission_id))

    def _un_snooze(self, mission_id: int):
        self._notified_ready.discard(mission_id)
        self._notified_pre.discard(mission_id)

    def _open_mission_settings(self, mission_id: int):
        mission = None
        for m in self._tracked_missions:
            if m["id"] == mission_id:
                mission = m
                break
        if not mission:
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Settings — {mission.get('name', '?')}")
        dlg.setFixedWidth(320)
        dlg.setStyleSheet(f"background: {PRIMARY}; color: {TEXT};")
        layout = QVBoxLayout(dlg)

        # Notify checkbox
        notify_cb = QCheckBox("Enable notifications")
        notify_cb.setChecked(mission.get("notify", True))
        layout.addWidget(notify_cb)

        # Pre-reminder
        pre_row = QHBoxLayout()
        pre_row.addWidget(QLabel("Pre-reminder:"))
        pre_spin = QSpinBox()
        pre_spin.setRange(1, 120)
        pre_spin.setValue(mission.get("notify_minutes_before", 5))
        pre_spin.setSuffix(" min before")
        pre_spin.setStyleSheet(f"background: {SECONDARY}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 3px; padding: 2px;")
        pre_row.addWidget(pre_spin)
        layout.addLayout(pre_row)

        # Save button
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: #fff; border: none;
                border-radius: 4px; padding: 6px 16px; font-size: 12px;
            }}
            QPushButton:hover {{ background: {ACCENT_HOVER}; }}
        """)

        def on_save():
            mission["notify"] = notify_cb.isChecked()
            mission["notify_minutes_before"] = pre_spin.value()
            self._schedule_save()
            self._refresh_missions_table()
            dlg.accept()

        save_btn.clicked.connect(on_save)
        layout.addWidget(save_btn)
        dlg.exec()

    # ------------------------------------------------------------------
    # Custom dailies
    # ------------------------------------------------------------------

    def _open_custom_daily_dialog(self):
        dlg = _CustomDailyDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_data:
            data = dlg.result_data
            # Assign next custom ID
            max_id = 0
            for m in self._tracked_missions:
                mid = m.get("id", "")
                if isinstance(mid, str) and mid.startswith("c_"):
                    try:
                        max_id = max(max_id, int(mid[2:]))
                    except ValueError:
                        pass
            new_id = f"c_{max_id + 1}"

            loc, planet = _parse_waypoint(data.get("waypoint", ""))
            entry = {
                "id": new_id,
                "is_custom": True,
                "name": data["name"],
                "planet": planet or "",
                "cooldown_duration": data["cooldown_duration"],
                "cooldown_starts_on": data["cooldown_starts_on"],
                "cooldown_ms": data["cooldown_ms"],
                "order": len(self._tracked_missions),
                "cooldown_started_at": None,
                "notify": True,
                "notify_minutes_before": 5,
                "start_location": loc,
                "waypoint": data.get("waypoint", ""),
                "has_expiry": False,
                "enabled": True,
            }
            self._tracked_missions.append(entry)
            self._schedule_save()
            self._refresh_missions_table()

    def _edit_custom_daily(self, mission_id):
        mission = None
        for m in self._tracked_missions:
            if m["id"] == mission_id:
                mission = m
                break
        if not mission:
            return

        dlg = _CustomDailyDialog(parent=self, existing=mission)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_data:
            data = dlg.result_data
            loc, planet = _parse_waypoint(data.get("waypoint", ""))
            mission["name"] = data["name"]
            mission["cooldown_duration"] = data["cooldown_duration"]
            mission["cooldown_starts_on"] = data["cooldown_starts_on"]
            mission["cooldown_ms"] = data["cooldown_ms"]
            mission["waypoint"] = data.get("waypoint", "")
            mission["start_location"] = loc
            mission["planet"] = planet or ""
            self._schedule_save()
            self._refresh_missions_table()

    def _toggle_custom_enabled(self, mission_id, enabled: bool):
        for m in self._tracked_missions:
            if m["id"] == mission_id:
                m["enabled"] = enabled
                break
        self._schedule_save()
        self._refresh_missions_table()

    # ------------------------------------------------------------------
    # Mission picker dialog
    # ------------------------------------------------------------------

    def _open_mission_picker(self):
        dlg = _MissionPickerDialog(
            parent=self,
            missions=self._all_missions,
            planets=self._planets,
            tracked_ids={m["id"] for m in (self._tracked_missions or [])},
        )
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected:
            for mission in dlg.selected:
                order = len(self._tracked_missions)
                # Extract start location coordinates
                start_loc = mission.get("StartLocation") or {}
                start_coords = (
                    start_loc.get("Coordinates")
                    or (start_loc.get("Properties") or {}).get("Coordinates")
                    or {}
                )
                start_location = None
                if start_coords.get("Longitude") is not None and start_coords.get("Latitude") is not None:
                    start_location = {
                        "longitude": start_coords["Longitude"],
                        "latitude": start_coords["Latitude"],
                        "altitude": start_coords.get("Altitude", 100),
                        "name": start_loc.get("Name") or "",
                    }

                # Check for AIKillCycle/AIHandIn objectives → 24h expiry
                has_expiry = False
                for step in (mission.get("Steps") or []):
                    for obj in (step.get("Objectives") or []):
                        if obj.get("Type") in ("AIKillCycle", "AIHandIn"):
                            has_expiry = True
                            break
                    if has_expiry:
                        break

                entry = {
                    "id": mission["Id"],
                    "name": mission.get("Name", "?"),
                    "planet": (mission.get("Planet") or {}).get("Name", "Unknown"),
                    "cooldown_duration": _normalize_interval(
                        (mission.get("Properties") or {}).get("CooldownDuration")
                    ) or "1 day",
                    "cooldown_starts_on": (mission.get("Properties") or {}).get("CooldownStartsOn", "Completion"),
                    "cooldown_ms": interval_to_ms(
                        (mission.get("Properties") or {}).get("CooldownDuration")
                    ),
                    "order": order,
                    "cooldown_started_at": None,
                    "notify": True,
                    "notify_minutes_before": 5,
                    "start_location": start_location,
                    "has_expiry": has_expiry,
                }
                self._tracked_missions.append(entry)
            self._schedule_save()
            self._refresh_missions_table()

    # ------------------------------------------------------------------
    # Event reminders
    # ------------------------------------------------------------------

    def _toggle_event_reminder(self, event_id: int, event: dict):
        reminders = self._config.tracker_event_reminders
        existing = [r for r in reminders if r["event_id"] == event_id]
        if existing:
            self._config.tracker_event_reminders = [
                r for r in reminders if r["event_id"] != event_id
            ]
        else:
            reminders.append({
                "event_id": event_id,
                "title": event.get("title", "?"),
                "start_date": event.get("start_date", ""),
                "remind_minutes_before": 15,
                "notified": False,
            })
        self._schedule_save()
        self._refresh_events_table()

    # ------------------------------------------------------------------
    # Tick — countdown updates and notification checks
    # ------------------------------------------------------------------

    def _on_tick(self):
        now_ms = int(time.time() * 1000)
        tracked = self._tracked_missions or []
        table = self._missions_table

        # Quick-update status cells without rebuilding the table
        for row in range(table.rowCount()):
            name_item = table.item(row, COL_NAME)
            if not name_item:
                continue
            mid = name_item.data(Qt.ItemDataRole.UserRole)

            # Find matching mission
            mission = None
            for m in tracked:
                if m.get("id") == mid:
                    mission = m
                    break
            if not mission:
                continue

            # Skip disabled custom dailies entirely (they show "Disabled")
            if mission.get("is_custom") and not mission.get("enabled", True):
                continue

            started = mission.get("cooldown_started_at")
            if not started:
                continue

            try:
                started_ms = int(datetime.fromisoformat(started).timestamp() * 1000)
            except (ValueError, TypeError):
                continue
            cd_ms = mission.get("cooldown_ms", MS_24H)
            remaining = max(0, cd_ms - (now_ms - started_ms))

            status_item = table.item(row, COL_STATUS)
            if status_item:
                if remaining > 0:
                    status_item.setText(format_countdown(remaining))
                    status_item.setForeground(QColor(TEXT_MUTED))
                elif status_item.text() != "Ready":
                    status_item.setText("Ready")
                    status_item.setForeground(QColor(SUCCESS))
                    # Rebuild to swap action buttons (Start vs Reset)
                    QTimer.singleShot(0, self._refresh_missions_table)

            # --- Notification checks ---
            if not mission.get("notify"):
                continue

            # Pre-reminder
            pre_ms = mission.get("notify_minutes_before", 5) * 60_000
            if remaining > 0 and remaining <= pre_ms and mid not in self._notified_pre:
                self._notified_pre.add(mid)
                self._queue_notification(mission, remaining, is_pre=True)

            # Ready
            if remaining == 0 and mid not in self._notified_ready:
                self._notified_ready.add(mid)
                self._queue_notification(mission, 0, is_pre=False)

            # Reset flags when cooldown restarts (remaining is large again)
            if remaining > pre_ms:
                self._notified_ready.discard(mid)
                self._notified_pre.discard(mid)

        # --- Event reminder checks ---
        self._check_event_reminders()

    def _check_event_reminders(self):
        now = datetime.now(timezone.utc)
        changed = False
        for reminder in (self._config.tracker_event_reminders or []):
            if reminder.get("notified"):
                continue
            try:
                start = datetime.fromisoformat(
                    reminder["start_date"].replace("Z", "+00:00")
                )
            except (ValueError, TypeError, KeyError):
                continue
            before = timedelta(minutes=reminder.get("remind_minutes_before", 15))
            if now >= start - before:
                reminder["notified"] = True
                changed = True
                self._event_bus.publish(EVENT_TRACKER_EVENT_REMINDER, {
                    "title": f"Event: {reminder.get('title', '?')}",
                    "body": f"Starting in {reminder.get('remind_minutes_before', 15)} minutes",
                    "metadata": {"event_id": reminder.get("event_id")},
                })
        if changed:
            self._schedule_save()

    # ------------------------------------------------------------------
    # Notification grouping
    # ------------------------------------------------------------------

    def _queue_notification(self, mission: dict, remaining_ms: int, *, is_pre: bool):
        self._pending_group.append({
            "mission": mission,
            "remaining_ms": remaining_ms,
            "is_pre": is_pre,
        })
        self._group_timer.start()  # restart 5s window

    def _flush_group(self):
        pending = self._pending_group
        self._pending_group = []
        if not pending:
            return

        ready = [p for p in pending if not p["is_pre"]]
        pre = [p for p in pending if p["is_pre"]]

        if ready:
            if len(ready) == 1:
                m = ready[0]["mission"]
                title = f'{m["name"]} is ready!'
                body = m.get("planet", "")
            else:
                title = f"{len(ready)} dailies ready!"
                body = ", ".join(p["mission"]["name"] for p in ready)
            self._event_bus.publish(EVENT_TRACKER_DAILY_READY, {
                "title": title, "body": body,
                "metadata": {"mission_ids": [p["mission"]["id"] for p in ready]},
            })

        if pre:
            if len(pre) == 1:
                m = pre[0]["mission"]
                title = f'{m["name"]} ready soon'
                body = f"Cooldown ends in {format_countdown(pre[0]['remaining_ms'])}"
            else:
                title = f"{len(pre)} dailies coming up"
                body = ", ".join(
                    f'{p["mission"]["name"]} ({format_countdown(p["remaining_ms"])})'
                    for p in pre
                )
            self._event_bus.publish(EVENT_TRACKER_DAILY_READY, {
                "title": title, "body": body,
                "metadata": {"mission_ids": [p["mission"]["id"] for p in pre]},
            })

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _schedule_save(self):
        self._save_timer.start()

    def _persist(self):
        """Save tracked missions and custom dailies to DB, event reminders to config."""
        api_missions = [m for m in self._tracked_missions if not m.get("is_custom")]
        custom_dailies = [m for m in self._tracked_missions if m.get("is_custom")]
        self._db.save_tracked_missions(api_missions)
        self._db.save_custom_dailies(custom_dailies)
        from ...core.config import save_config
        save_config(self._config, self._config_path)

    def _migrate_config_to_db(self):
        """One-time migration of tracker_missions from config to database."""
        legacy = self._config.tracker_missions
        if not legacy:
            return
        log.info("Migrating %d tracked missions from config to database", len(legacy))
        self._db.save_tracked_missions(legacy)
        self._config.tracker_missions = []
        from ...core.config import save_config
        save_config(self._config, self._config_path)

    def cleanup(self):
        self._tick_timer.stop()
        self._group_timer.stop()
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._persist()


# ---------------------------------------------------------------------------
# Mission picker dialog
# ---------------------------------------------------------------------------

class _MissionPickerDialog(QDialog):
    """Dialog to search and select recurring missions to track."""

    def __init__(self, *, parent, missions, planets, tracked_ids):
        super().__init__(parent)
        self.setWindowTitle("Add Recurring Missions")
        self.setMinimumSize(800, 500)
        self.setStyleSheet(f"background: {PRIMARY}; color: {TEXT};")
        self.selected: list[dict] = []

        self._missions = missions
        self._tracked_ids = tracked_ids

        layout = QVBoxLayout(self)

        # Filters row
        filters = QHBoxLayout()

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search missions...")
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background: {SECONDARY}; color: {TEXT}; border: 1px solid {BORDER};
                border-radius: 4px; padding: 6px 10px; font-size: 13px;
            }}
        """)
        self._search.textChanged.connect(self._apply_filters)
        filters.addWidget(self._search, 2)

        self._planet_filter = QComboBox()
        self._planet_filter.addItem("All Planets", "")
        for p in planets:
            self._planet_filter.addItem(p, p)
        self._planet_filter.setStyleSheet(f"""
            QComboBox {{
                background: {SECONDARY}; color: {TEXT}; border: 1px solid {BORDER};
                border-radius: 4px; padding: 4px 8px; font-size: 12px;
            }}
        """)
        self._planet_filter.currentIndexChanged.connect(self._apply_filters)
        filters.addWidget(self._planet_filter)

        self._cd_filter = QComboBox()
        self._cd_filter.addItem("Any Cooldown", "")
        self._cd_filter.addItem("24h or less", "<=24h")
        self._cd_filter.addItem("More than 24h", ">24h")
        self._cd_filter.setStyleSheet(self._planet_filter.styleSheet())
        self._cd_filter.currentIndexChanged.connect(self._apply_filters)
        filters.addWidget(self._cd_filter)

        layout.addLayout(filters)

        # Table
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Mission", "Planet", "Cooldown", "Starts On"])
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background: {PRIMARY}; color: {TEXT}; border: 1px solid {BORDER};
                border-radius: 4px;
            }}
            QTableWidget::item {{ padding: 4px 8px; border-bottom: 1px solid {BORDER}; }}
            QTableWidget::item:selected {{ background: {HOVER}; }}
            QHeaderView::section {{
                background: {SECONDARY}; color: {TEXT_MUTED}; border: none;
                padding: 4px 8px; font-size: 11px; font-weight: bold;
            }}
        """)
        thdr = self._table.horizontalHeader()
        thdr.setStretchLastSection(False)
        thdr.setMinimumSectionSize(80)
        thdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        thdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        thdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        thdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(1, 140)
        self._table.setColumnWidth(2, 120)
        self._table.setColumnWidth(3, 130)
        layout.addWidget(self._table)

        # Bottom buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        add_btn = QPushButton("Add Selected")
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: #fff; border: none;
                border-radius: 4px; padding: 6px 16px; font-size: 12px;
            }}
            QPushButton:hover {{ background: {ACCENT_HOVER}; }}
        """)
        add_btn.clicked.connect(self._on_add)
        btn_row.addWidget(add_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {SECONDARY}; color: {TEXT}; border: 1px solid {BORDER};
                border-radius: 4px; padding: 6px 16px; font-size: 12px;
            }}
            QPushButton:hover {{ background: {HOVER}; }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

        self._apply_filters()

    def _apply_filters(self):
        query = self._search.text().strip().lower()
        planet = self._planet_filter.currentData()
        cd_filter = self._cd_filter.currentData()

        filtered = []
        for m in self._missions:
            if m.get("Id") in self._tracked_ids:
                continue
            name = m.get("Name", "")
            if query and query not in name.lower():
                continue
            m_planet = (m.get("Planet") or {}).get("Name", "")
            if planet and m_planet != planet:
                continue
            props = m.get("Properties") or {}
            cd_ms = interval_to_ms(props.get("CooldownDuration"))
            if cd_filter == "<=24h" and cd_ms > MS_24H:
                continue
            if cd_filter == ">24h" and cd_ms <= MS_24H:
                continue
            filtered.append(m)

        self._filtered = filtered
        self._table.setUpdatesEnabled(False)
        try:
            self._table.setRowCount(len(filtered))
            for row, m in enumerate(filtered):
                props = m.get("Properties") or {}
                self._table.setItem(row, 0, QTableWidgetItem(m.get("Name", "?")))
                self._table.setItem(row, 1, QTableWidgetItem((m.get("Planet") or {}).get("Name", "?")))
                self._table.setItem(row, 2, QTableWidgetItem(format_cooldown_label(props.get("CooldownDuration"))))
                self._table.setItem(row, 3, QTableWidgetItem(props.get("CooldownStartsOn", "Completion")))
                self._table.setRowHeight(row, 32)
        finally:
            self._table.setUpdatesEnabled(True)

    def _on_add(self):
        rows = set()
        for idx in self._table.selectedIndexes():
            rows.add(idx.row())
        self.selected = [self._filtered[r] for r in sorted(rows) if r < len(self._filtered)]
        if self.selected:
            self.accept()


# ---------------------------------------------------------------------------
# Custom daily dialog
# ---------------------------------------------------------------------------

_COOLDOWN_UNITS = [("Minutes", 60_000), ("Hours", 3_600_000), ("Days", 86_400_000)]


class _CustomDailyDialog(QDialog):
    """Dialog to create or edit a custom daily."""

    def __init__(self, *, parent, existing: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Edit Custom Daily" if existing else "New Custom Daily")
        self.setFixedWidth(400)
        self.setStyleSheet(f"background: {PRIMARY}; color: {TEXT};")
        self.result_data: dict | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        _input_style = (
            f"background: {SECONDARY}; color: {TEXT}; border: 1px solid {BORDER};"
            " border-radius: 4px; padding: 6px 10px; font-size: 13px;"
        )
        _combo_style = (
            f"background: {SECONDARY}; color: {TEXT}; border: 1px solid {BORDER};"
            " border-radius: 4px; padding: 4px 8px; font-size: 12px;"
        )

        # Name
        layout.addWidget(QLabel("Name"))
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g., Daily Token Collection")
        self._name.setStyleSheet(f"QLineEdit {{ {_input_style} }}")
        if existing:
            self._name.setText(existing.get("name", ""))
        layout.addWidget(self._name)

        # Cooldown row
        layout.addWidget(QLabel("Cooldown"))
        cd_row = QHBoxLayout()
        self._cd_amount = QSpinBox()
        self._cd_amount.setRange(1, 999)
        self._cd_amount.setStyleSheet(
            f"QSpinBox {{ {_input_style} }}"
        )
        cd_row.addWidget(self._cd_amount)

        self._cd_unit = QComboBox()
        for label, _ in _COOLDOWN_UNITS:
            self._cd_unit.addItem(label)
        self._cd_unit.setStyleSheet(f"QComboBox {{ {_combo_style} }}")
        cd_row.addWidget(self._cd_unit)
        layout.addLayout(cd_row)

        # Pre-fill cooldown from existing
        if existing:
            cd_ms = existing.get("cooldown_ms", MS_24H)
            # Find best-fit unit
            if cd_ms % 86_400_000 == 0:
                self._cd_unit.setCurrentIndex(2)  # Days
                self._cd_amount.setValue(cd_ms // 86_400_000)
            elif cd_ms % 3_600_000 == 0:
                self._cd_unit.setCurrentIndex(1)  # Hours
                self._cd_amount.setValue(cd_ms // 3_600_000)
            else:
                self._cd_unit.setCurrentIndex(0)  # Minutes
                self._cd_amount.setValue(max(1, cd_ms // 60_000))
        else:
            self._cd_unit.setCurrentIndex(1)  # Hours
            self._cd_amount.setValue(24)

        # Cooldown starts on
        layout.addWidget(QLabel("Cooldown starts on"))
        self._starts_on = QComboBox()
        self._starts_on.addItems(["Completion", "Accept"])
        self._starts_on.setStyleSheet(f"QComboBox {{ {_combo_style} }}")
        if existing:
            idx = self._starts_on.findText(existing.get("cooldown_starts_on", "Completion"))
            if idx >= 0:
                self._starts_on.setCurrentIndex(idx)
        layout.addWidget(self._starts_on)

        # Waypoint
        layout.addWidget(QLabel("Waypoint (optional)"))
        self._waypoint = QLineEdit()
        self._waypoint.setPlaceholderText("/wp [Planet, Long, Lat, Alt, Name]")
        self._waypoint.setStyleSheet(f"QLineEdit {{ {_input_style} }}")
        if existing:
            wp = existing.get("waypoint", "")
            self._waypoint.setText(wp)
        layout.addWidget(self._waypoint)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._save_btn = QPushButton("Save")
        self._save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT}; color: #fff; border: none;
                border-radius: 4px; padding: 6px 16px; font-size: 12px;
            }}
            QPushButton:hover {{ background: {ACCENT_HOVER}; }}
            QPushButton:disabled {{ background: {SECONDARY}; color: {TEXT_MUTED}; }}
        """)
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {SECONDARY}; color: {TEXT}; border: 1px solid {BORDER};
                border-radius: 4px; padding: 6px 16px; font-size: 12px;
            }}
            QPushButton:hover {{ background: {HOVER}; }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        # Validation
        self._name.textChanged.connect(self._validate)
        self._validate()

    def _validate(self):
        self._save_btn.setEnabled(bool(self._name.text().strip()))

    def _on_save(self):
        name = self._name.text().strip()
        if not name:
            return

        amount = self._cd_amount.value()
        unit_idx = self._cd_unit.currentIndex()
        unit_label, unit_ms = _COOLDOWN_UNITS[unit_idx]
        cooldown_ms = amount * unit_ms

        # Build human-readable duration string
        unit_word = unit_label.lower()
        if amount == 1:
            unit_word = unit_word.rstrip("s")  # "hours" → "hour"
        cooldown_duration = f"{amount} {unit_word}"

        raw_wp = _normalize_waypoint_input(self._waypoint.text())

        self.result_data = {
            "name": name,
            "cooldown_duration": cooldown_duration,
            "cooldown_starts_on": self._starts_on.currentText(),
            "cooldown_ms": cooldown_ms,
            "waypoint": raw_wp,
        }
        self.accept()
