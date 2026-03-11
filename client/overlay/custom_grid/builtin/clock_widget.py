"""Clock widget — shows current time and optional session uptime."""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer

from ..grid_widget import GridWidget, WidgetContext

_LABEL_STYLE = "color: #e0e0e0; font-size: 20px; font-weight: bold; font-family: monospace;"
_SUB_STYLE = "color: #888888; font-size: 10px;"


class ClockWidget(GridWidget):
    WIDGET_ID = "com.entropianexus.clock"
    DISPLAY_NAME = "Clock"
    DESCRIPTION = "Shows the current local time."
    MIN_WIDTH = 100
    MIN_HEIGHT = 44

    def __init__(self, config: dict):
        super().__init__(config)
        self._label: QLabel | None = None
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
        self._label.setStyleSheet(_LABEL_STYLE)
        layout.addWidget(self._label)

        sub = QLabel("Local Time")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(_SUB_STYLE)
        layout.addWidget(sub)

        self._timer = QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._tick()
        return w

    def _tick(self) -> None:
        if self._label:
            self._label.setText(datetime.now().strftime("%H:%M:%S"))

    def teardown(self) -> None:
        if self._timer:
            self._timer.stop()
            self._timer = None
        super().teardown()
