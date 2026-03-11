"""WidgetPickerDialog — let the user choose a widget class to add to the grid."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QLineEdit, QFrame, QFileDialog,
    QMessageBox,
)
from PyQt6.QtCore import Qt

if TYPE_CHECKING:
    from .widget_registry import WidgetRegistry
    from .grid_widget import GridWidget

_STYLE = """
    QDialog { background: #1a1a2e; }
    QLabel { color: #e0e0e0; }
    QListWidget {
        background: #1e1e30; color: #e0e0e0;
        border: 1px solid #444; border-radius: 4px;
        font-size: 11px;
    }
    QListWidget::item { padding: 4px 8px; }
    QListWidget::item:selected { background: #333355; }
    QListWidget::item:hover { background: #2a2a45; }
    QLineEdit {
        background: #252535; color: #e0e0e0;
        border: 1px solid #555; border-radius: 4px;
        padding: 4px 8px; font-size: 11px;
    }
    QPushButton {
        background: #333350; color: #e0e0e0;
        border: 1px solid #555; border-radius: 4px;
        padding: 4px 12px; font-size: 11px;
    }
    QPushButton:hover { background: #404060; }
    QPushButton:disabled { color: #666; background: #2a2a3a; }
"""


class WidgetPickerDialog(QDialog):
    """Presents all registered widgets; user selects one to add to the grid."""

    def __init__(self, registry: 'WidgetRegistry', parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Widget")
        self.setMinimumSize(440, 380)
        self.setStyleSheet(_STYLE)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
        )

        self._registry = registry
        self._selected_class: type[GridWidget] | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Choose a widget to add:")
        title.setStyleSheet("font-size: 12px; font-weight: bold; color: #c0d8ff;")
        layout.addWidget(title)

        # Search bar
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search widgets…")
        self._search.textChanged.connect(self._filter)
        layout.addWidget(self._search)

        # Widget list
        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_selection_changed)
        self._list.itemDoubleClicked.connect(self._accept_selected)
        layout.addWidget(self._list)

        # Description area
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #444;")
        layout.addWidget(sep)

        self._desc = QLabel("")
        self._desc.setWordWrap(True)
        self._desc.setStyleSheet("color: #aaa; font-size: 10px; min-height: 28px;")
        layout.addWidget(self._desc)

        # Load errors warning
        errors = registry.get_load_errors()
        if errors:
            warn = QLabel(f"⚠ {len(errors)} widget file(s) failed to load")
            warn.setStyleSheet("color: #ffaa66; font-size: 10px;")
            warn.setToolTip("\n".join(f"{k}: {v}" for k, v in errors.items()))
            layout.addWidget(warn)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        import_btn = QPushButton("Import .py…")
        import_btn.setToolTip("Load a custom widget file")
        import_btn.clicked.connect(self._import_user_widget)
        btn_row.addWidget(import_btn)

        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self._add_btn = QPushButton("Add Widget")
        self._add_btn.setEnabled(False)
        self._add_btn.setStyleSheet(
            "QPushButton { background: #305090; }"
            "QPushButton:hover { background: #4060b0; }"
            "QPushButton:disabled { background: #2a2a3a; color: #666; }"
        )
        self._add_btn.clicked.connect(self._accept_selected)
        btn_row.addWidget(self._add_btn)

        layout.addLayout(btn_row)

        self._populate()

    def _populate(self, filter_text: str = "") -> None:
        self._list.clear()
        ft = filter_text.lower()
        for cls in self._registry.get_all():
            if ft and ft not in cls.DISPLAY_NAME.lower() and ft not in cls.DESCRIPTION.lower():
                continue
            item = QListWidgetItem(cls.DISPLAY_NAME)
            item.setData(Qt.ItemDataRole.UserRole, cls)
            self._list.addItem(item)

    def _filter(self, text: str) -> None:
        self._populate(text)

    def _on_selection_changed(self, current, _prev) -> None:
        if current is None:
            self._selected_class = None
            self._desc.setText("")
            self._add_btn.setEnabled(False)
        else:
            cls = current.data(Qt.ItemDataRole.UserRole)
            self._selected_class = cls
            self._desc.setText(cls.DESCRIPTION or "No description.")
            self._add_btn.setEnabled(True)

    def _accept_selected(self, *_) -> None:
        if self._selected_class is not None:
            self.accept()

    def _import_user_widget(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Widget File", "", "Python Files (*.py)"
        )
        if not path:
            return
        from pathlib import Path
        found = self._registry.load_user_file(Path(path))
        if found:
            self._populate(self._search.text())
        else:
            QMessageBox.warning(
                self, "Import Failed",
                f"No valid GridWidget subclasses found in {Path(path).name}.\n\n"
                "Make sure the file contains a class that inherits from GridWidget "
                "with a unique WIDGET_ID.",
            )

    def selected_class(self) -> type[GridWidget] | None:
        return self._selected_class
