"""Wiki entity table — sortable, filterable, with configurable columns."""

from __future__ import annotations

import re
from typing import Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView,
    QLabel, QPushButton, QLineEdit, QHeaderView, QAbstractItemView,
)
from PyQt6.QtCore import (
    Qt, QTimer, QAbstractTableModel, QModelIndex, QSortFilterProxyModel,
)

from ..theme import TEXT_MUTED, BORDER, SECONDARY, PRIMARY
from ...data.wiki_columns import COLUMN_DEFS, DEFAULT_COLUMNS, get_item_name


# ---------------------------------------------------------------------------
# Filter matching
# ---------------------------------------------------------------------------

_OP_RE = re.compile(r"^(>=|<=|>|<|=|!)(.+)$")


def _matches_filter(raw_value, display_text: str, filter_text: str) -> bool:
    """Check if a cell value matches a filter expression."""
    filter_text = filter_text.strip()
    if not filter_text:
        return True

    m = _OP_RE.match(filter_text)
    if m:
        op, operand = m.group(1), m.group(2).strip()

        # Numeric operators
        if op in (">", "<", ">=", "<="):
            try:
                threshold = float(operand)
            except ValueError:
                return True  # invalid number → don't filter
            if raw_value is None or not isinstance(raw_value, (int, float)):
                return False
            if op == ">":
                return raw_value > threshold
            if op == "<":
                return raw_value < threshold
            if op == ">=":
                return raw_value >= threshold
            if op == "<=":
                return raw_value <= threshold

        # Exact match
        if op == "=":
            return display_text.lower() == operand.lower()

        # Exclude
        if op == "!":
            return operand.lower() not in display_text.lower()

    # Default: substring search
    return filter_text.lower() in display_text.lower()


# ---------------------------------------------------------------------------
# Table model — stores data, provides it on demand (no widget items)
# ---------------------------------------------------------------------------

class _WikiTableModel(QAbstractTableModel):
    """Flat table model backed by a pre-computed cache of (raw, display) tuples."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers: list[str] = []
        # Per-cell cache: _cache[row][col] = (raw_value, display_text)
        self._cache: list[list[tuple]] = []
        # Per-column flags: True if the column holds numeric data
        self._numeric: list[bool] = []

    def set_data(self, items: list[dict], col_defs: list[dict]):
        """Rebuild the entire cache from raw entity dicts + column definitions."""
        self.beginResetModel()
        self._headers = ["Name"] + [d["header"] for d in col_defs]
        self._numeric = [False] + [True] * len(col_defs)  # assume numeric; refined below

        cache: list[list[tuple]] = []
        for item in items:
            name = get_item_name(item)
            row: list[tuple] = [(name, name)]
            for col_def in col_defs:
                raw = col_def["get_value"](item)
                display = str(col_def["format"](raw))
                row.append((raw, display))
            cache.append(row)

        # Determine which columns are actually numeric (check first non-None value)
        for col in range(len(self._headers)):
            self._numeric[col] = False
            for row in cache:
                raw = row[col][0]
                if raw is not None:
                    self._numeric[col] = isinstance(raw, (int, float))
                    break

        self._cache = cache
        self.endResetModel()

    # --- QAbstractTableModel interface ---

    def rowCount(self, parent=QModelIndex()):
        return len(self._cache)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        r, c = index.row(), index.column()
        if r < 0 or r >= len(self._cache) or c < 0 or c >= len(self._headers):
            return None

        raw, display = self._cache[r][c]

        if role == Qt.ItemDataRole.DisplayRole:
            return display
        if role == Qt.ItemDataRole.UserRole:
            return raw
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if self._numeric[c]:
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if 0 <= section < len(self._headers):
                return self._headers[section]
        return None

    # --- Helpers for proxy ---

    def raw_value(self, row: int, col: int):
        if 0 <= row < len(self._cache) and 0 <= col < len(self._headers):
            return self._cache[row][col][0]
        return None

    def display_value(self, row: int, col: int) -> str:
        if 0 <= row < len(self._cache) and 0 <= col < len(self._headers):
            return self._cache[row][col][1]
        return ""


# ---------------------------------------------------------------------------
# Sort/filter proxy
# ---------------------------------------------------------------------------

class _WikiSortFilterProxy(QSortFilterProxyModel):
    """Proxy that sorts by raw values (None to bottom) and filters per-column."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._col_filters: list[str] = []

    def set_column_filters(self, filters: list[str]):
        self._col_filters = filters
        self.invalidateFilter()

    # --- Sorting ---

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        raw_l = left.data(Qt.ItemDataRole.UserRole)
        raw_r = right.data(Qt.ItemDataRole.UserRole)

        # None → always sort to the bottom regardless of sort direction.
        # QSortFilterProxyModel flips lessThan in descending order, so we
        # need to check the current sort order and compensate.
        if raw_l is None or raw_r is None:
            if raw_l is None and raw_r is None:
                return False
            ascending = self.sortOrder() == Qt.SortOrder.AscendingOrder
            if raw_l is None:
                return not ascending  # ascending → False (bottom); desc → True (still bottom)
            return ascending          # ascending → True (other goes bottom); desc → False

        if isinstance(raw_l, (int, float)) and isinstance(raw_r, (int, float)):
            return raw_l < raw_r
        return str(raw_l).lower() < str(raw_r).lower()

    # --- Filtering ---

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not any(f.strip() for f in self._col_filters):
            return True

        model: _WikiTableModel = self.sourceModel()
        for col, ft in enumerate(self._col_filters):
            if not ft.strip():
                continue
            raw = model.raw_value(source_row, col)
            display = model.display_value(source_row, col)
            if not _matches_filter(raw, display, ft):
                return False
        return True


# ---------------------------------------------------------------------------
# WikiTableView
# ---------------------------------------------------------------------------

FILTER_DEBOUNCE_MS = 200


class WikiTableView(QWidget):
    """Table view for wiki entity data with sorting, filtering, and column config."""

    def __init__(
        self,
        page_type_id: str,
        column_prefs: dict[str, list[str]] | None = None,
        on_columns_changed: Callable[[str, list[str]], None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._page_type_id = page_type_id
        self._column_prefs = column_prefs or {}
        self._on_columns_changed = on_columns_changed
        self._items: list[dict] = []
        self._active_col_keys: list[str] = []

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 4)
        toolbar.setSpacing(8)

        self._count_label = QLabel("")
        self._count_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        toolbar.addWidget(self._count_label)

        toolbar.addStretch()

        self._config_btn = QPushButton("\u2699")  # ⚙
        self._config_btn.setToolTip("Configure columns")
        self._config_btn.setFixedSize(28, 28)
        self._config_btn.setStyleSheet(
            f"QPushButton {{ font-size: 16px; padding: 0; border: 1px solid {BORDER};"
            f" border-radius: 4px; background: {SECONDARY}; }}"
            f"QPushButton:hover {{ background: {PRIMARY}; }}"
        )
        self._config_btn.clicked.connect(self._open_column_config)
        toolbar.addWidget(self._config_btn)

        layout.addLayout(toolbar)

        # Filter row
        self._filter_container = QWidget()
        self._filter_layout = QHBoxLayout(self._filter_container)
        self._filter_layout.setContentsMargins(0, 0, 0, 0)
        self._filter_layout.setSpacing(0)
        self._filter_inputs: list[QLineEdit] = []
        layout.addWidget(self._filter_container)

        # Model / proxy
        self._model = _WikiTableModel(self)
        self._proxy = _WikiSortFilterProxy(self)
        self._proxy.setSourceModel(self._model)

        # Table view
        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionsClickable(True)
        self._table.setSortingEnabled(True)
        self._table.setStyleSheet(
            "QTableView { alternate-background-color: #2a2a2a; }"
        )
        layout.addWidget(self._table)

        # Sync filter widths with column header sizes
        header = self._table.horizontalHeader()
        header.sectionResized.connect(self._on_section_resized)
        header.geometriesChanged.connect(self._sync_all_filter_widths)

        # Filter debounce timer
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(FILTER_DEBOUNCE_MS)
        self._filter_timer.timeout.connect(self._apply_filters)

    # --- Public API ---

    def set_data(self, items: list[dict]):
        """Populate the table with entity data."""
        self._items = items
        self._resolve_columns()
        self._rebuild_table()

    def set_loading(self):
        """Show loading state."""
        self._count_label.setText("Loading...")
        self._model.set_data([], [])

    # --- Column resolution ---

    def _resolve_columns(self):
        """Determine which column keys to show."""
        # Check user prefs first
        prefs = self._column_prefs.get(self._page_type_id)
        if prefs:
            self._active_col_keys = list(prefs)
            return

        # Fall back to defaults (all columns for the type)
        defaults = DEFAULT_COLUMNS.get(self._page_type_id, [])
        self._active_col_keys = list(defaults)

    def _get_column_defs(self) -> list[dict]:
        """Get resolved column definition dicts for active keys."""
        all_defs = COLUMN_DEFS.get(self._page_type_id, {})
        return [all_defs[k] for k in self._active_col_keys if k in all_defs]

    # --- Table rebuild ---

    def _rebuild_table(self):
        """Rebuild the entire table from current items and column config."""
        col_defs = self._get_column_defs()

        # Feed data into model (proxy auto-updates)
        self._model.set_data(self._items, col_defs)

        # Size columns: Name stretches, data columns fit content
        header = self._table.horizontalHeader()
        col_count = 1 + len(col_defs)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, col_count):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        # Rebuild filter inputs to match columns
        self._rebuild_filters(col_count)

        # Update count
        self._update_count_label()

        # Sync filter widths after layout settles
        QTimer.singleShot(0, self._sync_all_filter_widths)

    def _rebuild_filters(self, col_count: int):
        """Rebuild the filter input row to match current columns."""
        # Clear old
        for inp in self._filter_inputs:
            inp.deleteLater()
        self._filter_inputs.clear()

        # Create new — one filter per column
        for i in range(col_count):
            inp = QLineEdit()
            inp.setPlaceholderText("Filter...")
            inp.setFixedHeight(24)
            inp.setStyleSheet("font-size: 11px; padding: 2px 4px;")
            inp.textChanged.connect(self._on_filter_changed)
            self._filter_layout.addWidget(inp)
            self._filter_inputs.append(inp)

    # --- Filter width synchronization ---

    def _on_section_resized(self, logical_index: int, _old_size: int, new_size: int):
        """Keep a single filter input in sync with its column width."""
        if 0 <= logical_index < len(self._filter_inputs):
            self._filter_inputs[logical_index].setFixedWidth(new_size)

    def _sync_all_filter_widths(self):
        """Resync all filter input widths with the current header section sizes."""
        header = self._table.horizontalHeader()
        for i, inp in enumerate(self._filter_inputs):
            w = header.sectionSize(i)
            if w > 0:
                inp.setFixedWidth(w)

    # --- Filtering ---

    def _on_filter_changed(self):
        """Schedule filter application with debounce."""
        self._filter_timer.start()

    def _apply_filters(self):
        """Push current filter texts into the proxy model."""
        filter_texts = [inp.text() for inp in self._filter_inputs]
        self._proxy.set_column_filters(filter_texts)
        self._update_count_label()

    def _update_count_label(self):
        total = len(self._items)
        visible = self._proxy.rowCount()
        if visible != total:
            self._count_label.setText(f"{visible} / {total} items")
        else:
            self._count_label.setText(f"{total} items")

    # --- Column config ---

    def _open_column_config(self):
        """Open column configuration dialog."""
        from .column_config_dialog import ColumnConfigDialog

        all_defs = COLUMN_DEFS.get(self._page_type_id, {})
        if not all_defs:
            return

        dialog = ColumnConfigDialog(
            all_defs=all_defs,
            current_keys=list(self._active_col_keys),
            parent=self,
        )
        if dialog.exec():
            new_keys = dialog.selected_keys()
            if new_keys != self._active_col_keys:
                self._active_col_keys = new_keys
                self._rebuild_table()
                if self._on_columns_changed:
                    self._on_columns_changed(self._page_type_id, new_keys)
