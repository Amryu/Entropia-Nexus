"""VS Code-style icon sidebar for page navigation."""

import requests

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QStyleOption, QStyle
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QPainterPath

from ..theme import (
    SIDEBAR_WIDTH, SIDEBAR_INDICATOR_WIDTH,
    PRIMARY, SECONDARY, MAIN_DARK, HOVER, TEXT, TEXT_MUTED, ACCENT, BORDER, ERROR,
)
from ..icons import svg_icon, svg_pixmap, DASHBOARD, SKILLS, LOADOUT, INVENTORY, WIKI, MAPS, EXCHANGE, TRACKER, GALLERY, BELL, SETTINGS, USER

# Page definitions: (svg_data, tooltip)
PAGE_ICONS = [
    (DASHBOARD, "Dashboard"),
    (WIKI, "Wiki"),
    (MAPS, "Maps"),
    (SKILLS, "Skills"),
    (LOADOUT, "Loadout"),
    (INVENTORY, "Inventory"),
    (EXCHANGE, "Exchange"),
    (TRACKER, "Tracker"),
    (GALLERY, "Gallery"),
]

SETTINGS_ENTRY = (SETTINGS, "Settings")  # always at the bottom

ICON_SIZE = 20
AVATAR_SIZE = 32


def _button_style(active=False):
    if active:
        return f"""
            QPushButton {{
                background-color: {PRIMARY};
                border: none;
                border-left: {SIDEBAR_INDICATOR_WIDTH}px solid {ACCENT};
                font-size: 18px;
                min-width: {SIDEBAR_WIDTH}px;
                max-width: {SIDEBAR_WIDTH}px;
                min-height: 48px;
                max-height: 48px;
                padding: 0px;
                border-radius: 0px;
            }}
        """
    return f"""
        QPushButton {{
            background-color: transparent;
            border: none;
            border-left: none;
            font-size: 18px;
            min-width: {SIDEBAR_WIDTH}px;
            max-width: {SIDEBAR_WIDTH}px;
            min-height: 48px;
            max-height: 48px;
            padding: 0px;
            border-radius: 0px;
        }}
        QPushButton:hover {{
            background-color: {HOVER};
        }}
    """


def _make_round_pixmap(source: QPixmap, size: int) -> QPixmap:
    """Clip a pixmap into a circle."""
    scaled = source.scaled(
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
    # Center the scaled image
    x = (size - scaled.width()) // 2
    y = (size - scaled.height()) // 2
    painter.drawPixmap(x, y, scaled)
    painter.end()
    return result


class _BellButton(QPushButton):
    """Bell icon button with an unread-count badge overlay."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._unread = 0
        self.setToolTip("Notifications")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self.setStyleSheet(_button_style(active=False))
        self.setIcon(svg_icon(BELL, TEXT_MUTED, ICON_SIZE))

    def set_unread_count(self, count: int):
        if count != self._unread:
            self._unread = count
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._unread <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        badge_size = 16
        x = self.width() - badge_size - 6
        y = 6
        from PyQt6.QtGui import QColor, QFont
        from PyQt6.QtCore import QRect
        painter.setBrush(QColor(ERROR))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(x, y, badge_size, badge_size)
        painter.setPen(QColor(TEXT))
        font = QFont()
        font.setPixelSize(10)
        font.setBold(True)
        painter.setFont(font)
        text = str(self._unread) if self._unread < 100 else "99+"
        painter.drawText(QRect(x, y, badge_size, badge_size),
                         Qt.AlignmentFlag.AlignCenter, text)
        painter.end()


class _AvatarLoader(QThread):
    """Background thread to download user avatar image."""
    finished = pyqtSignal(QPixmap)

    def __init__(self, nexus_base_url: str, user_id: str, avatar_hash: str | None):
        super().__init__()
        self._base_url = nexus_base_url
        self._user_id = user_id
        self._avatar_hash = avatar_hash

    def run(self):
        urls = self._build_url_chain()
        for url in urls:
            pixmap = self._try_download(url)
            if pixmap and not pixmap.isNull():
                self.finished.emit(pixmap)
                return
        # All failed — emit null pixmap (sidebar will show SVG fallback)
        self.finished.emit(QPixmap())

    def _build_url_chain(self) -> list[str]:
        """Priority: custom profile pic → Discord avatar → Discord default."""
        urls = []
        # 1. Custom profile picture from Nexus
        urls.append(f"{self._base_url}/api/image/user/{self._user_id}")
        # 2. Discord avatar (if hash exists)
        if self._avatar_hash:
            urls.append(
                f"https://cdn.discordapp.com/avatars/{self._user_id}/{self._avatar_hash}.png"
            )
        # 3. Default Discord avatar
        try:
            index = int(self._user_id) % 5
        except (ValueError, TypeError):
            index = 0
        urls.append(f"https://cdn.discordapp.com/embed/avatars/{index}.png")
        return urls

    @staticmethod
    def _try_download(url: str) -> QPixmap | None:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code != 200:
                return None
            pixmap = QPixmap()
            pixmap.loadFromData(resp.content)
            return pixmap if not pixmap.isNull() else None
        except Exception:
            return None


class IconSidebar(QWidget):
    """Narrow icon sidebar for switching between pages."""

    page_changed = pyqtSignal(int)
    notification_clicked = pyqtSignal()
    profile_clicked = pyqtSignal()

    def __init__(self, *, signals=None, config=None, parent=None):
        super().__init__(parent)
        self._signals = signals
        self._config = config
        self._avatar_loader = None

        self.setFixedWidth(SIDEBAR_WIDTH)
        self.setObjectName("iconSidebar")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._buttons: list[QPushButton] = []
        self._icon_data: list[str] = []
        self._active_index = 0

        # Top page buttons
        for i, (svg_data, tooltip) in enumerate(PAGE_ICONS):
            btn = self._create_button(svg_data, tooltip, i)
            layout.addWidget(btn)
            self._buttons.append(btn)
            self._icon_data.append(svg_data)

        layout.addStretch()

        # Notification bell (above settings)
        self._bell_btn = _BellButton()
        self._bell_btn.clicked.connect(lambda: self.notification_clicked.emit())
        layout.addWidget(self._bell_btn)

        # Settings at bottom
        settings_btn = self._create_button(
            SETTINGS_ENTRY[0], SETTINGS_ENTRY[1], len(PAGE_ICONS)
        )
        layout.addWidget(settings_btn)
        self._buttons.append(settings_btn)
        self._icon_data.append(SETTINGS_ENTRY[0])

        # User avatar (below settings) — clickable to open profile
        self._avatar_btn = QPushButton()
        self._avatar_btn.setFixedSize(SIDEBAR_WIDTH, SIDEBAR_WIDTH)
        self._avatar_btn.setToolTip("Not logged in")
        self._avatar_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 0px;
                min-width: {SIDEBAR_WIDTH}px;
                max-width: {SIDEBAR_WIDTH}px;
                min-height: {SIDEBAR_WIDTH}px;
                max-height: {SIDEBAR_WIDTH}px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {HOVER};
            }}
        """)
        self._avatar_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._avatar_btn.clicked.connect(self._on_avatar_clicked)
        self._avatar_btn.hide()
        layout.addWidget(self._avatar_btn)

        # Initial active state
        self._apply_styles()

        # Listen for auth changes
        if signals:
            signals.auth_state_changed.connect(self._on_auth_changed)

    def _create_button(self, svg_data: str, tooltip: str, index: int) -> QPushButton:
        btn = QPushButton()
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        btn.clicked.connect(lambda _, i=index: self.set_active(i))
        return btn

    def set_active(self, index: int):
        """Switch to a page and update button styles."""
        if index == self._active_index:
            return
        self._active_index = index
        self._apply_styles()
        self.page_changed.emit(index)

    def set_active_no_emit(self, index: int):
        """Update visual active state without emitting page_changed."""
        self._active_index = index
        self._apply_styles()

    def set_unread_count(self, count: int):
        """Update the notification bell badge."""
        self._bell_btn.set_unread_count(count)

    def _apply_styles(self):
        for i, btn in enumerate(self._buttons):
            active = i == self._active_index
            btn.setStyleSheet(_button_style(active=active))
            color = ACCENT if active else TEXT_MUTED
            btn.setIcon(svg_icon(self._icon_data[i], color, ICON_SIZE))

    # --- Avatar ---

    def _on_auth_changed(self, state):
        if state.authenticated and state.user_id:
            # Show fallback icon while loading
            fallback = svg_pixmap(USER, TEXT_MUTED, AVATAR_SIZE)
            self._set_avatar_pixmap(_make_round_pixmap(fallback, AVATAR_SIZE))
            self._avatar_btn.setToolTip(state.username or "User")
            self._avatar_btn.show()
            # Start background download
            self._load_avatar(
                str(state.user_id),
                state.avatar_url,  # Discord avatar hash
            )
        else:
            self._avatar_btn.hide()
            self._avatar_btn.setToolTip("Not logged in")

    def _load_avatar(self, user_id: str, avatar_hash: str | None):
        if self._avatar_loader and self._avatar_loader.isRunning():
            self._avatar_loader.quit()
            self._avatar_loader.wait(1000)

        base_url = self._config.nexus_base_url if self._config else "https://entropianexus.com"
        self._avatar_loader = _AvatarLoader(base_url, user_id, avatar_hash)
        self._avatar_loader.finished.connect(self._on_avatar_loaded)
        self._avatar_loader.start()

    def _on_avatar_clicked(self):
        """Avatar button clicked — open own profile."""
        self.profile_clicked.emit()

    def _set_avatar_pixmap(self, pixmap: QPixmap):
        """Set the avatar button icon from a pixmap."""
        self._avatar_btn.setIcon(QIcon(pixmap))
        self._avatar_btn.setIconSize(QSize(AVATAR_SIZE, AVATAR_SIZE))

    def _on_avatar_loaded(self, pixmap: QPixmap):
        if pixmap.isNull():
            # Keep the SVG fallback already set
            return
        self._set_avatar_pixmap(_make_round_pixmap(pixmap, AVATAR_SIZE))

    def paintEvent(self, event):
        """Required for QWidget subclasses to honour stylesheet backgrounds."""
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
        p.end()
