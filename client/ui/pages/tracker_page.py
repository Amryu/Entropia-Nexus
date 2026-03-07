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
    QAbstractItemView, QSpinBox,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor

from ..theme import (
    PRIMARY, SECONDARY, HOVER, TEXT, TEXT_MUTED, ACCENT, ACCENT_HOVER,
    BORDER, SUCCESS, ERROR, WARNING,
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
_COMING_SOON_TABS = {2, 3, 4}

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

    def __init__(self, *, signals, config, config_path, data_client, event_bus, oauth):
        super().__init__()
        self._signals = signals
        self._config = config
        self._config_path = config_path
        self._data_client = data_client
        self._event_bus = event_bus
        self._authenticated = oauth.auth_state.authenticated

        # Track auth state for submit button
        signals.auth_state_changed.connect(self._on_auth_changed)

        # Debounced config save
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self._persist_config)

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
        self._stack.addWidget(self._build_dailies_page())
        self._stack.addWidget(self._build_events_page())
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
        hdr.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        for c in (COL_PLANET, COL_COOLDOWN, COL_STARTS_ON, COL_STATUS):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(COL_ACTIONS, QHeaderView.ResizeMode.Fixed)
        hdr.resizeSection(COL_ACTIONS, 180)
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
        threading.Thread(target=self._fetch_data, daemon=True).start()

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
        tracked = self._config.tracker_missions or []
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

        # Sort: on-cooldown by remaining (asc), then ready (0), then idle (-1) by order
        def sort_key(pair):
            m, r = pair
            if r > 0:
                return (0, r)
            if r == 0:
                return (1, m.get("order", 0))
            return (2, m.get("order", 0))

        entries.sort(key=sort_key)

        self._missions_table.setUpdatesEnabled(False)
        try:
            self.__populate_missions_rows(entries)
        finally:
            self._missions_table.setUpdatesEnabled(True)

    def __populate_missions_rows(self, entries):
        self._missions_table.setRowCount(len(entries))
        for row, (m, remaining) in enumerate(entries):
            mid = m.get("id")

            # Name
            name_item = QTableWidgetItem(m.get("name", "?"))
            name_item.setData(Qt.ItemDataRole.UserRole, mid)
            self._missions_table.setItem(row, COL_NAME, name_item)

            # Planet
            self._missions_table.setItem(row, COL_PLANET, QTableWidgetItem(m.get("planet", "?")))

            # Cooldown duration
            self._missions_table.setItem(
                row, COL_COOLDOWN, QTableWidgetItem(format_cooldown_label(m.get("cooldown_duration")))
            )

            # Starts on
            self._missions_table.setItem(
                row, COL_STARTS_ON, QTableWidgetItem(m.get("cooldown_starts_on", "Completion"))
            )

            # Status
            status_item = QTableWidgetItem()
            if remaining > 0:
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
            actions_layout.setSpacing(4)

            if remaining > 0:
                reset_btn = QPushButton("Reset")
                reset_btn.setFixedSize(50, 22)
                reset_btn.setStyleSheet(self._small_btn_style())
                reset_btn.clicked.connect(lambda _, i=mid: self._reset_cooldown(i))
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

            settings_btn = QPushButton("...")
            settings_btn.setFixedSize(24, 22)
            settings_btn.setToolTip("Settings")
            settings_btn.setStyleSheet(self._small_btn_style())
            settings_btn.clicked.connect(lambda _, i=mid: self._open_mission_settings(i))
            actions_layout.addWidget(settings_btn)

            rm_btn = QPushButton("x")
            rm_btn.setFixedSize(24, 22)
            rm_btn.setToolTip("Remove")
            rm_btn.setStyleSheet(self._small_btn_style(danger=True))
            rm_btn.clicked.connect(lambda _, i=mid: self._remove_mission(i))
            actions_layout.addWidget(rm_btn)

            actions_layout.addStretch()
            self._missions_table.setCellWidget(row, COL_ACTIONS, actions)
            self._missions_table.setRowHeight(row, 36)

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
        for m in self._config.tracker_missions:
            if m["id"] == mission_id:
                m["cooldown_started_at"] = datetime.now(timezone.utc).isoformat()
                break
        # Reset notification state for this mission
        self._notified_ready.discard(mission_id)
        self._notified_pre.discard(mission_id)
        self._schedule_save()
        self._refresh_missions_table()

    def _reset_cooldown(self, mission_id: int):
        for m in self._config.tracker_missions:
            if m["id"] == mission_id:
                m["cooldown_started_at"] = None
                break
        self._notified_ready.discard(mission_id)
        self._notified_pre.discard(mission_id)
        self._schedule_save()
        self._refresh_missions_table()

    def _remove_mission(self, mission_id: int):
        self._config.tracker_missions = [
            m for m in self._config.tracker_missions if m["id"] != mission_id
        ]
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
        for m in self._config.tracker_missions:
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

        # Order
        order_row = QHBoxLayout()
        order_row.addWidget(QLabel("Sort order:"))
        order_spin = QSpinBox()
        order_spin.setRange(0, 999)
        order_spin.setValue(mission.get("order", 0))
        order_spin.setStyleSheet(pre_spin.styleSheet())
        order_row.addWidget(order_spin)
        layout.addLayout(order_row)

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
            mission["order"] = order_spin.value()
            self._schedule_save()
            self._refresh_missions_table()
            dlg.accept()

        save_btn.clicked.connect(on_save)
        layout.addWidget(save_btn)
        dlg.exec()

    # ------------------------------------------------------------------
    # Mission picker dialog
    # ------------------------------------------------------------------

    def _open_mission_picker(self):
        dlg = _MissionPickerDialog(
            parent=self,
            missions=self._all_missions,
            planets=self._planets,
            tracked_ids={m["id"] for m in (self._config.tracker_missions or [])},
        )
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected:
            for mission in dlg.selected:
                order = len(self._config.tracker_missions)
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
                }
                self._config.tracker_missions.append(entry)
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
        tracked = self._config.tracker_missions or []
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

    def _persist_config(self):
        from ...core.config import save_config
        save_config(self._config, self._config_path)

    def cleanup(self):
        self._tick_timer.stop()
        self._group_timer.stop()
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._persist_config()


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
