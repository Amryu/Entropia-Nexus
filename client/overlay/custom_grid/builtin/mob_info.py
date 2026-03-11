"""Mob Info widget — current locked target mob name and HP bar."""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt

from ..grid_widget import GridWidget, WidgetContext
from ....core.constants import EVENT_TARGET_LOCK_UPDATE, EVENT_TARGET_LOCK_LOST, EVENT_MOB_TARGET_CHANGED

_TITLE_STYLE = "color: #00ccff; font-weight: bold; font-size: 11px;"
_MOB_STYLE = "color: #e0e0e0; font-size: 12px; font-weight: bold;"
_IDLE_STYLE = "color: #666666; font-size: 10px; font-style: italic;"
_HP_STYLE = (
    "QProgressBar { background: #1a1a28; border: 1px solid #444; border-radius: 3px; "
    "height: 8px; text-align: center; color: transparent; }"
    "QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
    "stop:0 #c0302a, stop:0.5 #e05030, stop:1 #e06040); border-radius: 2px; }"
)


class MobInfoWidget(GridWidget):
    WIDGET_ID = "com.entropianexus.mob_info"
    DISPLAY_NAME = "Mob Info"
    DESCRIPTION = "Shows the current locked target's name and health bar."
    MIN_WIDTH = 120
    MIN_HEIGHT = 50

    def __init__(self, config: dict):
        super().__init__(config)
        self._mob_label: QLabel | None = None
        self._hp_bar: QProgressBar | None = None

    def setup(self, context: WidgetContext) -> None:
        super().setup(context)
        self._subscribe(EVENT_TARGET_LOCK_UPDATE, self._on_target_update)
        self._subscribe(EVENT_TARGET_LOCK_LOST, self._on_target_lost)
        self._subscribe(EVENT_MOB_TARGET_CHANGED, self._on_mob_changed)

    def create_widget(self, parent: QWidget) -> QWidget:
        w = QWidget(parent)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        title = QLabel("Target")
        title.setStyleSheet(_TITLE_STYLE)
        layout.addWidget(title)

        self._mob_label = QLabel("No target")
        self._mob_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mob_label.setStyleSheet(_IDLE_STYLE)
        self._mob_label.setWordWrap(True)
        layout.addWidget(self._mob_label)

        self._hp_bar = QProgressBar()
        self._hp_bar.setRange(0, 100)
        self._hp_bar.setValue(0)
        self._hp_bar.setTextVisible(False)
        self._hp_bar.setFixedHeight(8)
        self._hp_bar.setStyleSheet(_HP_STYLE)
        layout.addWidget(self._hp_bar)

        return w

    def _on_target_update(self, data) -> None:
        if not data or self._mob_label is None:
            return
        name = data.get("mob_name") or "Unknown"
        self._mob_label.setText(name)
        self._mob_label.setStyleSheet(_MOB_STYLE)

        hp_pct = data.get("hp_percent")
        if self._hp_bar is not None and hp_pct is not None:
            self._hp_bar.setValue(max(0, min(100, int(hp_pct))))

    def _on_target_lost(self, _data) -> None:
        if self._mob_label:
            self._mob_label.setText("No target")
            self._mob_label.setStyleSheet(_IDLE_STYLE)
        if self._hp_bar:
            self._hp_bar.setValue(0)

    def _on_mob_changed(self, data) -> None:
        if data and self._mob_label:
            mob = data.get("mob_name") or "—"
            self._mob_label.setText(mob)
            self._mob_label.setStyleSheet(_MOB_STYLE)
