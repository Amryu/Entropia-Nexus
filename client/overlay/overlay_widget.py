"""Base class for managed overlay widgets — snap-aware, visibility-coordinated."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt

from ..core.config import save_config

if TYPE_CHECKING:
    from .overlay_manager import OverlayManager


class OverlayWidget(QWidget):
    """Frameless, always-on-top, translucent overlay with drag, snap, and position save.

    Replaces ``BaseOverlay`` with OverlayManager integration:
    - Snap-aware dragging (edges snap to other registered overlays)
    - Visibility coordinated via ``wants_visible`` flag + manager focus state
    - Auto-registers with the manager on init, auto-unregisters on close

    Subclasses should build their UI inside ``self._container``.
    """

    def __init__(
        self,
        *,
        config,
        config_path: str,
        position_key: str,
        manager: OverlayManager | None = None,
    ):
        super().__init__()
        self._config = config
        self._config_path = config_path
        self._position_key = position_key
        self._manager = manager
        self._drag_pos = None
        self._wants_visible = False

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
        if pos:
            self.move(pos[0], pos[1])

        # Register with manager
        if self._manager:
            self._manager.register(self)

    # --- Visibility coordination ---

    @property
    def wants_visible(self) -> bool:
        """Whether this widget *wants* to be shown (independent of game focus)."""
        return self._wants_visible

    def set_wants_visible(self, visible: bool) -> None:
        """Set visibility intent and immediately show/hide based on game focus."""
        self._wants_visible = visible
        if visible:
            if self._manager is None or self._manager.game_focused:
                self.show()
        else:
            self.hide()

    # --- Dragging with snap ---

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self._drag_pos
            x, y = new_pos.x(), new_pos.y()

            # Snap to other overlay edges
            if self._manager:
                targets = self._manager.get_snap_targets(self)
                from .overlay_manager import OverlayManager
                x, y = OverlayManager.snap_position(
                    x, y, self.width(), self.height(), targets,
                )

            self.move(x, y)

    def mouseReleaseEvent(self, event):
        if self._drag_pos is not None:
            self._drag_pos = None
            self._save_position()

    # --- Scroll containment (defense-in-depth) ---

    def wheelEvent(self, event):
        """Accept wheel events so they never propagate to the game window."""
        event.accept()

    # --- Position persistence ---

    def _save_position(self):
        pos = (self.x(), self.y())
        setattr(self._config, self._position_key, pos)
        save_config(self._config, self._config_path)

    # --- Cleanup ---

    def closeEvent(self, event):
        if self._manager:
            self._manager.unregister(self)
        super().closeEvent(event)
