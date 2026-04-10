"""Detail views for the hunt dashboard right panel.

Each view is a QWidget constructed with read-only data. Phase 1 does
not expose any editing controls - those are Phase 2 / 3. The factory
``tool_detail_for`` picks the right view class for the tool's category.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QScrollArea, QFrame, QGridLayout,
)

from ...hunt.session import MobEncounter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _aggregate_tool(name: str, encounters: list[MobEncounter]) -> dict:
    shots = 0
    damage = 0.0
    crits = 0
    used_in = 0
    for enc in encounters:
        ts = enc.tool_stats.get(name)
        if ts is None:
            continue
        shots += ts.shots_fired
        damage += ts.damage_dealt
        crits += ts.critical_hits
        used_in += 1
    return {
        "shots": shots,
        "damage": damage,
        "crits": crits,
        "encounters": used_in,
        "avg_damage": damage / shots if shots else 0.0,
        "crit_rate": (crits / shots * 100) if shots else 0.0,
    }


def _stat_row(layout: QGridLayout, row: int, label: str, value: str) -> None:
    title = QLabel(label)
    title.setStyleSheet("color: #b8b8b8;")
    value_label = QLabel(value)
    value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    layout.addWidget(title, row, 0)
    layout.addWidget(value_label, row, 1)


# ---------------------------------------------------------------------------
# Tool detail views
# ---------------------------------------------------------------------------

class _BaseToolDetailView(QWidget):
    def __init__(self, tool_name: str, encounters: list[MobEncounter], parent=None):
        super().__init__(parent)
        self._tool_name = tool_name
        self._encounters = encounters
        self._agg = _aggregate_tool(tool_name, encounters)
        self._build()

    def _build(self) -> None:
        raise NotImplementedError


class WeaponDetailView(_BaseToolDetailView):
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(6)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(3)
        _stat_row(grid, 0, "Shots", f"{self._agg['shots']:,}")
        _stat_row(grid, 1, "Damage", f"{self._agg['damage']:,.0f}")
        _stat_row(grid, 2, "Crits", f"{self._agg['crits']:,}")
        _stat_row(grid, 3, "Avg dmg/shot", f"{self._agg['avg_damage']:.2f}")
        _stat_row(grid, 4, "Crit rate", f"{self._agg['crit_rate']:.1f}%")
        _stat_row(grid, 5, "Encounters used", f"{self._agg['encounters']:,}")
        outer.addLayout(grid)

        note = QLabel("Configuration (enhancers, decay, ammo overrides) coming in Phase 2.")
        note.setStyleSheet("color: #888888; font-style: italic;")
        note.setWordWrap(True)
        outer.addWidget(note)
        outer.addStretch(1)


class HealingDetailView(_BaseToolDetailView):
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(6)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(3)
        # Healing tools reuse the tool_stats shots/damage fields for
        # uses and total healing; the dashboard reads them that way.
        _stat_row(grid, 0, "Uses", f"{self._agg['shots']:,}")
        _stat_row(grid, 1, "Total heal", f"{self._agg['damage']:,.0f}")
        _stat_row(grid, 2, "Avg heal/use", f"{self._agg['avg_damage']:.2f}")
        _stat_row(grid, 3, "Encounters used", f"{self._agg['encounters']:,}")
        outer.addLayout(grid)

        outer.addStretch(1)


class ArmorDetailView(_BaseToolDetailView):
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(6)
        grid = QGridLayout()
        _stat_row(grid, 0, "Encounters worn", f"{self._agg['encounters']:,}")
        outer.addLayout(grid)
        note = QLabel("Armor decay tracking lands in Phase 2.")
        note.setStyleSheet("color: #888888; font-style: italic;")
        note.setWordWrap(True)
        outer.addWidget(note)
        outer.addStretch(1)


class UtilityDetailView(_BaseToolDetailView):
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(6)
        grid = QGridLayout()
        _stat_row(grid, 0, "Uses", f"{self._agg['shots']:,}")
        _stat_row(grid, 1, "Encounters used", f"{self._agg['encounters']:,}")
        outer.addLayout(grid)
        outer.addStretch(1)


def tool_detail_for(tool_name: str, encounters: list[MobEncounter],
                    category: str | None, item_type: str | None) -> QWidget:
    """Pick the right detail view class for the tool's category / type."""
    item_type_l = (item_type or "").lower()
    if "armor" in item_type_l or category == "defense" and "armor" in item_type_l:
        return ArmorDetailView(tool_name, encounters)
    if "medical" in item_type_l or "fap" in item_type_l or "stimulant" in item_type_l:
        return HealingDetailView(tool_name, encounters)
    if category == "offense":
        return WeaponDetailView(tool_name, encounters)
    if category == "defense":
        # Defense category without medical keyword: treat as armor.
        return ArmorDetailView(tool_name, encounters)
    return UtilityDetailView(tool_name, encounters)


# ---------------------------------------------------------------------------
# Encounter detail view
# ---------------------------------------------------------------------------

class EncounterDetailView(QWidget):
    """Stats cards, chronological event log, tool breakdown, loot list."""

    def __init__(self, encounter: MobEncounter, combat_log=None, parent=None):
        super().__init__(parent)
        self._enc = encounter
        self._combat_log = combat_log
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(6)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)

        # Stat grid.
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        _stat_row(grid, 0, "Damage dealt", f"{self._enc.damage_dealt:,.0f}")
        _stat_row(grid, 1, "Damage taken", f"{self._enc.damage_taken:,.0f}")
        _stat_row(grid, 2, "Shots fired", f"{self._enc.shots_fired:,}")
        duration_s = "-"
        if self._enc.start_time and self._enc.end_time:
            duration_s = f"{(self._enc.end_time - self._enc.start_time).total_seconds():.0f}s"
        _stat_row(grid, 3, "Duration", duration_s)
        _stat_row(grid, 4, "Cost", f"{self._enc.cost:.2f} PED")
        _stat_row(grid, 5, "Loot TT", f"{self._enc.loot_total_ped:.2f} PED")
        if self._enc.cost > 0:
            mult = f"{self._enc.loot_total_ped / self._enc.cost:.2f}x"
        else:
            mult = "-"
        _stat_row(grid, 6, "Multiplier", mult)
        content_layout.addLayout(grid)

        # Tool breakdown.
        if self._enc.tool_stats:
            content_layout.addWidget(QLabel("Tools used:"))
            tools_table = QTableWidget()
            tools_table.setColumnCount(3)
            tools_table.setHorizontalHeaderLabels(["Tool", "Shots", "Damage"])
            tools_table.horizontalHeader().setSectionResizeMode(
                0, QHeaderView.ResizeMode.Stretch
            )
            tools_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            tools_table.setRowCount(len(self._enc.tool_stats))
            for i, (name, ts) in enumerate(self._enc.tool_stats.items()):
                tools_table.setItem(i, 0, QTableWidgetItem(name))
                tools_table.setItem(i, 1, QTableWidgetItem(str(ts.shots_fired)))
                tools_table.setItem(i, 2, QTableWidgetItem(f"{ts.damage_dealt:.0f}"))
            tools_table.setMaximumHeight(140)
            content_layout.addWidget(tools_table)

        # Event log (includes pre_encounter phase actions).
        if self._combat_log is not None:
            actions = self._combat_log.get_by_encounter(self._enc.id)
            if actions:
                content_layout.addWidget(QLabel("Event log:"))
                log_table = QTableWidget()
                log_table.setColumnCount(4)
                log_table.setHorizontalHeaderLabels(["Time", "Event", "Amount", "Tool"])
                log_table.horizontalHeader().setSectionResizeMode(
                    1, QHeaderView.ResizeMode.Stretch
                )
                log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
                log_table.setRowCount(len(actions))
                for i, a in enumerate(actions):
                    t_str = a.timestamp.strftime("%H:%M:%S") if a.timestamp else ""
                    prefix = "[pre] " if getattr(a, "phase", "encounter") == "pre_encounter" else ""
                    log_table.setItem(i, 0, QTableWidgetItem(t_str))
                    log_table.setItem(i, 1, QTableWidgetItem(prefix + a.event_type))
                    log_table.setItem(i, 2, QTableWidgetItem(f"{a.amount:.1f}"))
                    log_table.setItem(i, 3, QTableWidgetItem(a.tool_name or ""))
                log_table.setMaximumHeight(260)
                content_layout.addWidget(log_table)

        # Loot items.
        loot_items = list(getattr(self._enc, "loot_items", []) or [])
        if loot_items:
            content_layout.addWidget(QLabel("Loot items:"))
            loot_table = QTableWidget()
            loot_table.setColumnCount(3)
            loot_table.setHorizontalHeaderLabels(["Item", "Qty", "TT"])
            loot_table.horizontalHeader().setSectionResizeMode(
                0, QHeaderView.ResizeMode.Stretch
            )
            loot_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            loot_table.setRowCount(len(loot_items))
            for i, li in enumerate(loot_items):
                loot_table.setItem(i, 0, QTableWidgetItem(li.item_name))
                loot_table.setItem(i, 1, QTableWidgetItem(str(li.quantity)))
                loot_table.setItem(i, 2, QTableWidgetItem(f"{li.value_ped:.2f}"))
            loot_table.setMaximumHeight(160)
            content_layout.addWidget(loot_table)

        content_layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
