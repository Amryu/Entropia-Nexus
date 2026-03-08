"""Reusable table-based gear picker dialog for the loadout calculator."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QWidget, QAbstractItemView,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from ..theme import (
    ACCENT, BORDER, HOVER, PRIMARY, SECONDARY, TEXT, TEXT_MUTED,
    TABLE_ROW_ALT, WARNING, ERROR,
)
from .fuzzy_line_edit import score_search

# Row-class name → foreground color mapping
_ROW_COLORS = {
    "overamp-warn": WARNING,
    "overamp-danger": ERROR,
}


class GearPickerDialog(QDialog):
    """Modal dialog that shows a filterable, sortable table of gear items.

    Parameters
    ----------
    title : str
        Dialog window title.
    columns : list[dict]
        Each dict has ``key`` (str), ``header`` (str), and optional
        ``width`` (int).  The first column is treated as the name column.
    rows : list[dict]
        Each dict has keys matching ``columns[*].key`` plus ``_name`` (str)
        with the item name to emit on selection.
    row_class : callable or None
        ``(row_dict) -> str`` returning a class name for highlighting
        (e.g. ``"overamp-warn"``, ``"overamp-danger"``).
    header_widget : QWidget or None
        Extra widget placed in the title bar (e.g. a checkbox).
    """

    item_selected = pyqtSignal(str)

    def __init__(
        self,
        title: str,
        columns: list[dict],
        rows: list[dict],
        parent: QWidget | None = None,
        *,
        row_class=None,
        header_widget: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(700, 400)
        self.resize(860, 520)

        self._columns = columns
        self._all_rows = rows
        self._row_class = row_class

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # --- Header bar (optional extra widget) ---
        if header_widget:
            hbar = QHBoxLayout()
            hbar.addStretch()
            hbar.addWidget(header_widget)
            root.addLayout(hbar)

        # --- Search ---
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._apply_filter)
        self._search.setStyleSheet(
            f"QLineEdit {{ background: {PRIMARY}; color: {TEXT}; "
            f"border: 1px solid {BORDER}; border-radius: 4px; padding: 4px 8px; }}"
        )
        root.addWidget(self._search)

        # --- Table ---
        self._table = QTableWidget(0, len(columns))
        self._table.setHorizontalHeaderLabels([c["header"] for c in columns])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(True)
        self._table.doubleClicked.connect(self._on_double_click)

        hdr = self._table.horizontalHeader()
        for i, col in enumerate(columns):
            if "width" in col:
                hdr.resizeSection(i, col["width"])
            elif i == 0:
                hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        self._table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {SECONDARY};
                alternate-background-color: {TABLE_ROW_ALT};
                border: 1px solid {BORDER};
                border-radius: 6px;
                gridline-color: {BORDER};
                color: {TEXT};
            }}
            QTableWidget::item {{
                padding: 2px 8px;
            }}
            QTableWidget::item:selected {{
                background-color: {HOVER};
                color: {TEXT};
            }}
            QHeaderView::section {{
                background-color: {PRIMARY};
                color: {TEXT_MUTED};
                font-weight: 600;
                font-size: 11px;
                border: none;
                border-bottom: 1px solid {BORDER};
                padding: 4px 8px;
            }}
        """)
        root.addWidget(self._table, 1)

        self.setStyleSheet(f"QDialog {{ background-color: {SECONDARY}; }}")

        self._populate(rows)
        self._search.setFocus()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def refresh_rows(self, rows: list[dict]):
        """Replace table content (e.g. after toggling a filter)."""
        self._all_rows = rows
        self._apply_filter(self._search.text())

    def update_columns(self, columns: list[dict]):
        """Update column definitions and headers (e.g. after toggling overamp mode)."""
        self._columns = columns
        self._table.setColumnCount(len(columns))
        self._table.setHorizontalHeaderLabels([c["header"] for c in columns])
        hdr = self._table.horizontalHeader()
        for i, col in enumerate(columns):
            if "width" in col:
                hdr.resizeSection(i, col["width"])
            elif i == 0:
                hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _populate(self, rows: list[dict]):
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            cls = self._row_class(row) if self._row_class else ""
            fg = QColor(_ROW_COLORS[cls]) if cls in _ROW_COLORS else None
            for j, col in enumerate(self._columns):
                val = row.get(col["key"], "")
                item = QTableWidgetItem(str(val) if val is not None else "")
                item.setData(Qt.ItemDataRole.UserRole, row.get("_name", ""))
                if fg:
                    item.setForeground(fg)
                # Right-align numeric columns (not the name column)
                if j > 0:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self._table.setItem(i, j, item)
        self._table.setSortingEnabled(True)

    def _apply_filter(self, text: str):
        query = text.strip()
        if not query:
            self._populate(self._all_rows)
            return
        scored = []
        for row in self._all_rows:
            s = score_search(row.get("_name", ""), query)
            if s > 0:
                scored.append((s, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        self._populate([r for _, r in scored])

    def _on_double_click(self, index):
        item = self._table.item(index.row(), 0)
        if item:
            name = item.data(Qt.ItemDataRole.UserRole)
            if name:
                self.item_selected.emit(name)
                self.accept()
