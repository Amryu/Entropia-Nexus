"""Base class for draggable, always-on-top overlays with position persistence."""

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt

from ..core.config import save_config


class BaseOverlay(QWidget):
    """Frameless, always-on-top, translucent overlay with drag and position save.

    Subclasses should:
    1. Call ``super().__init__(...)`` with ``position_key`` set to the
       ``AppConfig`` attribute name that stores this overlay's (x, y).
    2. Build their UI inside ``self._container`` (the rounded background widget)
       or add their own layout to ``self``.
    """

    def __init__(self, *, config, config_path: str, position_key: str):
        super().__init__()
        self._config = config
        self._config_path = config_path
        self._position_key = position_key
        self._drag_pos = None

        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(config.overlay_opacity)

        # Background container — subclasses add their layout here
        self._container = QWidget(self)
        self._container.setStyleSheet(
            "background-color: rgba(20, 20, 30, 200); "
            "border-radius: 8px; padding: 8px;"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._container)

        # Restore saved position
        pos = getattr(config, position_key, (50, 50))
        self.move(pos[0], pos[1])

    # --- Dragging ---

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        if self._drag_pos is not None:
            self._drag_pos = None
            self._save_position()

    # --- Position persistence ---

    def _save_position(self):
        pos = (self.x(), self.y())
        setattr(self._config, self._position_key, pos)
        save_config(self._config, self._config_path)
