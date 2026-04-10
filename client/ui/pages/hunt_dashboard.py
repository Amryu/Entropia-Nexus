"""Hunt dashboard — live glanceable view of the current hunt / session.

Composition:
    HuntDashboardView -- primary widget, cards + tables + stats
    Card widgets      -- CurrentToolCard, CurrentEncounterCard,
                         LastKillCard, StatsBlock, GlobalFeedPanel
    Tables            -- RecentKillsTable (QTableView + model),
                         ToolsUsedTable, OpenEncountersPanel
    DetailPanel       -- shared right panel switching between tool
                         detail views and EncounterDetailView

Signals and state updates go through the existing AppSignals bridge;
this widget never touches the database directly. All scope-aware
reads come from the HuntTracker instance that is resolved lazily via
the getter passed by HuntPage / main_window.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Literal

from PyQt6.QtCore import (
    Qt, QTimer, QAbstractTableModel, QModelIndex, QSize, pyqtSignal,
)
from PyQt6.QtGui import QColor, QBrush, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QSplitter, QTableWidget, QTableWidgetItem, QHeaderView, QTableView,
    QButtonGroup, QStyledItemDelegate, QSizePolicy, QScrollArea,
    QStackedWidget, QToolButton,
)

from ...core.constants import EVENT_CONFIG_CHANGED
from ...core.logger import get_logger
from ...hunt import stats as hunt_stats
from ...hunt.session import MobEncounter

log = get_logger("HuntDashboard")

Scope = Literal["hunt", "session"]
ReturnMode = Literal["percent", "signed_ped"]

RECENT_KILLS_VISIBLE_ROWS = 50
TICKER_INTERVAL_MS = 1000


# ---------------------------------------------------------------------------
# Helper formatters
# ---------------------------------------------------------------------------

def _fmt_ped(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:,.2f}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:,.1f}%"


def _fmt_signed_ped(value: float | None) -> str:
    if value is None:
        return "-"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:,.2f}"


def _fmt_duration(delta: timedelta | None) -> str:
    if delta is None:
        return "-"
    total = int(delta.total_seconds())
    if total < 0:
        total = 0
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def _fmt_relative(ts: datetime | None, now: datetime | None = None) -> str:
    if ts is None:
        return "-"
    now = now or datetime.utcnow()
    delta = now - ts
    secs = int(delta.total_seconds())
    if secs < 0:
        return "now"
    if secs < 60:
        return f"{secs}s ago"
    mins = secs // 60
    if mins < 60:
        return f"{mins}m ago"
    hours = mins // 60
    mins = mins % 60
    if hours < 24:
        return f"{hours}h {mins}m ago"
    days = hours // 24
    return f"{days}d ago"


# ---------------------------------------------------------------------------
# Recent Kills model + delegate
# ---------------------------------------------------------------------------

class RecentKillsModel(QAbstractTableModel):
    COLS = ("Time", "Mob", "Cost", "Mult", "Return TT")
    COL_TIME = 0
    COL_MOB = 1
    COL_COST = 2
    COL_MULT = 3
    COL_RETURN = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[MobEncounter] = []

    def set_encounters(self, encounters: list[MobEncounter]) -> None:
        self.beginResetModel()
        # Most recent first.
        self._rows = list(reversed([e for e in encounters if e.start_time]))
        self.endResetModel()

    def encounter_at(self, row: int) -> MobEncounter | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def tick_time_column(self) -> None:
        if not self._rows:
            return
        top = self.index(0, self.COL_TIME)
        bottom = self.index(len(self._rows) - 1, self.COL_TIME)
        self.dataChanged.emit(top, bottom, [Qt.ItemDataRole.DisplayRole])

    # -- Qt model API --

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.COLS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self.COLS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        if row >= len(self._rows):
            return None
        enc = self._rows[row]

        if role == Qt.ItemDataRole.DisplayRole:
            if col == self.COL_TIME:
                return _fmt_relative(enc.end_time or enc.start_time)
            if col == self.COL_MOB:
                return enc.mob_name or "Unknown"
            if col == self.COL_COST:
                return _fmt_ped(enc.cost)
            if col == self.COL_MULT:
                if enc.cost > 0:
                    return f"{enc.loot_total_ped / enc.cost:.2f}x"
                return "-"
            if col == self.COL_RETURN:
                return _fmt_ped(enc.loot_total_ped)
        elif role == Qt.ItemDataRole.ToolTipRole:
            if col == self.COL_TIME:
                ts = enc.end_time or enc.start_time
                return ts.isoformat(sep=" ", timespec="seconds") if ts else ""
        elif role == Qt.ItemDataRole.ForegroundRole:
            if col == self.COL_MULT and enc.cost > 0:
                ratio = enc.loot_total_ped / enc.cost
                if ratio >= 2.0:
                    return QBrush(QColor("#3ecf8e"))
                if ratio < 0.5:
                    return QBrush(QColor("#cf6b3e"))
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (self.COL_COST, self.COL_MULT, self.COL_RETURN):
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None


# ---------------------------------------------------------------------------
# Card widgets
# ---------------------------------------------------------------------------

class _Card(QFrame):
    """Base card: bordered QFrame with title + body layout."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("huntDashboardCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(4)
        self._title_label = QLabel(title)
        title_font = QFont()
        title_font.setBold(True)
        self._title_label.setFont(title_font)
        outer.addWidget(self._title_label)
        self._body = QVBoxLayout()
        self._body.setContentsMargins(0, 0, 0, 0)
        self._body.setSpacing(2)
        outer.addLayout(self._body)
        self._body.addStretch(1)

    def set_title(self, text: str) -> None:
        self._title_label.setText(text)


class CurrentToolCard(_Card):
    """Shows active weapon / tool, enhancer chips, cost/shot, DPP."""

    def __init__(self, parent=None):
        super().__init__("Current Tool", parent)
        self._name_label = QLabel("-")
        self._name_label.setStyleSheet("font-size: 14px;")
        self._body.insertWidget(0, self._name_label)
        self._cost_label = QLabel("Cost/shot: -")
        self._body.insertWidget(1, self._cost_label)
        self._dpp_label = QLabel("DPP: -")
        self._body.insertWidget(2, self._dpp_label)
        self._enh_label = QLabel("Enhancers: -")
        self._enh_label.setWordWrap(True)
        self._body.insertWidget(3, self._enh_label)
        # Enhancer-edit button is a Phase 3 stub.
        self._enh_edit_btn = QPushButton("Edit Enhancers")
        self._enh_edit_btn.setEnabled(False)
        self._enh_edit_btn.setToolTip("Coming in a future update")
        self._body.insertWidget(4, self._enh_edit_btn)

    def set_tool(self, name: str | None, cost_per_shot: float | None,
                 dpp: float | None,
                 declared_enhancers: list[str] | None = None,
                 inferred_enhancers: list[str] | None = None) -> None:
        self._name_label.setText(name or "-")
        self._cost_label.setText(
            f"Cost/shot: {cost_per_shot:.4f} PED" if cost_per_shot else "Cost/shot: -"
        )
        self._dpp_label.setText(
            f"DPP: {dpp:.3f}" if dpp else "DPP: -"
        )
        parts: list[str] = []
        for e in declared_enhancers or []:
            parts.append(e)
        for e in inferred_enhancers or []:
            parts.append(f"<i>{e}</i>")
        self._enh_label.setText("Enhancers: " + (", ".join(parts) if parts else "-"))
        self._enh_label.setTextFormat(Qt.TextFormat.RichText)


class CurrentEncounterCard(_Card):
    """Shows the live encounter being fought (or last encounter when idle)."""

    def __init__(self, parent=None):
        super().__init__("Current Encounter", parent)
        self._mob_label = QLabel("-")
        self._mob_label.setStyleSheet("font-size: 14px;")
        self._body.insertWidget(0, self._mob_label)
        self._dmg_label = QLabel("DMG dealt: - / taken: -")
        self._body.insertWidget(1, self._dmg_label)
        self._shots_label = QLabel("Shots: -")
        self._body.insertWidget(2, self._shots_label)
        self._duration_label = QLabel("Duration: -")
        self._body.insertWidget(3, self._duration_label)
        self._idle = True

    def set_active(self, enc: MobEncounter) -> None:
        self._idle = False
        self.set_title("Current Encounter")
        self._render(enc)

    def set_idle(self, last: MobEncounter | None) -> None:
        self._idle = True
        self.set_title("Current Encounter (idle)")
        if last is None:
            self._mob_label.setText("Waiting for encounter...")
            self._dmg_label.setText("DMG dealt: - / taken: -")
            self._shots_label.setText("Shots: -")
            self._duration_label.setText("Duration: -")
        else:
            self._render(last, prefix="Last: ")

    def refresh_duration(self) -> None:
        # Ticker hook; for live encounters only.
        if self._idle:
            return

    def _render(self, enc: MobEncounter, prefix: str = "") -> None:
        self._mob_label.setText(f"{prefix}{enc.mob_name or 'Unknown'}")
        self._dmg_label.setText(
            f"DMG dealt: {enc.damage_dealt:.0f} / taken: {enc.damage_taken:.0f}"
        )
        self._shots_label.setText(f"Shots: {enc.shots_fired}")
        if enc.start_time and enc.end_time:
            delta = enc.end_time - enc.start_time
            self._duration_label.setText(f"Duration: {_fmt_duration(delta)}")
        elif enc.start_time:
            delta = datetime.utcnow() - enc.start_time
            self._duration_label.setText(f"Duration: {_fmt_duration(delta)}")
        else:
            self._duration_label.setText("Duration: -")


class LastKillCard(_Card):
    """Summary of the most recent kill with collapsible loot list."""

    markup_edit_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("Last Kill", parent)
        self._mob_label = QLabel("-")
        self._mob_label.setStyleSheet("font-size: 14px;")
        self._body.insertWidget(0, self._mob_label)
        self._cost_label = QLabel("Cost: - | Return: -")
        self._body.insertWidget(1, self._cost_label)
        self._mult_label = QLabel("Multiplier: -")
        self._body.insertWidget(2, self._mult_label)
        self._shots_label = QLabel("Shots: -")
        self._body.insertWidget(3, self._shots_label)
        self._global_label = QLabel("")
        self._body.insertWidget(4, self._global_label)

        # Collapsible loot list.
        self._toggle_btn = QToolButton()
        self._toggle_btn.setText("Show loot")
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setArrowType(Qt.ArrowType.RightArrow)
        self._toggle_btn.toggled.connect(self._on_toggle)
        self._body.insertWidget(5, self._toggle_btn)

        self._loot_table = QTableWidget()
        self._loot_table.setColumnCount(3)
        self._loot_table.setHorizontalHeaderLabels(["Item", "Qty", "TT"])
        self._loot_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._loot_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._loot_table.setMaximumHeight(120)
        self._loot_table.setVisible(False)
        self._loot_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._loot_table.customContextMenuRequested.connect(self._on_loot_menu)
        self._body.insertWidget(6, self._loot_table)

    def _on_loot_menu(self, pos) -> None:
        from PyQt6.QtWidgets import QMenu
        row = self._loot_table.rowAt(pos.y())
        if row < 0:
            return
        item = self._loot_table.item(row, 0)
        if item is None:
            return
        menu = QMenu(self._loot_table)
        act = menu.addAction("Set session markup...")
        chosen = menu.exec(self._loot_table.viewport().mapToGlobal(pos))
        if chosen is act:
            self.markup_edit_requested.emit(item.text())

    def _on_toggle(self, checked: bool) -> None:
        self._toggle_btn.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )
        self._toggle_btn.setText("Hide loot" if checked else "Show loot")
        self._loot_table.setVisible(checked)

    def set_kill(self, enc: MobEncounter | None) -> None:
        if enc is None:
            self._mob_label.setText("-")
            self._cost_label.setText("Cost: - | Return: -")
            self._mult_label.setText("Multiplier: -")
            self._shots_label.setText("Shots: -")
            self._global_label.setText("")
            self._loot_table.setRowCount(0)
            return
        self._mob_label.setText(enc.mob_name or "Unknown")
        self._cost_label.setText(
            f"Cost: {enc.cost:.2f} PED | Return: {enc.loot_total_ped:.2f} PED"
        )
        if enc.cost > 0:
            self._mult_label.setText(
                f"Multiplier: {enc.loot_total_ped / enc.cost:.2f}x"
            )
        else:
            self._mult_label.setText("Multiplier: -")
        self._shots_label.setText(f"Shots: {enc.shots_fired}")
        badge = ""
        if enc.is_hof:
            badge = "HoF!"
        elif enc.is_global:
            badge = "Global!"
        self._global_label.setText(badge)

        loot_items = list(getattr(enc, "loot_items", []) or [])
        self._loot_table.setRowCount(len(loot_items))
        for i, li in enumerate(loot_items):
            self._loot_table.setItem(i, 0, QTableWidgetItem(li.item_name))
            self._loot_table.setItem(i, 1, QTableWidgetItem(str(li.quantity)))
            self._loot_table.setItem(i, 2, QTableWidgetItem(f"{li.value_ped:.2f}"))


class StatsBlock(_Card):
    """Return / duration / avg kill cost / G+HoF / MU consumed."""

    def __init__(self, parent=None):
        super().__init__("Statistics", parent)
        self._labels: dict[str, QLabel] = {}
        grid = QVBoxLayout()
        grid.setSpacing(2)
        for key, caption in (
            ("return", "Return"),
            ("duration", "Duration"),
            ("avg_kill_cost", "Avg kill cost"),
            ("globals", "Globals / HoFs"),
            ("mu", "MU consumed"),
        ):
            row = QHBoxLayout()
            title = QLabel(caption + ":")
            title.setMinimumWidth(110)
            value = QLabel("-")
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(title)
            row.addWidget(value, 1)
            grid.addLayout(row)
            self._labels[key] = value
        self._body.insertLayout(0, grid)

    def set_stats(self, *, return_pct: float | None, profit_loss: float | None,
                  return_mode: ReturnMode, duration: timedelta | None,
                  avg_kill_cost: float | None, globals_count: int,
                  hof_count: int, mu_consumed: float | None) -> None:
        if return_mode == "signed_ped":
            self._labels["return"].setText(_fmt_signed_ped(profit_loss))
        else:
            self._labels["return"].setText(_fmt_pct(return_pct))
        self._labels["duration"].setText(_fmt_duration(duration))
        self._labels["avg_kill_cost"].setText(
            f"{avg_kill_cost:.2f} PED" if avg_kill_cost else "-"
        )
        self._labels["globals"].setText(f"{globals_count} / {hof_count}")
        if mu_consumed is None:
            self._labels["mu"].setText("-")
        else:
            self._labels["mu"].setText(f"{mu_consumed:.2f} PED")


class GlobalFeedPanel(_Card):
    """Most recent globals / HoFs (up to 5)."""

    MAX_ROWS = 5

    def __init__(self, parent=None):
        super().__init__("Globals / HoFs", parent)
        self._list = QTableWidget()
        self._list.setColumnCount(3)
        self._list.setHorizontalHeaderLabels(["Time", "Mob", "Amount"])
        self._list.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._list.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._list.setMaximumHeight(140)
        self._body.insertWidget(0, self._list)
        self._entries: list[tuple[datetime, str, float, bool]] = []

    def add_entry(self, ts: datetime, mob: str, amount: float, is_hof: bool) -> None:
        self._entries.insert(0, (ts, mob, amount, is_hof))
        self._entries = self._entries[: self.MAX_ROWS]
        self._render()

    def set_entries(self, entries: list[tuple[datetime, str, float, bool]]) -> None:
        self._entries = entries[: self.MAX_ROWS]
        self._render()

    def _render(self) -> None:
        self._list.setRowCount(len(self._entries))
        for i, (ts, mob, amount, is_hof) in enumerate(self._entries):
            self._list.setItem(i, 0, QTableWidgetItem(_fmt_relative(ts)))
            label = (f"HoF: {mob}" if is_hof else mob) or "Unknown"
            self._list.setItem(i, 1, QTableWidgetItem(label))
            self._list.setItem(i, 2, QTableWidgetItem(f"{amount:.2f}"))


# ---------------------------------------------------------------------------
# Tools Used table
# ---------------------------------------------------------------------------

class ToolsUsedTable(QTableWidget):
    """Grouped by category: offense / defense / utility. Sorted by cost caused."""

    COLS = ("Tool", "Shots", "Cost", "In LO", "Flags")
    COL_NAME = 0
    COL_SHOTS = 1
    COL_COST = 2
    COL_LOADOUT = 3
    COL_FLAGS = 4

    row_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(self.COLS))
        self.setHorizontalHeaderLabels(self.COLS)
        self.horizontalHeader().setSectionResizeMode(
            self.COL_NAME, QHeaderView.ResizeMode.Stretch
        )
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.verticalHeader().setVisible(False)
        self.cellClicked.connect(self._on_cell_clicked)

    def _on_cell_clicked(self, row: int, _col: int) -> None:
        item = self.item(row, self.COL_NAME)
        if item is None:
            return
        tool_name = item.data(Qt.ItemDataRole.UserRole)
        if tool_name:
            self.row_clicked.emit(tool_name)

    def populate(self, rows: list[dict]) -> None:
        """Rows in display order, including group-header pseudo-rows."""
        self.setRowCount(len(rows))
        for i, row in enumerate(rows):
            if row.get("header"):
                header_item = QTableWidgetItem(row["title"])
                font = header_item.font()
                font.setBold(True)
                header_item.setFont(font)
                header_item.setBackground(QBrush(QColor("#303848")))
                self.setItem(i, 0, header_item)
                self.setSpan(i, 0, 1, len(self.COLS))
                continue
            name_item = QTableWidgetItem(row["name"])
            name_item.setData(Qt.ItemDataRole.UserRole, row["name"])
            self.setItem(i, self.COL_NAME, name_item)
            self.setItem(i, self.COL_SHOTS, QTableWidgetItem(str(row["shots"])))
            cost_item = QTableWidgetItem(_fmt_ped(row["cost"]))
            cost_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.setItem(i, self.COL_COST, cost_item)
            self.setItem(i, self.COL_LOADOUT, QTableWidgetItem("*" if row["in_loadout"] else ""))
            flags = row.get("flags", "")
            self.setItem(i, self.COL_FLAGS, QTableWidgetItem(flags))


# ---------------------------------------------------------------------------
# Open Encounters panel
# ---------------------------------------------------------------------------

class OpenEncountersPanel(_Card):
    """List of unresolved encounters with Abandon / Undo-merge actions."""

    abandon_requested = pyqtSignal(str)
    undo_merge_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("Open Encounters", parent)
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Mob", "Outcome", "Damage", "Auto", ""])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setMaximumHeight(180)
        self._body.insertWidget(0, self._table)

    def set_encounters(self, encounters: list[dict]) -> None:
        self._table.setRowCount(len(encounters))
        for i, enc in enumerate(encounters):
            self._table.setItem(i, 0, QTableWidgetItem(enc.get("mob_name") or "Unknown"))
            self._table.setItem(i, 1, QTableWidgetItem(enc.get("outcome") or "-"))
            dmg = enc.get("damage_dealt") or 0
            self._table.setItem(i, 2, QTableWidgetItem(f"{dmg:.0f}"))
            auto_merged = bool(enc.get("merged_from"))
            self._table.setItem(i, 3, QTableWidgetItem("auto" if auto_merged else ""))
            action = QPushButton("Undo merge" if auto_merged else "Abandon")
            enc_id = enc.get("id") or ""
            if auto_merged:
                action.clicked.connect(lambda _=False, eid=enc_id: self.undo_merge_requested.emit(eid))
            else:
                action.clicked.connect(lambda _=False, eid=enc_id: self.abandon_requested.emit(eid))
            self._table.setCellWidget(i, 4, action)


# ---------------------------------------------------------------------------
# Detail panel shell (views live in hunt_dashboard_details.py)
# ---------------------------------------------------------------------------

class DetailPanel(QFrame):
    """Right-hand detail panel hosting tool- and encounter-detail views."""

    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("huntDetailPanel")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(340)
        self.setMaximumWidth(420)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        header = QHBoxLayout()
        self._title = QLabel("")
        title_font = QFont()
        title_font.setBold(True)
        self._title.setFont(title_font)
        header.addWidget(self._title, 1)
        close_btn = QToolButton()
        close_btn.setText("\u2715")
        close_btn.setAutoRaise(True)
        close_btn.clicked.connect(self.closed.emit)
        header.addWidget(close_btn)
        outer.addLayout(header)
        self._stack = QStackedWidget()
        outer.addWidget(self._stack, 1)
        self._placeholder = QLabel("Select a tool or kill for details.")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stack.addWidget(self._placeholder)

    def show_view(self, title: str, view: QWidget) -> None:
        self._title.setText(title)
        # Remove any previous non-placeholder view.
        while self._stack.count() > 1:
            w = self._stack.widget(1)
            self._stack.removeWidget(w)
            w.deleteLater()
        self._stack.addWidget(view)
        self._stack.setCurrentWidget(view)

    def clear(self) -> None:
        self._title.setText("")
        self._stack.setCurrentWidget(self._placeholder)


# ---------------------------------------------------------------------------
# HuntDashboardView
# ---------------------------------------------------------------------------

class HuntDashboardView(QWidget):
    """Primary current-hunt dashboard widget."""

    def __init__(self, *, signals, db, event_bus, config, config_path,
                 markup_resolver, data_client, tool_categorizer,
                 hunt_tracker_getter: Callable[[], object | None],
                 parent=None):
        super().__init__(parent)
        self._signals = signals
        self._db = db
        self._event_bus = event_bus
        self._config = config
        self._config_path = config_path
        self._markup_resolver = markup_resolver
        self._data_client = data_client
        self._tool_categorizer = tool_categorizer
        self._get_tracker = hunt_tracker_getter

        self._scope: Scope = getattr(config, "hunt_dashboard_scope", "hunt")
        self._return_mode: ReturnMode = getattr(
            config, "hunt_dashboard_return_mode", "percent"
        )
        self._last_kill: MobEncounter | None = None
        self._session_start: datetime | None = None
        self._current_tool_name: str | None = None
        self._gear_overrides_cache: dict = {}

        self._build_ui()
        self._connect_signals()

        self._ticker = QTimer(self)
        self._ticker.setInterval(TICKER_INTERVAL_MS)
        self._ticker.timeout.connect(self._on_tick)
        self._ticker.start()

    # -- Lifecycle ---------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        if not self._ticker.isActive():
            self._ticker.start()
        self.refresh()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._ticker.stop()

    # -- UI layout ---------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)

        scope_label = QLabel("Scope:")
        header.addWidget(scope_label)
        self._scope_hunt_btn = QPushButton("Hunt")
        self._scope_session_btn = QPushButton("Session")
        for btn in (self._scope_hunt_btn, self._scope_session_btn):
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
        self._scope_hunt_btn.setChecked(self._scope == "hunt")
        self._scope_session_btn.setChecked(self._scope == "session")
        self._scope_hunt_btn.clicked.connect(lambda: self._set_scope("hunt"))
        self._scope_session_btn.clicked.connect(lambda: self._set_scope("session"))
        header.addWidget(self._scope_hunt_btn)
        header.addWidget(self._scope_session_btn)

        header.addSpacing(16)

        return_label = QLabel("Return:")
        header.addWidget(return_label)
        self._return_pct_btn = QPushButton("%")
        self._return_ped_btn = QPushButton("+/-")
        for btn in (self._return_pct_btn, self._return_ped_btn):
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setMaximumWidth(48)
        self._return_pct_btn.setChecked(self._return_mode == "percent")
        self._return_ped_btn.setChecked(self._return_mode == "signed_ped")
        self._return_pct_btn.clicked.connect(lambda: self._set_return_mode("percent"))
        self._return_ped_btn.clicked.connect(lambda: self._set_return_mode("signed_ped"))
        header.addWidget(self._return_pct_btn)
        header.addWidget(self._return_ped_btn)

        header.addStretch(1)

        self._archive_btn = QPushButton("Archive view")
        self._archive_btn.setEnabled(False)
        self._archive_btn.setToolTip("Coming soon")
        header.addWidget(self._archive_btn)

        root.addLayout(header)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setChildrenCollapsible(False)

        # Left column — cards + tables
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        row_a = QHBoxLayout()
        self._tool_card = CurrentToolCard()
        self._encounter_card = CurrentEncounterCard()
        row_a.addWidget(self._tool_card, 1)
        row_a.addWidget(self._encounter_card, 1)
        left_layout.addLayout(row_a)

        row_b = QHBoxLayout()
        self._last_kill_card = LastKillCard()
        self._last_kill_card.markup_edit_requested.connect(
            self._open_session_markup_dialog
        )
        self._stats_block = StatsBlock()
        row_b.addWidget(self._last_kill_card, 1)
        row_b.addWidget(self._stats_block, 1)
        left_layout.addLayout(row_b)

        kills_label = QLabel("Recent Kills")
        kills_label.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(kills_label)
        self._kills_model = RecentKillsModel(self)
        self._kills_view = QTableView()
        self._kills_view.setModel(self._kills_model)
        self._kills_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._kills_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._kills_view.setAlternatingRowColors(True)
        self._kills_view.verticalHeader().setVisible(False)
        self._kills_view.horizontalHeader().setSectionResizeMode(
            RecentKillsModel.COL_MOB, QHeaderView.ResizeMode.Stretch
        )
        self._kills_view.clicked.connect(self._on_kill_clicked)
        left_layout.addWidget(self._kills_view, 2)

        tools_label = QLabel("Tools Used")
        tools_label.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(tools_label)
        self._tools_table = ToolsUsedTable()
        self._tools_table.row_clicked.connect(self._on_tool_clicked)
        left_layout.addWidget(self._tools_table, 1)

        self._open_panel = OpenEncountersPanel()
        self._open_panel.abandon_requested.connect(self._on_abandon_encounter)
        self._open_panel.undo_merge_requested.connect(self._on_undo_merge)
        left_layout.addWidget(self._open_panel)
        self._open_panel.setVisible(False)

        self._global_panel = GlobalFeedPanel()
        left_layout.addWidget(self._global_panel)
        self._global_panel.setVisible(False)

        main_splitter.addWidget(left)

        self._detail_panel = DetailPanel()
        self._detail_panel.closed.connect(self._close_detail)
        main_splitter.addWidget(self._detail_panel)
        self._detail_panel.setVisible(False)

        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 1)
        self._main_splitter = main_splitter
        root.addWidget(main_splitter, 1)

    def _connect_signals(self) -> None:
        s = self._signals
        s.hunt_session_started.connect(self._on_session_started)
        s.hunt_session_stopped.connect(self._on_session_stopped)
        s.hunt_session_updated.connect(self._on_session_updated)
        s.hunt_encounter_started.connect(self._on_encounter_started)
        s.hunt_encounter_ended.connect(self._on_encounter_ended)
        s.hunt_started.connect(self._on_hunt_started)
        s.hunt_ended.connect(self._on_hunt_ended)
        s.hunt_split.connect(self._on_hunt_split)
        s.mob_target_changed.connect(self._on_mob_changed)
        s.active_tool_changed.connect(self._on_active_tool_changed)
        s.enhancer_break.connect(self._on_enhancer_break)
        s.global_event.connect(self._on_global_event)
        s.own_global.connect(self._on_own_global)
        s.open_encounter_updated.connect(self._on_open_encounter_updated)
        s.gear_override_changed.connect(self._on_gear_override_changed)
        s.session_markup_changed.connect(self._on_session_markup_changed)

    # -- Scope / mode toggles ----------------------------------------

    def _set_scope(self, scope: Scope) -> None:
        if scope == self._scope:
            return
        self._scope = scope
        self._persist_config("hunt_dashboard_scope", scope)
        self.refresh()

    def _set_return_mode(self, mode: ReturnMode) -> None:
        if mode == self._return_mode:
            return
        self._return_mode = mode
        self._persist_config("hunt_dashboard_return_mode", mode)
        self._refresh_stats()

    def _persist_config(self, key: str, value) -> None:
        from ...core.config import save_config
        setattr(self._config, key, value)
        try:
            save_config(self._config, self._config_path)
        except Exception as e:
            log.warning("Failed to persist %s: %s", key, e)
        self._event_bus.publish(EVENT_CONFIG_CHANGED, self._config)

    # -- Data fetch --------------------------------------------------

    def _scoped_encounters(self) -> list[MobEncounter]:
        tracker = self._get_tracker()
        if tracker is None or getattr(tracker, "_session", None) is None:
            return []
        session = tracker._session
        if self._scope == "session":
            return list(session.encounters)
        # Hunt scope: current hunt only.
        if tracker._hunt_detector and tracker._hunt_detector.current_hunt:
            return list(tracker._hunt_detector.current_hunt.encounters)
        return list(session.encounters)

    def _scope_start_time(self) -> datetime | None:
        tracker = self._get_tracker()
        if tracker is None or getattr(tracker, "_session", None) is None:
            return None
        if self._scope == "session":
            return tracker._session.start_time
        if tracker._hunt_detector and tracker._hunt_detector.current_hunt:
            return tracker._hunt_detector.current_hunt.start_time
        return tracker._session.start_time

    def _current_loadout(self) -> dict | None:
        tracker = self._get_tracker()
        if tracker is None:
            return None
        mgr = getattr(tracker, "_loadout_mgr", None)
        if mgr is None:
            return None
        return getattr(mgr, "active_loadout", None)

    # -- Refresh -----------------------------------------------------

    def refresh(self) -> None:
        encounters = self._scoped_encounters()
        self._kills_model.set_encounters(encounters)
        self._refresh_tools_table(encounters)
        self._refresh_stats(encounters)
        self._refresh_open_encounters()
        self._refresh_globals_feed(encounters)

    def _refresh_tools_table(self, encounters: list[MobEncounter]) -> None:
        tool_stats = hunt_stats.aggregate_by_tool(encounters)
        # Need cost caused per tool. Fold in cost_per_shot via tracker.
        tracker = self._get_tracker()
        ti = getattr(tracker, "_tool_inference", None) if tracker else None
        loadout = self._current_loadout()
        overrides = {}
        try:
            overrides = self._db.get_all_gear_overrides() or {}
        except Exception:
            overrides = {}
        self._gear_overrides_cache = overrides

        rows_by_cat: dict[str, list[dict]] = {"offense": [], "defense": [], "utility": []}
        for name, stats in tool_stats.items():
            cost_per_shot = 0.0
            if ti is not None:
                try:
                    cost_per_shot = ti.get_cost_per_shot(name) or 0.0
                except Exception:
                    cost_per_shot = 0.0
            # cost_per_shot from ToolInferenceEngine is PEC; convert to PED.
            cost = stats["shots_fired"] * (cost_per_shot / 100.0)
            category = self._tool_categorizer.category_for(name) if self._tool_categorizer else "utility"
            if category is None:
                continue  # mining tool, skipped
            in_lo = self._tool_categorizer.is_in_loadout(name, loadout) if self._tool_categorizer else False
            flags = []
            if name.lower() in overrides:
                flags.append("OVR")
            rows_by_cat.setdefault(category, []).append({
                "name": name,
                "shots": stats["shots_fired"],
                "cost": cost,
                "in_loadout": in_lo,
                "flags": " ".join(flags),
            })

        for bucket in rows_by_cat.values():
            bucket.sort(key=lambda r: r["cost"], reverse=True)

        display: list[dict] = []
        for category in ("offense", "defense", "utility"):
            bucket = rows_by_cat.get(category) or []
            if not bucket:
                continue
            display.append({"header": True, "title": category.title()})
            display.extend(bucket)
        self._tools_table.populate(display)

    def _refresh_stats(self, encounters: list[MobEncounter] | None = None) -> None:
        if encounters is None:
            encounters = self._scoped_encounters()
        economy = hunt_stats.encounters_economy(encounters)
        start = self._scope_start_time()
        duration = None
        if start:
            duration = datetime.utcnow() - start
        globals_count = sum(1 for e in encounters if e.is_global)
        hof_count = sum(1 for e in encounters if e.is_hof)
        tracker = self._get_tracker()
        session_id = tracker._session.id if tracker and tracker._session else None
        mu = hunt_stats.mu_consumed(
            encounters, self._markup_resolver,
            gear_overrides=self._gear_overrides_cache,
            session_id=session_id,
        )
        self._stats_block.set_stats(
            return_pct=economy["return_pct"],
            profit_loss=economy["profit_loss"],
            return_mode=self._return_mode,
            duration=duration,
            avg_kill_cost=economy["cost_per_kill"],
            globals_count=globals_count,
            hof_count=hof_count,
            mu_consumed=mu,
        )

    def _refresh_open_encounters(self) -> None:
        tracker = self._get_tracker()
        if tracker is None:
            self._open_panel.setVisible(False)
            return
        encounters = [enc.to_dict() for enc in getattr(tracker, "_open_encounters", [])]
        self._open_panel.set_encounters(encounters)
        self._open_panel.setVisible(bool(encounters))

    def _refresh_globals_feed(self, encounters: list[MobEncounter]) -> None:
        entries: list[tuple[datetime, str, float, bool]] = []
        for enc in reversed(encounters):
            if enc.is_global or enc.is_hof:
                entries.append((
                    enc.end_time or enc.start_time,
                    enc.mob_name or "Unknown",
                    enc.loot_total_ped,
                    enc.is_hof,
                ))
            if len(entries) >= GlobalFeedPanel.MAX_ROWS:
                break
        self._global_panel.set_entries(entries)
        self._global_panel.setVisible(bool(entries))

    # -- Ticker ------------------------------------------------------

    def _on_tick(self) -> None:
        self._kills_model.tick_time_column()
        self._encounter_card.refresh_duration()
        # Duration in stats block updates via _refresh_stats, which is
        # cheap; avoid full tools-table rebuild here.
        encounters = self._scoped_encounters()
        self._refresh_stats(encounters)

    # -- Signal handlers ---------------------------------------------

    def _on_session_started(self, data) -> None:
        self._session_start = datetime.utcnow()
        self._last_kill = None
        self.refresh()

    def _on_session_stopped(self, data) -> None:
        self.refresh()

    def _on_session_updated(self, data) -> None:
        self.refresh()

    def _on_encounter_started(self, data) -> None:
        tracker = self._get_tracker()
        if tracker is None or tracker._manager is None:
            return
        enc = tracker._manager.current_encounter
        if enc:
            self._encounter_card.set_active(enc)

    def _on_encounter_ended(self, data) -> None:
        tracker = self._get_tracker()
        if tracker is None or tracker._session is None:
            return
        encounters = self._scoped_encounters()
        if encounters:
            self._last_kill = encounters[-1]
            self._last_kill_card.set_kill(self._last_kill)
        self._encounter_card.set_idle(self._last_kill)
        self.refresh()

    def _on_hunt_started(self, data) -> None:
        if self._scope == "hunt":
            self.refresh()

    def _on_hunt_ended(self, data) -> None:
        if self._scope == "hunt":
            self.refresh()

    def _on_hunt_split(self, data) -> None:
        if self._scope == "hunt":
            self.refresh()

    def _on_mob_changed(self, data) -> None:
        tracker = self._get_tracker()
        if tracker is None or tracker._manager is None:
            return
        enc = tracker._manager.current_encounter
        if enc:
            self._encounter_card.set_active(enc)

    def _on_active_tool_changed(self, data) -> None:
        name = data.get("tool_name") if isinstance(data, dict) else str(data)
        self._current_tool_name = name
        self._refresh_tool_card()

    def _on_enhancer_break(self, data) -> None:
        self._refresh_tool_card()

    def _on_global_event(self, event) -> None:
        # Dashboard's running feed is re-derived from encounters; a
        # global event alone is not enough (mob attribution comes via
        # the encounter's is_global flag). Just schedule a refresh.
        self.refresh()

    def _on_own_global(self, event) -> None:
        self.refresh()

    def _on_open_encounter_updated(self, data) -> None:
        self._refresh_open_encounters()

    def _on_gear_override_changed(self, data) -> None:
        """Refresh costs when a gear override is edited."""
        self.refresh()

    def _on_session_markup_changed(self, data) -> None:
        """Refresh loot valuation when a session (L) markup changes."""
        self.refresh()

    def _refresh_tool_card(self) -> None:
        tracker = self._get_tracker()
        name = self._current_tool_name
        cost = None
        dpp = None
        declared: list[str] = []
        inferred: list[str] = []
        if tracker and name:
            ti = tracker._tool_inference
            try:
                cost = ti.get_cost_per_shot(name)
            except Exception:
                cost = None
            enh = getattr(tracker, "_enhancer_inference", None)
            if enh is not None:
                try:
                    state = enh.get_tool_state(name) if hasattr(enh, "get_tool_state") else None
                    if state and getattr(state, "state", None) == "CONFIRMED_PRESENT":
                        inferred.append("(auto-detected)")
                except Exception:
                    pass
            loadout = self._current_loadout() or {}
            weapon = (loadout.get("Gear") or {}).get("Weapon") or {}
            if weapon.get("Name") == name:
                enhancers = weapon.get("Enhancers") or {}
                for slot, entry in enhancers.items():
                    if isinstance(entry, dict):
                        enh_name = entry.get("Name")
                        if enh_name:
                            declared.append(f"{slot}: {enh_name}")
        self._tool_card.set_tool(name, cost, dpp, declared, inferred)

    # -- Row interactions --------------------------------------------

    def _on_kill_clicked(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        enc = self._kills_model.encounter_at(index.row())
        if enc is None:
            return
        self._open_encounter_detail(enc)

    def _on_tool_clicked(self, tool_name: str) -> None:
        if not tool_name:
            return
        self._open_tool_detail(tool_name)

    def _open_tool_detail(self, tool_name: str) -> None:
        from .hunt_dashboard_details import tool_detail_for
        category = self._tool_categorizer.category_for(tool_name) if self._tool_categorizer else "utility"
        item_type = self._tool_categorizer.item_type_for(tool_name) if self._tool_categorizer else None
        encounters = self._scoped_encounters()
        view = tool_detail_for(tool_name, encounters, category, item_type)
        if hasattr(view, "edit_override_requested"):
            view.edit_override_requested.connect(self._open_gear_override_dialog)
        self._detail_panel.show_view(tool_name, view)
        self._detail_panel.setVisible(True)

    def _open_gear_override_dialog(self, tool_name: str) -> None:
        from .hunt_dashboard_gear_override_dialog import GearOverrideDialog
        dialog = GearOverrideDialog(
            tool_name=tool_name,
            db=self._db,
            event_bus=self._event_bus,
            parent=self,
        )
        dialog.exec()

    def _open_session_markup_dialog(self, item_name: str) -> None:
        tracker = self._get_tracker()
        if tracker is None or tracker._session is None:
            return
        from .hunt_dashboard_session_markup_dialog import SessionMarkupDialog
        dialog = SessionMarkupDialog(
            item_name=item_name,
            session_id=tracker._session.id,
            db=self._db,
            event_bus=self._event_bus,
            parent=self,
        )
        dialog.exec()

    def _open_encounter_detail(self, enc: MobEncounter) -> None:
        from .hunt_dashboard_details import EncounterDetailView
        tracker = self._get_tracker()
        combat_log = getattr(tracker, "_combat_log", None) if tracker else None
        view = EncounterDetailView(enc, combat_log)
        title = f"{enc.mob_name or 'Unknown'} - kill"
        self._detail_panel.show_view(title, view)
        self._detail_panel.setVisible(True)

    def _close_detail(self) -> None:
        self._detail_panel.clear()
        self._detail_panel.setVisible(False)

    def _on_abandon_encounter(self, enc_id: str) -> None:
        tracker = self._get_tracker()
        if tracker is None or not enc_id:
            return
        try:
            tracker.abandon_open_encounter(enc_id)
        except Exception as e:
            log.warning("abandon_open_encounter(%s) failed: %s", enc_id, e)

    def _on_undo_merge(self, enc_id: str) -> None:
        tracker = self._get_tracker()
        if tracker is None or not enc_id:
            return
        try:
            tracker.split_merged_encounter(enc_id)
        except Exception as e:
            log.warning("split_merged_encounter(%s) failed: %s", enc_id, e)
