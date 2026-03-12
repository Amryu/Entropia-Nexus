"""Mob Info widget — current locked target mob name and HP bar."""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt

from ..grid_widget import GridWidget, WidgetContext
from ....core.constants import EVENT_TARGET_LOCK_UPDATE, EVENT_TARGET_LOCK_LOST, EVENT_MOB_TARGET_CHANGED
from ._common import font_value, font_label, font_title, C_ACCENT, C_TEXT, C_IDLE

_HP_STYLE = (
    "QProgressBar {{ background: #1a1a28; border: 1px solid #444; border-radius: 3px; "
    "height: {h}px; text-align: center; color: transparent; }}"
    "QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
    "stop:0 #c0302a, stop:0.5 #e05030, stop:1 #e06040); border-radius: 2px; }}"
)


class MobInfoWidget(GridWidget):
    WIDGET_ID = "com.entropianexus.mob_info"
    DISPLAY_NAME = "Mob Info"
    DESCRIPTION = "Shows the current locked target's name and health bar."
    DEFAULT_COLSPAN = 4
    DEFAULT_ROWSPAN = 3
    MIN_WIDTH = 80
    MIN_HEIGHT = 40

    def __init__(self, config: dict):
        super().__init__(config)
        self._title_label: QLabel | None = None
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

        self._title_label = QLabel("Target")
        self._title_label.setStyleSheet(
            f"color: {C_ACCENT}; font-weight: bold; font-size: 11px;"
        )
        layout.addWidget(self._title_label)

        self._mob_label = QLabel("No target")
        self._mob_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mob_label.setStyleSheet(f"color: {C_IDLE}; font-size: 12px; font-style: italic;")
        self._mob_label.setWordWrap(True)
        layout.addWidget(self._mob_label, 1)

        self._hp_bar = QProgressBar()
        self._hp_bar.setRange(0, 100)
        self._hp_bar.setValue(0)
        self._hp_bar.setTextVisible(False)
        self._hp_bar.setFixedHeight(8)
        self._hp_bar.setStyleSheet(_HP_STYLE.format(h=8))
        layout.addWidget(self._hp_bar)

        return w

    def _on_target_update(self, data) -> None:
        if not data or self._mob_label is None:
            return
        name = data.get("mob_name") or "Unknown"
        self._mob_label.setText(name)
        self._mob_label.setStyleSheet(
            f"color: {C_TEXT}; font-size: 12px; font-weight: bold;"
        )
        hp_pct = data.get("hp_percent")
        if self._hp_bar is not None and hp_pct is not None:
            self._hp_bar.setValue(max(0, min(100, int(hp_pct))))

    def _on_target_lost(self, _data) -> None:
        if self._mob_label:
            self._mob_label.setText("No target")
            self._mob_label.setStyleSheet(
                f"color: {C_IDLE}; font-size: 12px; font-style: italic;"
            )
        if self._hp_bar:
            self._hp_bar.setValue(0)

    def _on_mob_changed(self, data) -> None:
        if data and self._mob_label:
            mob = data.get("mob_name") or "—"
            self._mob_label.setText(mob)
            self._mob_label.setStyleSheet(
                f"color: {C_TEXT}; font-size: 12px; font-weight: bold;"
            )

    def on_resize(self, width: int, height: int) -> None:
        mob_fs = font_value(height)
        if self._title_label:
            self._title_label.setStyleSheet(
                f"color: {C_ACCENT}; font-weight: bold; font-size: {font_title(height)}px;"
            )
        if self._mob_label:
            # Preserve active/idle style colour, update font size only
            current = self._mob_label.styleSheet()
            if C_TEXT in current:
                self._mob_label.setStyleSheet(
                    f"color: {C_TEXT}; font-size: {mob_fs}px; font-weight: bold;"
                )
            else:
                self._mob_label.setStyleSheet(
                    f"color: {C_IDLE}; font-size: {mob_fs}px; font-style: italic;"
                )
        bar_h = max(6, min(16, height // 8))
        if self._hp_bar:
            self._hp_bar.setFixedHeight(bar_h)
            self._hp_bar.setStyleSheet(_HP_STYLE.format(h=bar_h))
