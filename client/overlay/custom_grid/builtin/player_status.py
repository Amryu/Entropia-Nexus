"""Player Status widget — health and reload bars from the player status detector."""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt

from ..grid_widget import GridWidget, WidgetContext
from ....core.constants import EVENT_PLAYER_STATUS_UPDATE, EVENT_PLAYER_STATUS_LOST

_TITLE_STYLE = "color: #00ccff; font-weight: bold; font-size: 11px;"
_KEY_STYLE = "color: #888888; font-size: 10px;"
_IDLE_STYLE = "color: #555555; font-size: 10px; font-style: italic;"

_HP_BAR = (
    "QProgressBar { background: #1a1a28; border: 1px solid #444; border-radius: 3px; "
    "text-align: center; font-size: 9px; color: #ccc; }"
    "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
    "stop:0 #7b2020, stop:0.5 #c03030, stop:1 #e04040); border-radius: 2px; }"
)
_RELOAD_BAR = (
    "QProgressBar { background: #1a1a28; border: 1px solid #444; border-radius: 3px; "
    "text-align: center; font-size: 9px; color: transparent; }"
    "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
    "stop:0 #204060, stop:1 #4080c0); border-radius: 2px; }"
)


class PlayerStatusWidget(GridWidget):
    WIDGET_ID = "com.entropianexus.player_status"
    DISPLAY_NAME = "Player Status"
    DESCRIPTION = "Shows your current health % and reload bar (requires Player Status detector)."
    MIN_WIDTH = 130
    MIN_HEIGHT = 60

    def __init__(self, config: dict):
        super().__init__(config)
        self._hp_bar: QProgressBar | None = None
        self._reload_bar: QProgressBar | None = None

    def setup(self, context: WidgetContext) -> None:
        super().setup(context)
        self._subscribe(EVENT_PLAYER_STATUS_UPDATE, self._on_status)
        self._subscribe(EVENT_PLAYER_STATUS_LOST, self._on_lost)

    def create_widget(self, parent: QWidget) -> QWidget:
        w = QWidget(parent)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        title = QLabel("Player Status")
        title.setStyleSheet(_TITLE_STYLE)
        layout.addWidget(title)

        # Health row
        hp_row = QHBoxLayout()
        hp_row.setSpacing(6)
        hp_lbl = QLabel("HP:")
        hp_lbl.setStyleSheet(_KEY_STYLE)
        hp_lbl.setFixedWidth(28)
        hp_row.addWidget(hp_lbl)
        self._hp_bar = QProgressBar()
        self._hp_bar.setRange(0, 100)
        self._hp_bar.setValue(0)
        self._hp_bar.setFixedHeight(14)
        self._hp_bar.setFormat("%p%")
        self._hp_bar.setStyleSheet(_HP_BAR)
        hp_row.addWidget(self._hp_bar, 1)
        layout.addLayout(hp_row)

        # Reload row
        rl_row = QHBoxLayout()
        rl_row.setSpacing(6)
        rl_lbl = QLabel("Reload:")
        rl_lbl.setStyleSheet(_KEY_STYLE)
        rl_lbl.setFixedWidth(46)
        rl_row.addWidget(rl_lbl)
        self._reload_bar = QProgressBar()
        self._reload_bar.setRange(0, 100)
        self._reload_bar.setValue(0)
        self._reload_bar.setFixedHeight(8)
        self._reload_bar.setTextVisible(False)
        self._reload_bar.setStyleSheet(_RELOAD_BAR)
        rl_row.addWidget(self._reload_bar, 1)
        layout.addLayout(rl_row)

        idle = QLabel("Requires Player Status detector")
        idle.setStyleSheet(_IDLE_STYLE)
        idle.setWordWrap(True)
        layout.addWidget(idle)

        return w

    def _on_status(self, data) -> None:
        if not data:
            return
        if isinstance(data, dict):
            hp = data.get("health_pct")
            reload_pct = data.get("reload_pct")
        else:
            hp = getattr(data, "health_pct", None)
            reload_pct = getattr(data, "reload_pct", None)

        if hp is not None and self._hp_bar:
            self._hp_bar.setValue(max(0, min(100, int(hp * 100))))
        if reload_pct is not None and self._reload_bar:
            self._reload_bar.setValue(max(0, min(100, int(reload_pct * 100))))

    def _on_lost(self, _data) -> None:
        if self._hp_bar:
            self._hp_bar.setValue(0)
        if self._reload_bar:
            self._reload_bar.setValue(0)
