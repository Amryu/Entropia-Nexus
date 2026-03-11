"""Graph widget — line chart of a live data series (e.g. loot over time)."""

from __future__ import annotations

from collections import deque

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath

from ..grid_widget import GridWidget, WidgetContext
from ....core.constants import EVENT_LOOT_GROUP

_TITLE_STYLE = "color: #00ccff; font-weight: bold; font-size: 11px;"
_AXIS_COLOR = QColor(80, 80, 100)
_LINE_COLOR = QColor(80, 180, 120)
_FILL_COLOR = QColor(60, 160, 100, 50)
_BG_COLOR = QColor(16, 16, 26)

MAX_POINTS = 60


class _GraphCanvas(QWidget):
    """Bare canvas that plots a deque of float values as a line chart."""

    def __init__(self, values: deque, parent=None):
        super().__init__(parent)
        self._values = values
        self.setMinimumSize(60, 40)

    def refresh(self) -> None:
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        pad = 4

        # Background
        painter.fillRect(0, 0, w, h, _BG_COLOR)

        vals = list(self._values)
        if len(vals) < 2:
            return

        mn, mx = min(vals), max(vals)
        span = mx - mn if mx != mn else 1.0

        def px(i: int) -> float:
            return pad + (i / (len(vals) - 1)) * (w - 2 * pad)

        def py(v: float) -> float:
            return h - pad - ((v - mn) / span) * (h - 2 * pad)

        # Build path
        path = QPainterPath()
        path.moveTo(px(0), py(vals[0]))
        for i, v in enumerate(vals[1:], 1):
            path.lineTo(px(i), py(v))

        # Fill area under line
        fill_path = QPainterPath(path)
        fill_path.lineTo(px(len(vals) - 1), h - pad)
        fill_path.lineTo(px(0), h - pad)
        fill_path.closeSubpath()
        painter.fillPath(fill_path, _FILL_COLOR)

        # Draw line
        pen = QPen(_LINE_COLOR, 1.5)
        painter.setPen(pen)
        painter.drawPath(path)

        # Axis
        painter.setPen(QPen(_AXIS_COLOR, 1))
        painter.drawLine(pad, h - pad, w - pad, h - pad)

        # Min/Max labels
        painter.setPen(QPen(QColor(120, 120, 140), 1))
        from PyQt6.QtGui import QFont
        f = QFont()
        f.setPointSize(7)
        painter.setFont(f)
        painter.drawText(pad, pad + 8, f"{mx:.1f}")
        painter.drawText(pad, h - pad - 2, f"{mn:.1f}")


class GraphWidget(GridWidget):
    WIDGET_ID = "com.entropianexus.graph"
    DISPLAY_NAME = "Graph"
    DESCRIPTION = "Line chart showing loot PED per drop over the last 60 events."
    DEFAULT_COLSPAN = 2
    MIN_WIDTH = 160
    MIN_HEIGHT = 80

    def __init__(self, config: dict):
        super().__init__(config)
        self._values: deque[float] = deque(maxlen=MAX_POINTS)
        self._canvas: _GraphCanvas | None = None

    def setup(self, context: WidgetContext) -> None:
        super().setup(context)
        self._subscribe(EVENT_LOOT_GROUP, self._on_loot)

    def create_widget(self, parent: QWidget) -> QWidget:
        w = QWidget(parent)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        title = QLabel("Loot Graph")
        title.setStyleSheet(_TITLE_STYLE)
        layout.addWidget(title)

        self._canvas = _GraphCanvas(self._values)
        layout.addWidget(self._canvas, 1)

        return w

    def _on_loot(self, data) -> None:
        if not data:
            return
        total = data.get("total_ped", 0.0)
        self._values.append(float(total))
        if self._canvas:
            self._canvas.refresh()

    def on_resize(self, width: int, height: int) -> None:
        if self._canvas:
            self._canvas.update()
