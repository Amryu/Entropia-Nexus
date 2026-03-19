"""Real-time hunt stats overlay — always-on-top, draggable, position persisted."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QVBoxLayout, QLabel, QHBoxLayout, QWidget
from PyQt6.QtCore import Qt, QTimer

from .overlay_widget import OverlayWidget
from ..ui.signals import AppSignals

if TYPE_CHECKING:
    from .overlay_manager import OverlayManager


class HuntOverlay(OverlayWidget):
    """Compact always-on-top overlay showing live hunt stats.

    Displays: session timer, active encounters, kills, loot, return %.
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
        self.setMinimumWidth(240)

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        # Title + timer
        title_row = QHBoxLayout()
        title = QLabel("Hunt Tracker")
        title.setStyleSheet("color: #00ccff; font-weight: bold; font-size: 12px;")
        title_row.addWidget(title)
        title_row.addStretch()
        self._timer_label = QLabel("")
        self._timer_label.setStyleSheet("color: #aaaaaa; font-size: 10px; font-family: Consolas;")
        title_row.addWidget(self._timer_label)
        layout.addLayout(title_row)

        # Encounters area (dynamically populated)
        self._encounters_widget = QWidget()
        self._encounters_layout = QVBoxLayout(self._encounters_widget)
        self._encounters_layout.setContentsMargins(0, 4, 0, 4)
        self._encounters_layout.setSpacing(1)
        layout.addWidget(self._encounters_widget)

        # Separator
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(255, 255, 255, 30);")
        layout.addWidget(sep)

        # Summary stats
        self._stat_labels = {}
        stats_defs = [
            ("Kills", "0"),
            ("Loot", "0.00 PED"),
            ("Cost", "0.00 PED"),
            ("Return", "—"),
        ]
        for name, default in stats_defs:
            row = QHBoxLayout()
            row.setSpacing(4)
            name_lbl = QLabel(f"{name}:")
            name_lbl.setStyleSheet("color: #aaaaaa; font-size: 10px;")
            name_lbl.setFixedWidth(50)
            row.addWidget(name_lbl)

            val_lbl = QLabel(default)
            val_lbl.setStyleSheet("color: #ffffff; font-size: 10px; font-weight: bold;")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(val_lbl)

            layout.addLayout(row)
            self._stat_labels[name] = val_lbl

        # Timer
        self._session_start: datetime | None = None
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._update_timer)

        # Connect signals
        signals.hunt_session_updated.connect(self._on_session_updated)
        signals.mob_target_changed.connect(self._on_mob_changed)
        signals.hunt_session_started.connect(self._on_session_started)
        signals.hunt_session_stopped.connect(self._on_session_stopped)

        self.hide()  # Hidden until a hunt session starts

    def _on_session_started(self, _data):
        self._session_start = datetime.utcnow()
        self._tick_timer.start()
        self.set_wants_visible(True)

    def _on_session_stopped(self, _data):
        self._tick_timer.stop()
        self._timer_label.setText("")
        self._session_start = None
        self.set_wants_visible(False)

    def _update_timer(self):
        if not self._session_start:
            return
        elapsed = datetime.utcnow() - self._session_start
        total_secs = int(elapsed.total_seconds())
        h, rem = divmod(total_secs, 3600)
        m, s = divmod(rem, 60)
        self._timer_label.setText(f"{h:02d}:{m:02d}:{s:02d}")

    def _on_session_updated(self, data):
        if not isinstance(data, dict):
            return

        # Update summary stats
        kills = data.get("kills", 0)
        loot = data.get("loot_total", 0)
        cost = data.get("total_cost", 0)
        self._stat_labels["Kills"].setText(str(kills))
        self._stat_labels["Loot"].setText(f"{loot:.2f} PED")
        self._stat_labels["Cost"].setText(f"{cost:.2f} PED")
        if cost > 0:
            ret = loot / cost * 100
            color = "#4ec9b0" if ret >= 100 else "#ff6b6b"
            self._stat_labels["Return"].setText(
                f"<span style='color:{color}'>{ret:.1f}%</span>"
            )
        else:
            self._stat_labels["Return"].setText("—")

        # Update alive encounters list
        alive = data.get("alive_encounters", [])
        self._rebuild_encounters(alive)

    def _rebuild_encounters(self, alive: list[dict]):
        """Rebuild the encounters area from the alive encounters list."""
        # Clear existing
        while self._encounters_layout.count():
            item = self._encounters_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not alive:
            return

        for enc in alive:
            is_active = enc.get("is_active", False)
            mob = enc.get("mob_name", "?")
            state = enc.get("state", "")
            dmg = enc.get("damage_dealt", 0)

            if is_active:
                color = "#00ccff"
                indicator = "\u25b8"  # ▸
                state_tag = ""
            else:
                color = "#888888"
                indicator = "\u25b8"
                state_tag = " <span style='color:#666'>[idle]</span>"

            lbl = QLabel(
                f"<span style='color:{color}'>{indicator} {mob}</span>"
                f"{state_tag}"
                f"  <span style='color:#aaa;font-size:9px'>{dmg:.0f} dmg</span>"
            )
            lbl.setStyleSheet("font-size: 10px;")
            self._encounters_layout.addWidget(lbl)

    def _on_mob_changed(self, data):
        pass  # Encounters are updated via _on_session_updated
