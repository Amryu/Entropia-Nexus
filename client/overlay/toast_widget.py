"""In-game toast notifications — ephemeral, auto-dismissing, stacking."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import (
    Qt, QObject, QTimer, QPropertyAnimation, QPoint, QEasingCurve,
    pyqtSignal,
)
from ..notifications.models import (
    Notification,
    SOURCE_GLOBAL, SOURCE_TRADE_CHAT, SOURCE_NEXUS, SOURCE_SYSTEM, SOURCE_STREAM,
)

from PyQt6.QtGui import QScreen

if TYPE_CHECKING:
    from ..core.config import AppConfig

# --- Constants ---

TOAST_WIDTH = 320
TOAST_MAX_VISIBLE = 4
TOAST_AUTO_DISMISS_MS = 20_000  # 20 seconds
TOAST_GAP = 8
TOAST_MARGIN = 16
TOAST_ANIM_MS = 200

# Overlay-matching colors
BG_COLOR = "rgba(20, 20, 30, 220)"
TEXT_COLOR = "#e0e0e0"
TEXT_DIM = "#999999"
ACCENT = "#00ccff"

_SOURCE_COLORS = {
    SOURCE_GLOBAL: "#fbbf24",
    SOURCE_TRADE_CHAT: "#00ccff",
    SOURCE_NEXUS: "#16a34a",
    SOURCE_SYSTEM: "#aaaaaa",
    SOURCE_STREAM: "#E05050",
}

_SOURCE_LABELS = {
    SOURCE_GLOBAL: "Global",
    SOURCE_TRADE_CHAT: "Trade",
    SOURCE_NEXUS: "Nexus",
    SOURCE_SYSTEM: "System",
    SOURCE_STREAM: "Stream",
}

# Corner constants
CORNER_BOTTOM_RIGHT = "bottom_right"
CORNER_BOTTOM_LEFT = "bottom_left"
CORNER_TOP_RIGHT = "top_right"
CORNER_TOP_LEFT = "top_left"


def _get_toast_action(notif: Notification):
    """Return (label, action_type, action_data) for a context action, or None."""
    if notif.source == SOURCE_STREAM:
        url = notif.metadata.get("channel_url", "")
        if url and url.lower().startswith(("https://", "http://")):
            return ("Watch", "url", url)
    if notif.source == SOURCE_NEXUS:
        url = notif.metadata.get("url", "https://entropianexus.com")
        return ("Open on Nexus", "url", url)
    if notif.source == SOURCE_TRADE_CHAT:
        return ("Exchange", "overlay", "exchange")
    return None


# =====================================================================
# Single toast widget
# =====================================================================

class ToastWidget(QWidget):
    """A single ephemeral toast notification."""

    dismissed = pyqtSignal(object)  # emits self
    action_clicked = pyqtSignal(str, str)  # (action_type, action_data)

    def __init__(self, notif: Notification, *, opacity: float = 0.92):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowOpacity(opacity)
        self.setFixedWidth(TOAST_WIDTH)

        source_color = _SOURCE_COLORS.get(notif.source, TEXT_DIM)

        # --- Container with left accent border ---
        container = QWidget(self)
        container.setStyleSheet(
            f"background-color: {BG_COLOR};"
            f" border-left: 3px solid {source_color};"
            f" border-radius: 6px;"
            f" padding: 0px;"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(container)

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(10, 8, 8, 8)
        main_layout.setSpacing(4)

        # --- Top row: source badge + title + close ---
        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        src_lbl = QLabel(_SOURCE_LABELS.get(notif.source, "?"))
        src_lbl.setStyleSheet(
            f"color: {source_color}; font-size: 12px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        src_lbl.setFixedWidth(38)
        top_row.addWidget(src_lbl)

        title_lbl = QLabel(notif.title)
        title_lbl.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 12px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        title_lbl.setWordWrap(True)
        fm = title_lbl.fontMetrics()
        title_lbl.setText(
            fm.elidedText(notif.title, Qt.TextElideMode.ElideRight, TOAST_WIDTH - 100)
        )
        top_row.addWidget(title_lbl, stretch=1)

        close_btn = QPushButton("\u00d7")  # ×
        close_btn.setFixedSize(20, 20)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            f"QPushButton {{ color: {TEXT_DIM}; background: transparent;"
            f" border: none; font-size: 16px; font-weight: bold; padding: 0px; }}"
            f"QPushButton:hover {{ color: {TEXT_COLOR}; }}"
        )
        close_btn.clicked.connect(self._on_dismiss)
        top_row.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignTop)

        main_layout.addLayout(top_row)

        # --- Body ---
        if notif.body:
            body_lbl = QLabel(notif.body)
            body_lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 12px;"
                f" background: transparent; border: none;"
            )
            body_lbl.setWordWrap(True)
            body_lbl.setMaximumHeight(48)
            main_layout.addWidget(body_lbl)

        # --- Action button ---
        action = _get_toast_action(notif)
        if action:
            label, a_type, a_data = action
            btn_row = QHBoxLayout()
            btn_row.addStretch()
            action_btn = QPushButton(label)
            action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            action_btn.setStyleSheet(
                f"QPushButton {{ color: {ACCENT}; background: transparent;"
                f" border: 1px solid {ACCENT}; border-radius: 3px;"
                f" padding: 2px 10px; font-size: 12px; }}"
                f"QPushButton:hover {{ background: rgba(0, 204, 255, 30); }}"
            )
            action_btn.clicked.connect(
                lambda _checked, at=a_type, ad=a_data: self._on_action(at, ad)
            )
            btn_row.addWidget(action_btn)
            main_layout.addLayout(btn_row)

        # --- Auto-dismiss timer ---
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(TOAST_AUTO_DISMISS_MS)
        self._timer.timeout.connect(self._on_dismiss)

    def start_timer(self):
        self._timer.start()

    def _on_dismiss(self):
        self._timer.stop()
        self.dismissed.emit(self)

    def _on_action(self, action_type: str, action_data: str):
        self.action_clicked.emit(action_type, action_data)
        self._on_dismiss()

    def wheelEvent(self, event):
        event.accept()


# =====================================================================
# Toast manager
# =====================================================================

class ToastManager(QObject):
    """Manages the lifecycle and stacking of in-game toast notifications."""

    toast_action_triggered = pyqtSignal(str, str)  # (action_type, action_data)

    def __init__(self, *, config: AppConfig):
        super().__init__()
        self._config = config
        self._active: list[ToastWidget] = []
        self._visible = True

    # --- Public API ---

    def show_toast(self, notif: Notification) -> None:
        """Create and display a new toast for *notif*."""
        # Anti-spam: dismiss oldest if at capacity
        while len(self._active) >= TOAST_MAX_VISIBLE:
            self._remove_toast(self._active[0], animate=False)

        toast = ToastWidget(notif, opacity=self._config.overlay_opacity)
        toast.dismissed.connect(self._on_toast_dismissed)
        toast.action_clicked.connect(self.toast_action_triggered)
        self._active.append(toast)

        # Position and show
        toast.adjustSize()
        self._reposition_all()
        if self._visible:
            toast.show()
        toast.start_timer()

    def set_visible(self, visible: bool) -> None:
        """Show or hide all active toasts (tracks game focus)."""
        self._visible = visible
        for t in self._active:
            if visible:
                t.show()
            else:
                t.hide()

    def clear(self) -> None:
        """Dismiss all active toasts immediately."""
        for t in list(self._active):
            self._remove_toast(t, animate=False)

    # --- Internal ---

    def _on_toast_dismissed(self, toast: ToastWidget) -> None:
        self._remove_toast(toast, animate=True)

    def _remove_toast(self, toast: ToastWidget, *, animate: bool) -> None:
        if toast in self._active:
            self._active.remove(toast)
        toast.hide()
        toast.deleteLater()
        if animate:
            self._reposition_all()

    def _reposition_all(self) -> None:
        """Recalculate positions for all active toasts based on corner setting."""
        if not self._active:
            return

        screen = self._get_screen()
        if not screen:
            return

        geom = screen.availableGeometry()
        corner = getattr(self._config, "notification_toast_corner", CORNER_BOTTOM_RIGHT)

        # Determine anchor point and stacking direction
        if corner == CORNER_BOTTOM_RIGHT:
            anchor_x = geom.right() - TOAST_WIDTH - TOAST_MARGIN
            anchor_y = geom.bottom() - TOAST_MARGIN
            direction = -1  # stack upward
        elif corner == CORNER_BOTTOM_LEFT:
            anchor_x = geom.left() + TOAST_MARGIN
            anchor_y = geom.bottom() - TOAST_MARGIN
            direction = -1
        elif corner == CORNER_TOP_RIGHT:
            anchor_x = geom.right() - TOAST_WIDTH - TOAST_MARGIN
            anchor_y = geom.top() + TOAST_MARGIN
            direction = 1  # stack downward
        elif corner == CORNER_TOP_LEFT:
            anchor_x = geom.left() + TOAST_MARGIN
            anchor_y = geom.top() + TOAST_MARGIN
            direction = 1
        else:
            anchor_x = geom.right() - TOAST_WIDTH - TOAST_MARGIN
            anchor_y = geom.bottom() - TOAST_MARGIN
            direction = -1

        # Stack toasts: newest last in _active, but visually newest closest to corner
        # For bottom corners: iterate reversed so newest is at bottom edge
        # For top corners: iterate in order so newest is at top edge
        if direction == -1:
            # Bottom corners: newest toast closest to bottom edge
            offset_y = 0
            for toast in reversed(self._active):
                h = toast.sizeHint().height()
                target_y = anchor_y - offset_y - h
                target = QPoint(anchor_x, target_y)
                self._animate_to(toast, target)
                offset_y += h + TOAST_GAP
        else:
            # Top corners: newest toast closest to top edge
            offset_y = 0
            for toast in reversed(self._active):
                h = toast.sizeHint().height()
                target_y = anchor_y + offset_y
                target = QPoint(anchor_x, target_y)
                self._animate_to(toast, target)
                offset_y += h + TOAST_GAP

    def _animate_to(self, toast: ToastWidget, target: QPoint) -> None:
        """Smoothly slide *toast* to *target* position."""
        if not toast.isVisible():
            # Not yet shown — just move directly
            toast.move(target)
            return

        current = toast.pos()
        if current == target:
            return

        anim = QPropertyAnimation(toast, b"pos", toast)
        anim.setDuration(TOAST_ANIM_MS)
        anim.setStartValue(current)
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _get_screen(self) -> QScreen | None:
        """Return the screen to position toasts on."""
        from PyQt6.QtWidgets import QApplication
        return QApplication.primaryScreen()
