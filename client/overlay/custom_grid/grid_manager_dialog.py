"""GridManagerDialog — create, rename, open/close, and delete named custom grids."""

from __future__ import annotations

import uuid
from typing import Callable

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QLineEdit, QComboBox, QMessageBox,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal

_DIALOG_STYLE = """
    QDialog       { background: #1a1a2e; }
    QScrollArea   { background: transparent; border: none; }
    QWidget#rowWidget { background: #1e1e30; border-radius: 4px; }
    QLabel        { color: #cccccc; font-size: 12px; background: transparent; }
    QLineEdit     { background: #252535; color: #e0e0e0; border: 1px solid #555;
                    border-radius: 4px; padding: 3px 6px; font-size: 12px; }
    QPushButton   { background: #333350; color: #e0e0e0; border: 1px solid #555;
                    border-radius: 4px; padding: 4px 10px; font-size: 12px; }
    QPushButton:hover   { background: #404060; }
    QPushButton:pressed { background: #252540; }
    QComboBox     { background: #252535; color: #e0e0e0; border: 1px solid #555;
                    border-radius: 4px; padding: 3px 6px; font-size: 12px; }
    QComboBox QAbstractItemView { background: #252535; color: #e0e0e0; }
"""

_PRESETS = {
    "Empty": [],
    "Hunting Tracker": [
        {"id": "com.entropianexus.hunt_stats",   "col": 0, "row": 0, "colspan": 5, "rowspan": 5, "config": {}},
        {"id": "com.entropianexus.mob_info",      "col": 5, "row": 0, "colspan": 4, "rowspan": 3, "config": {}},
        {"id": "com.entropianexus.loot_list",     "col": 0, "row": 5, "colspan": 5, "rowspan": 5, "config": {}},
        {"id": "com.entropianexus.timer",         "col": 5, "row": 3, "colspan": 4, "rowspan": 3, "config": {}},
    ],
    "Mining Tracker": [
        {"id": "com.entropianexus.stat_label",    "col": 0, "row": 0, "colspan": 3, "rowspan": 2, "config": {}},
        {"id": "com.entropianexus.timer",         "col": 3, "row": 0, "colspan": 4, "rowspan": 3, "config": {}},
        {"id": "com.entropianexus.loot_list",     "col": 0, "row": 2, "colspan": 5, "rowspan": 5, "config": {}},
    ],
    "Live Market": [
        {"id": "com.entropianexus.exchange_price", "col": 0, "row": 0, "colspan": 4, "rowspan": 3, "config": {}},
        {"id": "com.entropianexus.exchange_price", "col": 4, "row": 0, "colspan": 4, "rowspan": 3, "config": {}},
        {"id": "com.entropianexus.exchange_price", "col": 0, "row": 3, "colspan": 4, "rowspan": 3, "config": {}},
        {"id": "com.entropianexus.exchange_price", "col": 4, "row": 3, "colspan": 4, "rowspan": 3, "config": {}},
    ],
    "Skill Progress": [
        {"id": "com.entropianexus.skill_gain",    "col": 0, "row": 0, "colspan": 5, "rowspan": 5, "config": {}},
        {"id": "com.entropianexus.label",         "col": 5, "row": 0, "colspan": 3, "rowspan": 2, "config": {"text": "Skill Goals"}},
    ],
}


class _NewGridDialog(QDialog):
    """Small dialog to create a new named grid with optional preset."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Custom Grid")
        self.setMinimumWidth(320)
        self.setStyleSheet(_DIALOG_STYLE)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        form = QHBoxLayout()
        form.addWidget(QLabel("Name:"))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Hunting Tracker")
        form.addWidget(self._name_edit)
        layout.addLayout(form)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        self._preset_combo = QComboBox()
        self._preset_combo.addItems(list(_PRESETS.keys()))
        preset_row.addWidget(self._preset_combo)
        layout.addLayout(preset_row)

        btns = QHBoxLayout()
        btns.addStretch()
        ok_btn = QPushButton("Create")
        ok_btn.setStyleSheet(
            "QPushButton { background: #305090; border-color: #4070b0; }"
            "QPushButton:hover { background: #3a60a8; }"
        )
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)
        btns.addWidget(ok_btn)
        layout.addLayout(btns)

    def _on_ok(self):
        if not self._name_edit.text().strip():
            self._name_edit.setStyleSheet(
                "background: #252535; color: #e0e0e0; border: 1px solid #aa4444;"
                "border-radius: 4px; padding: 3px 6px; font-size: 12px;"
            )
            return
        self.accept()

    def result_data(self) -> tuple[str, str]:
        """Return (name, preset_key)."""
        return self._name_edit.text().strip(), self._preset_combo.currentText()


class _GridRow(QWidget):
    """One row in the manager list: name | open/close | rename | delete."""

    open_clicked = pyqtSignal(str)     # grid_id
    close_clicked = pyqtSignal(str)
    delete_clicked = pyqtSignal(str)
    rename_committed = pyqtSignal(str, str)  # grid_id, new_name

    def __init__(self, grid_id: str, name: str, is_open: bool, parent=None):
        super().__init__(parent)
        self._grid_id = grid_id
        self.setObjectName("rowWidget")
        self.setFixedHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # Name (inline editable)
        self._name_label = QLabel(name)
        self._name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._name_edit = QLineEdit(name)
        self._name_edit.hide()
        self._name_edit.editingFinished.connect(self._commit_rename)
        layout.addWidget(self._name_label)
        layout.addWidget(self._name_edit)

        # Open/Close toggle
        self._toggle_btn = QPushButton()
        self._toggle_btn.setFixedSize(60, 24)
        self._toggle_btn.clicked.connect(self._on_toggle)
        layout.addWidget(self._toggle_btn)

        # Rename button
        rename_btn = QPushButton("✏")
        rename_btn.setFixedSize(26, 24)
        rename_btn.setToolTip("Rename")
        rename_btn.clicked.connect(self._start_rename)
        layout.addWidget(rename_btn)

        # Delete button
        delete_btn = QPushButton("🗑")
        delete_btn.setFixedSize(26, 24)
        delete_btn.setToolTip("Delete")
        delete_btn.clicked.connect(self._on_delete)
        layout.addWidget(delete_btn)

        self.set_open(is_open)

    def set_open(self, is_open: bool) -> None:
        self._is_open = is_open
        if is_open:
            self._toggle_btn.setText("Close")
            self._toggle_btn.setStyleSheet(
                "QPushButton { background: #3a3a60; border: 1px solid #6060a0; }"
                "QPushButton:hover { background: #4a4a70; }"
            )
        else:
            self._toggle_btn.setText("Open")
            self._toggle_btn.setStyleSheet(
                "QPushButton { background: #305090; border-color: #4070b0; }"
                "QPushButton:hover { background: #3a60a8; }"
            )

    def _on_toggle(self):
        if self._is_open:
            self.close_clicked.emit(self._grid_id)
        else:
            self.open_clicked.emit(self._grid_id)

    def _on_delete(self):
        reply = QMessageBox.question(
            self, "Delete Grid",
            f"Delete \"{self._name_label.text()}\"? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.delete_clicked.emit(self._grid_id)

    def _start_rename(self):
        self._name_label.hide()
        self._name_edit.setText(self._name_label.text())
        self._name_edit.show()
        self._name_edit.setFocus()
        self._name_edit.selectAll()

    def _commit_rename(self):
        new_name = self._name_edit.text().strip()
        if new_name:
            self._name_label.setText(new_name)
            self.rename_committed.emit(self._grid_id, new_name)
        self._name_edit.hide()
        self._name_label.show()


class CustomGridManagerDialog(QDialog):
    """Modeless dialog for managing multiple named custom grid overlays."""

    open_grid   = pyqtSignal(str)       # grid_id
    close_grid  = pyqtSignal(str)
    grid_deleted = pyqtSignal(str)
    grid_renamed = pyqtSignal(str, str)  # grid_id, new_name

    def __init__(self, config, save_fn: Callable, parent=None):
        super().__init__(parent)
        self._config = config
        self._save_fn = save_fn  # callable() → saves config
        self._is_open_fn: Callable[[str], bool] = lambda _: False
        self.setWindowTitle("Custom Grids")
        self.setMinimumWidth(380)
        self.setStyleSheet(_DIALOG_STYLE)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowCloseButtonHint
        )

        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        # Header row
        header = QHBoxLayout()
        title_lbl = QLabel("Custom Grids")
        title_lbl.setStyleSheet("color: #00ccff; font-size: 14px; font-weight: bold;")
        header.addWidget(title_lbl)
        header.addStretch()
        new_btn = QPushButton("+ New Grid")
        new_btn.setStyleSheet(
            "QPushButton { background: #305090; border-color: #4070b0; padding: 4px 12px; }"
            "QPushButton:hover { background: #3a60a8; }"
        )
        new_btn.clicked.connect(self._on_new_grid)
        header.addWidget(new_btn)
        root.addLayout(header)

        # Scrollable grid list
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setSpacing(4)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.addStretch()
        self._scroll_area.setWidget(self._list_container)
        root.addWidget(self._scroll_area)

        # Empty state label
        self._empty_label = QLabel("No grids yet. Click \"+ New Grid\" to create one.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: #666688; font-size: 12px; padding: 20px;")
        root.addWidget(self._empty_label)

    def _refresh_rows(self) -> None:
        """Rebuild the list of grid rows from config.custom_grids."""
        # Remove all existing row widgets (not the stretch)
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        grids = self._config.custom_grids or []
        self._empty_label.setVisible(len(grids) == 0)
        self._scroll_area.setVisible(len(grids) > 0)

        for g in grids:
            grid_id = g.get("id", "")
            name = g.get("name", "Custom Grid")
            is_open = self._is_open_fn(grid_id)
            row = _GridRow(grid_id, name, is_open)
            row.open_clicked.connect(self.open_grid)
            row.close_clicked.connect(self.close_grid)
            row.delete_clicked.connect(self.grid_deleted)
            row.rename_committed.connect(self.grid_renamed)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)

    def _on_new_grid(self) -> None:
        dlg = _NewGridDialog(self)
        if not dlg.exec():
            return
        name, preset_key = dlg.result_data()
        grid_id = str(uuid.uuid4())
        preset_widgets = list(_PRESETS.get(preset_key, []))
        entry = {
            "id": grid_id,
            "name": name,
            "position": [220, 220],
            "cols": 12,
            "rows": 12,
            "tile_size": 0,
            "widgets": preset_widgets,
        }
        self._config.custom_grids.append(entry)
        try:
            self._save_fn()
        except Exception:
            pass
        self._refresh_rows()
        self.open_grid.emit(grid_id)
