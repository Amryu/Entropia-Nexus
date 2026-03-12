"""Hunt Stats widget — live stats for the current hunt encounter or session."""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt

from ..grid_widget import GridWidget, WidgetContext
from ....core.constants import (
    EVENT_HUNT_SESSION_STARTED,
    EVENT_HUNT_SESSION_STOPPED,
    EVENT_HUNT_SESSION_UPDATED,
    EVENT_MOB_TARGET_CHANGED,
)
from ._common import font_title, font_label, font_value, C_ACCENT, C_TEXT, C_DIM


def _pct(num: float, denom: float) -> str:
    if denom <= 0:
        return "—"
    return f"{num / denom * 100:.1f}%"


class HuntStatsWidget(GridWidget):
    WIDGET_ID = "com.entropianexus.hunt_stats"
    DISPLAY_NAME = "Hunt Stats"
    DESCRIPTION = "Live encounter and session statistics (kills, damage, loot, return %)."
    DEFAULT_COLSPAN = 5
    DEFAULT_ROWSPAN = 5
    MIN_WIDTH = 100
    MIN_HEIGHT = 80

    def __init__(self, config: dict):
        super().__init__(config)
        self._kills = 0
        self._dmg_dealt = 0.0
        self._dmg_taken = 0.0
        self._loot_ped = 0.0
        self._current_mob = "—"
        self._active = False

        self._title_label: QLabel | None = None
        self._mob_label: QLabel | None = None
        self._key_labels: dict[str, QLabel] = {}
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

        self._title_label = QLabel("Hunt Stats")
        self._title_label.setStyleSheet(
            f"color: {C_ACCENT}; font-weight: bold; font-size: 11px;"
        )
        layout.addWidget(self._title_label)

        self._mob_label = QLabel("No active session")
        self._mob_label.setStyleSheet(
            f"color: {C_DIM}; font-size: 10px; font-style: italic;"
        )
        layout.addWidget(self._mob_label)

        for key, default in [
            ("Kills",     "0"),
            ("Dmg Dealt", "0.00"),
            ("Dmg Taken", "0.00"),
            ("Loot",      "0.00 PED"),
            ("Return",    "—"),
        ]:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)

            k_lbl = QLabel(f"{key}:")
            k_lbl.setStyleSheet(f"color: {C_DIM}; font-size: 10px;")
            k_lbl.setFixedWidth(70)
            row.addWidget(k_lbl)

            v_lbl = QLabel(default)
            v_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            v_lbl.setStyleSheet(f"color: {C_TEXT}; font-size: 10px; font-weight: bold;")
            row.addWidget(v_lbl)

            layout.addLayout(row)
            self._key_labels[key] = k_lbl
            self._val_labels[key] = v_lbl

        return w

    def on_resize(self, width: int, height: int) -> None:
        fs_key = font_label(height)
        fs_val = font_label(height)  # keep key/val same size for alignment
        fs_ttl = font_title(height)
        key_w  = max(50, width // 3)

        if self._title_label:
            self._title_label.setStyleSheet(
                f"color: {C_ACCENT}; font-weight: bold; font-size: {fs_ttl}px;"
            )
        if self._mob_label:
            mob_style = self._mob_label.styleSheet()
            color = C_TEXT if "font-weight: bold" in mob_style else C_DIM
            italic = "" if "font-weight: bold" in mob_style else "font-style: italic;"
            self._mob_label.setStyleSheet(
                f"color: {color}; font-size: {fs_val}px; {italic}"
            )
        for k_lbl in self._key_labels.values():
            k_lbl.setStyleSheet(f"color: {C_DIM}; font-size: {fs_key}px;")
            k_lbl.setFixedWidth(key_w)
        for v_lbl in self._val_labels.values():
            v_lbl.setStyleSheet(
                f"color: {C_TEXT}; font-size: {fs_val}px; font-weight: bold;"
            )

    # --- Event handlers ---

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
        self._kills     = data.get("kills",      self._kills)
        self._dmg_dealt = data.get("dmg_dealt",  self._dmg_dealt)
        self._dmg_taken = data.get("dmg_taken",  self._dmg_taken)
        self._loot_ped  = data.get("loot_ped",   self._loot_ped)
        self._active = True
        self._refresh()

    def _on_mob_changed(self, data) -> None:
        self._current_mob = (data.get("mob_name") or "—") if data else "—"
        self._refresh()

    def _refresh(self) -> None:
        if self._mob_label is None:
            return
        if self._active:
            self._mob_label.setText(self._current_mob)
            self._mob_label.setStyleSheet(
                f"color: {C_TEXT}; font-size: 10px; font-weight: bold;"
            )
        else:
            self._mob_label.setText("No active session")
            self._mob_label.setStyleSheet(
                f"color: {C_DIM}; font-size: 10px; font-style: italic;"
            )

        updates = {
            "Kills":     str(self._kills),
            "Dmg Dealt": f"{self._dmg_dealt:.2f}",
            "Dmg Taken": f"{self._dmg_taken:.2f}",
            "Loot":      f"{self._loot_ped:.2f} PED",
            "Return":    _pct(self._loot_ped, self._dmg_dealt),
        }
        for key, val in updates.items():
            if key in self._val_labels:
                self._val_labels[key].setText(val)
