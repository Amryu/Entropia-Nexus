"""User profile overlay — always-on-top overlay showing a Nexus user profile."""

from __future__ import annotations

import threading
import webbrowser
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QPushButton,
    QScrollArea, QStackedWidget, QTextEdit, QTextBrowser, QComboBox, QLineEdit,
    QFileDialog,
)
from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QBrush

from .overlay_widget import OverlayWidget
from ..ui.icons import svg_icon

if TYPE_CHECKING:
    from .overlay_manager import OverlayManager

# --- Layout ---
PROFILE_WIDTH = 460
BODY_HEIGHT = 420
TAB_STRIP_W = 28
TAB_BTN_SIZE = 22

# --- Colors (overlay dark theme — matches detail_overlay) ---
BG_COLOR = "rgba(20, 20, 30, 180)"
TITLE_BG = "rgba(30, 30, 45, 200)"
TAB_BG = "rgba(25, 25, 40, 180)"
TAB_ACTIVE_BG = "rgba(60, 60, 90, 180)"
TAB_HOVER_BG = "rgba(50, 50, 70, 160)"
CONTENT_BG = "rgba(30, 30, 45, 160)"
TEXT_COLOR = "#e0e0e0"
TEXT_DIM = "#999999"
TEXT_BRIGHT = "#ffffff"
ACCENT = "#00ccff"
SECTION_COLOR = "#00ccff"
BADGE_BG = "rgba(50, 50, 70, 160)"
FOOTER_BG = "rgba(25, 25, 40, 160)"
SUCCESS_COLOR = "#16a34a"
ERROR_COLOR = "#ef4444"

# Image upload limit (bytes)
MAX_IMAGE_SIZE = 3 * 1024 * 1024  # 3 MB

# --- SVG icon paths (24x24 viewBox) ---
_PIN_SVG = '<path d="M16 12V4h1V2H7v2h1v8l-2 2v2h5v6l1 1 1-1v-6h5v-2z"/>'

_CLOSE_SVG = (
    '<path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59'
    ' 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>'
)

# Tab icons
_TAB_GENERAL_SVG = (
    '<circle cx="12" cy="8" r="4"/>'
    '<path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"/>'
)

_TAB_SERVICES_SVG = (
    '<path d="M20 6h-4V4c0-1.1-.9-2-2-2h-4c-1.1 0-2 .9-2 2v2H4c-1.1 0-2 .9-2 2v11'
    'c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zM10 4h4v2h-4V4z"/>'
)

_TAB_SHOPS_SVG = (
    '<path d="M20 4H4v2h16V4zm1 10v-2l-1-5H4l-1 5v2h1v6h10v-6h4v6h2v-6h1zm-9 4H6v-4h6v4z"/>'
)

_TAB_ORDERS_SVG = (
    '<path d="M6.99 11L3 15l3.99 4v-3H14v-2H6.99v-3zM21 9l-3.99-4v3H10v2h7.01v3L21 9z"/>'
)

_TAB_RENTALS_SVG = (
    '<path d="M12.65 10C11.83 7.67 9.61 6 7 6c-3.31 0-6 2.69-6 6s2.69 6 6 6c2.61 0'
    ' 4.83-1.67 5.65-4H17v4h4v-4h2v-4H12.65zM7 14c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2'
    '-.9 2-2 2z"/>'
)

_TAB_SETTINGS_SVG = (
    '<path d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7zm0 5a1.5 1.5 0 1 1 0-3'
    ' 1.5 1.5 0 0 1 0 3z"/>'
    '<path d="M21.2 10.8h-1.5a7.5 7.5 0 0 0-.6-1.5l1.1-1.1a.8.8 0 0 0 0-1.1l-2.3-2.3'
    'a.8.8 0 0 0-1.1 0l-1.1 1.1a7.5 7.5 0 0 0-1.5-.6V3.8a.8.8 0 0 0-.8-.8h-3.2'
    'a.8.8 0 0 0-.8.8v1.5a7.5 7.5 0 0 0-1.5.6L6.8 4.8a.8.8 0 0 0-1.1 0L3.4 7.1'
    'a.8.8 0 0 0 0 1.1l1.1 1.1a7.5 7.5 0 0 0-.6 1.5H2.4a.8.8 0 0 0-.8.8v3.2'
    'a.8.8 0 0 0 .8.8h1.5a7.5 7.5 0 0 0 .6 1.5l-1.1 1.1a.8.8 0 0 0 0 1.1l2.3 2.3'
    'a.8.8 0 0 0 1.1 0l1.1-1.1a7.5 7.5 0 0 0 1.5.6v1.5a.8.8 0 0 0 .8.8h3.2'
    'a.8.8 0 0 0 .8-.8v-1.5a7.5 7.5 0 0 0 1.5-.6l1.1 1.1a.8.8 0 0 0 1.1 0l2.3-2.3'
    'a.8.8 0 0 0 0-1.1l-1.1-1.1a7.5 7.5 0 0 0 .6-1.5h1.5a.8.8 0 0 0 .8-.8v-3.2'
    'a.8.8 0 0 0-.8-.8z"/>'
)

# Open-in-browser icon
_LINK_SVG = (
    '<path d="M19 19H5V5h7V3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9'
    ' 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/>'
)

_COPY_SVG = (
    '<path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2'
    ' 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>'
)

_CHECK_SVG = '<path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>'

# Globals tab icon (trophy)
_TAB_GLOBALS_SVG = (
    '<path d="M19 5h-2V3H7v2H5c-1.1 0-2 .9-2 2v1c0 2.55 1.92 4.63 4.39 4.94'
    '.63 1.5 1.67 2.71 3.11 3.36V19H8v2h8v-2h-2.5v-2.7c1.44-.65 2.48-1.86'
    ' 3.11-3.36C19.08 12.63 21 10.55 21 8V7c0-1.1-.9-2-2-2zM5 8V7h2v3.82'
    'C5.84 10.4 5 9.3 5 8zm14 0c0 1.3-.84 2.4-2 2.82V7h2v1z"/>'
)

# --- Tab IDs ---
TAB_GENERAL = "general"
TAB_SERVICES = "services"
TAB_SHOPS = "shops"
TAB_ORDERS = "orders"
TAB_RENTALS = "rentals"
TAB_GLOBALS = "globals"
TAB_SETTINGS = "settings"

# Map website defaultTab values to our tab IDs
_DEFAULT_TAB_MAP = {
    "General": TAB_GENERAL,
    "Services": TAB_SERVICES,
    "Shops": TAB_SHOPS,
    "Orders": TAB_ORDERS,
    "Rentals": TAB_RENTALS,
}

# --- Button styles ---
_BTN_STYLE = (
    "QPushButton {"
    "  background: transparent; border: none; border-radius: 3px;"
    "  padding: 0px; margin: 0px;"
    "}"
    "QPushButton:hover {"
    "  background-color: rgba(60, 60, 80, 200);"
    "}"
)


def _tab_btn_style(active: bool) -> str:
    bg = TAB_ACTIVE_BG if active else "transparent"
    return (
        f"QPushButton {{"
        f"  background-color: {bg}; border: none; border-radius: 3px;"
        f"  padding: 2px;"
        f"}}"
        f"QPushButton:hover {{"
        f"  background-color: {TAB_HOVER_BG};"
        f"}}"
    )


class _ElidedLabel(QLabel):
    """QLabel that truncates text with an ellipsis when it doesn't fit."""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._full_text = text
        self.setMinimumWidth(0)
        self.setText(text)

    def set_text(self, text: str):
        self._full_text = text
        fm = self.fontMetrics()
        elided = fm.elidedText(
            self._full_text, Qt.TextElideMode.ElideRight, self.width(),
        )
        super().setText(elided)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        fm = self.fontMetrics()
        elided = fm.elidedText(
            self._full_text, Qt.TextElideMode.ElideRight, self.width(),
        )
        super().setText(elided)


def _round_pixmap(pixmap: QPixmap, size: int) -> QPixmap:
    """Create a circular-cropped pixmap."""
    scaled = pixmap.scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    result = QPixmap(size, size)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)
    x = (scaled.width() - size) // 2
    y = (scaled.height() - size) // 2
    painter.drawPixmap(0, 0, scaled, x, y, size, size)
    painter.end()
    return result


def _separator() -> QWidget:
    sep = QWidget()
    sep.setFixedHeight(1)
    sep.setStyleSheet("background-color: rgba(100, 100, 120, 80);")
    return sep


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {SECTION_COLOR}; font-size: 10px; font-weight: bold;"
        " letter-spacing: 1px; background: transparent;"
    )
    lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
    return lbl


def _stat_row(label: str, value: str) -> QWidget:
    row = QWidget()
    row.setStyleSheet("background: transparent;")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 1, 0, 1)
    layout.setSpacing(4)
    lbl = QLabel(label)
    lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px; background: transparent;")
    layout.addWidget(lbl)
    val = QLabel(value)
    val.setStyleSheet(
        f"color: {TEXT_BRIGHT}; font-size: 12px; font-weight: bold;"
        " background: transparent;"
    )
    val.setAlignment(Qt.AlignmentFlag.AlignRight)
    layout.addWidget(val)
    return row


def _clickable_row(text: str, sub: str = "", url: str = "") -> QWidget:
    """A row with a clickable name and optional subtitle, opening a URL."""
    from PyQt6.QtWidgets import QFrame
    row = QFrame()
    row.setFrameShape(QFrame.Shape.NoFrame)
    row.setStyleSheet(
        "QFrame { background: transparent; }"
        "QFrame:hover { background-color: rgba(60, 60, 80, 100); }"
    )
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 2, 0, 2)
    layout.setSpacing(6)
    lbl = QLabel(text)
    color = ACCENT if url else TEXT_COLOR
    lbl.setStyleSheet(f"color: {color}; font-size: 12px; background: transparent;")
    if url:
        lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        lbl.mousePressEvent = lambda _ev, u=url: (webbrowser.open(u), None)[-1]
    layout.addWidget(lbl, 1)
    if sub:
        sub_lbl = QLabel(sub)
        sub_lbl.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 11px; background: transparent;"
        )
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(sub_lbl)
    return row


def _get_profile_tabs(data: dict) -> list[tuple[str, str, str]]:
    """Return (svg_path, tooltip, tab_id) for each tab based on profile data."""
    tabs = [(_TAB_GENERAL_SVG, "General", TAB_GENERAL)]
    if data.get("services"):
        tabs.append((_TAB_SERVICES_SVG, "Services", TAB_SERVICES))
    if data.get("shops"):
        tabs.append((_TAB_SHOPS_SVG, "Shops", TAB_SHOPS))
    if data.get("orders"):
        tabs.append((_TAB_ORDERS_SVG, "Exchange Orders", TAB_ORDERS))
    if data.get("rentals"):
        tabs.append((_TAB_RENTALS_SVG, "Rentals", TAB_RENTALS))
    # Globals tab shown if user has EU name (data loaded lazily)
    profile = data.get("profile", {})
    if profile.get("euName"):
        tabs.append((_TAB_GLOBALS_SVG, "Globals", TAB_GLOBALS))
    if data.get("permissions", {}).get("isOwner"):
        tabs.append((_TAB_SETTINGS_SVG, "Settings", TAB_SETTINGS))
    return tabs


class ProfileOverlayWidget(OverlayWidget):
    """Always-on-top overlay showing a user's Nexus profile."""

    open_profile_web = pyqtSignal(dict)
    open_entity = pyqtSignal(dict)
    open_exchange = pyqtSignal(int)  # item_id → open exchange overlay orderbook
    _profile_loaded = pyqtSignal(object)       # dict or None
    _avatar_loaded = pyqtSignal(object)         # QPixmap or None
    _globals_loaded = pyqtSignal(object)        # dict or None
    _globals_recent_loaded = pyqtSignal(object) # dict or None (recent poll)
    _save_result = pyqtSignal(bool, str)        # (success, error_msg)
    _upload_result = pyqtSignal(bool, str)       # (success, error_msg)

    def __init__(
        self,
        user_name: str,
        *,
        config,
        config_path: str,
        nexus_client,
        manager: OverlayManager | None = None,
    ):
        super().__init__(
            config=config,
            config_path=config_path,
            position_key="profile_overlay_position",
            manager=manager,
        )
        self._user_name = user_name
        self._nexus_client = nexus_client
        self._profile_data: dict | None = None
        self._pinned = False
        self._click_origin = None
        self._load_gen = 0
        self._globals_data: dict | None = None
        self._globals_fetched = False
        self._globals_loading = False

        # Auto-resize to content
        self.layout().setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        self._container.setFixedWidth(PROFILE_WIDTH)
        self._container.setStyleSheet(
            f"background-color: {BG_COLOR}; border-radius: 8px;"
        )

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Title bar ---
        self._title_bar = self._build_title_bar()
        layout.addWidget(self._title_bar)

        # --- Body ---
        self._body = QWidget()
        self._body.setFixedHeight(BODY_HEIGHT)
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Content row: tab strip + content stack
        content_row = QWidget()
        cr_layout = QHBoxLayout(content_row)
        cr_layout.setContentsMargins(0, 0, 0, 0)
        cr_layout.setSpacing(0)

        # Tab strip (left)
        self._tab_buttons: list[QPushButton] = []
        self._tab_defs = [(_TAB_GENERAL_SVG, "General", TAB_GENERAL)]
        self._tab_ids = [TAB_GENERAL]
        self._tab_strip_widget = self._build_tab_strip()
        cr_layout.addWidget(self._tab_strip_widget)

        # Content stack (right)
        self._content_stack = QStackedWidget()
        self._content_stack.setStyleSheet("background: transparent;")
        cr_layout.addWidget(self._content_stack, 1)

        body_layout.addWidget(content_row, 1)

        # Footer
        footer = self._build_footer()
        body_layout.addWidget(footer)
        layout.addWidget(self._body)

        # Initialize with loading placeholder
        self._init_loading_tab()
        self._switch_tab(0)

        # Connect cross-thread signals
        self._profile_loaded.connect(self._on_profile_loaded)
        self._avatar_loaded.connect(self._on_avatar_loaded)
        self._globals_loaded.connect(self._on_globals_loaded)
        self._globals_recent_loaded.connect(self._on_globals_recent_loaded)
        self._save_result.connect(self._on_save_result)
        self._upload_result.connect(self._on_upload_result)

        # Avatar label reference (set during General tab build)
        self._avatar_label: QLabel | None = None
        self._settings_widgets: dict = {}

        # Start visible
        self.set_wants_visible(True)
        self.activateWindow()

        # Fetch profile in background
        self._fetch_profile()

    # --- Properties ---

    @property
    def pinned(self) -> bool:
        return self._pinned

    # --- Title bar ---

    def _build_title_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(24)
        bar.setStyleSheet(
            f"background-color: {TITLE_BG};"
            " border-top-left-radius: 8px; border-top-right-radius: 8px;"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)

        # Pin button
        self._pin_btn = QPushButton()
        self._pin_btn.setFixedSize(18, 18)
        self._pin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pin_btn.setStyleSheet(_BTN_STYLE)
        self._pin_btn.clicked.connect(self._toggle_pin)
        self._update_pin_icon()
        layout.addWidget(self._pin_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        # Name
        self._name_label = _ElidedLabel(self._user_name)
        self._name_label.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 13px; font-weight: bold;"
            " background: transparent;"
        )
        self._name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self._name_label, 1, Qt.AlignmentFlag.AlignVCenter)

        # Copy EU name button
        self._copy_btn = QPushButton()
        self._copy_btn.setFixedSize(18, 18)
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.setIcon(svg_icon(_COPY_SVG, TEXT_DIM, 14))
        self._copy_btn.setStyleSheet(_BTN_STYLE)
        self._copy_btn.setToolTip("Copy EU name")
        self._copy_btn.clicked.connect(self._copy_eu_name)
        layout.addWidget(self._copy_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        # Type badge
        badge = QLabel("User")
        badge.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 10px;"
            f" background-color: {BADGE_BG}; border-radius: 2px;"
            f" padding: 1px 4px;"
        )
        badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)

        # Close button
        close_btn = QPushButton()
        close_btn.setFixedSize(18, 18)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setIcon(svg_icon(_CLOSE_SVG, TEXT_DIM, 14))
        close_btn.setStyleSheet(_BTN_STYLE)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        return bar

    # --- Mouse events: click-vs-drag on title bar ---

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._click_origin = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        click_origin = self._click_origin
        self._click_origin = None
        super().mouseReleaseEvent(event)

        if click_origin and event.button() == Qt.MouseButton.LeftButton:
            delta = (
                event.globalPosition().toPoint() - click_origin
            ).manhattanLength()
            if delta < 5:
                click_local = self.mapFromGlobal(click_origin)
                title_bottom = self._title_bar.mapTo(
                    self, QPoint(0, self._title_bar.height()),
                ).y()
                if click_local.y() <= title_bottom:
                    self._body.setVisible(not self._body.isVisible())

    def _toggle_pin(self):
        self._pinned = not self._pinned
        self._update_pin_icon()

    def _update_pin_icon(self):
        color = ACCENT if self._pinned else TEXT_DIM
        self._pin_btn.setIcon(svg_icon(_PIN_SVG, color, 14))
        self._pin_btn.setToolTip("Unpin" if self._pinned else "Pin")

    def _copy_eu_name(self):
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self._user_name)
        self._copy_btn.setIcon(svg_icon(_CHECK_SVG, SUCCESS_COLOR, 14))
        QTimer.singleShot(
            1500, lambda: self._copy_btn.setIcon(svg_icon(_COPY_SVG, TEXT_DIM, 14))
        )

    # --- Tab strip ---

    def _build_tab_strip(self) -> QWidget:
        strip = QWidget()
        strip.setFixedWidth(TAB_STRIP_W)
        strip.setStyleSheet(
            f"background-color: {TAB_BG};"
            " border-bottom-left-radius: 8px;"
        )
        layout = QVBoxLayout(strip)
        layout.setContentsMargins(3, 4, 3, 4)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._tab_buttons.clear()
        for i, (svg_path, tooltip, _tab_id) in enumerate(self._tab_defs):
            btn = QPushButton()
            btn.setFixedSize(TAB_BTN_SIZE, TAB_BTN_SIZE)
            btn.setIcon(svg_icon(svg_path, TEXT_DIM, 16))
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, idx=i: self._switch_tab(idx))
            btn.setStyleSheet(_tab_btn_style(False))
            layout.addWidget(btn)
            self._tab_buttons.append(btn)

        return strip

    def _rebuild_tab_strip(self, new_defs):
        """Tear down and rebuild the tab strip + content stack."""
        old_strip = self._tab_strip_widget
        parent_layout = old_strip.parent().layout()

        # Remove old strip
        parent_layout.removeWidget(old_strip)
        old_strip.deleteLater()

        # Clear content stack
        while self._content_stack.count():
            w = self._content_stack.widget(0)
            self._content_stack.removeWidget(w)
            w.deleteLater()

        # Rebuild
        self._tab_defs = new_defs
        self._tab_ids = [td[2] for td in new_defs]
        self._tab_strip_widget = self._build_tab_strip()
        parent_layout.insertWidget(0, self._tab_strip_widget)

    # --- Footer ---

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setStyleSheet(
            f"background-color: {FOOTER_BG};"
            " border-bottom-right-radius: 8px;"
        )
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(TAB_STRIP_W + 4, 2, 4, 3)
        layout.setSpacing(4)

        open_btn = QPushButton("Open Profile")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setIcon(svg_icon(_LINK_SVG, ACCENT, 12))
        open_btn.setStyleSheet(
            f"color: {ACCENT}; font-size: 11px; background: transparent;"
            " border: none; padding: 2px 4px;"
        )
        open_btn.clicked.connect(self._open_in_browser)
        layout.addWidget(open_btn)
        layout.addStretch(1)

        return footer

    def closeEvent(self, event):
        if hasattr(self, "_globals_recent_timer"):
            self._stop_globals_timers()
        super().closeEvent(event)

    def _open_in_browser(self):
        base = self._nexus_client._config.nexus_base_url.rstrip("/")
        encoded = self._user_name.replace(" ", "~")
        webbrowser.open(f"{base}/users/{encoded}")

    # --- Tab switching ---

    def _switch_tab(self, index: int):
        if index >= self._content_stack.count():
            return
        self._content_stack.setCurrentIndex(index)
        for i, btn in enumerate(self._tab_buttons):
            active = i == index
            btn.setStyleSheet(_tab_btn_style(active))
            svg_path = self._tab_defs[i][0]
            color = ACCENT if active else TEXT_DIM
            btn.setIcon(svg_icon(svg_path, color, 16))

        is_globals = (index < len(self._tab_defs)
                      and self._tab_defs[index][2] == TAB_GLOBALS)

        if is_globals:
            if not self._globals_fetched and not self._globals_loading:
                # First visit: fetch from scratch
                self._fetch_globals()
            elif self._globals_fetched and not self._globals_loading:
                # Returning to tab: stale-while-revalidate
                self._fetch_globals()
            self._start_globals_timers_if_active()
        else:
            if hasattr(self, "_globals_recent_timer"):
                self._stop_globals_timers()

    # --- Loading state ---

    def _init_loading_tab(self):
        scroll = self._make_scroll()
        layout = scroll.widget().layout()
        lbl = QLabel("Loading...")
        lbl.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)
        layout.addStretch()
        self._content_stack.addWidget(scroll)

    def _make_scroll(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical {"
            "  background: transparent; width: 6px; margin: 0;"
            "}"
            "QScrollBar::handle:vertical {"
            "  background: rgba(100,100,120,120); border-radius: 3px; min-height: 20px;"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            "  height: 0; background: none;"
            "}"
        )
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
        scroll.setWidget(content)
        return scroll

    # --- Data loading ---

    def _fetch_profile(self):
        self._load_gen += 1
        gen = self._load_gen
        nc = self._nexus_client
        name = self._user_name

        def _worker():
            data = nc.get_profile(name)
            if gen == self._load_gen:
                self._profile_loaded.emit(data)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_profile_loaded(self, data):
        if data is None:
            self._show_error("Failed to load profile", retry=True)
            return

        self._profile_data = data
        profile = data.get("profile", {})

        # Update title
        eu_name = profile.get("euName", self._user_name)
        self._name_label.set_text(eu_name)

        # Build tabs based on data
        tab_defs = _get_profile_tabs(data)
        self._rebuild_tab_strip(tab_defs)

        # Build content for each tab
        self._build_general_tab(data)

        if TAB_SERVICES in self._tab_ids:
            self._build_services_tab(data.get("services", []))
        if TAB_SHOPS in self._tab_ids:
            self._build_shops_tab(data.get("shops", []))
        if TAB_ORDERS in self._tab_ids:
            self._build_orders_tab(data.get("orders", []))
        if TAB_RENTALS in self._tab_ids:
            self._build_rentals_tab(data.get("rentals", []))
        if TAB_GLOBALS in self._tab_ids:
            self._build_globals_placeholder()
        if TAB_SETTINGS in self._tab_ids:
            self._build_settings_tab(data)

        # Switch to user's preferred default tab (or General)
        default_tab_name = profile.get("defaultTab", "General")
        default_tab_id = _DEFAULT_TAB_MAP.get(default_tab_name, TAB_GENERAL)
        if default_tab_id in self._tab_ids:
            self._switch_tab(self._tab_ids.index(default_tab_id))
        else:
            self._switch_tab(0)

        # Fetch avatar
        self._fetch_avatar(data)

    def _show_error(self, message: str, retry: bool = False):
        """Replace content with an error message."""
        while self._content_stack.count():
            w = self._content_stack.widget(0)
            self._content_stack.removeWidget(w)
            w.deleteLater()

        scroll = self._make_scroll()
        layout = scroll.widget().layout()
        lbl = QLabel(message)
        lbl.setStyleSheet(
            f"color: {ERROR_COLOR}; font-size: 12px; background: transparent;"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)
        if retry:
            btn = QPushButton("Retry")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"color: {ACCENT}; font-size: 11px; background: transparent;"
                " border: 1px solid rgba(100,100,120,150); border-radius: 3px;"
                " padding: 4px 12px;"
            )
            btn.clicked.connect(self._retry_load)
            layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        self._content_stack.addWidget(scroll)
        self._switch_tab(0)

    def _retry_load(self):
        # Clear error and re-init loading
        while self._content_stack.count():
            w = self._content_stack.widget(0)
            self._content_stack.removeWidget(w)
            w.deleteLater()
        self._init_loading_tab()
        self._switch_tab(0)
        self._fetch_profile()

    # --- Avatar loading ---

    def _fetch_avatar(self, data: dict):
        profile = data.get("profile", {})
        user_id = profile.get("id")
        base_url = self._nexus_client._config.nexus_base_url.rstrip("/")
        gen = self._load_gen

        # Determine avatar URL
        if profile.get("hasCustomImage") and user_id:
            avatar_url = f"{base_url}/api/image/user/{user_id}"
        elif profile.get("discordAvatarUrl"):
            avatar_url = profile["discordAvatarUrl"]
        else:
            self._avatar_loaded.emit(None)
            return

        def _worker():
            try:
                import requests
                resp = requests.get(avatar_url, timeout=10)
                resp.raise_for_status()
                pm = QPixmap()
                pm.loadFromData(resp.content)
                if gen == self._load_gen and not pm.isNull():
                    self._avatar_loaded.emit(pm)
                else:
                    self._avatar_loaded.emit(None)
            except Exception:
                if gen == self._load_gen:
                    self._avatar_loaded.emit(None)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_avatar_loaded(self, pixmap):
        if pixmap is None or self._avatar_label is None:
            return
        rounded = _round_pixmap(pixmap, 64)
        self._avatar_label.setPixmap(rounded)

    # --- General tab ---

    def _build_general_tab(self, data: dict):
        profile = data.get("profile", {})
        scores = data.get("scores", {})

        scroll = self._make_scroll()
        layout = scroll.widget().layout()

        # Header row: avatar + names
        header = QWidget()
        header.setStyleSheet("background: transparent;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(10)

        # Avatar
        self._avatar_label = QLabel()
        self._avatar_label.setFixedSize(64, 64)
        self._avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._avatar_label.setStyleSheet(
            "background-color: rgba(40, 40, 60, 180); border-radius: 32px;"
        )
        h_layout.addWidget(self._avatar_label, 0, Qt.AlignmentFlag.AlignTop)

        # Names column
        names = QWidget()
        names.setStyleSheet("background: transparent;")
        n_layout = QVBoxLayout(names)
        n_layout.setContentsMargins(0, 2, 0, 0)
        n_layout.setSpacing(2)

        eu_name = profile.get("euName", self._user_name)
        name_lbl = QLabel(eu_name)
        name_lbl.setStyleSheet(
            f"color: {TEXT_BRIGHT}; font-size: 14px; font-weight: bold;"
            " background: transparent;"
        )
        n_layout.addWidget(name_lbl)

        discord = profile.get("discordName", "")
        if discord:
            d_lbl = QLabel(discord)
            d_lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 11px; background: transparent;"
            )
            n_layout.addWidget(d_lbl)

        society = profile.get("society")
        if society:
            soc_name = society.get("name", "")
            soc_abbr = society.get("abbreviation", "")
            soc_text = f"{soc_name} [{soc_abbr}]" if soc_abbr else soc_name
            s_btn = QPushButton(soc_text)
            s_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            s_btn.setStyleSheet(
                f"color: {ACCENT}; font-size: 11px; background: transparent;"
                " border: none; padding: 0; text-align: left;"
            )
            s_btn.clicked.connect(
                lambda _, n=soc_name: self.open_entity.emit({"Name": n, "Type": "Society"})
            )
            n_layout.addWidget(s_btn)

        n_layout.addStretch()
        h_layout.addWidget(names, 1)
        layout.addWidget(header)

        layout.addWidget(_separator())

        # Contribution scores
        layout.addWidget(_section_label("CONTRIBUTION"))
        total = scores.get("total", 0)
        total_rank = scores.get("totalRank")
        monthly = scores.get("monthly", 0)
        monthly_rank = scores.get("monthlyRank")
        total_text = f"{total}"
        if total_rank:
            total_text += f"  (#{total_rank})"
        monthly_text = f"{monthly}"
        if monthly_rank:
            monthly_text += f"  (#{monthly_rank})"
        layout.addWidget(_stat_row("Total Score", total_text))
        layout.addWidget(_stat_row("Monthly Score", monthly_text))

        # Biography
        bio = profile.get("biographyHtml", "")
        if bio and bio.strip():
            layout.addWidget(_separator())
            layout.addWidget(_section_label("BIOGRAPHY"))
            bio_browser = QTextBrowser()
            bio_browser.setOpenExternalLinks(True)
            bio_browser.setHtml(
                f'<body style="color:{TEXT_COLOR}; font-size:12px; font-family:sans-serif;">'
                f"<style>"
                f"  a {{ color: {ACCENT}; text-decoration: none; }}"
                f"  a:hover {{ text-decoration: underline; }}"
                f"  p {{ margin: 4px 0; }}"
                f"  blockquote {{ margin: 4px 0 4px 8px; padding-left: 6px;"
                f"    border-left: 2px solid {TEXT_DIM}; color: {TEXT_DIM}; }}"
                f"  code {{ background: rgba(60,60,80,120); padding: 1px 3px;"
                f"    border-radius: 2px; }}"
                f"</style>"
                f"{bio}</body>"
            )
            bio_browser.setStyleSheet(
                "QTextBrowser { background: transparent; border: none;"
                f" color: {TEXT_COLOR}; }}"
                " QScrollBar { width: 0px; }"
            )
            bio_browser.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            # Size to content (up to a reasonable max)
            bio_browser.document().setDocumentMargin(0)
            doc_height = int(bio_browser.document().size().height()) + 4
            bio_browser.setFixedHeight(min(doc_height, 200))
            layout.addWidget(bio_browser)

        layout.addStretch()
        self._content_stack.addWidget(scroll)

    # --- Services tab ---

    def _build_services_tab(self, services: list[dict]):
        scroll = self._make_scroll()
        layout = scroll.widget().layout()
        layout.addWidget(_section_label("SERVICES"))

        base = self._nexus_client._config.nexus_base_url.rstrip("/")

        # Group by type
        by_type: dict[str, list] = {}
        for svc in services:
            t = svc.get("type", "Other")
            by_type.setdefault(t, []).append(svc)

        for svc_type, items in by_type.items():
            type_lbl = QLabel(svc_type)
            type_lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 10px; font-weight: bold;"
                " background: transparent; margin-top: 4px;"
            )
            layout.addWidget(type_lbl)
            for svc in items:
                url = f"{base}/services/{svc.get('id', '')}"
                layout.addWidget(_clickable_row(svc.get("title", ""), url=url))

        layout.addStretch()
        self._content_stack.addWidget(scroll)

    # --- Shops tab ---

    def _build_shops_tab(self, shops: list[dict]):
        scroll = self._make_scroll()
        layout = scroll.widget().layout()
        layout.addWidget(_section_label("SHOPS"))

        base = self._nexus_client._config.nexus_base_url.rstrip("/")
        for shop in shops:
            planet = shop.get("planet_name", "")
            url = f"{base}/market/shops/{shop.get('id', '')}"
            layout.addWidget(_clickable_row(
                shop.get("name", "Unknown"),
                sub=planet,
                url=url,
            ))

        layout.addStretch()
        self._content_stack.addWidget(scroll)

    # --- Orders tab ---

    def _build_orders_tab(self, orders: list[dict]):
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        buy_orders = [o for o in orders if o.get("type") == "BUY"]
        sell_orders = [o for o in orders if o.get("type") == "SELL"]

        # Toggle bar — full-width BUY / SELL switch
        toggle_bar = QWidget()
        toggle_bar.setFixedHeight(20)
        toggle_bar.setStyleSheet(f"background-color: {TAB_BG};")
        toggle_layout = QHBoxLayout(toggle_bar)
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        toggle_layout.setSpacing(0)

        sell_btn = QPushButton(f"Sell Orders ({len(sell_orders)})")
        buy_btn = QPushButton(f"Buy Orders ({len(buy_orders)})")
        for btn in (sell_btn, buy_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(20)
        toggle_layout.addWidget(sell_btn)
        toggle_layout.addWidget(buy_btn)
        outer.addWidget(toggle_bar)

        # Stacked lists
        order_stack = QStackedWidget()

        base = self._nexus_client._config.nexus_base_url.rstrip("/")

        for order_list in (sell_orders, buy_orders):
            scroll = self._make_scroll()
            layout = scroll.widget().layout()
            for order in order_list:
                layout.addWidget(self._build_order_row(order, base))
            if not order_list:
                empty = QLabel("No orders")
                empty.setStyleSheet(
                    f"color: {TEXT_DIM}; font-size: 11px; background: transparent;"
                    " padding: 8px;"
                )
                empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(empty)
            layout.addStretch()
            order_stack.addWidget(scroll)

        outer.addWidget(order_stack, 1)

        # Toggle button styling and connection
        active_style = (
            f"QPushButton {{ background-color: #0077aa; color: #fff;"
            f" font-size: 10px; font-weight: bold; border: none; padding: 0px 4px; }}"
        )
        inactive_style = (
            f"QPushButton {{ background-color: {TAB_BG}; color: {TEXT_DIM};"
            f" font-size: 10px; border: none; padding: 0px 4px; }}"
            f"QPushButton:hover {{ background-color: {TAB_HOVER_BG}; }}"
        )

        def _switch(idx):
            order_stack.setCurrentIndex(idx)
            sell_btn.setStyleSheet(active_style if idx == 0 else inactive_style)
            buy_btn.setStyleSheet(active_style if idx == 1 else inactive_style)

        sell_btn.clicked.connect(lambda: _switch(0))
        buy_btn.clicked.connect(lambda: _switch(1))

        # Default to Sell if any exist, else Buy
        _switch(0 if sell_orders else 1)

        self._content_stack.addWidget(container)

    def _build_order_row(self, order: dict, base_url: str) -> QWidget:
        """Build a single order row with item name, details, and exchange link."""
        details = order.get("details") or {}
        name = details.get("item_name", "") or order.get("item_name", "Unknown")
        markup = order.get("markup", 100)
        qty = order.get("quantity", 0)
        item_type = order.get("item_type", "")
        planet = order.get("planet") or ""
        state = order.get("computed_state", "active")
        item_id = order.get("item_id")

        # Exchange URL for the item
        url = ""
        if item_id and item_type:
            type_slug = item_type.lower().replace(" ", "-")
            url = f"{base_url}/market/exchange/{type_slug}/{item_id}"

        row = QWidget()
        row.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(1)

        # Top line: item name + markup
        top = QHBoxLayout()
        top.setSpacing(6)
        name_lbl = QLabel(name)
        clickable = item_id is not None
        color = ACCENT if clickable else TEXT_COLOR
        name_lbl.setStyleSheet(
            f"color: {color}; font-size: 12px; background: transparent;"
        )
        if clickable:
            name_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            name_lbl.mousePressEvent = lambda _ev, iid=item_id: self.open_exchange.emit(iid)
        top.addWidget(name_lbl, 1)

        # Right side: quantity + markup
        right_parts = []
        if qty > 1:
            right_parts.append(f"x{qty}")
        right_parts.append(f"{markup}%")
        right_lbl = QLabel("  ".join(right_parts))
        right_lbl.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 11px; background: transparent;"
        )
        right_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        top.addWidget(right_lbl)
        layout.addLayout(top)

        # Bottom line: type + planet + status
        sub_parts = []
        if item_type:
            sub_parts.append(item_type)
        if planet:
            sub_parts.append(planet)
        sub_text = " · ".join(sub_parts)

        if sub_text or state != "active":
            bottom = QHBoxLayout()
            bottom.setSpacing(4)
            if sub_text:
                sub_lbl = QLabel(sub_text)
                sub_lbl.setStyleSheet(
                    f"color: {TEXT_DIM}; font-size: 10px; background: transparent;"
                )
                bottom.addWidget(sub_lbl, 1)
            else:
                bottom.addStretch(1)
            if state and state != "active":
                state_color = "#f59e0b" if state == "stale" else ERROR_COLOR
                state_lbl = QLabel(state.capitalize())
                state_lbl.setStyleSheet(
                    f"color: {state_color}; font-size: 10px; background: transparent;"
                )
                state_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
                bottom.addWidget(state_lbl)
            layout.addLayout(bottom)

        return row

    # --- Rentals tab ---

    def _build_rentals_tab(self, rentals: list[dict]):
        scroll = self._make_scroll()
        layout = scroll.widget().layout()
        layout.addWidget(_section_label("RENTALS"))

        base = self._nexus_client._config.nexus_base_url.rstrip("/")
        for rental in rentals:
            title = rental.get("title", "")
            ppd = float(rental.get("price_per_day", 0))
            url = f"{base}/services/rentals/{rental.get('id', '')}"
            layout.addWidget(_clickable_row(
                title,
                sub=f"{ppd:.2f} PED/day",
                url=url,
            ))

        layout.addStretch()
        self._content_stack.addWidget(scroll)

    # --- Globals tab (lazy-loaded, auto-refreshed) ---

    _GLOBALS_RECENT_INTERVAL = 10_000     # 10 seconds
    _GLOBALS_FULL_INTERVAL = 900_000      # 15 minutes

    def _build_globals_placeholder(self):
        """Add a loading placeholder for the Globals tab."""
        scroll = self._make_scroll()
        layout = scroll.widget().layout()
        lbl = QLabel("Loading...")
        lbl.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)
        layout.addStretch()
        self._content_stack.addWidget(scroll)
        self._globals_stack_index = self._content_stack.count() - 1

        # Per-section toggle state and refresh timers
        self._globals_sort_best = {"hunting": False, "mining": False, "crafting": False}
        self._globals_recent_timer = QTimer(self)
        self._globals_recent_timer.timeout.connect(self._poll_globals)
        self._globals_full_timer = QTimer(self)
        self._globals_full_timer.timeout.connect(self._poll_globals_full)

    def _fetch_globals(self):
        """Fetch globals data in background thread."""
        self._globals_loading = True
        profile = self._profile_data.get("profile", {}) if self._profile_data else {}
        eu_name = profile.get("euName", self._user_name)

        def _do():
            data = self._nexus_client.get_player_globals(eu_name)
            self._globals_loaded.emit(data)

        threading.Thread(target=_do, daemon=True).start()

    def _on_globals_loaded(self, data):
        """Replace the globals placeholder with actual content."""
        self._globals_loading = False
        self._globals_fetched = True
        self._globals_data = data

        if not hasattr(self, "_globals_stack_index"):
            return

        idx = self._globals_stack_index

        old = self._content_stack.widget(idx)
        if old:
            # Check BEFORE insert/remove — the operations shift currentIndex
            was_showing_globals = self._content_stack.currentIndex() == idx
            new_widget = self._build_globals_content(data)
            self._content_stack.insertWidget(idx, new_widget)
            self._content_stack.removeWidget(old)
            old.deleteLater()

            if was_showing_globals:
                self._content_stack.setCurrentIndex(idx)

        # Start refresh timers if globals tab is active
        self._start_globals_timers_if_active()

    def _start_globals_timers_if_active(self):
        """Start timers only when the globals tab is the active tab."""
        if not hasattr(self, "_globals_stack_index"):
            return
        if self._content_stack.currentIndex() == self._globals_stack_index:
            if not self._globals_recent_timer.isActive():
                self._globals_recent_timer.start(self._GLOBALS_RECENT_INTERVAL)
            if not self._globals_full_timer.isActive():
                self._globals_full_timer.start(self._GLOBALS_FULL_INTERVAL)

    def _stop_globals_timers(self):
        self._globals_recent_timer.stop()
        self._globals_full_timer.stop()

    def _poll_globals(self):
        """Lightweight poll: fetch data and update recent section only."""
        if self._globals_loading:
            return
        self._globals_loading = True
        profile = self._profile_data.get("profile", {}) if self._profile_data else {}
        eu_name = profile.get("euName", self._user_name)

        def _do():
            data = self._nexus_client.get_player_globals(eu_name)
            self._globals_recent_loaded.emit(data)

        threading.Thread(target=_do, daemon=True).start()

    def _poll_globals_full(self):
        """Full poll: fetch and rebuild everything."""
        if self._globals_loading:
            return
        self._fetch_globals()

    def _on_globals_recent_loaded(self, data):
        """Update only the recent section with fresh data."""
        self._globals_loading = False
        if data and "recent" in data:
            self._globals_data = data
            self._refresh_recent_section(data.get("recent", []))

    def _refresh_recent_section(self, recent: list[dict]):
        """Update the recent globals container in-place."""
        if not hasattr(self, "_recent_container"):
            return
        # Clear and repopulate
        layout = self._recent_container.layout()
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._populate_recent(layout, recent)

    def _build_globals_content(self, data: dict | None) -> QWidget:
        """Build the globals tab content widget."""
        scroll = self._make_scroll()
        layout = scroll.widget().layout()

        if not data or "summary" not in data:
            lbl = QLabel("No globals recorded")
            lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)
            layout.addStretch()
            return scroll

        summary = data["summary"]

        # --- Summary ---
        layout.addWidget(_section_label("SUMMARY"))
        total = summary.get("total_count", 0)
        total_value = summary.get("total_value", 0)
        hof_count = summary.get("hof_count", 0)
        layout.addWidget(_stat_row("Globals", str(total)))
        layout.addWidget(_stat_row("HoFs", str(hof_count)))
        layout.addWidget(_stat_row("Total Value", f"{total_value:,.0f} PED"))

        kill_count = summary.get("kill_count", 0) + summary.get("team_kill_count", 0)
        deposit_count = summary.get("deposit_count", 0)
        craft_count = summary.get("craft_count", 0)
        layout.addWidget(_stat_row("Hunting", str(kill_count)))
        layout.addWidget(_stat_row("Mining", str(deposit_count)))
        layout.addWidget(_stat_row("Crafting", str(craft_count)))

        # --- Recent globals ---
        recent = data.get("recent", [])
        if recent:
            layout.addWidget(_separator())
            layout.addWidget(_section_label("RECENT"))
            self._recent_container = QWidget()
            self._recent_container.setStyleSheet("background: transparent;")
            rc_layout = QVBoxLayout(self._recent_container)
            rc_layout.setContentsMargins(0, 0, 0, 0)
            rc_layout.setSpacing(2)
            self._populate_recent(rc_layout, recent)
            layout.addWidget(self._recent_container)

        # --- Top sections with Total/Best toggle ---
        hunting = data.get("hunting", [])
        resources = data.get("mining", {}).get("resources", [])
        crafts = data.get("crafting", {}).get("items", [])

        if hunting:
            layout.addWidget(_separator())
            header, container = self._build_top_section_header("TOP HUNTING", "hunting")
            layout.addWidget(header)
            self._hunting_container = container
            layout.addWidget(container)
            self._populate_hunting(container, hunting)

        if resources:
            layout.addWidget(_separator())
            header, container = self._build_top_section_header("TOP MINING", "mining")
            layout.addWidget(header)
            self._mining_container = container
            layout.addWidget(container)
            self._populate_mining(container, resources)

        if crafts:
            layout.addWidget(_separator())
            header, container = self._build_top_section_header("TOP CRAFTING", "crafting")
            layout.addWidget(header)
            self._crafting_container = container
            layout.addWidget(container)
            self._populate_crafting(container, crafts)

        # --- View all ---
        layout.addWidget(_separator())
        base = self._nexus_client._config.nexus_base_url.rstrip("/")
        profile = self._profile_data.get("profile", {}) if self._profile_data else {}
        eu_name = profile.get("euName", self._user_name)
        url = f"{base}/globals/player/{eu_name.replace(' ', '~')}"
        view_btn = QPushButton("View All Globals")
        view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        view_btn.setStyleSheet(
            f"color: {ACCENT}; font-size: 11px;"
            " background: transparent; border: 1px solid rgba(100,100,120,150);"
            " border-radius: 3px; padding: 4px 8px;"
        )
        view_btn.clicked.connect(lambda _=None, u=url: webbrowser.open(u))
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(view_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()
        return scroll

    # --- Recent section helpers ---

    def _populate_recent(self, layout: QVBoxLayout, recent: list[dict]):
        """Fill the recent globals container with up to 5 entries."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        for entry in recent[:5]:
            target = entry.get("target", "Unknown")
            value = entry.get("value", 0)
            gtype = entry.get("type", "")
            hof = entry.get("hof", False)
            ts_str = entry.get("timestamp", "")

            # Relative time
            age = ""
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str)
                    delta = now - ts
                    secs = int(delta.total_seconds())
                    if secs < 60:
                        age = f"{secs}s ago"
                    elif secs < 3600:
                        age = f"{secs // 60}m ago"
                    elif secs < 86400:
                        age = f"{secs // 3600}h ago"
                    else:
                        age = f"{secs // 86400}d ago"
                except (ValueError, TypeError):
                    pass

            # Type badge color
            type_colors = {
                "kill": "#ef4444", "team_kill": "#ef4444",
                "deposit": "#3b82f6", "craft": "#a855f7",
                "rare_item": "#f59e0b", "discovery": "#10b981",
            }
            badge_color = type_colors.get(gtype, TEXT_DIM)
            type_label = gtype.replace("_", " ").title() if gtype else ""

            row = QWidget()
            row.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 1, 0, 1)
            rl.setSpacing(4)

            # Type badge
            badge = QLabel(type_label)
            badge.setFixedWidth(60)
            badge.setStyleSheet(
                f"color: {badge_color}; font-size: 9px; font-weight: bold;"
                " background: transparent;"
            )
            rl.addWidget(badge)

            # Target name
            name_lbl = QLabel(target)
            name_lbl.setStyleSheet(
                f"color: {TEXT_COLOR}; font-size: 11px; background: transparent;"
            )
            rl.addWidget(name_lbl, 1)

            # Value + HoF badge
            val_text = f"{value:,.0f} PED"
            if hof:
                val_text += " HoF"
            val_lbl = QLabel(val_text)
            val_color = "#f59e0b" if hof else TEXT_DIM
            val_lbl.setStyleSheet(
                f"color: {val_color}; font-size: 11px; background: transparent;"
            )
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            rl.addWidget(val_lbl)

            # Age
            if age:
                age_lbl = QLabel(age)
                age_lbl.setFixedWidth(45)
                age_lbl.setStyleSheet(
                    f"color: {TEXT_DIM}; font-size: 10px; background: transparent;"
                )
                age_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
                rl.addWidget(age_lbl)

            layout.addWidget(row)

    # --- Top sections with Total/Best toggle ---

    def _build_top_section_header(self, title: str, section_key: str) -> tuple[QWidget, QWidget]:
        """Build a section header with Total/Best toggle. Returns (header, container)."""
        header = QWidget()
        header.setStyleSheet("background: transparent;")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(4)

        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"color: {SECTION_COLOR}; font-size: 10px; font-weight: bold;"
            " letter-spacing: 1px; background: transparent;"
        )
        hl.addWidget(lbl, 1)

        active_style = (
            f"color: {TEXT_BRIGHT}; font-size: 9px; font-weight: bold;"
            f" background: {TAB_ACTIVE_BG}; border: none;"
            " border-radius: 2px; padding: 1px 5px;"
        )
        inactive_style = (
            f"color: {TEXT_DIM}; font-size: 9px;"
            " background: transparent; border: none;"
            " border-radius: 2px; padding: 1px 5px;"
        )

        is_best = self._globals_sort_best.get(section_key, False)
        total_btn = QPushButton("Total")
        best_btn = QPushButton("Best")
        total_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        best_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        total_btn.setStyleSheet(inactive_style if is_best else active_style)
        best_btn.setStyleSheet(active_style if is_best else inactive_style)
        hl.addWidget(total_btn)
        hl.addWidget(best_btn)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        QVBoxLayout(container).setContentsMargins(0, 0, 0, 0)
        container.layout().setSpacing(2)

        def _set_mode(best: bool):
            self._globals_sort_best[section_key] = best
            total_btn.setStyleSheet(inactive_style if best else active_style)
            best_btn.setStyleSheet(active_style if best else inactive_style)
            self._refresh_top_section(section_key)

        total_btn.clicked.connect(lambda: _set_mode(False))
        best_btn.clicked.connect(lambda: _set_mode(True))

        return header, container

    def _refresh_top_section(self, section_key: str):
        """Re-populate a single top section using its current sort mode."""
        data = self._globals_data
        if not data:
            return
        if section_key == "hunting" and hasattr(self, "_hunting_container"):
            self._clear_container(self._hunting_container)
            self._populate_hunting(self._hunting_container, data.get("hunting", []))
        elif section_key == "mining" and hasattr(self, "_mining_container"):
            self._clear_container(self._mining_container)
            self._populate_mining(
                self._mining_container,
                data.get("mining", {}).get("resources", []),
            )
        elif section_key == "crafting" and hasattr(self, "_crafting_container"):
            self._clear_container(self._crafting_container)
            self._populate_crafting(
                self._crafting_container,
                data.get("crafting", {}).get("items", []),
            )

    @staticmethod
    def _clear_container(container: QWidget):
        layout = container.layout()
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _populate_hunting(self, container: QWidget, hunting: list[dict]):
        layout = container.layout()
        best = self._globals_sort_best["hunting"]
        if best:
            items = sorted(hunting, key=lambda m: m.get("best_value", 0), reverse=True)
        else:
            items = hunting  # already sorted by total_value from server
        for mob in items[:5]:
            name = mob.get("target", "Unknown")
            if best:
                value = mob.get("best_value", 0)
                # Find the maturity with the highest best_value
                maturities = mob.get("maturities", [])
                mat_name = ""
                if maturities:
                    top_mat = max(maturities, key=lambda m: m.get("best_value", 0))
                    mat_name = top_mat.get("target", "")
                if mat_name and mat_name != name:
                    sub = f"{mat_name} · {value:,.0f} PED"
                else:
                    sub = f"{value:,.0f} PED"
            else:
                kills = mob.get("kills", 0)
                value = mob.get("total_value", 0)
                sub = f"{kills} kills · {value:,.0f} PED"
            layout.addWidget(_clickable_row(name, sub=sub))

    def _populate_mining(self, container: QWidget, resources: list[dict]):
        layout = container.layout()
        best = self._globals_sort_best["mining"]
        if best:
            items = sorted(resources, key=lambda r: r.get("best_value", 0), reverse=True)
        else:
            items = resources
        for res in items[:5]:
            name = res.get("target", "Unknown")
            if best:
                value = res.get("best_value", 0)
                sub = f"{value:,.0f} PED"
            else:
                finds = res.get("finds", 0)
                value = res.get("total_value", 0)
                sub = f"{finds} finds · {value:,.0f} PED"
            layout.addWidget(_clickable_row(name, sub=sub))

    def _populate_crafting(self, container: QWidget, crafts: list[dict]):
        layout = container.layout()
        best = self._globals_sort_best["crafting"]
        if best:
            items = sorted(crafts, key=lambda c: c.get("best_value", 0), reverse=True)
        else:
            items = crafts
        for item in items[:5]:
            name = item.get("target", "Unknown")
            if best:
                value = item.get("best_value", 0)
                sub = f"{value:,.0f} PED"
            else:
                count = item.get("crafts", 0)
                value = item.get("total_value", 0)
                sub = f"{count} crafts · {value:,.0f} PED"
            layout.addWidget(_clickable_row(name, sub=sub))

    # --- Settings tab (owner only) ---

    def _build_settings_tab(self, data: dict):
        profile = data.get("profile", {})

        scroll = self._make_scroll()
        layout = scroll.widget().layout()

        # Profile image section
        layout.addWidget(_section_label("PROFILE IMAGE"))
        img_row = QHBoxLayout()
        img_row.setSpacing(8)

        self._settings_avatar = QLabel()
        self._settings_avatar.setFixedSize(80, 80)
        self._settings_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._settings_avatar.setStyleSheet(
            "background-color: rgba(40, 40, 60, 180); border-radius: 40px;"
        )
        img_row.addWidget(self._settings_avatar)

        img_btns = QVBoxLayout()
        img_btns.setSpacing(4)
        upload_btn = QPushButton("Upload Image")
        upload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        upload_btn.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 11px;"
            " background: rgba(50, 50, 70, 180); border: 1px solid rgba(100,100,120,150);"
            " border-radius: 3px; padding: 4px 8px;"
        )
        upload_btn.clicked.connect(self._on_upload_image)
        img_btns.addWidget(upload_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 11px;"
            " background: transparent; border: 1px solid rgba(100,100,120,100);"
            " border-radius: 3px; padding: 4px 8px;"
        )
        remove_btn.clicked.connect(self._on_remove_image)
        remove_btn.setVisible(profile.get("hasCustomImage", False))
        img_btns.addWidget(remove_btn)
        self._settings_widgets["remove_btn"] = remove_btn

        img_btns.addStretch()
        img_row.addLayout(img_btns)
        img_row.addStretch()
        layout.addLayout(img_row)

        # Upload status label
        self._upload_status = QLabel("")
        self._upload_status.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 10px; background: transparent;"
        )
        self._upload_status.setVisible(False)
        layout.addWidget(self._upload_status)

        layout.addWidget(_separator())

        # Biography
        layout.addWidget(_section_label("BIOGRAPHY"))
        self._bio_edit = QTextEdit()
        self._bio_edit.setMaximumHeight(80)
        self._bio_edit.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 12px;"
            " background: rgba(40, 40, 55, 200); border: 1px solid rgba(100,100,120,150);"
            " border-radius: 3px; padding: 4px;"
        )
        # Strip HTML for editing
        import re
        bio_html = profile.get("biographyHtml", "")
        plain = re.sub(r'<[^>]+>', '', bio_html).strip() if bio_html else ""
        self._bio_edit.setPlainText(plain)
        layout.addWidget(self._bio_edit)

        layout.addWidget(_separator())

        # Default tab
        layout.addWidget(_section_label("DEFAULT TAB"))
        self._default_tab_combo = QComboBox()
        tab_options = ["General", "Services", "Shops", "Orders", "Rentals"]
        self._default_tab_combo.addItems(tab_options)
        current_default = profile.get("defaultTab", "General")
        if current_default in tab_options:
            self._default_tab_combo.setCurrentText(current_default)
        self._default_tab_combo.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 12px;"
            " background: rgba(40, 40, 55, 200); border: 1px solid rgba(100,100,120,150);"
            " border-radius: 3px; padding: 3px 6px;"
        )
        layout.addWidget(self._default_tab_combo)

        layout.addWidget(_separator())

        # Showcase loadout
        layout.addWidget(_section_label("SHOWCASE LOADOUT"))
        self._showcase_input = QLineEdit()
        self._showcase_input.setPlaceholderText("Share code (optional)")
        self._showcase_input.setText(profile.get("showcaseLoadoutCode", "") or "")
        self._showcase_input.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 12px;"
            " background: rgba(40, 40, 55, 200); border: 1px solid rgba(100,100,120,150);"
            " border-radius: 3px; padding: 4px 6px;"
        )
        layout.addWidget(self._showcase_input)

        layout.addWidget(_separator())

        # Society
        layout.addWidget(_section_label("SOCIETY"))
        society = profile.get("society")
        society_id = profile.get("societyId")
        base = self._nexus_client._config.nexus_base_url.rstrip("/")

        if society and society_id and society_id > 0:
            # Member of a society
            soc_name = society.get("name", "")
            soc_abbr = society.get("abbreviation", "")
            soc_text = f"{soc_name} [{soc_abbr}]" if soc_abbr else soc_name
            soc_lbl = QLabel(soc_text)
            soc_lbl.setStyleSheet(
                f"color: {ACCENT}; font-size: 12px; background: transparent;"
            )
            layout.addWidget(soc_lbl)
            view_soc_btn = QPushButton("View Society")
            view_soc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            view_soc_btn.setStyleSheet(
                f"color: {TEXT_COLOR}; font-size: 11px;"
                " background: rgba(50, 50, 70, 180); border: 1px solid rgba(100,100,120,150);"
                " border-radius: 3px; padding: 4px 8px;"
            )
            soc_url = f"{base}/societies/{soc_name.replace(' ', '~')}"
            view_soc_btn.clicked.connect(lambda _=None, u=soc_url: webbrowser.open(u))
            soc_btn_row = QHBoxLayout()
            soc_btn_row.addWidget(view_soc_btn)
            soc_btn_row.addStretch()
            layout.addLayout(soc_btn_row)
        elif society_id == -1:
            # Pending join request
            pending_soc = profile.get("pendingSocietyRequest")
            pending_name = society.get("name", "Unknown") if society else "Unknown"
            pending_lbl = QLabel(f"Pending: {pending_name}")
            pending_lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
                " font-style: italic;"
            )
            layout.addWidget(pending_lbl)
        else:
            # No society
            no_soc_lbl = QLabel("No society")
            no_soc_lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
            )
            layout.addWidget(no_soc_lbl)
            join_btn = QPushButton("Join / Create")
            join_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            join_btn.setStyleSheet(
                f"color: {TEXT_COLOR}; font-size: 11px;"
                " background: rgba(50, 50, 70, 180); border: 1px solid rgba(100,100,120,150);"
                " border-radius: 3px; padding: 4px 8px;"
            )
            eu_name = profile.get("euName", self._user_name)
            profile_url = f"{base}/users/{eu_name.replace(' ', '~')}"
            join_btn.clicked.connect(lambda _=None, u=profile_url: webbrowser.open(u))
            join_row = QHBoxLayout()
            join_row.addWidget(join_btn)
            join_row.addStretch()
            layout.addLayout(join_row)

        # Save button
        layout.addSpacing(8)
        save_row = QHBoxLayout()
        save_row.addStretch()
        save_btn = QPushButton("Save Settings")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(
            f"color: {TEXT_BRIGHT}; font-size: 12px; font-weight: bold;"
            f" background: rgba(6, 182, 212, 180); border: none;"
            " border-radius: 3px; padding: 6px 16px;"
        )
        save_btn.clicked.connect(self._on_save_settings)
        save_row.addWidget(save_btn)
        self._settings_widgets["save_btn"] = save_btn
        layout.addLayout(save_row)

        # Save status
        self._save_status = QLabel("")
        self._save_status.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 10px; background: transparent;"
        )
        self._save_status.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._save_status.setVisible(False)
        layout.addWidget(self._save_status)

        layout.addStretch()
        self._content_stack.addWidget(scroll)

        # Copy avatar to settings preview
        if self._avatar_label and self._avatar_label.pixmap() and not self._avatar_label.pixmap().isNull():
            pm = self._avatar_label.pixmap()
            self._settings_avatar.setPixmap(_round_pixmap(pm, 80))

    # --- Settings actions ---

    def _on_upload_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Profile Image", "",
            "Images (*.png *.jpg *.jpeg *.webp *.gif);;All Files (*)",
        )
        if not path:
            return

        try:
            with open(path, "rb") as f:
                data = f.read()
        except IOError:
            return

        if len(data) > MAX_IMAGE_SIZE:
            self._upload_status.setText("Image too large (max 3 MB)")
            self._upload_status.setStyleSheet(
                f"color: {ERROR_COLOR}; font-size: 10px; background: transparent;"
            )
            self._upload_status.setVisible(True)
            QTimer.singleShot(5000, lambda: self._upload_status.setVisible(False))
            return

        # Determine content type
        import mimetypes
        ct, _ = mimetypes.guess_type(path)
        if not ct or not ct.startswith("image/"):
            ct = "application/octet-stream"

        profile = self._profile_data.get("profile", {})
        user_id = profile.get("id")
        if not user_id:
            return

        self._upload_status.setText("Uploading...")
        self._upload_status.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 10px; background: transparent;"
        )
        self._upload_status.setVisible(True)

        nc = self._nexus_client

        def _worker():
            result = nc.upload_profile_image(user_id, data, ct)
            self._upload_result.emit(result is not None, "" if result else "Upload failed")

        threading.Thread(target=_worker, daemon=True).start()

    def _on_upload_result(self, success: bool, error: str):
        if success:
            self._upload_status.setText("Image uploaded")
            self._upload_status.setStyleSheet(
                f"color: {SUCCESS_COLOR}; font-size: 10px; background: transparent;"
            )
            self._upload_status.setVisible(True)
            QTimer.singleShot(3000, lambda: self._upload_status.setVisible(False))
            # Show remove button
            if "remove_btn" in self._settings_widgets:
                self._settings_widgets["remove_btn"].setVisible(True)
            # Reload avatar
            if self._profile_data:
                # Force custom image flag
                self._profile_data.setdefault("profile", {})["hasCustomImage"] = True
                self._fetch_avatar(self._profile_data)
        else:
            self._upload_status.setText(error or "Upload failed")
            self._upload_status.setStyleSheet(
                f"color: {ERROR_COLOR}; font-size: 10px; background: transparent;"
            )
            self._upload_status.setVisible(True)
            QTimer.singleShot(5000, lambda: self._upload_status.setVisible(False))

    def _on_remove_image(self):
        profile = (self._profile_data or {}).get("profile", {})
        user_id = profile.get("id")
        if not user_id:
            return

        nc = self._nexus_client

        def _worker():
            ok = nc.delete_profile_image(user_id)
            self._upload_result.emit(ok, "" if ok else "Failed to remove image")

        threading.Thread(target=_worker, daemon=True).start()

        # Clear avatar immediately
        if self._avatar_label:
            self._avatar_label.clear()
        if hasattr(self, "_settings_avatar"):
            self._settings_avatar.clear()
        if "remove_btn" in self._settings_widgets:
            self._settings_widgets["remove_btn"].setVisible(False)

    def _on_save_settings(self):
        if not self._profile_data:
            return

        # Collect data
        bio_text = self._bio_edit.toPlainText().strip()
        bio_html = f"<p>{bio_text}</p>" if bio_text else ""
        default_tab = self._default_tab_combo.currentText()
        showcase = self._showcase_input.text().strip() or None

        payload = {
            "biographyHtml": bio_html,
            "defaultTab": default_tab,
            "showcaseLoadoutCode": showcase,
        }

        save_btn = self._settings_widgets.get("save_btn")
        if save_btn:
            save_btn.setEnabled(False)
            save_btn.setText("Saving...")

        nc = self._nexus_client
        name = self._user_name

        def _worker():
            result = nc.update_profile(name, payload)
            self._save_result.emit(result is not None, "" if result else "Save failed")

        threading.Thread(target=_worker, daemon=True).start()

    def _on_save_result(self, success: bool, error: str):
        save_btn = self._settings_widgets.get("save_btn")
        if save_btn:
            save_btn.setEnabled(True)
            save_btn.setText("Save Settings")

        if success:
            self._save_status.setText("Saved")
            self._save_status.setStyleSheet(
                f"color: {SUCCESS_COLOR}; font-size: 10px; background: transparent;"
            )
            self._save_status.setVisible(True)
            QTimer.singleShot(3000, lambda: self._save_status.setVisible(False))
        else:
            self._save_status.setText(error or "Save failed")
            self._save_status.setStyleSheet(
                f"color: {ERROR_COLOR}; font-size: 10px; background: transparent;"
            )
            self._save_status.setVisible(True)
            QTimer.singleShot(5000, lambda: self._save_status.setVisible(False))

    # --- Overrides ---

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setWidth(PROFILE_WIDTH)
        return hint
