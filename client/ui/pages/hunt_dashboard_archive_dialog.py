"""Archive view: read-only browser for past hunt sessions.

Phase 3 ships a minimal session picker that lists recent sessions and
shows their summary + kill log in a read-only panel. Full dashboard
parity for archived sessions (cards, detail panel, etc.) is deferred
to Phase 4 when the dashboard view can be instantiated with a
non-tracker data source.
"""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSplitter, QTreeWidget,
    QTreeWidgetItem, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QDialogButtonBox,
)

from ...core.logger import get_logger

log = get_logger("ArchiveDialog")


def _fmt_datetime(iso: str | None) -> str:
    if not iso:
        return "-"
    try:
        return datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso


class ArchiveDialog(QDialog):
    def __init__(self, *, db, parent=None):
        super().__init__(parent)
        self._db = db
        self.setWindowTitle("Hunt session archive")
        self.setMinimumSize(760, 480)

        outer = QVBoxLayout(self)
        outer.setSpacing(8)

        intro = QLabel(
            "Read-only archive of past hunt sessions. Select a row to view "
            "its kills. Editing is not available in Phase 3."
        )
        intro.setWordWrap(True)
        outer.addWidget(intro)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(splitter, 1)

        # Left: sessions list.
        self._sessions_tree = QTreeWidget()
        self._sessions_tree.setHeaderLabels([
            "Start", "Mob", "Kills", "Cost", "Loot"
        ])
        self._sessions_tree.itemSelectionChanged.connect(self._on_session_selected)
        splitter.addWidget(self._sessions_tree)

        # Right: kill log for selected session.
        self._kills_table = QTableWidget()
        self._kills_table.setColumnCount(5)
        self._kills_table.setHorizontalHeaderLabels([
            "Time", "Mob", "Cost", "Multiplier", "Loot TT"
        ])
        self._kills_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._kills_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        splitter.addWidget(self._kills_table)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        outer.addWidget(buttons)

        self._populate_sessions()

    def _populate_sessions(self) -> None:
        try:
            rows = self._db.list_hunt_sessions(limit=100)
        except Exception as e:
            log.warning("Failed to list hunt sessions: %s", e)
            rows = []
        for row in rows:
            tree_row = QTreeWidgetItem([
                _fmt_datetime(row.get("start_time")),
                row.get("primary_mob") or "-",
                str(row.get("kill_count") or 0),
                f"{row.get('cost_total') or 0:.2f}",
                f"{row.get('loot_total') or 0:.2f}",
            ])
            tree_row.setData(0, Qt.ItemDataRole.UserRole, row.get("id"))
            self._sessions_tree.addTopLevelItem(tree_row)

    def _on_session_selected(self) -> None:
        items = self._sessions_tree.selectedItems()
        if not items:
            self._kills_table.setRowCount(0)
            return
        session_id = items[0].data(0, Qt.ItemDataRole.UserRole)
        if not session_id:
            return
        try:
            encounters = self._db.get_session_encounters(session_id)
        except Exception as e:
            log.warning("Failed to load encounters: %s", e)
            encounters = []
        self._kills_table.setRowCount(len(encounters))
        for i, enc in enumerate(encounters):
            self._kills_table.setItem(
                i, 0, QTableWidgetItem(_fmt_datetime(enc.get("end_time") or enc.get("start_time")))
            )
            self._kills_table.setItem(
                i, 1, QTableWidgetItem(enc.get("mob_name") or "Unknown")
            )
            cost = enc.get("cost") or 0
            loot = enc.get("loot_total_ped") or 0
            self._kills_table.setItem(i, 2, QTableWidgetItem(f"{cost:.2f}"))
            mult = f"{(loot / cost):.2f}x" if cost else "-"
            self._kills_table.setItem(i, 3, QTableWidgetItem(mult))
            self._kills_table.setItem(i, 4, QTableWidgetItem(f"{loot:.2f}"))
