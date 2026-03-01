"""Real-time hunt stats overlay — always-on-top, draggable, position persisted."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QVBoxLayout, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt

from .overlay_widget import OverlayWidget
from ..ui.signals import AppSignals

if TYPE_CHECKING:
    from .overlay_manager import OverlayManager


class HuntOverlay(OverlayWidget):
    """Compact always-on-top overlay showing live hunt stats.

    Displays: current mob, kills, damage dealt, loot total, return %.
    """

    def __init__(
        self,
        *,
        signals: AppSignals,
        config,
        config_path: str,
        manager: OverlayManager | None = None,
    ):
        super().__init__(
            config=config,
            config_path=config_path,
            position_key="hunt_overlay_position",
            manager=manager,
        )
        self._signals = signals
        self.setMinimumWidth(220)

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Title
        title = QLabel("Hunt Tracker")
        title.setStyleSheet("color: #00ccff; font-weight: bold; font-size: 12px;")
        layout.addWidget(title)

        # Current mob
        self._mob_label = QLabel("Target: —")
        self._mob_label.setStyleSheet("color: #ffffff; font-size: 11px;")
        layout.addWidget(self._mob_label)

        # Stats grid
        self._stat_labels = {}
        stats_defs = [
            ("Kills", "0"),
            ("Dmg Dealt", "0.00"),
            ("Dmg Taken", "0.00"),
            ("Loot", "0.00 PED"),
            ("Return", "—"),
        ]
        for name, default in stats_defs:
            row = QHBoxLayout()
            name_lbl = QLabel(f"{name}:")
            name_lbl.setStyleSheet("color: #aaaaaa; font-size: 10px;")
            name_lbl.setFixedWidth(80)
            row.addWidget(name_lbl)

            val_lbl = QLabel(default)
            val_lbl.setStyleSheet("color: #ffffff; font-size: 10px; font-weight: bold;")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(val_lbl)

            layout.addLayout(row)
            self._stat_labels[name] = val_lbl

        # Connect signals
        signals.hunt_session_updated.connect(self._on_session_updated)
        signals.mob_target_changed.connect(self._on_mob_changed)
        signals.hunt_session_started.connect(lambda _: self.set_wants_visible(True))
        signals.hunt_session_stopped.connect(lambda _: self.set_wants_visible(False))

        self.hide()  # Hidden until a hunt session starts

    def _on_session_updated(self, data):
        if not isinstance(data, dict):
            return
        self._stat_labels["Kills"].setText(str(data.get("kills", 0)))
        self._stat_labels["Dmg Dealt"].setText(f"{data.get('damage_dealt', 0):.2f}")
        self._stat_labels["Dmg Taken"].setText(f"{data.get('damage_taken', 0):.2f}")
        loot = data.get("loot_total", 0)
        self._stat_labels["Loot"].setText(f"{loot:.2f} PED")

        cost = data.get("total_cost", 0)
        if cost > 0:
            self._stat_labels["Return"].setText(f"{(loot / cost) * 100:.1f}%")

    def _on_mob_changed(self, data):
        mob_name = data.get("mob_name", "—") if isinstance(data, dict) else str(data)
        self._mob_label.setText(f"Target: {mob_name}")
