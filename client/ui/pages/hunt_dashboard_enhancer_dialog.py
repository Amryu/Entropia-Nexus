"""Enhancer timeline editor dialog.

Lets the user record an enhancer change at a chosen anchor (session
start, current-hunt start, or a specific encounter). The event is
stored as an anchored row in session_loadout_events; the tracker then
triggers a replay so dependent panels refresh.

Phase 3 scope covers the current session only. Editing anchored
events in past sessions is reachable from the history view via the
same dialog but requires confirmation.
"""

from __future__ import annotations

import json
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QDialogButtonBox, QMessageBox, QTreeWidget, QTreeWidgetItem,
    QFormLayout, QSpinBox,
)

from ...core.logger import get_logger

log = get_logger("EnhancerTimelineDialog")

ANCHOR_SESSION_START = "session_start"
ANCHOR_HUNT_START = "hunt_start"
ANCHOR_ENCOUNTER = "encounter"

ENHANCER_SLOTS = ("Damage", "Economy", "Accuracy", "Range", "SkillMod",
                  "Heal", "Defense", "Durability")


class EnhancerTimelineDialog(QDialog):
    def __init__(self, *, session, hunt_tracker, db, event_bus, parent=None):
        super().__init__(parent)
        self._session = session
        self._tracker = hunt_tracker
        self._db = db
        self._event_bus = event_bus
        self.setWindowTitle("Enhancer timeline")
        self.setMinimumSize(520, 480)

        outer = QVBoxLayout(self)
        outer.setSpacing(8)

        intro = QLabel(
            "Record an enhancer change at a chosen anchor. Existing anchored "
            "events appear below; new events scope to the current session."
        )
        intro.setWordWrap(True)
        outer.addWidget(intro)

        # Anchor picker
        anchor_row = QHBoxLayout()
        anchor_row.addWidget(QLabel("Anchor:"))
        self._anchor_combo = QComboBox()
        self._anchor_combo.addItem("Session start", ANCHOR_SESSION_START)
        self._anchor_combo.addItem("Current hunt start", ANCHOR_HUNT_START)
        self._anchor_combo.addItem("Specific encounter", ANCHOR_ENCOUNTER)
        self._anchor_combo.currentIndexChanged.connect(self._on_anchor_changed)
        anchor_row.addWidget(self._anchor_combo, 1)
        outer.addLayout(anchor_row)

        # Encounter picker tree (shown when anchor = encounter)
        self._encounter_tree = QTreeWidget()
        self._encounter_tree.setHeaderLabels(["Encounter", "Start", "Cost"])
        self._encounter_tree.setVisible(False)
        self._encounter_tree.setMaximumHeight(180)
        outer.addWidget(self._encounter_tree)
        self._populate_encounter_tree()

        # Enhancer delta form
        form = QFormLayout()
        self._slot_combo = QComboBox()
        for slot in ENHANCER_SLOTS:
            self._slot_combo.addItem(slot)
        form.addRow("Slot:", self._slot_combo)

        self._count_spin = QSpinBox()
        self._count_spin.setRange(0, 10)
        self._count_spin.setValue(1)
        form.addRow("Count:", self._count_spin)

        self._note_edit = QLineEdit()
        self._note_edit.setPlaceholderText("Optional note")
        form.addRow("Note:", self._note_edit)
        outer.addLayout(form)

        outer.addWidget(QLabel("Existing anchored events:"))
        self._events_tree = QTreeWidget()
        self._events_tree.setHeaderLabels(["Anchor", "Slot/Delta", "Note"])
        self._events_tree.setMaximumHeight(140)
        outer.addWidget(self._events_tree)
        self._populate_events_tree()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Close
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _on_anchor_changed(self, idx: int) -> None:
        kind = self._anchor_combo.itemData(idx)
        self._encounter_tree.setVisible(kind == ANCHOR_ENCOUNTER)

    def _populate_encounter_tree(self) -> None:
        if not self._session:
            return
        for enc in self._session.encounters:
            ts = enc.start_time.strftime("%H:%M:%S") if enc.start_time else "-"
            cost = f"{enc.cost:.2f}"
            row = QTreeWidgetItem([enc.mob_name or "?", ts, cost])
            row.setData(0, Qt.ItemDataRole.UserRole, enc.id)
            self._encounter_tree.addTopLevelItem(row)

    def _populate_events_tree(self) -> None:
        if not self._session:
            return
        try:
            events = self._db.get_anchored_loadout_events(self._session.id)
        except Exception as e:
            log.warning("Failed to load anchored events: %s", e)
            return
        for e in events:
            kind = e.get("anchor_kind") or ""
            anchor_id = e.get("anchor_encounter_id")
            if anchor_id:
                kind = f"{kind} ({anchor_id[:8]})"
            delta_text = e.get("enhancer_delta") or ""
            try:
                delta_parsed = json.loads(delta_text) if delta_text else {}
                delta_text = ", ".join(f"{k}:{v}" for k, v in delta_parsed.items())
            except (ValueError, TypeError):
                pass
            row = QTreeWidgetItem([kind, delta_text, e.get("description") or ""])
            self._events_tree.addTopLevelItem(row)

    def _on_save(self) -> None:
        if self._tracker is None or self._session is None:
            QMessageBox.warning(self, "No session", "No active session to record against.")
            return

        kind = self._anchor_combo.currentData()
        anchor_encounter_id = None
        if kind == ANCHOR_ENCOUNTER:
            current = self._encounter_tree.currentItem()
            if current is None:
                QMessageBox.warning(self, "Pick encounter",
                                     "Select an encounter to anchor to.")
                return
            anchor_encounter_id = current.data(0, Qt.ItemDataRole.UserRole)

        slot = self._slot_combo.currentText()
        count = self._count_spin.value()
        delta = {slot: count}

        try:
            self._db.insert_anchored_loadout_event(
                self._session.id,
                timestamp=datetime.utcnow().isoformat(),
                event_type="enhancer_adjust",
                anchor_kind=kind,
                anchor_encounter_id=anchor_encounter_id,
                description=self._note_edit.text().strip() or None,
                enhancer_delta=json.dumps(delta),
            )
        except Exception as e:
            log.error("Failed to insert anchored loadout event: %s", e)
            QMessageBox.critical(self, "Save failed", str(e))
            return

        try:
            self._tracker.replay_enhancer_timeline(
                from_encounter_id=anchor_encounter_id,
            )
        except Exception as e:
            log.warning("replay_enhancer_timeline failed: %s", e)

        self.accept()
