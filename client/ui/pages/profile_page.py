"""Profile page — view and edit user profiles."""

from __future__ import annotations

import re
import threading
import webbrowser
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QTabWidget, QStackedWidget, QTextBrowser,
    QTextEdit, QLineEdit, QComboBox, QFileDialog, QApplication,
    QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QCursor, QColor

from ..theme import (
    PRIMARY, SECONDARY, MAIN_DARK, HOVER, BORDER, BORDER_HOVER,
    TEXT, TEXT_MUTED, ACCENT, ACCENT_HOVER, ACCENT_LIGHT, DISABLED,
    SUCCESS, SUCCESS_BG, ERROR, ERROR_BG, WARNING, FONT_FAMILY,
)
from ..icons import svg_icon, svg_pixmap
from ...core.logger import get_logger

if TYPE_CHECKING:
    from ...api.nexus_client import NexusClient

log = get_logger("ProfilePage")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AVATAR_SIZE = 100
AVATAR_BORDER_RADIUS = 50  # circular

# Image upload limit (bytes)
MAX_IMAGE_SIZE = 3 * 1024 * 1024  # 3 MB

# Globals auto-refresh intervals
GLOBALS_RECENT_INTERVAL_MS = 10_000    # 10 seconds
GLOBALS_FULL_INTERVAL_MS = 900_000     # 15 minutes

# Social icon colors
SOCIAL_DISCORD_COLOR = "#5865F2"
SOCIAL_YOUTUBE_COLOR = "#FF0000"
SOCIAL_TWITCH_COLOR = "#9146FF"

# Default tab name to index mapping
_DEFAULT_TAB_OPTIONS = ["General", "Services", "Shops", "Orders", "Rentals"]

# ---------------------------------------------------------------------------
# SVG icon paths (24x24 viewBox)
# ---------------------------------------------------------------------------

DISCORD_SVG = (
    '<path d="M20.317 4.369a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037'
    'c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617'
    '-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032'
    '.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0'
    ' 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0'
    ' 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2'
    ' 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074'
    '.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299'
    ' 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076'
    ' 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177'
    '-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085'
    '-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.095 2.157 2.42 0'
    ' 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333'
    '.955-2.419 2.157-2.419 1.21 0 2.176 1.095 2.157 2.42 0 1.333-.946 2.418-2.157'
    ' 2.418z"/>'
)
YOUTUBE_SVG = (
    '<path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12'
    ' 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93'
    '.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0'
    ' 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814'
    'zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>'
)
TWITCH_SVG = (
    '<path d="M11.571 4.714h1.715v5.143H11.57zm4.715 0H18v5.143h-1.714zM6 0L1.714'
    ' 4.286v15.428h5.143V24l4.286-4.286h3.428L22.286 12V0zm14.571 11.143l-3.428'
    ' 3.428h-3.429l-3 3v-3H6.857V1.714h13.714z"/>'
)

_COPY_SVG = (
    '<path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2'
    ' 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>'
)

_CHECK_SVG = '<path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>'

_PENCIL_SVG = (
    '<path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25z'
    'M20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0'
    'l-1.83 1.83 3.75 3.75 1.83-1.83z"/>'
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


_card_frame_counter = 0


def _card_frame() -> QFrame:
    """Create a styled card QFrame."""
    global _card_frame_counter
    _card_frame_counter += 1
    obj_name = f"cardFrame{_card_frame_counter}"
    frame = QFrame()
    frame.setObjectName(obj_name)
    frame.setStyleSheet(
        f"#{obj_name} {{ background: {SECONDARY}; border: 1px solid {BORDER};"
        f" border-radius: 6px; padding: 12px; }}"
    )
    return frame


def _section_label(text: str) -> QLabel:
    """Create an uppercase section header label."""
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {ACCENT}; font-size: 11px; font-weight: bold;"
        " text-transform: uppercase; letter-spacing: 0.5px;"
        " background: transparent;"
    )
    return lbl


def _stat_widget(value: str, label: str) -> QWidget:
    """Create a stat display with a large value and a muted label below."""
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(w)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    val_lbl = QLabel(value)
    val_lbl.setStyleSheet(
        f"color: {TEXT}; font-size: 14px; font-weight: bold;"
        " background: transparent;"
    )
    val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(val_lbl)

    desc_lbl = QLabel(label)
    desc_lbl.setStyleSheet(
        f"color: {TEXT_MUTED}; font-size: 11px; background: transparent;"
    )
    desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(desc_lbl)

    return w


def _link_button(text: str) -> QPushButton:
    """Create a text-styled clickable link button."""
    btn = QPushButton(text)
    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    btn.setStyleSheet(
        f"QPushButton {{ color: {ACCENT}; border: none; background: transparent;"
        f" text-align: left; padding: 0; }}"
        f"QPushButton:hover {{ text-decoration: underline; }}"
    )
    return btn


def _accent_button(text: str) -> QPushButton:
    """Create an accent-colored action button."""
    btn = QPushButton(text)
    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    btn.setObjectName("accentButton")
    return btn


def _action_button(text: str) -> QPushButton:
    """Create a standard action button."""
    btn = QPushButton(text)
    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    return btn


def _social_icon_button(svg_path: str, color: str, tooltip: str, size: int = 20) -> QPushButton:
    """Create a small social icon button."""
    btn = QPushButton()
    btn.setFixedSize(size + 4, size + 4)
    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    btn.setIcon(svg_icon(svg_path, color, size))
    btn.setToolTip(tooltip)
    btn.setStyleSheet(
        "QPushButton { background: transparent; border: none; padding: 0; }"
        f"QPushButton:hover {{ background: {HOVER}; border-radius: 3px; }}"
    )
    return btn


_STACKABLE_TYPES = frozenset({
    'Material', 'Consumable', 'Capsule', 'Enhancer', 'Strongbox',
})
_ABSOLUTE_MARKUP_MATERIAL_SUBTYPES = frozenset({'Deed', 'Token', 'Share'})
_LIMITED_RE = re.compile(r'\(.*L.*\)')


def _is_absolute_markup_order(item_type: str, item_name: str, item_sub_type: str | None) -> bool:
    """Determine if an order uses absolute (+PED) markup from order fields."""
    if not item_type:
        return False
    # Stackable items use % markup (except Deed/Token/Share sub-types which use absolute)
    if item_type in _STACKABLE_TYPES:
        if item_sub_type and item_sub_type in _ABSOLUTE_MARKUP_MATERIAL_SUBTYPES:
            return True
        return False
    # (L) blueprints are stackable → percent; non-L blueprints → absolute
    if item_type == 'Blueprint':
        if item_name and _LIMITED_RE.search(item_name):
            return False  # (L) BP = stackable = percent markup
        return True  # non-L BP = absolute
    # Non-stackable condition items that are (L) → percent markup
    if item_name and _LIMITED_RE.search(item_name):
        return False
    # Everything else → absolute
    return True


def _format_relative_time(ts_str: str) -> str:
    """Format an ISO timestamp as a relative time string."""
    if not ts_str:
        return ""
    try:
        ts = datetime.fromisoformat(ts_str)
        delta = datetime.now(timezone.utc) - ts
        secs = int(delta.total_seconds())
        if secs < 60:
            return f"{secs}s ago"
        if secs < 3600:
            return f"{secs // 60}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"
    except (ValueError, TypeError):
        return ""


# Global type badge colors
_GLOBAL_TYPE_COLORS = {
    "kill": "#ef4444",
    "team_kill": "#ef4444",
    "deposit": "#3b82f6",
    "craft": "#a855f7",
    "rare_item": "#f59e0b",
    "discovery": "#10b981",
}


# ---------------------------------------------------------------------------
# ProfilePage
# ---------------------------------------------------------------------------

class ProfilePage(QWidget):
    """Full-page user profile display and editing."""

    # --- Signals ---
    navigation_changed = pyqtSignal(object)
    open_society = pyqtSignal(str)
    open_profile = pyqtSignal(str)

    # Cross-thread signals
    _profile_loaded = pyqtSignal(object)
    _avatar_loaded = pyqtSignal(object)
    _globals_loaded = pyqtSignal(object)
    _save_result = pyqtSignal(bool, str)
    _upload_result = pyqtSignal(bool, str)

    def __init__(self, *, signals=None, nexus_client: NexusClient, parent=None):
        super().__init__(parent)
        self._signals = signals
        self._nexus_client = nexus_client
        self._identifier: str | None = None
        self._profile_data: dict | None = None
        self._load_gen = 0
        self._edit_mode = False

        # Globals state
        self._globals_data: dict | None = None
        self._globals_fetched = False
        self._globals_loading = False
        self._globals_sort_best: dict[str, bool] = {
            "hunting": False, "mining": False, "crafting": False,
        }
        self._globals_recent_timer: QTimer | None = None
        self._globals_full_timer: QTimer | None = None
        self._globals_tab_index: int | None = None

        # Edit mode widget references
        self._edit_widgets: dict = {}

        # Connect cross-thread signals
        self._profile_loaded.connect(self._on_profile_loaded)
        self._avatar_loaded.connect(self._on_avatar_loaded)
        self._globals_loaded.connect(self._on_globals_loaded)
        self._save_result.connect(self._on_save_result)
        self._upload_result.connect(self._on_upload_result)

        # Build root layout
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        # Scroll area wrapping all content
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._root_layout.addWidget(self._scroll)

        # Show initial empty state
        self._build_empty_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def navigate_to(self, identifier: str):
        """Load and display a user profile by identifier (EU name or ID)."""
        if identifier == self._identifier:
            return
        self._identifier = identifier
        self._edit_mode = False
        self._globals_fetched = False
        self._globals_loading = False
        self._globals_data = None
        self._globals_sort_best = {
            "hunting": False, "mining": False, "crafting": False,
        }
        self._stop_globals_timers()
        self._load_gen += 1
        self._build_loading_state()
        self._fetch_profile()
        self.navigation_changed.emit(identifier)

    def get_scroll_position(self) -> int:
        """Return current vertical scroll position."""
        return self._scroll.verticalScrollBar().value()

    def set_scroll_position(self, pos: int):
        """Restore a previously saved scroll position."""
        self._scroll.verticalScrollBar().setValue(pos)

    def set_sub_state(self, sub_state):
        """Called by MainWindow when restoring navigation history."""
        if sub_state and sub_state != self._identifier:
            self.navigate_to(sub_state)

    def cleanup(self):
        """Stop timers and background work."""
        self._stop_globals_timers()
        self._load_gen += 1  # Invalidate any in-flight loads

    # ------------------------------------------------------------------
    # State screens
    # ------------------------------------------------------------------

    def _set_scroll_content(self, widget: QWidget):
        """Replace the scroll area's content widget."""
        old = self._scroll.takeWidget()
        self._scroll.setWidget(widget)
        if old is not None:
            old.deleteLater()

    def _build_empty_state(self):
        """Show a placeholder when no profile is loaded."""
        container = QWidget()
        container.setStyleSheet(f"background: {PRIMARY};")
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel("Select a profile to view")
        lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 14px; background: transparent;"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)
        self._set_scroll_content(container)

    def _build_loading_state(self):
        """Show a loading indicator."""
        container = QWidget()
        container.setStyleSheet(f"background: {PRIMARY};")
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel("Loading profile...")
        lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 14px; background: transparent;"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)
        self._set_scroll_content(container)

    def _build_error_state(self, message: str):
        """Show an error message with retry button."""
        container = QWidget()
        container.setStyleSheet(f"background: {PRIMARY};")
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl = QLabel(message)
        lbl.setStyleSheet(
            f"color: {ERROR}; font-size: 14px; background: transparent;"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        retry_btn = _action_button("Retry")
        retry_btn.clicked.connect(self._retry_load)
        layout.addWidget(retry_btn, 0, Qt.AlignmentFlag.AlignCenter)

        self._set_scroll_content(container)

    def _retry_load(self):
        """Re-attempt profile load after an error."""
        if self._identifier:
            self._load_gen += 1
            self._build_loading_state()
            self._fetch_profile()

    # ------------------------------------------------------------------
    # Data loading — profile
    # ------------------------------------------------------------------

    def _fetch_profile(self):
        gen = self._load_gen
        nc = self._nexus_client
        identifier = self._identifier

        def _worker():
            data = nc.get_profile(identifier)
            if gen == self._load_gen:
                self._profile_loaded.emit(data)

        threading.Thread(
            target=_worker, daemon=True, name="profile-page-load"
        ).start()

    def _on_profile_loaded(self, data):
        if data is None:
            self._build_error_state("Failed to load profile")
            return
        self._profile_data = data
        self._build_profile_ui(data)
        self._fetch_avatar(data)

    # ------------------------------------------------------------------
    # Data loading — avatar
    # ------------------------------------------------------------------

    def _fetch_avatar(self, data: dict):
        profile = data.get("profile", {})
        user_id = profile.get("id")
        base_url = self._nexus_client._config.nexus_base_url.rstrip("/")
        gen = self._load_gen

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

        threading.Thread(
            target=_worker, daemon=True, name="profile-page-avatar"
        ).start()

    def _on_avatar_loaded(self, pixmap):
        if pixmap is None or not hasattr(self, "_avatar_label"):
            return
        if self._avatar_label is None:
            return
        rounded = _round_pixmap(pixmap, AVATAR_SIZE)
        self._avatar_label.setPixmap(rounded)

    # ------------------------------------------------------------------
    # Data loading — globals
    # ------------------------------------------------------------------

    def _fetch_globals(self):
        """Fetch globals data in background."""
        self._globals_loading = True
        profile = (self._profile_data or {}).get("profile", {})
        eu_name = profile.get("euName")
        if not eu_name:
            self._globals_loading = False
            return
        gen = self._load_gen
        nc = self._nexus_client

        def _worker():
            data = nc.get_player_globals(eu_name)
            if gen == self._load_gen:
                self._globals_loaded.emit(data)

        threading.Thread(
            target=_worker, daemon=True, name="profile-page-globals"
        ).start()

    def _on_globals_loaded(self, data):
        self._globals_loading = False
        self._globals_fetched = True
        self._globals_data = data
        if hasattr(self, "_globals_tab_widget"):
            self._rebuild_globals_content(data)
        self._start_globals_timers_if_active()

    def _poll_globals_recent(self):
        """Lightweight poll for recent globals."""
        if self._globals_loading:
            return
        self._fetch_globals()

    def _poll_globals_full(self):
        """Full poll (same as recent for now, but could be differentiated)."""
        if self._globals_loading:
            return
        self._fetch_globals()

    def _start_globals_timers_if_active(self):
        """Start auto-refresh timers when globals tab is visible."""
        if self._globals_tab_index is None:
            return
        if not hasattr(self, "_tab_widget"):
            return
        if self._tab_widget.currentIndex() != self._globals_tab_index:
            return

        if self._globals_recent_timer is None:
            self._globals_recent_timer = QTimer(self)
            self._globals_recent_timer.timeout.connect(self._poll_globals_recent)
        if self._globals_full_timer is None:
            self._globals_full_timer = QTimer(self)
            self._globals_full_timer.timeout.connect(self._poll_globals_full)

        if not self._globals_recent_timer.isActive():
            self._globals_recent_timer.start(GLOBALS_RECENT_INTERVAL_MS)
        if not self._globals_full_timer.isActive():
            self._globals_full_timer.start(GLOBALS_FULL_INTERVAL_MS)

    def _stop_globals_timers(self):
        """Stop globals auto-refresh timers."""
        if self._globals_recent_timer and self._globals_recent_timer.isActive():
            self._globals_recent_timer.stop()
        if self._globals_full_timer and self._globals_full_timer.isActive():
            self._globals_full_timer.stop()

    # ------------------------------------------------------------------
    # Build full profile UI
    # ------------------------------------------------------------------

    def _build_profile_ui(self, data: dict):
        """Build the entire profile page layout from loaded data."""
        profile = data.get("profile", {})
        scores = data.get("scores", {})
        permissions = data.get("permissions", {})
        is_owner = permissions.get("isOwner", False)

        container = QWidget()
        container.setStyleSheet(f"background: {PRIMARY};")
        page_layout = QVBoxLayout(container)
        page_layout.setContentsMargins(24, 16, 24, 24)
        page_layout.setSpacing(16)

        # --- Header ---
        header = self._build_header(profile, is_owner)
        page_layout.addWidget(header)

        # --- Tabs ---
        self._tab_widget = QTabWidget()
        self._tab_widget.setDocumentMode(False)

        # Track tab indices for conditional tabs
        tab_index = 0
        self._globals_tab_index = None

        # General tab (always)
        general_tab = self._build_general_tab(profile, scores, is_owner)
        self._tab_widget.addTab(general_tab, "General")
        tab_index += 1

        # Globals tab (if user has EU name)
        if profile.get("euName"):
            globals_tab = self._build_globals_tab()
            self._tab_widget.addTab(globals_tab, "Globals")
            self._globals_tab_index = tab_index
            tab_index += 1

        # Services tab
        services = data.get("services", [])
        if services:
            services_tab = self._build_services_tab(services)
            self._tab_widget.addTab(services_tab, "Services")
            tab_index += 1

        # Rentals tab
        rentals = data.get("rentals", [])
        if rentals:
            rentals_tab = self._build_rentals_tab(rentals)
            self._tab_widget.addTab(rentals_tab, "Rentals")
            tab_index += 1

        # Shops tab
        shops = data.get("shops", [])
        if shops:
            shops_tab = self._build_shops_tab(shops)
            self._tab_widget.addTab(shops_tab, "Shops")
            tab_index += 1

        # Orders tab
        orders = data.get("orders", [])
        if orders:
            orders_tab = self._build_orders_tab(orders)
            self._tab_widget.addTab(orders_tab, "Orders")
            tab_index += 1

        # Tab change handler for lazy-loading globals
        self._tab_widget.currentChanged.connect(self._on_tab_changed)

        page_layout.addWidget(self._tab_widget, 1)

        # Switch to user's preferred default tab if available
        default_tab_name = profile.get("defaultTab", "General")
        for i in range(self._tab_widget.count()):
            if self._tab_widget.tabText(i) == default_tab_name:
                self._tab_widget.setCurrentIndex(i)
                break

        self._set_scroll_content(container)

    def _on_tab_changed(self, index: int):
        """Handle tab switch — lazy-load globals, manage timers."""
        if index == self._globals_tab_index:
            if not self._globals_fetched and not self._globals_loading:
                self._fetch_globals()
            elif self._globals_fetched and not self._globals_loading:
                # Stale-while-revalidate
                self._fetch_globals()
            self._start_globals_timers_if_active()
        else:
            self._stop_globals_timers()

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    def _build_header(self, profile: dict, is_owner: bool) -> QWidget:
        """Build the profile header with avatar, names, socials, edit button."""
        header = QFrame()
        header.setObjectName("profileHeader")
        header.setStyleSheet(
            f"#profileHeader {{ background: {SECONDARY}; border: 1px solid {BORDER};"
            f" border-radius: 12px; padding: 16px; }}"
        )
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 16, 16, 16)
        h_layout.setSpacing(16)

        # Avatar
        self._avatar_label = QLabel()
        self._avatar_label.setFixedSize(AVATAR_SIZE, AVATAR_SIZE)
        self._avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._avatar_label.setStyleSheet(
            f"background-color: {SECONDARY};"
            f" border-radius: {AVATAR_BORDER_RADIUS}px;"
            f" border: 1px solid {BORDER};"
        )
        h_layout.addWidget(self._avatar_label, 0, Qt.AlignmentFlag.AlignTop)

        # Info column
        info = QWidget()
        info.setStyleSheet("background: transparent;")
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)

        # Name row + social icons
        name_row = QWidget()
        name_row.setStyleSheet("background: transparent;")
        name_row.setMinimumHeight(36)
        name_row_layout = QHBoxLayout(name_row)
        name_row_layout.setContentsMargins(0, 0, 0, 0)
        name_row_layout.setSpacing(8)

        eu_name = profile.get("euName") or profile.get("discordName", "Unknown")
        name_lbl = QLabel(eu_name)
        name_lbl.setStyleSheet(
            f"color: {TEXT}; font-size: 18px; font-weight: bold;"
            " background: transparent;"
        )
        name_row_layout.addWidget(name_lbl)

        # Social icons
        discord_name = profile.get("socialDiscord")
        if discord_name:
            discord_btn = _social_icon_button(
                DISCORD_SVG, SOCIAL_DISCORD_COLOR,
                f"Copy Discord: {discord_name}",
            )
            self._discord_copy_btn = discord_btn
            discord_btn.clicked.connect(
                lambda _=None, n=discord_name: self._copy_discord(n)
            )
            name_row_layout.addWidget(
                discord_btn, 0, Qt.AlignmentFlag.AlignVCenter
            )

        yt_name = profile.get("socialYoutube")
        if yt_name:
            if yt_name.startswith("UC") and len(yt_name) >= 20:
                yt_url = f"https://youtube.com/channel/{yt_name}"
            else:
                yt_url = f"https://youtube.com/@{yt_name}"
            yt_btn = _social_icon_button(
                YOUTUBE_SVG, SOCIAL_YOUTUBE_COLOR, f"YouTube: {yt_name}"
            )
            yt_btn.clicked.connect(
                lambda _=None, u=yt_url: webbrowser.open(u)
            )
            name_row_layout.addWidget(
                yt_btn, 0, Qt.AlignmentFlag.AlignVCenter
            )

        twitch_name = profile.get("socialTwitch")
        if twitch_name:
            twitch_btn = _social_icon_button(
                TWITCH_SVG, SOCIAL_TWITCH_COLOR, f"Twitch: {twitch_name}"
            )
            twitch_btn.clicked.connect(
                lambda _=None, u=f"https://twitch.tv/{twitch_name}": webbrowser.open(u)
            )
            name_row_layout.addWidget(
                twitch_btn, 0, Qt.AlignmentFlag.AlignVCenter
            )

        name_row_layout.addStretch()

        # Edit / Save / Cancel buttons (owner only)
        if is_owner:
            self._edit_btn = _action_button("Edit Profile")
            self._edit_btn.setIcon(svg_icon(_PENCIL_SVG, TEXT, 14))
            self._edit_btn.clicked.connect(self._toggle_edit_mode)
            name_row_layout.addWidget(self._edit_btn)

            self._save_btn = QPushButton("Save")
            self._save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self._save_btn.setStyleSheet(
                f"QPushButton {{ background-color: {ACCENT}; color: {MAIN_DARK};"
                f" border: none; border-radius: 4px; font-weight: bold;"
                f" padding: 6px 20px; min-height: 24px; }}"
                f"QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}"
                f"QPushButton:disabled {{ background-color: {DISABLED};"
                f" color: {TEXT_MUTED}; }}"
            )
            self._save_btn.clicked.connect(self._on_save_settings)
            self._save_btn.setVisible(False)
            name_row_layout.addWidget(self._save_btn)

            self._cancel_btn = _action_button("Cancel")
            self._cancel_btn.clicked.connect(self._cancel_edit_mode)
            self._cancel_btn.setVisible(False)
            name_row_layout.addWidget(self._cancel_btn)

        info_layout.addWidget(name_row)

        # Meta rows (horizontal label: value pairs, matching website .meta-row)
        meta_widget = QWidget()
        meta_widget.setStyleSheet("background: transparent;")
        meta_layout = QVBoxLayout(meta_widget)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(6)

        # Discord name row
        discord_display = profile.get("discordName", "")
        if discord_display:
            discord_row = QHBoxLayout()
            discord_row.setSpacing(10)
            dl = QLabel("DISCORD")
            dl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 11px; font-weight: bold;"
                " letter-spacing: 0.5px; background: transparent;"
                " min-width: 70px;"
            )
            discord_row.addWidget(dl)
            dv = QLabel(f"@{discord_display}")
            dv.setStyleSheet(
                f"color: {TEXT}; font-size: 13px; background: transparent;"
            )
            discord_row.addWidget(dv)
            discord_row.addStretch()
            meta_layout.addLayout(discord_row)

        # Society row
        society = profile.get("society")
        if society:
            soc_row = QHBoxLayout()
            soc_row.setSpacing(10)
            sl = QLabel("SOCIETY")
            sl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 11px; font-weight: bold;"
                " letter-spacing: 0.5px; background: transparent;"
                " min-width: 70px;"
            )
            soc_row.addWidget(sl)
            soc_name = society.get("name", "")
            soc_abbr = society.get("abbreviation", "")
            soc_text = (
                f"{soc_name} ({soc_abbr})" if soc_abbr else soc_name
            )
            soc_btn = _link_button(soc_text)
            soc_btn.setStyleSheet(
                soc_btn.styleSheet() + " font-size: 13px;"
            )
            soc_btn.clicked.connect(
                lambda _=None, n=soc_name: self.open_society.emit(n)
            )
            soc_row.addWidget(soc_btn)
            soc_row.addStretch()
            meta_layout.addLayout(soc_row)

        info_layout.addWidget(meta_widget)
        info_layout.addStretch()
        h_layout.addWidget(info, 1)

        return header

    def _copy_discord(self, name: str):
        """Copy Discord name to clipboard with visual feedback."""
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(name)
        if hasattr(self, "_discord_copy_btn"):
            self._discord_copy_btn.setIcon(
                svg_icon(_CHECK_SVG, SUCCESS, 20)
            )
            QTimer.singleShot(
                1500,
                lambda: self._discord_copy_btn.setIcon(
                    svg_icon(DISCORD_SVG, SOCIAL_DISCORD_COLOR, 20)
                ),
            )

    # ------------------------------------------------------------------
    # Score cards
    # ------------------------------------------------------------------

    def _build_score_cards(self, scores: dict, profile: dict) -> QWidget:
        """Build the contribution score cards row (matches website .score-card)."""
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        total = scores.get("total", 0)
        total_rank = scores.get("totalRank")
        monthly = scores.get("monthly", 0)
        monthly_rank = scores.get("monthlyRank")
        reward_score = profile.get("rewardScore", 0)

        def _score_card(label: str, value: str, rank: str | None = None):
            card = _card_frame()
            cl = QVBoxLayout(card)
            cl.setContentsMargins(12, 10, 12, 10)
            cl.setSpacing(4)
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 11px; font-weight: bold;"
                " text-transform: uppercase; letter-spacing: 0.5px;"
                " background: transparent;"
            )
            cl.addWidget(lbl)
            val = QLabel(value)
            val.setStyleSheet(
                f"color: {TEXT}; font-size: 18px; font-weight: bold;"
                " background: transparent;"
            )
            cl.addWidget(val)
            if rank:
                rl = QLabel(rank)
                rl.setStyleSheet(
                    f"color: {TEXT_MUTED}; font-size: 11px;"
                    " background: transparent;"
                )
                cl.addWidget(rl)
            return card

        layout.addWidget(
            _score_card(
                "Total",
                f"{total:,}",
                f"Rank #{total_rank}" if total_rank else None,
            ),
            1,
        )
        layout.addWidget(
            _score_card(
                "This Month",
                f"{monthly:,}",
                f"Rank #{monthly_rank}" if monthly_rank else None,
            ),
            1,
        )
        if reward_score > 0:
            layout.addWidget(
                _score_card("Reward Score", f"{reward_score:,}"), 1
            )

        return row

    # ------------------------------------------------------------------
    # General tab
    # ------------------------------------------------------------------

    def _build_general_tab(
        self, profile: dict, scores: dict, is_owner: bool
    ) -> QWidget:
        """Build the General tab with score cards, biography, and edit fields."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setStyleSheet(f"background: {PRIMARY};")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(12)

        # Score cards (inside General tab, matching website)
        layout.addWidget(_section_label("CONTRIBUTION SCORE"))
        score_cards = self._build_score_cards(scores, profile)
        layout.addWidget(score_cards)

        # Biography display
        bio_html = profile.get("biographyHtml", "")
        if bio_html and bio_html.strip():
            layout.addWidget(_section_label("BIOGRAPHY"))
            bio_browser = QTextBrowser()
            bio_browser.setOpenExternalLinks(True)
            bio_browser.setHtml(
                f'<body style="color:{TEXT}; font-size:13px; font-family:{FONT_FAMILY};">'
                f"<style>"
                f"  a {{ color: {ACCENT}; text-decoration: none; }}"
                f"  a:hover {{ text-decoration: underline; }}"
                f"  p {{ margin: 4px 0; }}"
                f"  blockquote {{ margin: 4px 0 4px 8px; padding-left: 6px;"
                f"    border-left: 2px solid {TEXT_MUTED}; color: {TEXT_MUTED}; }}"
                f"  code {{ background: {SECONDARY}; padding: 1px 3px;"
                f"    border-radius: 2px; }}"
                f"</style>"
                f"{bio_html}</body>"
            )
            bio_browser.setStyleSheet(
                f"QTextBrowser {{ background: transparent; border: none;"
                f" color: {TEXT}; }}"
            )
            # Auto-size to content
            bio_browser.document().setDocumentMargin(4)
            doc_height = int(bio_browser.document().size().height()) + 8
            bio_browser.setMinimumHeight(min(doc_height, 300))
            bio_browser.setMaximumHeight(600)
            layout.addWidget(bio_browser)
            self._bio_browser = bio_browser
        else:
            if not is_owner:
                no_bio = QLabel("No biography set.")
                no_bio.setStyleSheet(
                    f"color: {TEXT_MUTED}; font-size: 13px;"
                    " background: transparent; font-style: italic;"
                )
                layout.addWidget(no_bio)
            self._bio_browser = None

        # --- Edit mode fields (hidden by default) ---
        self._edit_container = QWidget()
        self._edit_container.setStyleSheet("background: transparent;")
        self._edit_container.setVisible(False)
        edit_layout = QVBoxLayout(self._edit_container)
        edit_layout.setContentsMargins(0, 0, 0, 0)
        edit_layout.setSpacing(12)

        # Biography editor
        edit_layout.addWidget(_section_label("BIOGRAPHY"))
        self._bio_edit = QTextEdit()
        self._bio_edit.setPlaceholderText("Write your biography...")
        self._bio_edit.setMaximumHeight(120)
        plain = re.sub(r'<[^>]+>', '', bio_html).strip() if bio_html else ""
        self._bio_edit.setPlainText(plain)
        edit_layout.addWidget(self._bio_edit)

        # Social links
        edit_layout.addWidget(_section_label("SOCIAL LINKS"))
        for key, svg_path, color, placeholder in [
            ("socialDiscord", DISCORD_SVG, SOCIAL_DISCORD_COLOR, "Discord username"),
            ("socialYoutube", YOUTUBE_SVG, SOCIAL_YOUTUBE_COLOR, "YouTube channel name or ID"),
            ("socialTwitch", TWITCH_SVG, SOCIAL_TWITCH_COLOR, "Twitch username"),
        ]:
            row = QHBoxLayout()
            row.setSpacing(8)
            icon_lbl = QPushButton()
            icon_lbl.setFixedSize(24, 24)
            icon_lbl.setIcon(svg_icon(svg_path, color, 20))
            icon_lbl.setStyleSheet(
                "QPushButton { background: transparent; border: none; padding: 0; }"
            )
            icon_lbl.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )
            row.addWidget(icon_lbl)
            inp = QLineEdit()
            inp.setPlaceholderText(placeholder)
            inp.setText(profile.get(key, "") or "")
            inp.setMaxLength(200)
            row.addWidget(inp)
            edit_layout.addLayout(row)
            self._edit_widgets[key] = inp

        # Default tab
        edit_layout.addWidget(_section_label("DEFAULT TAB"))
        self._default_tab_combo = QComboBox()
        self._default_tab_combo.addItems(_DEFAULT_TAB_OPTIONS)
        current_default = profile.get("defaultTab", "General")
        if current_default in _DEFAULT_TAB_OPTIONS:
            self._default_tab_combo.setCurrentText(current_default)
        edit_layout.addWidget(self._default_tab_combo)

        # Showcase loadout
        edit_layout.addWidget(_section_label("SHOWCASE LOADOUT CODE"))
        self._showcase_input = QLineEdit()
        self._showcase_input.setPlaceholderText("Share code (optional)")
        self._showcase_input.setText(
            profile.get("showcaseLoadoutCode", "") or ""
        )
        edit_layout.addWidget(self._showcase_input)

        # Profile image
        edit_layout.addWidget(_section_label("PROFILE IMAGE"))
        img_row = QHBoxLayout()
        img_row.setSpacing(8)
        upload_btn = _action_button("Upload Image")
        upload_btn.clicked.connect(self._on_upload_image)
        img_row.addWidget(upload_btn)
        self._remove_img_btn = _action_button("Remove Image")
        self._remove_img_btn.setVisible(
            profile.get("hasCustomImage", False)
        )
        self._remove_img_btn.clicked.connect(self._on_remove_image)
        img_row.addWidget(self._remove_img_btn)
        img_row.addStretch()
        edit_layout.addLayout(img_row)

        # Upload status
        self._upload_status = QLabel("")
        self._upload_status.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; background: transparent;"
        )
        self._upload_status.setVisible(False)
        edit_layout.addWidget(self._upload_status)

        # Save status
        self._save_status = QLabel("")
        self._save_status.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; background: transparent;"
        )
        self._save_status.setVisible(False)
        edit_layout.addWidget(self._save_status)

        layout.addWidget(self._edit_container)
        layout.addStretch()

        scroll.setWidget(content)
        return scroll

    # ------------------------------------------------------------------
    # Edit mode
    # ------------------------------------------------------------------

    def _toggle_edit_mode(self):
        """Toggle edit mode on."""
        self._edit_mode = True
        self._edit_container.setVisible(True)
        if self._bio_browser:
            self._bio_browser.setVisible(False)
        if hasattr(self, "_edit_btn"):
            self._edit_btn.setVisible(False)
        if hasattr(self, "_save_btn"):
            self._save_btn.setVisible(True)
        if hasattr(self, "_cancel_btn"):
            self._cancel_btn.setVisible(True)
        # Switch to General tab where the edit fields live
        if hasattr(self, "_tab_widget"):
            self._tab_widget.setCurrentIndex(0)

    def _cancel_edit_mode(self):
        """Cancel edit mode, restoring original view."""
        self._edit_mode = False
        self._edit_container.setVisible(False)
        if self._bio_browser:
            self._bio_browser.setVisible(True)
        if hasattr(self, "_edit_btn"):
            self._edit_btn.setVisible(True)
        if hasattr(self, "_save_btn"):
            self._save_btn.setVisible(False)
        if hasattr(self, "_cancel_btn"):
            self._cancel_btn.setVisible(False)

    def _on_save_settings(self):
        """Collect edited fields and save via API."""
        if not self._profile_data or not self._identifier:
            return

        bio_text = self._bio_edit.toPlainText().strip()
        bio_html = f"<p>{bio_text}</p>" if bio_text else ""
        default_tab = self._default_tab_combo.currentText()
        showcase = self._showcase_input.text().strip() or None

        social_discord_w = self._edit_widgets.get("socialDiscord")
        social_youtube_w = self._edit_widgets.get("socialYoutube")
        social_twitch_w = self._edit_widgets.get("socialTwitch")

        payload = {
            "biographyHtml": bio_html,
            "defaultTab": default_tab,
            "showcaseLoadoutCode": showcase,
            "socialDiscord": (
                (social_discord_w.text().strip() or None)
                if social_discord_w else None
            ),
            "socialYoutube": (
                (social_youtube_w.text().strip() or None)
                if social_youtube_w else None
            ),
            "socialTwitch": (
                (social_twitch_w.text().strip() or None)
                if social_twitch_w else None
            ),
        }

        if hasattr(self, "_save_btn"):
            self._save_btn.setEnabled(False)
            self._save_btn.setText("Saving...")

        nc = self._nexus_client
        identifier = self._identifier
        gen = self._load_gen

        def _worker():
            result = nc.update_profile(identifier, payload)
            if gen == self._load_gen:
                self._save_result.emit(
                    result is not None,
                    "" if result else "Save failed",
                )

        threading.Thread(
            target=_worker, daemon=True, name="profile-page-save"
        ).start()

    def _on_save_result(self, success: bool, error: str):
        if hasattr(self, "_save_btn"):
            self._save_btn.setEnabled(True)
            self._save_btn.setText("Save")

        if success:
            self._save_status.setText("Settings saved successfully")
            self._save_status.setStyleSheet(
                f"color: {SUCCESS}; font-size: 11px; background: transparent;"
            )
            self._save_status.setVisible(True)
            QTimer.singleShot(
                3000, lambda: self._save_status.setVisible(False)
            )
            # Exit edit mode and reload
            self._cancel_edit_mode()
            self._load_gen += 1
            self._fetch_profile()
        else:
            self._save_status.setText(error or "Save failed")
            self._save_status.setStyleSheet(
                f"color: {ERROR}; font-size: 11px; background: transparent;"
            )
            self._save_status.setVisible(True)
            QTimer.singleShot(
                5000, lambda: self._save_status.setVisible(False)
            )

    # ------------------------------------------------------------------
    # Image upload / remove
    # ------------------------------------------------------------------

    def _on_upload_image(self):
        """Open file dialog and upload a profile image."""
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
                f"color: {ERROR}; font-size: 11px; background: transparent;"
            )
            self._upload_status.setVisible(True)
            QTimer.singleShot(
                5000, lambda: self._upload_status.setVisible(False)
            )
            return

        import mimetypes
        ct, _ = mimetypes.guess_type(path)
        if not ct or not ct.startswith("image/"):
            ct = "application/octet-stream"

        profile = (self._profile_data or {}).get("profile", {})
        user_id = profile.get("id")
        if not user_id:
            return

        self._upload_status.setText("Uploading...")
        self._upload_status.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; background: transparent;"
        )
        self._upload_status.setVisible(True)

        nc = self._nexus_client
        gen = self._load_gen

        def _worker():
            result = nc.upload_profile_image(user_id, data, ct)
            if gen == self._load_gen:
                self._upload_result.emit(
                    result is not None,
                    "" if result else "Upload failed",
                )

        threading.Thread(
            target=_worker, daemon=True, name="profile-page-upload"
        ).start()

    def _on_remove_image(self):
        """Remove the custom profile image."""
        profile = (self._profile_data or {}).get("profile", {})
        user_id = profile.get("id")
        if not user_id:
            return

        nc = self._nexus_client
        gen = self._load_gen

        def _worker():
            ok = nc.delete_profile_image(user_id)
            if gen == self._load_gen:
                self._upload_result.emit(
                    ok, "" if ok else "Failed to remove image"
                )

        threading.Thread(
            target=_worker, daemon=True, name="profile-page-delete-img"
        ).start()

        # Clear avatar immediately
        if hasattr(self, "_avatar_label") and self._avatar_label:
            self._avatar_label.clear()
        self._remove_img_btn.setVisible(False)

    def _on_upload_result(self, success: bool, error: str):
        if success:
            self._upload_status.setText("Image updated successfully")
            self._upload_status.setStyleSheet(
                f"color: {SUCCESS}; font-size: 11px; background: transparent;"
            )
            self._upload_status.setVisible(True)
            QTimer.singleShot(
                3000, lambda: self._upload_status.setVisible(False)
            )
            self._remove_img_btn.setVisible(True)
            # Reload avatar
            if self._profile_data:
                self._profile_data.setdefault("profile", {})[
                    "hasCustomImage"
                ] = True
                self._fetch_avatar(self._profile_data)
        else:
            self._upload_status.setText(error or "Upload failed")
            self._upload_status.setStyleSheet(
                f"color: {ERROR}; font-size: 11px; background: transparent;"
            )
            self._upload_status.setVisible(True)
            QTimer.singleShot(
                5000, lambda: self._upload_status.setVisible(False)
            )

    # ------------------------------------------------------------------
    # Globals tab
    # ------------------------------------------------------------------

    def _build_globals_tab(self) -> QWidget:
        """Build the Globals tab with a placeholder for lazy loading."""
        self._globals_tab_widget = QWidget()
        self._globals_tab_widget.setStyleSheet(f"background: {PRIMARY};")
        layout = QVBoxLayout(self._globals_tab_widget)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl = QLabel("Loading globals...")
        lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 13px; background: transparent;"
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)

        return self._globals_tab_widget

    def _rebuild_globals_content(self, data: dict | None):
        """Replace globals tab content with actual data."""
        if not hasattr(self, "_globals_tab_widget"):
            return

        # Clear existing content
        old_layout = self._globals_tab_widget.layout()
        if old_layout:
            while old_layout.count():
                child = old_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        layout = old_layout
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        if not data or "summary" not in data:
            lbl = QLabel("No globals recorded for this player.")
            lbl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 13px; background: transparent;"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)
            return

        # Wrap in scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        c_layout = QVBoxLayout(content)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(12)

        summary = data["summary"]

        # Summary cards
        summary_row = QWidget()
        summary_row.setStyleSheet("background: transparent;")
        sr_layout = QHBoxLayout(summary_row)
        sr_layout.setContentsMargins(0, 0, 0, 0)
        sr_layout.setSpacing(12)

        total_count = summary.get("total_count", 0)
        total_value = summary.get("total_value", 0)
        hof_count = summary.get("hof_count", 0)

        card1 = _card_frame()
        QHBoxLayout(card1).setSpacing(12)
        card1.layout().addWidget(
            _stat_widget(str(total_count), "Globals")
        )
        card1.layout().addWidget(
            _stat_widget(str(hof_count), "HoFs")
        )
        card1.layout().addWidget(
            _stat_widget(f"{total_value:,.0f}", "Total PED")
        )
        sr_layout.addWidget(card1, 1)

        kill_count = summary.get("kill_count", 0) + summary.get(
            "team_kill_count", 0
        )
        deposit_count = summary.get("deposit_count", 0)
        craft_count = summary.get("craft_count", 0)

        card2 = _card_frame()
        QHBoxLayout(card2).setSpacing(12)
        card2.layout().addWidget(
            _stat_widget(str(kill_count), "Hunting")
        )
        card2.layout().addWidget(
            _stat_widget(str(deposit_count), "Mining")
        )
        card2.layout().addWidget(
            _stat_widget(str(craft_count), "Crafting")
        )
        sr_layout.addWidget(card2, 1)

        c_layout.addWidget(summary_row)

        # Recent globals
        recent = data.get("recent", [])
        if recent:
            c_layout.addWidget(_section_label("RECENT"))
            self._recent_container = QWidget()
            self._recent_container.setStyleSheet("background: transparent;")
            rc_layout = QVBoxLayout(self._recent_container)
            rc_layout.setContentsMargins(0, 0, 0, 0)
            rc_layout.setSpacing(4)
            self._populate_recent(rc_layout, recent)
            c_layout.addWidget(self._recent_container)

        # Top sections with Total/Best toggle
        hunting = data.get("hunting", [])
        resources = data.get("mining", {}).get("resources", [])
        crafts = data.get("crafting", {}).get("items", [])

        if hunting:
            header_w, container = self._build_top_section_header(
                "TOP HUNTING", "hunting"
            )
            c_layout.addWidget(header_w)
            self._hunting_container = container
            c_layout.addWidget(container)
            self._populate_hunting(container, hunting)

        if resources:
            header_w, container = self._build_top_section_header(
                "TOP MINING", "mining"
            )
            c_layout.addWidget(header_w)
            self._mining_container = container
            c_layout.addWidget(container)
            self._populate_mining(container, resources)

        if crafts:
            header_w, container = self._build_top_section_header(
                "TOP CRAFTING", "crafting"
            )
            c_layout.addWidget(header_w)
            self._crafting_container = container
            c_layout.addWidget(container)
            self._populate_crafting(container, crafts)

        c_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _populate_recent(self, layout: QVBoxLayout, recent: list[dict]):
        """Fill the recent globals list."""
        for entry in recent[:10]:
            target = entry.get("target", "Unknown")
            value = entry.get("value", 0)
            gtype = entry.get("type", "")
            hof = entry.get("hof", False)
            ts_str = entry.get("timestamp", "")
            age = _format_relative_time(ts_str)

            badge_color = _GLOBAL_TYPE_COLORS.get(gtype, TEXT_MUTED)
            type_label = gtype.replace("_", " ").title() if gtype else ""

            row = QWidget()
            row.setStyleSheet(
                "QWidget { background: transparent; }"
                f"QWidget:hover {{ background: {HOVER}; border-radius: 4px; }}"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(4, 3, 4, 3)
            rl.setSpacing(8)

            # Type badge
            badge = QLabel(type_label)
            badge.setFixedWidth(70)
            badge.setStyleSheet(
                f"color: {badge_color}; font-size: 11px; font-weight: bold;"
                " background: transparent;"
            )
            rl.addWidget(badge)

            # Target name
            name_lbl = QLabel(target)
            name_lbl.setStyleSheet(
                f"color: {TEXT}; font-size: 12px; background: transparent;"
            )
            name_lbl.setToolTip(target)
            rl.addWidget(name_lbl, 1)

            # Value
            val_text = f"{value:,.0f} PED"
            if hof:
                val_text += "  HoF"
            val_lbl = QLabel(val_text)
            val_color = WARNING if hof else TEXT_MUTED
            val_lbl.setStyleSheet(
                f"color: {val_color}; font-size: 12px; background: transparent;"
            )
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            rl.addWidget(val_lbl)

            # Age
            if age:
                age_lbl = QLabel(age)
                age_lbl.setFixedWidth(55)
                age_lbl.setStyleSheet(
                    f"color: {TEXT_MUTED}; font-size: 11px;"
                    " background: transparent;"
                )
                age_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
                rl.addWidget(age_lbl)

            layout.addWidget(row)

    def _build_top_section_header(
        self, title: str, section_key: str
    ) -> tuple[QWidget, QWidget]:
        """Build a section header with Total/Best toggle."""
        header = QWidget()
        header.setStyleSheet("background: transparent;")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(0, 4, 0, 0)
        hl.setSpacing(8)

        lbl = _section_label(title)
        hl.addWidget(lbl, 1)

        is_best = self._globals_sort_best.get(section_key, False)

        total_btn = QPushButton("Total")
        best_btn = QPushButton("Best")
        total_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        best_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        total_btn.setFixedHeight(22)
        best_btn.setFixedHeight(22)

        active_style = (
            f"QPushButton {{ color: {TEXT}; font-size: 11px; font-weight: bold;"
            f" background: {ACCENT_LIGHT}; border: 1px solid {ACCENT};"
            " border-radius: 3px; padding: 2px 8px; }}"
        )
        inactive_style = (
            f"QPushButton {{ color: {TEXT_MUTED}; font-size: 11px;"
            f" background: transparent; border: 1px solid {BORDER};"
            " border-radius: 3px; padding: 2px 8px; }}"
            f"QPushButton:hover {{ background: {HOVER}; }}"
        )

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
            total_btn.setStyleSheet(
                inactive_style if best else active_style
            )
            best_btn.setStyleSheet(
                active_style if best else inactive_style
            )
            self._refresh_top_section(section_key)

        total_btn.clicked.connect(lambda: _set_mode(False))
        best_btn.clicked.connect(lambda: _set_mode(True))

        return header, container

    def _refresh_top_section(self, section_key: str):
        """Re-populate a top section using its current sort mode."""
        data = self._globals_data
        if not data:
            return
        if section_key == "hunting" and hasattr(self, "_hunting_container"):
            self._clear_container(self._hunting_container)
            self._populate_hunting(
                self._hunting_container, data.get("hunting", [])
            )
        elif section_key == "mining" and hasattr(self, "_mining_container"):
            self._clear_container(self._mining_container)
            self._populate_mining(
                self._mining_container,
                data.get("mining", {}).get("resources", []),
            )
        elif (
            section_key == "crafting"
            and hasattr(self, "_crafting_container")
        ):
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
            items = sorted(
                hunting, key=lambda m: m.get("best_value", 0), reverse=True
            )
        else:
            items = hunting
        for mob in items[:8]:
            name = mob.get("target", "Unknown")
            if best:
                value = mob.get("best_value", 0)
                maturities = mob.get("maturities", [])
                mat_name = ""
                if maturities:
                    top_mat = max(
                        maturities, key=lambda m: m.get("best_value", 0)
                    )
                    mat_name = top_mat.get("target", "")
                if mat_name and mat_name != name:
                    sub = f"{mat_name} -- {value:,.0f} PED"
                else:
                    sub = f"{value:,.0f} PED"
            else:
                kills = mob.get("kills", 0)
                value = mob.get("total_value", 0)
                sub = f"{kills} kills -- {value:,.0f} PED"
            layout.addWidget(self._top_row(name, sub))

    def _populate_mining(self, container: QWidget, resources: list[dict]):
        layout = container.layout()
        best = self._globals_sort_best["mining"]
        if best:
            items = sorted(
                resources, key=lambda r: r.get("best_value", 0), reverse=True
            )
        else:
            items = resources
        for res in items[:8]:
            name = res.get("target", "Unknown")
            if best:
                value = res.get("best_value", 0)
                sub = f"{value:,.0f} PED"
            else:
                finds = res.get("finds", 0)
                value = res.get("total_value", 0)
                sub = f"{finds} finds -- {value:,.0f} PED"
            layout.addWidget(self._top_row(name, sub))

    def _populate_crafting(self, container: QWidget, crafts: list[dict]):
        layout = container.layout()
        best = self._globals_sort_best["crafting"]
        if best:
            items = sorted(
                crafts, key=lambda c: c.get("best_value", 0), reverse=True
            )
        else:
            items = crafts
        for item in items[:8]:
            name = item.get("target", "Unknown")
            if best:
                value = item.get("best_value", 0)
                sub = f"{value:,.0f} PED"
            else:
                count = item.get("crafts", 0)
                value = item.get("total_value", 0)
                sub = f"{count} crafts -- {value:,.0f} PED"
            layout.addWidget(self._top_row(name, sub))

    def _top_row(self, name: str, sub: str) -> QWidget:
        """Build a row for a top section item."""
        row = QWidget()
        row.setStyleSheet(
            "QWidget { background: transparent; }"
            f"QWidget:hover {{ background: {HOVER}; border-radius: 4px; }}"
        )
        rl = QHBoxLayout(row)
        rl.setContentsMargins(4, 3, 4, 3)
        rl.setSpacing(8)

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color: {TEXT}; font-size: 12px; background: transparent;"
        )
        name_lbl.setToolTip(name)
        rl.addWidget(name_lbl, 1)

        sub_lbl = QLabel(sub)
        sub_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 12px; background: transparent;"
        )
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        rl.addWidget(sub_lbl)

        return row

    # ------------------------------------------------------------------
    # Services tab
    # ------------------------------------------------------------------

    def _build_services_tab(self, services: list[dict]) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setStyleSheet(f"background: {PRIMARY};")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(4)

        # Group by type
        by_type: dict[str, list] = {}
        for svc in services:
            t = svc.get("type", "Other")
            by_type.setdefault(t, []).append(svc)

        for svc_type, items in by_type.items():
            layout.addWidget(_section_label(svc_type.upper()))
            for svc in items:
                title = svc.get("title", "Untitled")
                row = QWidget()
                row.setStyleSheet(
                    "QWidget { background: transparent; }"
                    f"QWidget:hover {{ background: {HOVER};"
                    " border-radius: 4px; }}"
                )
                rl = QHBoxLayout(row)
                rl.setContentsMargins(4, 4, 4, 4)
                rl.setSpacing(8)
                name_lbl = QLabel(title)
                name_lbl.setStyleSheet(
                    f"color: {TEXT}; font-size: 13px;"
                    " background: transparent;"
                )
                rl.addWidget(name_lbl, 1)
                type_lbl = QLabel(svc_type)
                type_lbl.setStyleSheet(
                    f"color: {TEXT_MUTED}; font-size: 11px;"
                    " background: transparent;"
                )
                rl.addWidget(type_lbl)
                layout.addWidget(row)

        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    # ------------------------------------------------------------------
    # Rentals tab
    # ------------------------------------------------------------------

    def _build_rentals_tab(self, rentals: list[dict]) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setStyleSheet(f"background: {PRIMARY};")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(4)

        layout.addWidget(_section_label("RENTALS"))

        for rental in rentals:
            title = rental.get("title", "Untitled")
            ppd = float(rental.get("price_per_day", 0))

            row = QWidget()
            row.setStyleSheet(
                "QWidget { background: transparent; }"
                f"QWidget:hover {{ background: {HOVER};"
                " border-radius: 4px; }}"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(4, 4, 4, 4)
            rl.setSpacing(8)

            name_lbl = QLabel(title)
            name_lbl.setStyleSheet(
                f"color: {TEXT}; font-size: 13px; background: transparent;"
            )
            rl.addWidget(name_lbl, 1)

            price_lbl = QLabel(f"{ppd:.2f} PED/day")
            price_lbl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 12px;"
                " background: transparent;"
            )
            price_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            rl.addWidget(price_lbl)

            layout.addWidget(row)

        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    # ------------------------------------------------------------------
    # Shops tab
    # ------------------------------------------------------------------

    def _build_shops_tab(self, shops: list[dict]) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setStyleSheet(f"background: {PRIMARY};")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(4)

        layout.addWidget(_section_label("SHOPS"))

        for shop in shops:
            name = shop.get("name", "Unknown")
            planet = shop.get("planet_name", "")

            row = QWidget()
            row.setStyleSheet(
                "QWidget { background: transparent; }"
                f"QWidget:hover {{ background: {HOVER};"
                " border-radius: 4px; }}"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(4, 4, 4, 4)
            rl.setSpacing(8)

            name_lbl = QLabel(name)
            name_lbl.setStyleSheet(
                f"color: {TEXT}; font-size: 13px; background: transparent;"
            )
            rl.addWidget(name_lbl, 1)

            if planet:
                planet_lbl = QLabel(planet)
                planet_lbl.setStyleSheet(
                    f"color: {TEXT_MUTED}; font-size: 12px;"
                    " background: transparent;"
                )
                planet_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
                rl.addWidget(planet_lbl)

            layout.addWidget(row)

        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    # ------------------------------------------------------------------
    # Orders tab
    # ------------------------------------------------------------------

    def _build_orders_tab(self, orders: list[dict]) -> QWidget:
        container = QWidget()
        container.setStyleSheet(f"background: {PRIMARY};")
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        buy_orders = [o for o in orders if o.get("type") == "BUY"]
        sell_orders = [o for o in orders if o.get("type") == "SELL"]

        # Top bar: toggle + search
        top_bar = QWidget()
        top_bar.setStyleSheet("background: transparent;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(8, 8, 8, 4)
        top_layout.setSpacing(8)

        sell_btn = QPushButton(f"Sell Orders ({len(sell_orders)})")
        buy_btn = QPushButton(f"Buy Orders ({len(buy_orders)})")
        sell_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        buy_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        active_style = (
            f"QPushButton {{ background: {ACCENT_LIGHT}; color: {TEXT};"
            f" font-size: 12px; font-weight: bold;"
            f" border: 1px solid {ACCENT}; border-radius: 4px;"
            " padding: 6px 16px; }}"
        )
        inactive_style = (
            f"QPushButton {{ background: {SECONDARY}; color: {TEXT_MUTED};"
            f" font-size: 12px; border: 1px solid {BORDER};"
            " border-radius: 4px; padding: 6px 16px; }}"
            f"QPushButton:hover {{ background: {HOVER}; color: {TEXT}; }}"
        )

        top_layout.addWidget(sell_btn)
        top_layout.addWidget(buy_btn)
        top_layout.addStretch()

        search_input = QLineEdit()
        search_input.setPlaceholderText("Search items...")
        search_input.setFixedWidth(200)
        top_layout.addWidget(search_input)

        outer.addWidget(top_bar)

        # Stacked order tables
        order_stack = QStackedWidget()
        tables: list[QTableWidget] = []

        COLUMNS = ["Item", "Qty", "Markup", "Planet", "Status"]

        base_url = self._nexus_client._config.nexus_base_url.rstrip("/")

        for order_list in (sell_orders, buy_orders):
            table = QTableWidget(len(order_list), len(COLUMNS))
            table.setHorizontalHeaderLabels(COLUMNS)
            table.setSelectionBehavior(
                QTableWidget.SelectionBehavior.SelectRows
            )
            table.setSelectionMode(
                QTableWidget.SelectionMode.SingleSelection
            )
            table.setEditTriggers(
                QTableWidget.EditTrigger.NoEditTriggers
            )
            table.verticalHeader().setVisible(False)
            table.setAlternatingRowColors(True)
            table.setStyleSheet(
                f"QTableWidget {{ background: {PRIMARY}; gridline-color: {BORDER};"
                f" border: none; alternate-background-color: {SECONDARY}; }}"
                f"QTableWidget::item {{ padding: 4px 8px; }}"
                f"QTableWidget::item:hover {{ background: {HOVER}; }}"
            )

            # Column sizing
            header = table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            for col_idx in range(1, len(COLUMNS)):
                header.setSectionResizeMode(
                    col_idx, QHeaderView.ResizeMode.ResizeToContents
                )

            for row_idx, order in enumerate(order_list):
                self._populate_order_table_row(
                    table, row_idx, order, base_url
                )

            if not order_list:
                table.setRowCount(0)

            # Enable sorting AFTER all rows are populated
            table.setSortingEnabled(True)

            # Double-click opens exchange URL
            def _on_double_click(item, tbl=table):
                row = item.row()
                name_cell = tbl.item(row, 0)
                if name_cell:
                    url = name_cell.data(Qt.ItemDataRole.UserRole)
                    if url:
                        webbrowser.open(url)

            table.itemDoubleClicked.connect(_on_double_click)

            tables.append(table)
            order_stack.addWidget(table)

        outer.addWidget(order_stack, 1)

        # Search filter
        def _filter_tables(text: str):
            query = text.strip().lower()
            for tbl in tables:
                for row in range(tbl.rowCount()):
                    item_cell = tbl.item(row, 0)
                    name_text = item_cell.text().lower() if item_cell else ""
                    tbl.setRowHidden(
                        row, bool(query) and query not in name_text
                    )

        search_input.textChanged.connect(_filter_tables)

        # Toggle switch
        def _switch(idx):
            order_stack.setCurrentIndex(idx)
            sell_btn.setStyleSheet(
                active_style if idx == 0 else inactive_style
            )
            buy_btn.setStyleSheet(
                active_style if idx == 1 else inactive_style
            )

        sell_btn.clicked.connect(lambda: _switch(0))
        buy_btn.clicked.connect(lambda: _switch(1))

        # Default to Sell if any exist
        _switch(0 if sell_orders else 1)

        return container

    def _populate_order_table_row(
        self, table, row_idx: int, order: dict, base_url: str
    ):
        """Fill one row of the orders table."""
        details = order.get("details") or {}
        name = (
            details.get("item_name", "")
            or order.get("item_name", "Unknown")
        )
        markup = order.get("markup", 100)
        qty = order.get("quantity", 0)
        item_type = order.get("item_type", "")
        planet = order.get("planet") or ""
        state = order.get("computed_state", "active")

        # Column 0: Item name + exchange URL for click
        item_id = order.get("item_id")
        name_item = QTableWidgetItem(name)
        name_item.setForeground(QColor(ACCENT))
        if item_id and item_type:
            type_slug = item_type.lower().replace(" ", "-")
            exchange_url = f"{base_url}/market/exchange/{type_slug}/{item_id}"
            name_item.setData(Qt.ItemDataRole.UserRole, exchange_url)
        table.setItem(row_idx, 0, name_item)

        # Column 1: Qty
        qty_item = QTableWidgetItem()
        qty_item.setData(Qt.ItemDataRole.DisplayRole, qty)
        table.setItem(row_idx, 1, qty_item)

        # Column 2: Markup
        is_abs = _is_absolute_markup_order(
            item_type, name, order.get("item_sub_type")
        )
        if is_abs:
            mu_text = f"+{markup:.2f}" if isinstance(markup, (int, float)) else f"+{markup}"
        else:
            mu_text = f"{markup}%"
        mu_item = QTableWidgetItem(mu_text)
        # Store numeric for sorting
        try:
            mu_item.setData(Qt.ItemDataRole.UserRole, float(markup))
        except (TypeError, ValueError):
            pass
        table.setItem(row_idx, 2, mu_item)

        # Column 3: Planet
        table.setItem(row_idx, 3, QTableWidgetItem(planet))

        # Column 4: Status
        state_item = QTableWidgetItem(state.capitalize() if state else "Active")
        if state == "stale":
            state_item.setForeground(
                QColor(WARNING)
            )
        elif state and state not in ("active", "Active"):
            state_item.setForeground(
                QColor(ERROR)
            )
        table.setItem(row_idx, 4, state_item)
