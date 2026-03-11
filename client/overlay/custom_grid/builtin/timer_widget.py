"""Timer widget — elapsed time since hunt session started, or standalone stopwatch."""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, QTimer
import time

from ..grid_widget import GridWidget, WidgetContext
from ....core.constants import EVENT_HUNT_SESSION_STARTED, EVENT_HUNT_SESSION_STOPPED

_TIME_STYLE = "color: #e0e0e0; font-size: 18px; font-weight: bold; font-family: monospace;"
_SUB_STYLE = "color: #888888; font-size: 10px;"
_BTN_STYLE = (
    "QPushButton { background: #2a2a40; color: #c0c0d0; border: 1px solid #555; "
    "border-radius: 3px; padding: 1px 6px; font-size: 10px; }"
    "QPushButton:hover { background: #383858; }"
)


def _fmt(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class TimerWidget(GridWidget):
    WIDGET_ID = "com.entropianexus.timer"
    DISPLAY_NAME = "Timer"
    DESCRIPTION = "Stopwatch that auto-starts with hunt sessions, or runs standalone."
    MIN_WIDTH = 110
    MIN_HEIGHT = 52

    def __init__(self, config: dict):
        super().__init__(config)
        self._start_time: float | None = None
        self._elapsed_before_pause: float = 0.0
        self._running = False
        self._label: QLabel | None = None
        self._qt_timer: QTimer | None = None

    def setup(self, context: WidgetContext) -> None:
        super().setup(context)
        self._subscribe(EVENT_HUNT_SESSION_STARTED, self._on_session_start)
        self._subscribe(EVENT_HUNT_SESSION_STOPPED, self._on_session_stop)

    def create_widget(self, parent: QWidget) -> QWidget:
        w = QWidget(parent)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel("00:00:00")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(_TIME_STYLE)
        layout.addWidget(self._label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        start_btn = QPushButton("▶")
        start_btn.setFixedWidth(28)
        start_btn.setStyleSheet(_BTN_STYLE)
        start_btn.setToolTip("Start")
        start_btn.clicked.connect(self._manual_start)
        btn_row.addWidget(start_btn)

        stop_btn = QPushButton("⏸")
        stop_btn.setFixedWidth(28)
        stop_btn.setStyleSheet(_BTN_STYLE)
        stop_btn.setToolTip("Pause")
        stop_btn.clicked.connect(self._manual_stop)
        btn_row.addWidget(stop_btn)

        reset_btn = QPushButton("↺")
        reset_btn.setFixedWidth(28)
        reset_btn.setStyleSheet(_BTN_STYLE)
        reset_btn.setToolTip("Reset")
        reset_btn.clicked.connect(self._manual_reset)
        btn_row.addWidget(reset_btn)

        layout.addLayout(btn_row)

        self._qt_timer = QTimer()
        self._qt_timer.setInterval(500)
        self._qt_timer.timeout.connect(self._tick)
        self._qt_timer.start()
        return w

    def _tick(self) -> None:
        if self._label:
            self._label.setText(_fmt(self._current_elapsed()))

    def _current_elapsed(self) -> float:
        if self._running and self._start_time is not None:
            return self._elapsed_before_pause + (time.monotonic() - self._start_time)
        return self._elapsed_before_pause

    def _start(self) -> None:
        if not self._running:
            self._start_time = time.monotonic()
            self._running = True

    def _stop(self) -> None:
        if self._running:
            self._elapsed_before_pause = self._current_elapsed()
            self._start_time = None
            self._running = False

    def _reset(self) -> None:
        self._stop()
        self._elapsed_before_pause = 0.0
        if self._label:
            self._label.setText("00:00:00")

    def _manual_start(self) -> None:
        self._start()

    def _manual_stop(self) -> None:
        self._stop()

    def _manual_reset(self) -> None:
        self._reset()

    def _on_session_start(self, _data) -> None:
        self._reset()
        self._start()

    def _on_session_stop(self, _data) -> None:
        self._stop()

    def teardown(self) -> None:
        if self._qt_timer:
            self._qt_timer.stop()
            self._qt_timer = None
        super().teardown()
