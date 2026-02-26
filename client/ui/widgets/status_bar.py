"""Bottom status bar for persistent info (trackers, inventory value, etc.)."""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QStyleOption, QStyle
from PyQt6.QtGui import QPainter

from ..theme import STATUS_BAR_HEIGHT


class StatusBar(QWidget):
    """Thin bar at the bottom of the main window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(STATUS_BAR_HEIGHT)
        self.setObjectName("statusBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(0)

    def paintEvent(self, event):
        """Required for QWidget subclasses to honour stylesheet backgrounds."""
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
        p.end()
