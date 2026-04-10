"""Gear override editor dialog.

Opens from the weapon detail panel's Edit button. Lets the user
override decay / ammo use / markup for a single gear item. Writes
through to the gear_overrides table and publishes
EVENT_GEAR_OVERRIDE_CHANGED so the tracker can recompute costs.

Any field left blank clears that override field - the inferred value
from the loadout calculator takes over again.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QDialogButtonBox, QMessageBox, QTextEdit,
)

from ...core.constants import EVENT_GEAR_OVERRIDE_CHANGED
from ...core.logger import get_logger

log = get_logger("GearOverrideDialog")


def _parse_float(text: str) -> float | None:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


class GearOverrideDialog(QDialog):
    def __init__(self, *, tool_name: str, db, event_bus, parent=None):
        super().__init__(parent)
        self._tool_name = tool_name
        self._db = db
        self._event_bus = event_bus
        self.setWindowTitle(f"Overrides - {tool_name}")
        self.setMinimumWidth(360)

        outer = QVBoxLayout(self)
        outer.setSpacing(8)

        header = QLabel(
            f"Overrides for <b>{tool_name}</b>. Leave a field blank to clear "
            "that override and fall back to the loadout calculator."
        )
        header.setWordWrap(True)
        outer.addWidget(header)

        form = QFormLayout()
        self._decay_edit = QLineEdit()
        self._decay_edit.setPlaceholderText("e.g. 10.5 (PEC per use)")
        form.addRow("Decay (PEC / use):", self._decay_edit)

        self._ammo_edit = QLineEdit()
        self._ammo_edit.setPlaceholderText("e.g. 5.2 (PEC per shot)")
        form.addRow("Ammo (PEC / shot):", self._ammo_edit)

        markup_row = QHBoxLayout()
        self._markup_edit = QLineEdit()
        self._markup_edit.setPlaceholderText("e.g. 120")
        markup_row.addWidget(self._markup_edit, 1)
        self._markup_type_combo = QComboBox()
        self._markup_type_combo.addItems(["percentage", "absolute"])
        markup_row.addWidget(self._markup_type_combo)
        form.addRow("Custom markup:", markup_row)

        self._note_edit = QTextEdit()
        self._note_edit.setMaximumHeight(60)
        self._note_edit.setPlaceholderText("Optional note")
        form.addRow("Note:", self._note_edit)

        outer.addLayout(form)

        # Load existing override (if any) into the form.
        self._load_existing()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self._clear_btn = QPushButton("Clear Override")
        buttons.addButton(self._clear_btn, QDialogButtonBox.ButtonRole.DestructiveRole)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        self._clear_btn.clicked.connect(self._on_clear)
        outer.addWidget(buttons)

    def _load_existing(self) -> None:
        try:
            row = self._db.get_gear_override(self._tool_name)
        except Exception as e:
            log.warning("Failed to load gear override for %s: %s", self._tool_name, e)
            return
        if not row:
            return
        if row.get("decay_pec_per_use") is not None:
            self._decay_edit.setText(str(row["decay_pec_per_use"]))
        if row.get("ammo_use_per_shot") is not None:
            self._ammo_edit.setText(str(row["ammo_use_per_shot"]))
        if row.get("custom_markup") is not None:
            self._markup_edit.setText(str(row["custom_markup"]))
        if row.get("custom_markup_type"):
            idx = self._markup_type_combo.findText(row["custom_markup_type"])
            if idx >= 0:
                self._markup_type_combo.setCurrentIndex(idx)
        if row.get("note"):
            self._note_edit.setPlainText(row["note"])

    def _on_save(self) -> None:
        decay = _parse_float(self._decay_edit.text())
        ammo = _parse_float(self._ammo_edit.text())
        markup = _parse_float(self._markup_edit.text())
        markup_type = self._markup_type_combo.currentText() if markup is not None else None
        note = self._note_edit.toPlainText().strip() or None

        # If every field is empty, treat this as a clear.
        if decay is None and ammo is None and markup is None and not note:
            self._on_clear()
            return

        try:
            self._db.set_gear_override(
                self._tool_name,
                decay_pec_per_use=decay,
                ammo_use_per_shot=ammo,
                custom_markup=markup,
                custom_markup_type=markup_type,
                note=note,
            )
        except Exception as e:
            log.error("Failed to save gear override: %s", e)
            QMessageBox.critical(self, "Save failed", str(e))
            return
        self._event_bus.publish(EVENT_GEAR_OVERRIDE_CHANGED, {"item_name": self._tool_name})
        self.accept()

    def _on_clear(self) -> None:
        try:
            self._db.delete_gear_override(self._tool_name)
        except Exception as e:
            log.error("Failed to clear gear override: %s", e)
            QMessageBox.critical(self, "Clear failed", str(e))
            return
        self._event_bus.publish(EVENT_GEAR_OVERRIDE_CHANGED, {"item_name": self._tool_name})
        self.accept()
