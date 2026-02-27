"""Column configuration dialog — choose and reorder visible columns."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QAbstractItemView, QWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from ..theme import TEXT, TEXT_MUTED, ACCENT, BORDER, SECONDARY, PRIMARY

CONDENSED_COLUMN_COUNT = 5


class ColumnConfigDialog(QDialog):
    """Modal dialog for selecting and reordering wiki table columns."""

    def __init__(
        self,
        all_defs: dict[str, dict],
        current_keys: list[str],
        parent=None,
    ):
        super().__init__(parent)
        self._all_defs = all_defs
        self._current_keys = list(current_keys)

        self.setWindowTitle("Configure Columns")
        self.setMinimumSize(480, 360)
        self.setModal(True)

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)

        # Description
        desc = QLabel("Select and reorder the columns shown in the table.")
        desc.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        root.addWidget(desc)

        # Two-panel layout
        panels = QHBoxLayout()
        panels.setSpacing(12)

        # Left: available columns
        left_col = QVBoxLayout()
        left_label = QLabel("Available Columns")
        left_label.setStyleSheet(f"color: {TEXT}; font-weight: bold; font-size: 12px;")
        left_col.addWidget(left_label)

        self._available_list = QListWidget()
        self._available_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        left_col.addWidget(self._available_list)

        add_btn = QPushButton("Add \u2192")
        add_btn.clicked.connect(self._add_column)
        left_col.addWidget(add_btn)

        panels.addLayout(left_col)

        # Right: selected columns (ordered)
        right_col = QVBoxLayout()
        right_label = QLabel("Selected Columns")
        right_label.setStyleSheet(f"color: {TEXT}; font-weight: bold; font-size: 12px;")
        right_col.addWidget(right_label)

        hint = QLabel(f"First {CONDENSED_COLUMN_COUNT} columns are shown in condensed view.")
        hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        right_col.addWidget(hint)

        self._selected_list = QListWidget()
        self._selected_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._selected_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._selected_list.model().rowsMoved.connect(self._refresh_badges)
        right_col.addWidget(self._selected_list)

        btn_row = QHBoxLayout()
        remove_btn = QPushButton("\u2190 Remove")
        remove_btn.clicked.connect(self._remove_column)
        btn_row.addWidget(remove_btn, 1)

        up_btn = QPushButton("\u2191 Up")
        up_btn.clicked.connect(self._move_up)
        btn_row.addWidget(up_btn, 1)

        down_btn = QPushButton("\u2193 Down")
        down_btn.clicked.connect(self._move_down)
        btn_row.addWidget(down_btn, 1)

        right_col.addLayout(btn_row)
        panels.addLayout(right_col)

        root.addLayout(panels)

        # OK / Cancel
        buttons = QHBoxLayout()
        buttons.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        ok_btn = QPushButton("Apply")
        ok_btn.setObjectName("accentButton")
        ok_btn.clicked.connect(self.accept)
        buttons.addWidget(ok_btn)

        root.addLayout(buttons)

        # Populate lists
        self._populate()

    def _populate(self):
        """Fill available and selected lists."""
        selected_set = set(self._current_keys)

        # Selected list (in order)
        for key in self._current_keys:
            if key in self._all_defs:
                item = QListWidgetItem(self._all_defs[key]["header"])
                item.setData(Qt.ItemDataRole.UserRole, key)
                self._selected_list.addItem(item)

        # Available list (everything not selected)
        for key, col_def in self._all_defs.items():
            if key not in selected_set:
                item = QListWidgetItem(col_def["header"])
                item.setData(Qt.ItemDataRole.UserRole, key)
                self._available_list.addItem(item)

        self._refresh_badges()

    def _refresh_badges(self):
        """Update display — first N items get a styled 'E' badge."""
        for i in range(self._selected_list.count()):
            item = self._selected_list.item(i)
            key = item.data(Qt.ItemDataRole.UserRole)
            header = self._all_defs.get(key, {}).get("header", key)

            row_widget = QWidget()
            row_widget.setStyleSheet("background: transparent;")
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(4, 0, 4, 0)
            row_layout.setSpacing(6)

            name_label = QLabel(header)
            if i < CONDENSED_COLUMN_COUNT:
                name_label.setStyleSheet(f"color: {ACCENT}; background: transparent;")
            else:
                name_label.setStyleSheet(f"color: {TEXT}; background: transparent;")
            row_layout.addWidget(name_label, 1)

            if i < CONDENSED_COLUMN_COUNT:
                badge = QLabel("E")
                badge.setStyleSheet(
                    f"background-color: {ACCENT}; color: white;"
                    " font-size: 9px; font-weight: 600;"
                    " padding: 1px 4px; border-radius: 3px;"
                )
                badge.setFixedHeight(14)
                row_layout.addWidget(badge)

            self._selected_list.setItemWidget(item, row_widget)

    def _add_column(self):
        """Move selected available column to selected list."""
        current = self._available_list.currentItem()
        if not current:
            return
        row = self._available_list.row(current)
        taken = self._available_list.takeItem(row)
        self._selected_list.addItem(taken)
        self._refresh_badges()

    def _remove_column(self):
        """Move selected column back to available list."""
        current = self._selected_list.currentItem()
        if not current:
            return
        row = self._selected_list.row(current)
        taken = self._selected_list.takeItem(row)
        key = taken.data(Qt.ItemDataRole.UserRole)
        taken.setText(self._all_defs.get(key, {}).get("header", key))
        taken.setForeground(QColor(TEXT))
        self._available_list.addItem(taken)
        self._refresh_badges()

    def _move_up(self):
        """Move selected column up in the order."""
        row = self._selected_list.currentRow()
        if row <= 0:
            return
        item = self._selected_list.takeItem(row)
        self._selected_list.insertItem(row - 1, item)
        self._selected_list.setCurrentRow(row - 1)
        self._refresh_badges()

    def _move_down(self):
        """Move selected column down in the order."""
        row = self._selected_list.currentRow()
        if row < 0 or row >= self._selected_list.count() - 1:
            return
        item = self._selected_list.takeItem(row)
        self._selected_list.insertItem(row + 1, item)
        self._selected_list.setCurrentRow(row + 1)
        self._refresh_badges()

    def selected_keys(self) -> list[str]:
        """Return the ordered list of selected column keys."""
        keys = []
        for i in range(self._selected_list.count()):
            item = self._selected_list.item(i)
            key = item.data(Qt.ItemDataRole.UserRole)
            if key:
                keys.append(key)
        return keys
