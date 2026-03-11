"""Hunt Stats widget — live stats for the current hunt encounter or session."""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt

from ..grid_widget import GridWidget, WidgetContext
from ....core.constants import (
    EVENT_COMBAT,
    EVENT_LOOT_GROUP,
    EVENT_HUNT_SESSION_STARTED,
    EVENT_HUNT_SESSION_STOPPED,
    EVENT_HUNT_ENCOUNTER_STARTED,
    EVENT_HUNT_ENCOUNTER_ENDED,
    EVENT_HUNT_SESSION_UPDATED,
    EVENT_MOB_TARGET_CHANGED,
)

_TITLE_STYLE = "color: #00ccff; font-weight: bold; font-size: 11px;"
_MOB_STYLE = "color: #e0e0e0; font-size: 11px; font-weight: bold;"
_KEY_STYLE = "color: #888888; font-size: 10px;"
_VAL_STYLE = "color: #e0e0e0; font-size: 10px; font-weight: bold;"
_NO_SESSION_STYLE = "color: #666666; font-size: 10px; font-style: italic;"


def _pct(num: float, denom: float) -> str:
    if denom <= 0:
        return "—"
    return f"{num / denom * 100:.1f}%"


class HuntStatsWidget(GridWidget):
    WIDGET_ID = "com.entropianexus.hunt_stats"
    DISPLAY_NAME = "Hunt Stats"
    DESCRIPTION = "Live encounter and session statistics (kills, damage, loot, return %)."
    DEFAULT_COLSPAN = 2
    MIN_WIDTH = 160
    MIN_HEIGHT = 100

    def __init__(self, config: dict):
        super().__init__(config)
        # Session totals
        self._kills = 0
        self._dmg_dealt = 0.0
        self._dmg_taken = 0.0
        self._loot_ped = 0.0
        self._current_mob = "—"
        self._active = False

        # Qt labels (set after create_widget)
        self._mob_label: QLabel | None = None
        self._val_labels: dict[str, QLabel] = {}

    def setup(self, context: WidgetContext) -> None:
        super().setup(context)
        self._subscribe(EVENT_HUNT_SESSION_STARTED, self._on_session_start)
        self._subscribe(EVENT_HUNT_SESSION_STOPPED, self._on_session_stop)
        self._subscribe(EVENT_HUNT_SESSION_UPDATED, self._on_session_updated)
        self._subscribe(EVENT_MOB_TARGET_CHANGED, self._on_mob_changed)

    def create_widget(self, parent: QWidget) -> QWidget:
        w = QWidget(parent)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(3)

        title = QLabel("Hunt Stats")
        title.setStyleSheet(_TITLE_STYLE)
        layout.addWidget(title)

        self._mob_label = QLabel("No active session")
        self._mob_label.setStyleSheet(_NO_SESSION_STYLE)
        layout.addWidget(self._mob_label)

        rows = [
            ("Kills", "0"),
            ("Dmg Dealt", "0.00"),
            ("Dmg Taken", "0.00"),
            ("Loot", "0.00 PED"),
            ("Return", "—"),
        ]
        for key, default in rows:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)

            k_lbl = QLabel(f"{key}:")
            k_lbl.setStyleSheet(_KEY_STYLE)
            k_lbl.setFixedWidth(70)
            row.addWidget(k_lbl)

            v_lbl = QLabel(default)
            v_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            v_lbl.setStyleSheet(_VAL_STYLE)
            row.addWidget(v_lbl)

            layout.addLayout(row)
            self._val_labels[key] = v_lbl

        return w

    def _on_session_start(self, _data) -> None:
        self._kills = 0
        self._dmg_dealt = 0.0
        self._dmg_taken = 0.0
        self._loot_ped = 0.0
        self._active = True
        self._refresh()

    def _on_session_stop(self, _data) -> None:
        self._active = False
        self._refresh()

    def _on_session_updated(self, data) -> None:
        if not data:
            return
        self._kills = data.get("kills", self._kills)
        self._dmg_dealt = data.get("dmg_dealt", self._dmg_dealt)
        self._dmg_taken = data.get("dmg_taken", self._dmg_taken)
        self._loot_ped = data.get("loot_ped", self._loot_ped)
        self._active = True
        self._refresh()

    def _on_mob_changed(self, data) -> None:
        if data:
            self._current_mob = data.get("mob_name", "—") or "—"
        else:
            self._current_mob = "—"
        self._refresh()

    def _refresh(self) -> None:
        if self._mob_label is None:
            return
        if self._active:
            self._mob_label.setText(self._current_mob)
            self._mob_label.setStyleSheet(_MOB_STYLE)
        else:
            self._mob_label.setText("No active session")
            self._mob_label.setStyleSheet(_NO_SESSION_STYLE)

        if "Kills" in self._val_labels:
            self._val_labels["Kills"].setText(str(self._kills))
        if "Dmg Dealt" in self._val_labels:
            self._val_labels["Dmg Dealt"].setText(f"{self._dmg_dealt:.2f}")
        if "Dmg Taken" in self._val_labels:
            self._val_labels["Dmg Taken"].setText(f"{self._dmg_taken:.2f}")
        if "Loot" in self._val_labels:
            self._val_labels["Loot"].setText(f"{self._loot_ped:.2f} PED")
        if "Return" in self._val_labels:
            self._val_labels["Return"].setText(_pct(self._loot_ped, self._dmg_dealt))
