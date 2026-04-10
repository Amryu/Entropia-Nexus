"""Session-scoped (L) markup override dialog.

Overrides apply only to the current hunt session and live on the
hunt_sessions.session_item_markups JSON blob. MarkupResolver consults
them when called with a session_id parameter.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QComboBox, QDialogButtonBox, QMessageBox,
)

from ...core.constants import EVENT_SESSION_MARKUP_CHANGED
from ...core.logger import get_logger

log = get_logger("SessionMarkupDialog")


class SessionMarkupDialog(QDialog):
    def __init__(self, *, item_name: str, session_id: str, db, event_bus,
                 parent=None):
        super().__init__(parent)
        self._item_name = item_name
        self._session_id = session_id
        self._db = db
        self._event_bus = event_bus
        self.setWindowTitle(f"Session markup - {item_name}")
        self.setMinimumWidth(360)

        outer = QVBoxLayout(self)
        outer.setSpacing(8)

        header = QLabel(
            f"Set markup for <b>{item_name}</b> within this session only. "
            "Leave the value blank to clear and use the global markup chain."
        )
        header.setWordWrap(True)
        outer.addWidget(header)

        form = QFormLayout()
        row = QHBoxLayout()
        self._value_edit = QLineEdit()
        self._value_edit.setPlaceholderText("e.g. 120 or 5.5")
        row.addWidget(self._value_edit, 1)
        self._type_combo = QComboBox()
        self._type_combo.addItems(["percentage", "absolute"])
        row.addWidget(self._type_combo)
        form.addRow("Markup:", row)
        outer.addLayout(form)

        self._load_existing()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _load_existing(self) -> None:
        try:
            blob = self._db.get_session_item_markups(self._session_id)
        except Exception:
            blob = {}
        entry = blob.get(self._item_name.lower())
        if not isinstance(entry, dict):
            return
        if "value" in entry:
            self._value_edit.setText(str(entry["value"]))
        if "type" in entry:
            idx = self._type_combo.findText(entry["type"])
            if idx >= 0:
                self._type_combo.setCurrentIndex(idx)

    def _on_save(self) -> None:
        text = self._value_edit.text().strip()
        if not text:
            value = None
        else:
            try:
                value = float(text)
            except ValueError:
                QMessageBox.warning(self, "Invalid value", "Enter a numeric markup.")
                return
        try:
            self._db.set_session_item_markup(
                self._session_id, self._item_name, value,
                self._type_combo.currentText(),
            )
        except Exception as e:
            log.error("Failed to save session markup: %s", e)
            QMessageBox.critical(self, "Save failed", str(e))
            return
        self._event_bus.publish(EVENT_SESSION_MARKUP_CHANGED, {
            "session_id": self._session_id,
            "item_name": self._item_name,
        })
        self.accept()
