"""Loot editor dialog for retroactive edits.

Edits an encounter's loot_total_ped and the row-level loot items.
Writes through update_mob_encounter + replace_encounter_loot_items and
asks the tracker to recalculate the session so totals and stats pick
up the edit. Past-session edits prompt for confirmation since the
dashboard's default scope is the current session.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QDoubleSpinBox, QSpinBox, QTableWidget, QTableWidgetItem, QPushButton,
    QDialogButtonBox, QMessageBox, QHeaderView,
)

from ...core.constants import EVENT_HUNT_SESSION_UPDATED
from ...core.logger import get_logger
from ...hunt.session import EncounterLootItem

log = get_logger("LootEditorDialog")


@dataclass
class _LootRow:
    item_name: str
    quantity: int
    value_ped: float


class LootEditorDialog(QDialog):
    def __init__(self, *, encounter, hunt_tracker, db, event_bus,
                 is_past_session: bool = False, parent=None):
        super().__init__(parent)
        self._encounter = encounter
        self._tracker = hunt_tracker
        self._db = db
        self._event_bus = event_bus
        self._is_past_session = is_past_session
        self.setWindowTitle(f"Edit loot - {encounter.mob_name or 'Unknown'}")
        self.setMinimumSize(520, 440)

        outer = QVBoxLayout(self)
        outer.setSpacing(8)

        if is_past_session:
            warn = QLabel(
                "<b>Warning:</b> editing a past session. Changes persist "
                "and trigger a full recalculation."
            )
            warn.setStyleSheet("color: #d49b3a;")
            warn.setWordWrap(True)
            outer.addWidget(warn)

        form = QFormLayout()
        self._total_spin = QDoubleSpinBox()
        self._total_spin.setRange(0.0, 1_000_000.0)
        self._total_spin.setDecimals(2)
        self._total_spin.setValue(encounter.loot_total_ped or 0.0)
        form.addRow("Loot total (PED):", self._total_spin)
        outer.addLayout(form)

        outer.addWidget(QLabel("Loot items (leave empty for shrapnel-only)"))
        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Item", "Qty", "Value (PED)"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        outer.addWidget(self._table, 1)

        row_controls = QHBoxLayout()
        add_btn = QPushButton("+ Add row")
        add_btn.clicked.connect(self._add_row)
        del_btn = QPushButton("- Remove row")
        del_btn.clicked.connect(self._remove_row)
        row_controls.addWidget(add_btn)
        row_controls.addWidget(del_btn)
        row_controls.addStretch(1)
        outer.addLayout(row_controls)

        self._load_existing_rows()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _load_existing_rows(self) -> None:
        items = list(getattr(self._encounter, "loot_items", []) or [])
        if not items:
            # Pull fresh from DB since the in-memory list is stripped
            # after persist (see tracker._persist_encounter).
            try:
                rows = self._db.get_encounter_loot_items(self._encounter.id)
            except Exception:
                rows = []
            items = rows
        self._table.setRowCount(len(items))
        for i, li in enumerate(items):
            name = li.get("item_name") if isinstance(li, dict) else li.item_name
            qty = li.get("quantity") if isinstance(li, dict) else li.quantity
            val = li.get("value_ped") if isinstance(li, dict) else li.value_ped
            self._table.setItem(i, 0, QTableWidgetItem(name or ""))
            self._table.setItem(i, 1, QTableWidgetItem(str(qty or 0)))
            self._table.setItem(i, 2, QTableWidgetItem(f"{val or 0:.2f}"))

    def _add_row(self) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(""))
        self._table.setItem(row, 1, QTableWidgetItem("1"))
        self._table.setItem(row, 2, QTableWidgetItem("0.00"))

    def _remove_row(self) -> None:
        row = self._table.currentRow()
        if row >= 0:
            self._table.removeRow(row)

    def _collect_rows(self) -> list[EncounterLootItem]:
        rows: list[EncounterLootItem] = []
        for i in range(self._table.rowCount()):
            name_item = self._table.item(i, 0)
            qty_item = self._table.item(i, 1)
            val_item = self._table.item(i, 2)
            name = (name_item.text() if name_item else "").strip()
            if not name:
                continue
            try:
                qty = int(qty_item.text()) if qty_item else 0
            except ValueError:
                qty = 0
            try:
                value = float(val_item.text()) if val_item else 0.0
            except ValueError:
                value = 0.0
            rows.append(EncounterLootItem(
                item_name=name,
                quantity=qty,
                value_ped=value,
            ))
        return rows

    def _on_save(self) -> None:
        new_rows = self._collect_rows()
        new_total = float(self._total_spin.value())

        if self._is_past_session:
            confirm = QMessageBox.question(
                self, "Edit past session",
                "This edits a past session. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        try:
            self._db.update_mob_encounter(
                self._encounter.id,
                loot_total_ped=new_total,
            )
            self._db.replace_encounter_loot_items(self._encounter.id, new_rows)
        except Exception as e:
            log.error("Failed to save loot edit: %s", e)
            QMessageBox.critical(self, "Save failed", str(e))
            return

        # Sync in-memory state so the dashboard refresh picks it up
        # without waiting for recalculate_session to re-read rows.
        self._encounter.loot_total_ped = new_total
        self._encounter.loot_items = new_rows

        if self._tracker is not None:
            try:
                self._tracker.recalculate_session()
            except Exception as e:
                log.warning("recalculate_session after loot edit failed: %s", e)
            try:
                self._event_bus.publish(
                    EVENT_HUNT_SESSION_UPDATED,
                    self._tracker._build_summary(),
                )
            except Exception:
                pass

        self.accept()
