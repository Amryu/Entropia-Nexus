"""Wiki entity table — sortable, filterable, with configurable columns.

Thin adapter around FancyTable that handles wiki-specific column resolution,
user preferences, and the column config dialog.
"""

from __future__ import annotations

import re
from typing import Callable

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal

from .fancy_table import FancyTable, ColumnDef, column_def_from_dict
from ...data.wiki_columns import COLUMN_DEFS, DEFAULT_COLUMNS, get_item_name


# ---------------------------------------------------------------------------
# Cache builder — can run on any thread (used by wiki_page warmup)
# ---------------------------------------------------------------------------

# Max time (seconds) to hold the GIL before yielding. Matches 120fps frame budget.
_GIL_YIELD_BUDGET = 0.008


def build_column_cache(items: list[dict], col_defs: list[dict]):
    """Build (raw_value, display_text) cache for items x columns. Thread-safe.

    Returns (cache, numeric) where cache[row][col] = (raw, display)
    and numeric[col] = True if the column holds numeric data.
    Column 0 is always the Name column.
    """
    import time

    cache: list[list[tuple]] = []
    last_yield = time.monotonic()
    for item in items:
        name = get_item_name(item)
        row: list[tuple] = [(name, name)]
        for col_def in col_defs:
            raw = col_def["get_value"](item)
            display = str(col_def["format"](raw))
            row.append((raw, display))
        cache.append(row)
        # Time-gated GIL yield so global input hooks (keyboard library)
        # and the Qt event loop can process events without stalling.
        if time.monotonic() - last_yield > _GIL_YIELD_BUDGET:
            time.sleep(0)
            last_yield = time.monotonic()

    num_cols = 1 + len(col_defs)
    numeric = [False] * num_cols
    for col in range(num_cols):
        for row in cache:
            raw = row[col][0]
            if raw is not None:
                numeric[col] = isinstance(raw, (int, float))
                break

    return cache, numeric


# ---------------------------------------------------------------------------
# Filter matching (kept at module level for backward compat)
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

        if op in (">", "<", ">=", "<="):
            try:
                threshold = float(operand)
            except ValueError:
                return True
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

        if op == "=":
            return display_text.lower() == operand.lower()

        if op == "!":
            return operand.lower() not in display_text.lower()

    return filter_text.lower() in display_text.lower()


# ---------------------------------------------------------------------------
# Name column definition
# ---------------------------------------------------------------------------

_NAME_COLUMN = ColumnDef(
    key="_name",
    header="Name",
    main=True,
    width_basis="content",
    get_value=get_item_name,
    format=str,
)


# ---------------------------------------------------------------------------
# WikiTableView — thin adapter around FancyTable
# ---------------------------------------------------------------------------

class WikiTableView(QWidget):
    """Table view for wiki entity data with sorting, filtering, and column config."""

    row_activated = pyqtSignal(dict)  # emitted on double-click with the full item dict
    new_clicked = pyqtSignal()       # emitted when the "+" button is clicked

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
        self._full_col_keys: list[str] = []
        # Pre-computed cache covering ALL columns for the page type
        self._all_type_col_keys: list[str] = []
        self._full_cache: list[list[tuple]] = []
        self._full_numeric: list[bool] = []

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create FancyTable with empty columns (set on first set_data)
        self._table = FancyTable(columns=[], parent=self)
        self._table.row_clicked.connect(self._on_row_activated)
        self._table.config_button.clicked.connect(self._open_column_config)
        self._table.new_button.clicked.connect(self.new_clicked.emit)
        self._table.new_button.show()
        layout.addWidget(self._table, 1)

    # --- Public API ---

    def set_data(self, items: list[dict], full_cache=None, full_numeric=None):
        """Populate the table with entity data.

        If *full_cache* / *full_numeric* are supplied (pre-computed on a
        background thread) the expensive per-cell computation is skipped.
        """
        self._items = items
        self._resolve_columns()

        # Store (or compute) full cache covering ALL type columns
        all_defs = COLUMN_DEFS.get(self._page_type_id, {})
        self._all_type_col_keys = list(all_defs.keys())

        if full_cache is not None:
            self._full_cache = full_cache
            self._full_numeric = full_numeric
        else:
            col_defs_list = [all_defs[k] for k in self._all_type_col_keys]
            self._full_cache, self._full_numeric = build_column_cache(items, col_defs_list)

        self._rebuild_table()

    def set_loading(self):
        """Show loading state."""
        self._table.set_loading()

    # --- Column resolution ---

    def _resolve_columns(self):
        """Determine which column keys to show."""
        prefs = self._column_prefs.get(self._page_type_id)
        if prefs:
            self._full_col_keys = list(prefs)
        else:
            defaults = DEFAULT_COLUMNS.get(self._page_type_id, [])
            self._full_col_keys = list(defaults)

    # --- Cache subsetting ---

    def _subset_cache(self):
        """Extract active columns from the pre-computed full cache.

        Returns (column_defs, cache, numeric) ready for FancyTable.
        """
        key_to_idx = {k: i for i, k in enumerate(self._all_type_col_keys)}
        all_defs = COLUMN_DEFS.get(self._page_type_id, {})
        active_indices = [key_to_idx[k] for k in self._full_col_keys if k in key_to_idx]

        # Build ColumnDef list: Name + active data columns
        column_defs = [_NAME_COLUMN]
        for i in active_indices:
            key = self._all_type_col_keys[i]
            col_dict = all_defs[key]
            column_defs.append(column_def_from_dict(col_dict))

        numeric = [self._full_numeric[0]] + [self._full_numeric[i + 1] for i in active_indices]

        # +1 offset because column 0 is always Name in the full cache
        subset: list[list[tuple]] = []
        for full_row in self._full_cache:
            row = [full_row[0]]  # Name
            for i in active_indices:
                row.append(full_row[i + 1])
            subset.append(row)

        return column_defs, subset, numeric

    # --- Table rebuild ---

    def _rebuild_table(self):
        """Rebuild the FancyTable from the pre-computed cache."""
        column_defs, cache, numeric = self._subset_cache()
        self._table.set_columns(column_defs)
        self._table.set_data(self._items, cache=cache, numeric=numeric)

    # --- Row activation ---

    def _on_row_activated(self, item: dict, _index: int):
        """Bridge FancyTable signal to WikiTableView signal (drop index)."""
        self.row_activated.emit(item)

    # --- Column config ---

    def _open_column_config(self):
        """Open column configuration dialog."""
        from .column_config_dialog import ColumnConfigDialog

        all_defs = COLUMN_DEFS.get(self._page_type_id, {})
        if not all_defs:
            return

        dialog = ColumnConfigDialog(
            all_defs=all_defs,
            current_keys=list(self._full_col_keys),
            parent=self,
        )
        if dialog.exec():
            new_keys = dialog.selected_keys()
            if new_keys != self._full_col_keys:
                self._full_col_keys = new_keys
                self._rebuild_table()
                if self._on_columns_changed:
                    self._on_columns_changed(self._page_type_id, new_keys)
