"""Clock widget — shows current time and optional session uptime."""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer

from ..grid_widget import GridWidget, WidgetContext
from ._common import font_big, font_label, C_TEXT, C_DIM


class ClockWidget(GridWidget):
    WIDGET_ID = "com.entropianexus.clock"
    DISPLAY_NAME = "Clock"
    DESCRIPTION = "Shows the current local time."
    DEFAULT_COLSPAN = 4
    DEFAULT_ROWSPAN = 3
    MIN_WIDTH = 80
    MIN_HEIGHT = 40

    def __init__(self, config: dict):
        super().__init__(config)
        self._label: QLabel | None = None
        self._sub: QLabel | None = None
        self._timer: QTimer | None = None

    def setup(self, context: WidgetContext) -> None:
        super().setup(context)

    def create_widget(self, parent: QWidget) -> QWidget:
        w = QWidget(parent)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel("--:--:--")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(
            f"color: {C_TEXT}; font-size: 20px; font-weight: bold; font-family: monospace;"
        )
        layout.addWidget(self._label)

        self._sub = QLabel("Local Time")
        self._sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub.setStyleSheet(f"color: {C_DIM}; font-size: 10px;")
        layout.addWidget(self._sub)

        self._timer = QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._tick()
        return w

    def _tick(self) -> None:
        if self._label:
            self._label.setText(datetime.now().strftime("%H:%M:%S"))

    def on_resize(self, width: int, height: int) -> None:
        if self._label:
            self._label.setStyleSheet(
                f"color: {C_TEXT}; font-size: {font_big(height)}px;"
                " font-weight: bold; font-family: monospace;"
            )
        if self._sub:
            self._sub.setStyleSheet(f"color: {C_DIM}; font-size: {font_label(height)}px;")

    def teardown(self) -> None:
        if self._timer:
            self._timer.stop()
            self._timer = None
        super().teardown()
