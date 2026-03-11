"""CellContainer — visual chrome wrapping a single GridWidget's QWidget."""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QPen

from .grid_widget import GridWidget

_BORDER_EDIT = QColor(80, 140, 200, 200)
_BORDER_WIDTH = 1
_DRAG_HANDLE_COLOR = QColor(80, 140, 200, 100)
_DRAG_HANDLE_H = 6
_ERROR_BG = "rgba(140, 30, 30, 160)"
_ERROR_FG = "#ff9999"


class CellContainer(QWidget):
    """Wraps a GridWidget's QWidget.

    In edit mode:
    - A coloured drag-handle strip is painted at the top
    - A dashed border is painted around the cell
    - WA_TransparentForMouseEvents is set so the _GridCanvas receives all
      mouse events for drag and context-menu handling
    """

    def __init__(
        self,
        grid_widget: GridWidget,
        q_widget: QWidget | None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._grid_widget = grid_widget
        self._edit_mode = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if q_widget is not None:
            layout.addWidget(q_widget)
        else:
            err = QLabel(f"Error: {grid_widget.DISPLAY_NAME}")
            err.setAlignment(Qt.AlignmentFlag.AlignCenter)
            err.setWordWrap(True)
            err.setStyleSheet(
                f"background-color: {_ERROR_BG}; color: {_ERROR_FG}; "
                "font-size: 10px; padding: 4px; border-radius: 4px;"
            )
            layout.addWidget(err)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    @property
    def grid_widget(self) -> GridWidget:
        return self._grid_widget

    def set_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = enabled
        # Let canvas receive all mouse events when editing
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, enabled)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._edit_mode:
            return

        painter = QPainter(self)

        # Dashed border
        pen = QPen(_BORDER_EDIT, _BORDER_WIDTH)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)

        # Drag handle strip at top
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_DRAG_HANDLE_COLOR)
        painter.drawRect(1, 1, self.width() - 2, _DRAG_HANDLE_H)
