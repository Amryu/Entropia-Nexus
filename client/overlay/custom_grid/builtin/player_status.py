"""Player Status widget — health and reload bars from the player status detector."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
)
from PyQt6.QtCore import Qt

from ..grid_widget import GridWidget, WidgetContext
from ....core.constants import EVENT_PLAYER_STATUS_UPDATE, EVENT_PLAYER_STATUS_LOST
from ._common import font_title, font_label, C_ACCENT

_HP_BAR = (
    "QProgressBar {{ background: #1a1a28; border: 1px solid #444; border-radius: 3px; "
    "text-align: center; font-size: 9px; color: #ccc; }}"
    "QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
    "stop:0 #7b2020, stop:0.5 #c03030, stop:1 #e04040); border-radius: 2px; }}"
)
_RELOAD_BAR = (
    "QProgressBar {{ background: #1a1a28; border: 1px solid #444; border-radius: 3px; "
    "text-align: center; font-size: 9px; color: transparent; }}"
    "QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
    "stop:0 #204060, stop:1 #4080c0); border-radius: 2px; }}"
)


class PlayerStatusWidget(GridWidget):
    WIDGET_ID = "com.entropianexus.player_status"
    DISPLAY_NAME = "Player Status"
    DESCRIPTION = "Shows your current health % and reload bar (requires Player Status detector)."
    DEFAULT_COLSPAN = 4
    DEFAULT_ROWSPAN = 3
    MIN_WIDTH = 80
    MIN_HEIGHT = 40

    def __init__(self, config: dict):
        super().__init__(config)
        self._title_label: QLabel | None = None
        self._hp_lbl: QLabel | None = None
        self._rl_lbl: QLabel | None = None
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

        self._title_label = QLabel("Player Status")
        self._title_label.setStyleSheet(
            f"color: {C_ACCENT}; font-weight: bold; font-size: 11px;"
        )
        layout.addWidget(self._title_label)

        # Health row
        hp_row = QHBoxLayout()
        hp_row.setSpacing(6)
        self._hp_lbl = QLabel("HP:")
        self._hp_lbl.setStyleSheet("color: #888888; font-size: 10px;")
        self._hp_lbl.setFixedWidth(28)
        hp_row.addWidget(self._hp_lbl)
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
        self._rl_lbl = QLabel("Reload:")
        self._rl_lbl.setStyleSheet("color: #888888; font-size: 10px;")
        self._rl_lbl.setFixedWidth(46)
        rl_row.addWidget(self._rl_lbl)
        self._reload_bar = QProgressBar()
        self._reload_bar.setRange(0, 100)
        self._reload_bar.setValue(0)
        self._reload_bar.setFixedHeight(8)
        self._reload_bar.setTextVisible(False)
        self._reload_bar.setStyleSheet(_RELOAD_BAR)
        rl_row.addWidget(self._reload_bar, 1)
        layout.addLayout(rl_row)

        idle = QLabel("Requires Player Status detector")
        idle.setStyleSheet("color: #555555; font-size: 10px; font-style: italic;")
        idle.setWordWrap(True)
        layout.addWidget(idle)

        return w

    def _on_status(self, data) -> None:
        if not data:
            return
        hp = data.get("health_pct") if isinstance(data, dict) else getattr(data, "health_pct", None)
        rp = data.get("reload_pct") if isinstance(data, dict) else getattr(data, "reload_pct", None)
        if hp is not None and self._hp_bar:
            self._hp_bar.setValue(max(0, min(100, int(hp * 100))))
        if rp is not None and self._reload_bar:
            self._reload_bar.setValue(max(0, min(100, int(rp * 100))))

    def _on_lost(self, _data) -> None:
        if self._hp_bar:     self._hp_bar.setValue(0)
        if self._reload_bar: self._reload_bar.setValue(0)

    def on_resize(self, width: int, height: int) -> None:
        fs = font_label(height)
        if self._title_label:
            self._title_label.setStyleSheet(
                f"color: {C_ACCENT}; font-weight: bold; font-size: {font_title(height)}px;"
            )
        lbl_w = max(24, width // 6)
        if self._hp_lbl:
            self._hp_lbl.setStyleSheet(f"color: #888888; font-size: {fs}px;")
            self._hp_lbl.setFixedWidth(lbl_w)
        if self._rl_lbl:
            self._rl_lbl.setStyleSheet(f"color: #888888; font-size: {fs}px;")
            self._rl_lbl.setFixedWidth(lbl_w + 18)
        hp_h = max(10, min(20, height // 6))
        rl_h = max(6, min(14, height // 9))
        if self._hp_bar:
            self._hp_bar.setFixedHeight(hp_h)
        if self._reload_bar:
            self._reload_bar.setFixedHeight(rl_h)
