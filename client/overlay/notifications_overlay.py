"""Notifications overlay — in-game scrollable notification history."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QWidget, QPushButton, QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal

from .overlay_widget import OverlayWidget
from ..ui.icons import svg_icon

if TYPE_CHECKING:
    from .overlay_manager import OverlayManager
    from ..notifications.manager import NotificationManager

# --- Overlay constants ---

OVERLAY_WIDTH = 380
OVERLAY_HEIGHT = 500

# Colors (overlay dark theme)
BG_COLOR = "rgba(20, 20, 30, 180)"
TITLE_BG = "rgba(30, 30, 45, 200)"
TEXT_COLOR = "#e0e0e0"
TEXT_DIM = "#999999"
ACCENT = "#00ccff"
ACCENT_HOVER = "#4a9eff"

_BTN_STYLE = (
    "QPushButton { background: transparent; border: none; padding: 0px; }"
)

_CLOSE_SVG = (
    '<path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59'
    ' 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>'
)

# Source colors (duplicated for overlay context — keeps this module self-contained)
_SOURCE_COLORS = {
    "global": "#fbbf24",
    "trade_chat": "#00ccff",
    "nexus": "#16a34a",
    "system": "#aaaaaa",
    "stream": "#E05050",
    "exchange": "#b366ff",
}

_SOURCE_LABELS = {
    "global": "Global",
    "trade_chat": "Trade",
    "nexus": "Nexus",
    "system": "System",
    "stream": "Stream",
    "exchange": "Exchange",
}


def _time_ago(dt):
    """Human-readable relative timestamp."""
    from datetime import datetime
    delta = datetime.now() - dt
    secs = int(delta.total_seconds())
    if secs < 60:
        return "just now"
    mins = secs // 60
    if mins < 60:
        return f"{mins}m ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def _get_action(notif):
    """Return (label, url) for a context-dependent action, or None."""
    if notif.source == "nexus":
        return ("Open on Nexus", notif.metadata.get("url", "https://entropianexus.com"))
    if notif.source == "stream":
        url = notif.metadata.get("channel_url", "")
        if url and url.lower().startswith(("https://", "http://")):
            return ("Watch", url)
    return None


# =====================================================================
# Notification row (compact overlay version)
# =====================================================================

class _OverlayNotificationRow(QWidget):
    """Single notification row for the overlay list."""

    clicked = pyqtSignal(str)  # notification id (for mark-read)

    def __init__(self, notif, parent=None):
        super().__init__(parent)
        self._notif = notif
        self._expanded = False
        self._marked_read = notif.read
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(48)
        self.setMaximumHeight(48)

        source_color = _SOURCE_COLORS.get(notif.source, TEXT_DIM)
        self._update_bg()

        main = QVBoxLayout(self)
        main.setContentsMargins(8, 4, 8, 4)
        main.setSpacing(2)

        # --- Header row ---
        header = QHBoxLayout()
        header.setSpacing(6)

        # Unread dot
        self._dot = QLabel()
        self._dot.setFixedSize(6, 6)
        self._update_dot()
        header.addWidget(self._dot)

        # Source badge
        src_lbl = QLabel(_SOURCE_LABELS.get(notif.source, "?"))
        src_lbl.setFixedWidth(38)
        src_lbl.setStyleSheet(
            f"color: {source_color}; font-size: 12px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        header.addWidget(src_lbl)

        # Title (elided)
        self._title_lbl = QLabel()
        self._title_lbl.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 12px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        fm = self._title_lbl.fontMetrics()
        self._title_lbl.setText(
            fm.elidedText(notif.title, Qt.TextElideMode.ElideRight, 180)
        )
        header.addWidget(self._title_lbl, stretch=1)

        # Time
        time_lbl = QLabel(_time_ago(notif.timestamp))
        time_lbl.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 12px;"
            f" background: transparent; border: none;"
        )
        header.addWidget(time_lbl)

        main.addLayout(header)

        # --- Body (elided, always visible) ---
        self._body_lbl = QLabel()
        self._body_lbl.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 12px;"
            f" background: transparent; border: none;"
        )
        fm2 = self._body_lbl.fontMetrics()
        self._body_lbl.setText(
            fm2.elidedText(notif.body or "", Qt.TextElideMode.ElideRight, 260)
        )
        main.addWidget(self._body_lbl)

        # --- Expanded area (hidden by default) ---
        self._expanded_area = QWidget()
        self._expanded_area.setStyleSheet("border: none; background: transparent;")
        exp_layout = QVBoxLayout(self._expanded_area)
        exp_layout.setContentsMargins(20, 2, 8, 4)
        exp_layout.setSpacing(4)

        # Full title
        title_full = QLabel(notif.title)
        title_full.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 12px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        title_full.setWordWrap(True)
        exp_layout.addWidget(title_full)

        # Full body
        if notif.body:
            body_full = QLabel(notif.body)
            body_full.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 12px;"
                f" background: transparent; border: none;"
            )
            body_full.setWordWrap(True)
            exp_layout.addWidget(body_full)

        # Action button
        action = _get_action(notif)
        if action:
            label, url = action
            from PyQt6.QtCore import QUrl
            from PyQt6.QtGui import QDesktopServices
            action_btn = QPushButton(label)
            action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            action_btn.setFixedWidth(110)
            action_btn.setStyleSheet(
                f"QPushButton {{ color: {ACCENT}; background: transparent;"
                f" border: 1px solid {ACCENT}; border-radius: 3px;"
                f" padding: 2px 8px; font-size: 12px; }}"
                f"QPushButton:hover {{ background: rgba(0, 204, 255, 30); }}"
            )
            action_btn.clicked.connect(
                lambda _checked, u=url: QDesktopServices.openUrl(QUrl(u))
            )
            exp_layout.addWidget(action_btn)

        self._expanded_area.hide()
        main.addWidget(self._expanded_area)

    def _update_bg(self):
        bg = "rgba(30, 30, 45, 160)" if self._marked_read else "rgba(40, 40, 60, 180)"
        self.setStyleSheet(
            f"_OverlayNotificationRow {{ background: {bg};"
            f" border-bottom: 1px solid rgba(80, 80, 100, 80); border-radius: 0px; }}"
            f"_OverlayNotificationRow:hover {{ background: rgba(50, 50, 70, 180); }}"
        )

    def _update_dot(self):
        if not self._marked_read:
            self._dot.setStyleSheet(
                f"background: {ACCENT}; border-radius: 3px; border: none;"
            )
        else:
            self._dot.setStyleSheet("background: transparent; border: none;")

    def mousePressEvent(self, event):
        if not self._marked_read:
            self._marked_read = True
            self._update_dot()
            self._update_bg()
            self.clicked.emit(self._notif.id)

        self._expanded = not self._expanded
        if self._expanded:
            self._body_lbl.hide()
            self._title_lbl.hide()
            self._expanded_area.show()
            self.setMaximumHeight(16777215)
        else:
            self._expanded_area.hide()
            self._body_lbl.show()
            self._title_lbl.show()
            self.setMaximumHeight(48)

        super().mousePressEvent(event)


# =====================================================================
# Notifications overlay
# =====================================================================

class NotificationsOverlay(OverlayWidget):
    """In-game overlay showing scrollable notification history."""

    read_state_changed = pyqtSignal()

    def __init__(
        self,
        *,
        config,
        config_path: str,
        notif_manager: NotificationManager,
        manager: OverlayManager | None = None,
    ):
        super().__init__(
            config=config,
            config_path=config_path,
            position_key="notifications_overlay_position",
            manager=manager,
        )
        self._notif_manager = notif_manager
        self._rows: list[_OverlayNotificationRow] = []

        self.setFixedWidth(OVERLAY_WIDTH)
        self.setFixedHeight(OVERLAY_HEIGHT)

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Title bar ---
        title_bar = QWidget()
        title_bar.setFixedHeight(32)
        title_bar.setStyleSheet(
            f"background: {TITLE_BG};"
            f" border-top-left-radius: 8px; border-top-right-radius: 8px;"
        )
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(10, 0, 6, 0)
        tb_layout.setSpacing(6)

        title_lbl = QLabel("Notifications")
        title_lbl.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 13px; font-weight: bold;"
            f" background: transparent;"
        )
        title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        tb_layout.addWidget(title_lbl, 1, Qt.AlignmentFlag.AlignVCenter)

        mark_all_btn = QPushButton("Mark all read")
        mark_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        mark_all_btn.setStyleSheet(
            f"QPushButton {{ color: {ACCENT}; background: transparent;"
            f" border: none; font-size: 12px; padding: 2px 4px; }}"
            f"QPushButton:hover {{ color: {ACCENT_HOVER}; }}"
        )
        mark_all_btn.clicked.connect(self._on_mark_all)
        tb_layout.addWidget(mark_all_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        close_btn = QPushButton()
        close_btn.setFixedSize(18, 18)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setIcon(svg_icon(_CLOSE_SVG, TEXT_DIM, 14))
        close_btn.setStyleSheet(_BTN_STYLE)
        close_btn.clicked.connect(lambda: self.set_wants_visible(False))
        tb_layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(title_bar)

        # --- Scroll area ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: rgba(20, 20, 30, 180); }}"
            f"QScrollBar:vertical {{"
            f"  background: transparent; width: 8px; margin: 0; }}"
            f"QScrollBar::handle:vertical {{"
            f"  background: rgba(100, 100, 120, 160); border-radius: 4px;"
            f"  min-height: 24px; }}"
            f"QScrollBar::handle:vertical:hover {{"
            f"  background: rgba(120, 120, 140, 200); }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{"
            f"  height: 0; }}"
            f"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{"
            f"  background: transparent; }}"
        )
        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch()
        scroll.setWidget(self._list_widget)
        layout.addWidget(scroll)

        self.hide()

    # --- Public API ---

    def refresh(self):
        """Rebuild the notification list from the manager."""
        for row in self._rows:
            self._list_layout.removeWidget(row)
            row.deleteLater()
        self._rows.clear()

        notifications = self._notif_manager.get_notifications(limit=50)
        for notif in notifications:
            row = _OverlayNotificationRow(notif)
            row.clicked.connect(self._on_row_clicked)
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
            self._rows.append(row)

    # --- Events ---

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def _on_row_clicked(self, notif_id: str):
        self._notif_manager.mark_read(notif_id)
        self.read_state_changed.emit()

    def _on_mark_all(self):
        self._notif_manager.mark_all_read()
        self.refresh()
        self.read_state_changed.emit()
