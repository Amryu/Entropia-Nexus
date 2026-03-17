"""Stream overlay — watch Twitch streams with chat in an always-on-top overlay.

Uses streamlink + mpv for video playback (no Chromium) and WebSocket IRC
for read-only Twitch chat with emote/badge rendering.
"""

from __future__ import annotations

import os
import html as html_mod
import threading
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QWidget,
    QScrollArea, QStackedWidget, QLineEdit, QSlider,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QTextCursor

from .overlay_widget import OverlayWidget
from ..core.config import save_config
from ..core.logger import get_logger
from ..ui.icons import svg_icon, svg_pixmap, CLOSE_X, PLAY, PAUSE, VOLUME, ARROW_LEFT

if TYPE_CHECKING:
    from .overlay_manager import OverlayManager
    from ..api.nexus_client import NexusClient

log = get_logger("StreamOverlay")

# --- Layout constants ---
TITLE_H = 24
CHAT_WIDTH = 250
CONTROLS_H = 36
MAX_CHAT_MESSAGES = 200
CHAT_FLUSH_INTERVAL_MS = 100
MAX_MESSAGES_PER_FLUSH = 50

# Size presets (video area, 16:9)
_SIZE_PRESETS = [
    (400, 225),   # Small
    (640, 360),   # Medium
    (854, 480),   # Large
]
_SIZE_LABELS = ["S", "M", "L"]

# --- Pages ---
_PAGE_LIST = 0
_PAGE_PLAYER = 1

# --- Colors ---
BG_COLOR = "rgba(20, 20, 30, 220)"
TITLE_BG = "rgba(30, 30, 45, 200)"
CONTENT_BG = "rgba(30, 30, 45, 160)"
TEXT_COLOR = "#e0e0e0"
TEXT_DIM = "#999999"
TEXT_BRIGHT = "#ffffff"
ACCENT = "#00ccff"
TAB_HOVER_BG = "rgba(50, 50, 70, 180)"
LIVE_COLOR = "#e91916"
ROW_HOVER = "rgba(50, 50, 80, 120)"
VIDEO_BG = "rgba(0, 0, 0, 255)"
CHAT_BG = "rgba(18, 18, 28, 240)"

_BTN_STYLE = (
    "QPushButton {"
    "  background: transparent; border: none; border-radius: 3px;"
    "  padding: 0px; margin: 0px;"
    "}"
    "QPushButton:hover {"
    f"  background-color: {TAB_HOVER_BG};"
    "}"
)

def _size_btn_style(active: bool) -> str:
    if active:
        return (
            f"QPushButton {{ color: {ACCENT}; font-size: 10px; font-weight: 700;"
            f" background: rgba(60, 60, 90, 200); border: 1px solid {ACCENT};"
            " border-radius: 3px; padding: 0px; }}"
        )
    return (
        f"QPushButton {{ color: {TEXT_DIM}; font-size: 10px; font-weight: 600;"
        " background: transparent; border: 1px solid transparent;"
        " border-radius: 3px; padding: 0px; }}"
        f"QPushButton:hover {{ color: {TEXT_COLOR};"
        f" background: {TAB_HOVER_BG}; }}"
    )

_CTRL_BTN_STYLE = (
    "QPushButton {"
    "  background: rgba(40,40,55,200);"
    "  border: 1px solid rgba(80,80,100,180);"
    "  border-radius: 4px; padding: 2px;"
    "}"
    "QPushButton:hover {"
    "  background: rgba(60,60,80,220);"
    "  border-color: #00ccff;"
    "}"
)

_SLIDER_STYLE = (
    "QSlider { background: transparent; }"
    "QSlider::groove:horizontal {"
    "  background: rgba(100,100,120,200); height: 4px; border-radius: 2px;"
    "}"
    "QSlider::handle:horizontal {"
    "  background: #00ccff; width: 10px; height: 10px;"
    "  margin: -3px 0; border-radius: 5px;"
    "}"
    "QSlider::sub-page:horizontal {"
    "  background: #00ccff; border-radius: 2px;"
    "}"
)

_SCROLLBAR_STYLE = (
    "QScrollArea { background: transparent; border: none; }"
    "QScrollBar:vertical {"
    "  background: rgba(30, 30, 45, 100); width: 8px;"
    "}"
    "QScrollBar::handle:vertical {"
    "  background: rgba(80, 80, 100, 180); border-radius: 4px;"
    "  min-height: 20px;"
    "}"
    "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
    "  height: 0px;"
    "}"
)

# Twitch icon SVG (simplified Glitch logo)
_TWITCH_SVG = (
    '<path d="M4.265 2L2 6.529V19.471h5.294V22h3.529l2.647-2.529h3.882L22 14.824V2H4.265z'
    'M6.912 4.118h12.97v9.412l-3.235 3.058h-4.706L9.294 19.235v-2.647H6.912V4.118z"/>'
    '<path d="M11.647 7.412h2.118v5.294h-2.118zM16.412 7.412h2.118v5.294h-2.118z"/>'
)

# Chat bubble SVG
_CHAT_SVG = (
    '<path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>'
)

# Volume muted SVG
_VOLUME_MUTE_SVG = (
    '<path d="M3 9v6h4l5 5V4L7 9H3z"/>'
    '<path d="M16.5 12l2.1-2.1 1.4 1.4L17.9 13.4l2.1 2.1-1.4 1.4-2.1-2.1'
    '-2.1 2.1-1.4-1.4 2.1-2.1-2.1-2.1 1.4-1.4z"/>'
)

# Eye viewer icon
_VIEWER_SVG = (
    '<path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5'
    's9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5'
    's2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3'
    ' 3-1.34 3-3-1.34-3-3-3z"/>'
)

# Plus icon
_PLUS_SVG = '<path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>'

# Minus / remove icon
_REMOVE_SVG = '<path d="M19 13H5v-2h14v2z"/>'


def _overlay_icon(svg_data, size=14):
    return svg_icon(svg_data, TEXT_COLOR, size)


class StreamOverlay(OverlayWidget):
    """Twitch stream overlay with video playback and chat."""

    # Internal signals for thread → main-thread communication
    _streams_loaded = pyqtSignal(list)
    _avatar_ready = pyqtSignal(str, QPixmap)
    _viewer_count_ready = pyqtSignal(int)
    _twitch_login_done = pyqtSignal()
    _recent_messages_ready = pyqtSignal(list)

    def __init__(
        self,
        *,
        config,
        config_path: str,
        nexus_client: NexusClient | None = None,
        manager: OverlayManager | None = None,
    ):
        super().__init__(
            config=config,
            config_path=config_path,
            position_key="stream_overlay_position",
            manager=manager,
        )
        self._nexus_client = nexus_client
        self._stream_player = None
        self._chat_client = None
        self._emote_manager = None
        self._chat_buffer: list[dict] = []
        self._rendered_messages: list[dict] = []
        self._pending_emote_ids: set[str] = set()
        self._current_channel = ""
        self._current_channel_id = ""
        self._avatar_labels: dict[str, QLabel] = {}
        self._stream_rows: list[QWidget] = []
        self._size_btns: list[QPushButton] = []

        from ..streaming.twitch_auth import load_twitch_token, load_twitch_display_name
        self._twitch_token = load_twitch_token()
        self._twitch_display_name = load_twitch_display_name() or "You"

        # If token exists but display name was never fetched, fetch now
        if self._twitch_token and self._twitch_display_name == "You":
            threading.Thread(
                target=self._fetch_display_name,
                daemon=True,
                name="twitch-name",
            ).start()

        # Container style
        self._container.setStyleSheet(
            f"background-color: {BG_COLOR}; border-radius: 8px; padding: 0px;"
        )

        self._build_ui()
        self._apply_list_size()

        # Chat flush timer (batched updates)
        self._chat_flush_timer = QTimer(self)
        self._chat_flush_timer.setInterval(CHAT_FLUSH_INTERVAL_MS)
        self._chat_flush_timer.timeout.connect(self._flush_chat)

        # Viewer count poll timer (every 60s)
        self._viewer_poll_timer = QTimer(self)
        self._viewer_poll_timer.setInterval(60_000)
        self._viewer_poll_timer.timeout.connect(self._poll_viewer_count)

        # Connect internal signals
        self._streams_loaded.connect(self._on_streams_loaded)
        self._avatar_ready.connect(self._on_avatar_ready)
        self._viewer_count_ready.connect(self._on_viewer_count_ready)
        self._twitch_login_done.connect(self._reconnect_chat_authenticated)
        self._recent_messages_ready.connect(self._on_recent_messages)

        # Update login button if already authenticated
        if self._twitch_token:
            self._twitch_login_btn.setToolTip("Connected to Twitch")
            _user_svg = (
                '<path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4'
                ' 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>'
            )
            self._twitch_login_btn.setIcon(svg_icon(_user_svg, ACCENT, 12))

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._title_bar = self._build_title_bar()
        layout.addWidget(self._title_bar)

        # Body (hidden when minified)
        self._body = QWidget()
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self._stack = QStackedWidget()
        body_layout.addWidget(self._stack, 1)

        # Page 0: Stream list
        self._list_page = self._build_list_page()
        self._stack.addWidget(self._list_page)

        # Page 1: Player view
        self._player_page = self._build_player_page()
        self._stack.addWidget(self._player_page)

        self._stack.setCurrentIndex(_PAGE_LIST)
        layout.addWidget(self._body, 1)

        self._click_origin = None

    def _build_title_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(TITLE_H)
        bar.setStyleSheet(
            f"background-color: {TITLE_BG};"
            " border-top-left-radius: 8px; border-top-right-radius: 8px;"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(4, 0, 4, 0)
        lay.setSpacing(4)

        # Twitch icon
        icon_lbl = QLabel()
        icon_lbl.setPixmap(svg_pixmap(_TWITCH_SVG, ACCENT, 14))
        icon_lbl.setStyleSheet("background: transparent;")
        icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        lay.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        # Title label
        self._title_label = QLabel("Streams")
        self._title_label.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 13px; font-weight: bold;"
            " background: transparent;"
        )
        self._title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        lay.addWidget(self._title_label, 0, Qt.AlignmentFlag.AlignVCenter)

        lay.addStretch(1)

        # Size buttons (S/M/L) — hidden initially, shown during playback
        for i, label in enumerate(_SIZE_LABELS):
            btn = QPushButton(label)
            btn.setFixedSize(18, 18)
            active = i == self._config.stream_overlay_size_preset
            btn.setStyleSheet(_size_btn_style(active))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, idx=i: self._on_size_clicked(idx))
            btn.setVisible(False)
            lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)
            self._size_btns.append(btn)

        # Chat toggle button — hidden initially
        self._chat_toggle_btn = QPushButton()
        self._chat_toggle_btn.setFixedSize(18, 18)
        self._chat_toggle_btn.setIcon(svg_icon(_CHAT_SVG, TEXT_DIM, 14))
        self._chat_toggle_btn.setStyleSheet(_BTN_STYLE)
        self._chat_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._chat_toggle_btn.setToolTip("Toggle chat")
        self._chat_toggle_btn.clicked.connect(self._toggle_chat)
        self._chat_toggle_btn.setVisible(False)
        lay.addWidget(self._chat_toggle_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        # Minimize button
        _min_svg = '<path d="M19 13H5v-2h14v2z"/>'
        min_btn = QPushButton()
        min_btn.setFixedSize(18, 18)
        min_btn.setIcon(svg_icon(_min_svg, TEXT_DIM, 14))
        min_btn.setStyleSheet(_BTN_STYLE)
        min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        min_btn.setToolTip("Minimize")
        min_btn.clicked.connect(self._on_minimize)
        lay.addWidget(min_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        # Close button
        close_btn = QPushButton()
        close_btn.setFixedSize(18, 18)
        close_btn.setIcon(svg_icon(CLOSE_X, TEXT_DIM, 14))
        close_btn.setStyleSheet(_BTN_STYLE)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(self._on_close)
        lay.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        return bar

    # ------------------------------------------------------------------
    # Stream list page
    # ------------------------------------------------------------------

    def _build_list_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background-color: {CONTENT_BG}; border: none;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scrollable stream list
        self._list_scroll = QScrollArea()
        self._list_scroll.setWidgetResizable(True)
        self._list_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._list_scroll.setStyleSheet(_SCROLLBAR_STYLE)

        self._list_content = QWidget()
        self._list_layout = QVBoxLayout(self._list_content)
        self._list_layout.setContentsMargins(6, 6, 6, 6)
        self._list_layout.setSpacing(4)
        self._list_layout.addStretch(1)
        self._list_scroll.setWidget(self._list_content)
        layout.addWidget(self._list_scroll, 1)

        # Bottom: add custom streamer
        bottom = QWidget()
        bottom.setStyleSheet(
            f"background-color: {TITLE_BG};"
            " border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;"
        )
        bottom_lay = QHBoxLayout(bottom)
        bottom_lay.setContentsMargins(6, 4, 6, 4)
        bottom_lay.setSpacing(4)

        self._add_input = QLineEdit()
        self._add_input.setPlaceholderText("Add Twitch channel...")
        self._add_input.setStyleSheet(
            f"background: rgba(15,15,25,200); color: {TEXT_COLOR};"
            " border: 1px solid rgba(80,80,100,120); border-radius: 4px;"
            " padding: 3px 6px; font-size: 12px;"
        )
        self._add_input.returnPressed.connect(self._add_custom_streamer)
        bottom_lay.addWidget(self._add_input, 1)

        add_btn = QPushButton()
        add_btn.setFixedSize(24, 24)
        add_btn.setIcon(svg_icon(_PLUS_SVG, ACCENT, 16))
        add_btn.setStyleSheet(_CTRL_BTN_STYLE)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setToolTip("Add channel")
        add_btn.clicked.connect(self._add_custom_streamer)
        bottom_lay.addWidget(add_btn)

        layout.addWidget(bottom)

        return page

    def _build_stream_row(self, name: str, *, game: str = "",
                          viewers: int = 0, is_live: bool = False,
                          channel_url: str = "", avatar_url: str = "",
                          channel_id: int | str = 0,
                          is_custom: bool = False) -> QWidget:
        """Build a single stream entry row."""
        row = QWidget()
        row.setStyleSheet(
            f"QWidget {{ background: transparent; border-radius: 4px; }}"
            f"QWidget:hover {{ background: {ROW_HOVER}; }}"
        )
        row.setFixedHeight(48)
        row.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QHBoxLayout(row)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(8)

        # Avatar placeholder
        avatar_lbl = QLabel()
        avatar_lbl.setFixedSize(32, 32)
        avatar_lbl.setStyleSheet(
            "background: rgba(50,50,70,160); border-radius: 16px;"
        )
        avatar_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Show first letter as placeholder
        avatar_lbl.setText(name[0].upper() if name else "?")
        avatar_lbl.setStyleSheet(
            "background: rgba(50,50,70,160); border-radius: 16px;"
            f" color: {TEXT_DIM}; font-size: 14px; font-weight: bold;"
        )
        lay.addWidget(avatar_lbl)
        self._avatar_labels[name.lower()] = avatar_lbl

        # Name + game column
        info = QWidget()
        info.setStyleSheet("background: transparent;")
        info_lay = QVBoxLayout(info)
        info_lay.setContentsMargins(0, 0, 0, 0)
        info_lay.setSpacing(0)

        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color: {TEXT_BRIGHT}; font-size: 12px; font-weight: bold;"
            " background: transparent;"
        )
        info_lay.addWidget(name_lbl)

        if game:
            game_lbl = QLabel(game)
            game_lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 11px; background: transparent;"
            )
            game_lbl.setMaximumWidth(200)
            info_lay.addWidget(game_lbl)

        lay.addWidget(info, 1)

        # Live indicator + viewer count
        if is_live:
            live_w = QWidget()
            live_w.setStyleSheet("background: transparent;")
            live_lay = QHBoxLayout(live_w)
            live_lay.setContentsMargins(0, 0, 0, 0)
            live_lay.setSpacing(4)

            dot = QLabel("\u25CF")
            dot.setStyleSheet(f"color: {LIVE_COLOR}; font-size: 10px; background: transparent;")
            live_lay.addWidget(dot)

            if viewers > 0:
                viewer_lbl = QLabel(self._format_viewers(viewers))
                viewer_lbl.setStyleSheet(
                    f"color: {TEXT_DIM}; font-size: 11px; background: transparent;"
                )
                live_lay.addWidget(viewer_lbl)

            lay.addWidget(live_w)
        else:
            offline_lbl = QLabel("Offline")
            offline_lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 11px; background: transparent;"
            )
            lay.addWidget(offline_lbl)

        # Remove button for custom streamers
        if is_custom:
            rm_btn = QPushButton()
            rm_btn.setFixedSize(18, 18)
            rm_btn.setIcon(svg_icon(_REMOVE_SVG, TEXT_DIM, 14))
            rm_btn.setStyleSheet(_BTN_STYLE)
            rm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            rm_btn.setToolTip("Remove")
            rm_btn.clicked.connect(
                lambda checked, n=name: self._remove_custom_streamer(n)
            )
            lay.addWidget(rm_btn)

        # Store metadata for click handling
        row._stream_data = {
            "name": name,
            "channel_url": channel_url,
            "is_live": is_live,
            "channel_id": channel_id,
        }
        row.mousePressEvent = lambda event, r=row: self._on_stream_clicked(r)

        # Trigger avatar load
        if avatar_url:
            self._load_avatar(name, avatar_url)

        return row

    # ------------------------------------------------------------------
    # Player page
    # ------------------------------------------------------------------

    def _build_player_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main area: video + chat
        self._player_area = QWidget()
        self._player_area.setStyleSheet("background: transparent;")
        player_lay = QHBoxLayout(self._player_area)
        player_lay.setContentsMargins(0, 0, 0, 0)
        player_lay.setSpacing(0)

        # Video container (opaque black background for mpv)
        self._video_container = QWidget()
        self._video_container.setStyleSheet(f"background-color: {VIDEO_BG};")
        self._video_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding,
        )
        player_lay.addWidget(self._video_container, 1)

        # Chat panel (retractable)
        self._chat_panel = self._build_chat_panel()
        self._chat_panel.setVisible(self._config.stream_overlay_chat_visible)
        player_lay.addWidget(self._chat_panel)

        layout.addWidget(self._player_area, 1)

        # Controls bar
        self._controls_bar = self._build_controls()
        layout.addWidget(self._controls_bar)

        return page

    def _build_chat_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(CHAT_WIDTH)
        panel.setStyleSheet(
            f"background-color: {CHAT_BG};"
        )
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Chat header
        header = QWidget()
        header.setFixedHeight(24)
        header.setStyleSheet(f"background-color: {TITLE_BG};")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(6, 0, 6, 0)
        h_lay.setSpacing(4)

        chat_icon = QLabel()
        chat_icon.setPixmap(svg_pixmap(_CHAT_SVG, ACCENT, 12))
        chat_icon.setStyleSheet("background: transparent;")
        h_lay.addWidget(chat_icon)

        chat_title = QLabel("Chat")
        chat_title.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 11px; font-weight: bold;"
            " background: transparent;"
        )
        h_lay.addWidget(chat_title)
        h_lay.addStretch(1)

        # Twitch login button
        self._twitch_login_btn = QPushButton()
        self._twitch_login_btn.setFixedSize(16, 16)
        _login_svg = '<path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>'
        self._twitch_login_btn.setIcon(svg_icon(_login_svg, TEXT_DIM, 12))
        self._twitch_login_btn.setStyleSheet(_BTN_STYLE)
        self._twitch_login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._twitch_login_btn.setToolTip("Connect Twitch account")
        self._twitch_login_btn.clicked.connect(self._on_twitch_login)
        h_lay.addWidget(self._twitch_login_btn)

        lay.addWidget(header)

        # Chat message area
        from PyQt6.QtWidgets import QTextBrowser
        self._chat_browser = QTextBrowser()
        self._chat_browser.setOpenLinks(False)
        self._chat_browser.setStyleSheet(
            f"QTextBrowser {{"
            f"  background-color: {CHAT_BG}; color: {TEXT_COLOR};"
            f"  border: none; font-size: 12px; padding: 4px;"
            f"}}"
            + _SCROLLBAR_STYLE.replace("QScrollArea", "QTextBrowser")
        )
        self._chat_browser.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._chat_browser.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        lay.addWidget(self._chat_browser, 1)

        # Chat input (visible when authenticated)
        self._chat_input = QLineEdit()
        self._chat_input.setPlaceholderText("Send a message...")
        self._chat_input.setStyleSheet(
            f"background: rgba(15,15,25,200); color: {TEXT_COLOR};"
            " border: 1px solid rgba(80,80,100,120); border-radius: 0px;"
            " padding: 4px 6px; font-size: 12px;"
        )
        self._chat_input.returnPressed.connect(self._send_chat_message)
        self._chat_input.setVisible(bool(self._twitch_token))
        lay.addWidget(self._chat_input)

        return panel

    def _build_controls(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(CONTROLS_H)
        bar.setStyleSheet(
            f"background-color: {TITLE_BG};"
            " border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(6)

        # Back button
        back_btn = QPushButton()
        back_btn.setFixedSize(24, 24)
        back_btn.setIcon(svg_icon(ARROW_LEFT, TEXT_COLOR, 16))
        back_btn.setStyleSheet(_CTRL_BTN_STYLE)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setToolTip("Back to streams")
        back_btn.clicked.connect(self._on_back)
        lay.addWidget(back_btn)

        # Play/Pause button
        self._play_btn = QPushButton()
        self._play_btn.setFixedSize(24, 24)
        self._play_btn.setIcon(svg_icon(PAUSE, TEXT_COLOR, 14))
        self._play_btn.setStyleSheet(_CTRL_BTN_STYLE)
        self._play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._play_btn.setToolTip("Pause")
        self._play_btn.clicked.connect(self._on_play_pause)
        lay.addWidget(self._play_btn)

        # Mute button
        self._mute_btn = QPushButton()
        self._mute_btn.setFixedSize(24, 24)
        self._mute_btn.setIcon(svg_icon(VOLUME, TEXT_COLOR, 14))
        self._mute_btn.setStyleSheet(_CTRL_BTN_STYLE)
        self._mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mute_btn.setToolTip("Mute")
        self._mute_btn.clicked.connect(self._on_mute)
        lay.addWidget(self._mute_btn)

        # Volume slider
        self._vol_slider = QSlider(Qt.Orientation.Horizontal)
        self._vol_slider.setRange(0, 100)
        self._vol_slider.setValue(self._config.stream_overlay_volume)
        self._vol_slider.setFixedWidth(70)
        self._vol_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._vol_slider.setStyleSheet(_SLIDER_STYLE)
        self._vol_slider.valueChanged.connect(self._on_volume_changed)
        lay.addWidget(self._vol_slider)

        lay.addStretch(1)

        # Viewer count
        viewer_icon = QLabel()
        viewer_icon.setPixmap(svg_pixmap(_VIEWER_SVG, TEXT_DIM, 12))
        viewer_icon.setStyleSheet("background: transparent;")
        lay.addWidget(viewer_icon)

        self._viewer_label = QLabel("0")
        self._viewer_label.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 11px; background: transparent;"
        )
        lay.addWidget(self._viewer_label)

        return bar

    # ------------------------------------------------------------------
    # Visibility overrides
    # ------------------------------------------------------------------

    def set_wants_visible(self, visible: bool):
        super().set_wants_visible(visible)
        if visible and self._stack.currentIndex() == _PAGE_LIST:
            self._refresh_streams()

    def _on_minimize(self):
        self.set_wants_visible(False)

    def _on_close(self):
        self._stop_playback()
        self.set_wants_visible(False)

    # ------------------------------------------------------------------
    # Minify (click title bar to collapse/expand)
    # ------------------------------------------------------------------

    def _toggle_minify(self):
        expanding = not self._body.isVisible()
        self._body.setVisible(expanding)
        if expanding:
            self._title_bar.setStyleSheet(
                f"background-color: {TITLE_BG};"
                " border-top-left-radius: 8px; border-top-right-radius: 8px;"
            )
            if self._stack.currentIndex() == _PAGE_LIST:
                self._apply_list_size()
            else:
                self._apply_size_preset(self._config.stream_overlay_size_preset)
        else:
            self._title_bar.setStyleSheet(
                f"background-color: {TITLE_BG}; border-radius: 8px;"
            )
            self.setFixedSize(self.width(), TITLE_H)

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
                # Click (not drag) — toggle minify if in title bar area
                from PyQt6.QtCore import QPoint
                click_local = self.mapFromGlobal(click_origin)
                title_bottom = self._title_bar.mapTo(
                    self, QPoint(0, self._title_bar.height()),
                ).y()
                if click_local.y() <= title_bottom:
                    self._toggle_minify()

    # ------------------------------------------------------------------
    # Stream list logic
    # ------------------------------------------------------------------

    def _refresh_streams(self):
        """Fetch streams on a background thread."""
        if not self._nexus_client:
            return
        threading.Thread(
            target=self._fetch_streams,
            daemon=True,
            name="fetch-streams",
        ).start()

    def _fetch_streams(self):
        """Background thread: fetch stream data."""
        try:
            creators = self._nexus_client.get_streams() or []
        except Exception:
            creators = []
        self._streams_loaded.emit(creators)

    def _on_streams_loaded(self, creators: list):
        """Main-thread: rebuild the stream list (batched, no layout spam)."""
        self._list_content.setUpdatesEnabled(False)
        try:
            # Clear existing rows
            for row in self._stream_rows:
                row.setParent(None)
                row.deleteLater()
            self._stream_rows.clear()
            self._avatar_labels.clear()

            # Remove the stretch item
            while self._list_layout.count():
                item = self._list_layout.takeAt(0)
                if item.widget():
                    pass  # already handled above

            # Sort: live first, then alphabetical
            live = [c for c in creators if c.get("is_live")]
            offline = [c for c in creators if not c.get("is_live")]
            live.sort(key=lambda c: c.get("name", "").lower())
            offline.sort(key=lambda c: c.get("name", "").lower())

            # Section: Nexus Streamers
            if live or offline:
                section_lbl = QLabel("Nexus Streamers")
                section_lbl.setStyleSheet(
                    f"color: {ACCENT}; font-size: 11px; font-weight: bold;"
                    " background: transparent; padding: 2px 0px;"
                )
                self._list_layout.addWidget(section_lbl)
                self._stream_rows.append(section_lbl)

                for c in live + offline:
                    row = self._build_stream_row(
                        name=c.get("name", ""),
                        game=c.get("game_name", ""),
                        viewers=c.get("viewer_count", 0),
                        is_live=c.get("is_live", False),
                        channel_url=c.get("channel_url", ""),
                        avatar_url=c.get("avatar_url", ""),
                        channel_id=c.get("id", 0),
                    )
                    self._list_layout.addWidget(row)
                    self._stream_rows.append(row)

            # Section: Custom Streamers
            custom = getattr(self._config, "stream_custom_streamers", [])
            if custom:
                sep = QLabel("Custom Streamers")
                sep.setStyleSheet(
                    f"color: {ACCENT}; font-size: 11px; font-weight: bold;"
                    " background: transparent; padding: 6px 0px 2px 0px;"
                )
                self._list_layout.addWidget(sep)
                self._stream_rows.append(sep)

                for ch in custom:
                    row = self._build_stream_row(
                        name=ch,
                        channel_url=f"https://twitch.tv/{ch}",
                        is_custom=True,
                    )
                    self._list_layout.addWidget(row)
                    self._stream_rows.append(row)

            self._list_layout.addStretch(1)

        finally:
            self._list_content.setUpdatesEnabled(True)

    def _add_custom_streamer(self):
        """Add a custom streamer from the input field."""
        text = self._add_input.text().strip().lower()
        if not text:
            return

        # Strip URL prefix if pasted
        if "twitch.tv/" in text:
            text = text.split("twitch.tv/")[-1].split("/")[0].split("?")[0]

        custom = list(getattr(self._config, "stream_custom_streamers", []))
        if text not in custom:
            custom.append(text)
            self._config.stream_custom_streamers = custom
            save_config(self._config, self._config_path)
            self._add_input.clear()
            self._refresh_streams()

    def _remove_custom_streamer(self, name: str):
        """Remove a custom streamer."""
        custom = list(getattr(self._config, "stream_custom_streamers", []))
        if name in custom:
            custom.remove(name)
            self._config.stream_custom_streamers = custom
            save_config(self._config, self._config_path)
            self._refresh_streams()

    def _on_stream_clicked(self, row: QWidget):
        """Handle click on a stream row — start playback."""
        data = getattr(row, "_stream_data", None)
        if not data:
            return

        channel = data.get("name", "")
        if not channel:
            return

        self._start_playback(channel, channel_id=str(data.get("channel_id", "")))

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def _start_playback(self, channel: str, channel_id: str = ""):
        """Start playing a Twitch channel."""
        self._stop_playback()

        self._current_channel = channel
        self._current_channel_id = channel_id
        self._title_label.setText(channel)

        # Show player controls and resize to video preset
        for b in self._size_btns: b.setVisible(True)
        self._chat_toggle_btn.setVisible(True)
        self._apply_size_preset(self._config.stream_overlay_size_preset)
        self._stack.setCurrentIndex(_PAGE_PLAYER)

        # Initialize stream player — check dependencies
        from ..streaming.stream_player import (
            StreamPlayer, is_available, is_mpv_dll_missing,
            missing_components, _try_import_mpv,
        )

        if not is_available():
            if is_mpv_dll_missing():
                # Prompt user to download mpv-2.dll
                if not self._prompt_mpv_download():
                    self._on_back()
                    return
                # Re-check after download
                _try_import_mpv()
                if not is_available():
                    self._show_player_error("mpv-2.dll download failed")
                    return
            else:
                comps = missing_components()
                if comps:
                    self._show_player_error(
                        "Missing components:\n" + "\n".join(comps)
                    )
                    return

        self._stream_player = StreamPlayer(self._video_container, parent=self)
        self._stream_player.stream_started.connect(self._on_stream_started)
        self._stream_player.stream_error.connect(self._on_stream_error)
        self._stream_player.stream_ended.connect(self._on_stream_ended)
        self._stream_player.set_volume(self._vol_slider.value())
        self._stream_player.play_channel(channel)

        # Start chat
        self._start_chat(channel, channel_id)

    def _prompt_mpv_download(self) -> bool:
        """Show a dialog asking the user to download mpv-2.dll. Returns True on success."""
        from ..streaming.mpv_download_dialog import MpvDownloadDialog
        dialog = MpvDownloadDialog(parent=self)
        return dialog.exec() == dialog.DialogCode.Accepted

    def _stop_playback(self):
        """Stop current playback and clean up."""
        if self._stream_player:
            self._stream_player.stop()
            self._stream_player.cleanup()
            self._stream_player = None

        self._stop_chat()
        self._viewer_poll_timer.stop()
        self._current_channel = ""
        self._current_channel_id = ""

    def _show_player_error(self, message: str):
        """Show an error message in the video container."""
        # Clear any existing error labels
        for child in self._video_container.findChildren(QLabel):
            child.deleteLater()

        lbl = QLabel(message)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
            " padding: 20px;"
        )
        lay = self._video_container.layout()
        if lay is None:
            lay = QVBoxLayout(self._video_container)
            lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(lbl)

    def _on_stream_started(self):
        log.debug("Stream started: %s", self._current_channel)
        # Start viewer count polling
        self._poll_viewer_count()
        self._viewer_poll_timer.start()

    def _on_stream_error(self, error: str):
        log.debug("Stream error: %s", error)
        self._show_player_error(error)

    def _on_stream_ended(self):
        log.debug("Stream ended: %s", self._current_channel)

    def _on_back(self):
        """Return to stream list."""
        self._stop_playback()
        self._title_label.setText("Streams")
        for b in self._size_btns: b.setVisible(False)
        self._chat_toggle_btn.setVisible(False)
        self._stack.setCurrentIndex(_PAGE_LIST)
        self._apply_list_size()
        self._refresh_streams()

    def _on_play_pause(self):
        if not self._stream_player:
            return
        paused = self._stream_player.toggle_pause()
        icon_svg = PLAY if paused else PAUSE
        self._play_btn.setIcon(svg_icon(icon_svg, TEXT_COLOR, 14))
        self._play_btn.setToolTip("Play" if paused else "Pause")

    def _on_mute(self):
        if not self._stream_player:
            return
        muted = self._stream_player.toggle_mute()
        icon_svg = _VOLUME_MUTE_SVG if muted else VOLUME
        self._mute_btn.setIcon(svg_icon(icon_svg, TEXT_COLOR, 14))
        self._mute_btn.setToolTip("Unmute" if muted else "Mute")

    def _on_volume_changed(self, value: int):
        if self._stream_player:
            self._stream_player.set_volume(value)
        self._config.stream_overlay_volume = value
        save_config(self._config, self._config_path)

    # ------------------------------------------------------------------
    # Size presets
    # ------------------------------------------------------------------

    def _on_size_clicked(self, index: int):
        self._apply_size_preset(index)
        self._config.stream_overlay_size_preset = index
        save_config(self._config, self._config_path)

    def _apply_size_preset(self, index: int):
        """Resize the overlay based on the preset index (player view)."""
        index = max(0, min(len(_SIZE_PRESETS) - 1, index))
        video_w, video_h = _SIZE_PRESETS[index]

        chat_w = CHAT_WIDTH if self._config.stream_overlay_chat_visible else 0
        total_w = video_w + chat_w
        total_h = video_h + TITLE_H + CONTROLS_H

        self.setFixedSize(total_w, total_h)

        # Update button styles
        for i, btn in enumerate(self._size_btns):
            btn.setStyleSheet(_size_btn_style(i == index))

    def _apply_list_size(self):
        """Set a compact size for the stream list view."""
        self.setFixedSize(320, 400)

    # ------------------------------------------------------------------
    # Chat toggle
    # ------------------------------------------------------------------

    def _toggle_chat(self):
        visible = not self._chat_panel.isVisible()
        self._chat_panel.setVisible(visible)
        self._config.stream_overlay_chat_visible = visible
        save_config(self._config, self._config_path)
        self._apply_size_preset(self._config.stream_overlay_size_preset)

    # ------------------------------------------------------------------
    # Chat client
    # ------------------------------------------------------------------

    def _start_chat(self, channel: str, channel_id: str = ""):
        """Connect to Twitch IRC chat for the given channel."""
        from ..streaming.twitch_chat import TwitchChatClient, has_websockets

        if not has_websockets():
            log.debug("websockets not installed, chat disabled")
            return

        self._chat_buffer.clear()
        self._chat_browser.clear()

        token = self._twitch_token
        self._chat_client = TwitchChatClient(
            channel, oauth_token=token, parent=self,
        )
        self._chat_client.message_received.connect(self._on_chat_message)
        self._chat_client.room_id_received.connect(self._on_room_id)
        self._chat_client.connected.connect(
            lambda: log.debug("Chat connected to #%s", channel)
        )
        self._chat_client.disconnected.connect(
            lambda reason: log.debug("Chat disconnected: %s", reason)
        )
        self._chat_client.start()
        self._chat_flush_timer.start()

        # Load recent chat history in background
        threading.Thread(
            target=self._fetch_recent_messages,
            args=(channel,),
            daemon=True,
            name=f"recent-msgs-{channel}",
        ).start()

        # Load global emotes (channel emotes loaded when room_id arrives)
        self._ensure_emote_manager()

    def _stop_chat(self):
        """Disconnect chat and stop flush timer."""
        self._chat_flush_timer.stop()
        self._rendered_messages.clear()
        self._pending_emote_ids.clear()
        if self._chat_client:
            self._chat_client.stop()
            # Don't wait synchronously — the thread will exit on its own
            # after the next recv timeout (~1s).
            self._chat_client = None
        if self._emote_manager:
            self._emote_manager.clear_channel_emotes()

    def _ensure_emote_manager(self):
        """Create emote manager if not yet initialized."""
        if self._emote_manager is not None:
            return
        try:
            from ..streaming.twitch_emotes import EmoteManager
            cache_dir = os.path.join(
                os.path.expanduser("~"), ".entropia-nexus", "emote_cache"
            )
            self._emote_manager = EmoteManager(cache_dir)
            # Load globals in background
            threading.Thread(
                target=self._emote_manager.load_global_emotes,
                daemon=True,
                name="emotes-global",
            ).start()
        except Exception as exc:
            log.debug("Failed to create EmoteManager: %s", exc)

    def _on_room_id(self, room_id: str):
        """Main-thread: Twitch user ID received — load channel emotes."""
        self._current_channel_id = room_id
        if self._emote_manager and room_id:
            threading.Thread(
                target=self._load_emotes_for_channel,
                args=(self._current_channel, room_id),
                daemon=True,
                name=f"emotes-{self._current_channel}",
            ).start()

    def _load_emotes_for_channel(self, channel: str, channel_id: str):
        """Background thread: load channel-specific emotes."""
        if self._emote_manager and channel_id:
            self._emote_manager.load_channel_emotes(channel, channel_id)

    def _fetch_recent_messages(self, channel: str):
        """Background thread: fetch recent chat history and pre-download emotes."""
        from ..streaming.twitch_chat import fetch_recent_messages
        messages = fetch_recent_messages(channel)
        if messages:
            # Pre-download Twitch emotes so they're cached before rendering
            if self._emote_manager:
                emote_ids = set()
                for msg in messages:
                    for e in msg.get("emotes", []):
                        emote_ids.add(e["id"])
                if emote_ids:
                    self._emote_manager._download_twitch_emotes(list(emote_ids))
            self._recent_messages_ready.emit(messages)

    def _on_recent_messages(self, messages: list):
        """Main-thread: prepend recent messages to chat."""
        for msg in messages:
            self._chat_buffer.append(msg)

    def _on_chat_message(self, msg: dict):
        """Slot: buffer incoming chat message (no UI work here)."""
        self._chat_buffer.append(msg)

    def _flush_chat(self):
        """Timer slot: batch-render buffered chat messages into QTextBrowser."""
        has_new = bool(self._chat_buffer)

        # Check if any pending emotes are now cached → rebuild
        if self._pending_emote_ids and self._emote_manager:
            newly_cached = {
                eid for eid in self._pending_emote_ids
                if self._emote_manager.get_twitch_emote_path(eid)
            }
            if newly_cached:
                self._pending_emote_ids -= newly_cached
                # Absorb any buffered messages into rendered list first
                if self._chat_buffer:
                    self._rendered_messages.extend(
                        self._chat_buffer[-MAX_MESSAGES_PER_FLUSH:]
                    )
                    self._chat_buffer.clear()
                self._rebuild_chat()
                return

        if not has_new:
            return

        # Hard cap: keep only the last N messages per flush
        batch = self._chat_buffer[-MAX_MESSAGES_PER_FLUSH:]
        self._chat_buffer.clear()

        # Track rendered messages for potential rebuild
        self._rendered_messages.extend(batch)
        if len(self._rendered_messages) > MAX_CHAT_MESSAGES:
            self._rendered_messages = self._rendered_messages[-MAX_CHAT_MESSAGES:]

        # Collect Twitch emote IDs for background download
        if self._emote_manager:
            emote_ids = set()
            for msg in batch:
                for e in msg.get("emotes", []):
                    eid = e["id"]
                    emote_ids.add(eid)
                    if not self._emote_manager.get_twitch_emote_path(eid):
                        self._pending_emote_ids.add(eid)
            if emote_ids:
                self._emote_manager.queue_twitch_emotes(emote_ids)

        # Check if scrollbar is at the bottom before appending
        sb = self._chat_browser.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 5

        self._chat_browser.setUpdatesEnabled(False)
        try:
            html_parts = []
            for msg in batch:
                html_parts.append(self._render_chat_message(msg))

            if html_parts:
                self._chat_browser.append("".join(html_parts))

            # Prune old messages
            doc = self._chat_browser.document()
            block_count = doc.blockCount()
            if block_count > MAX_CHAT_MESSAGES:
                excess = block_count - MAX_CHAT_MESSAGES
                cursor = QTextCursor(doc)
                cursor.movePosition(QTextCursor.MoveOperation.Start)
                for _ in range(excess):
                    cursor.movePosition(
                        QTextCursor.MoveOperation.Down,
                        QTextCursor.MoveMode.KeepAnchor,
                    )
                cursor.movePosition(
                    QTextCursor.MoveOperation.StartOfBlock,
                    QTextCursor.MoveMode.KeepAnchor,
                )
                cursor.removeSelectedText()
                cursor.deleteChar()  # remove trailing newline

        finally:
            self._chat_browser.setUpdatesEnabled(True)

        # Auto-scroll only if user was already at the bottom
        if at_bottom:
            sb.setValue(sb.maximum())

    def _rebuild_chat(self):
        """Re-render all messages from the rendered buffer (emotes may have updated)."""
        sb = self._chat_browser.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 5

        self._chat_browser.setUpdatesEnabled(False)
        try:
            self._chat_browser.clear()
            html_parts = []
            for msg in self._rendered_messages:
                html_parts.append(self._render_chat_message(msg))
            if html_parts:
                self._chat_browser.setHtml("".join(html_parts))
        finally:
            self._chat_browser.setUpdatesEnabled(True)

        if at_bottom:
            sb.setValue(sb.maximum())

    def _render_chat_message(self, msg: dict) -> str:
        """Render a single chat message as HTML."""
        parts = []

        # Badges
        from ..streaming.twitch_badges import get_badge_file
        for badge_type in msg.get("badges", []):
            badge_path = get_badge_file(badge_type, 14)
            if badge_path:
                parts.append(
                    f'<img src="file:///{badge_path.replace(os.sep, "/")}" '
                    f'width="14" height="14" style="vertical-align: middle;"> '
                )

        # Username
        display_name = html_mod.escape(msg.get("display_name", ""))
        color = msg.get("color", "") or "#aaaaaa"
        parts.append(
            f'<b style="color: {color};">{display_name}</b>'
            f'<span style="color: {TEXT_DIM};">: </span>'
        )

        # Message text with emote replacement
        message = msg.get("message", "")
        emotes = msg.get("emotes", [])

        if emotes:
            # Replace Twitch native emotes by position
            segments = []
            last_end = 0
            for emote in emotes:
                start = emote["start"]
                end = emote["end"] + 1
                if start > last_end:
                    segments.append(("text", message[last_end:start]))
                # Get emote image
                emote_path = None
                if self._emote_manager:
                    emote_path = self._emote_manager.get_twitch_emote_path(emote["id"])
                if emote_path:
                    segments.append(("emote", emote_path))
                else:
                    segments.append(("text", message[start:end]))
                last_end = end
            if last_end < len(message):
                segments.append(("text", message[last_end:]))

            for seg_type, seg_val in segments:
                if seg_type == "emote":
                    parts.append(
                        f'<img src="file:///{seg_val.replace(os.sep, "/")}" '
                        f'height="22" style="vertical-align: middle;">'
                    )
                else:
                    parts.append(self._render_text_with_third_party(seg_val))
        else:
            parts.append(self._render_text_with_third_party(message))

        return f'<p style="margin: 2px 0;">{"".join(parts)}</p>'

    def _render_text_with_third_party(self, text: str) -> str:
        """Replace third-party emote codes in text with <img> tags."""
        if not self._emote_manager:
            return html_mod.escape(text)

        words = text.split(" ")
        result = []
        for word in words:
            emote_path = self._emote_manager.resolve_third_party(word)
            if emote_path:
                result.append(
                    f'<img src="file:///{emote_path.replace(os.sep, "/")}" '
                    f'height="22" style="vertical-align: middle;">'
                )
            else:
                result.append(html_mod.escape(word))

        return " ".join(result)

    # ------------------------------------------------------------------
    # Twitch auth & chat sending
    # ------------------------------------------------------------------

    def _fetch_display_name(self):
        """Background thread: fetch and cache Twitch display name."""
        from ..streaming.twitch_auth import (
            DEFAULT_TWITCH_CLIENT_ID, fetch_twitch_display_name,
            save_twitch_display_name,
        )
        client_id = (
            getattr(self._config, "twitch_client_id", "")
            or DEFAULT_TWITCH_CLIENT_ID
        )
        name = fetch_twitch_display_name(self._twitch_token, client_id)
        if name:
            save_twitch_display_name(name)
            self._twitch_display_name = name

    def _on_twitch_login(self):
        """Open Twitch OAuth login flow in a background thread."""
        from ..streaming.twitch_auth import DEFAULT_TWITCH_CLIENT_ID
        client_id = (
            getattr(self._config, "twitch_client_id", "")
            or DEFAULT_TWITCH_CLIENT_ID
        )

        # Run OAuth in a background thread (it blocks waiting for browser)
        threading.Thread(
            target=self._twitch_login_worker,
            args=(client_id,),
            daemon=True,
            name="twitch-oauth",
        ).start()

    def _twitch_login_worker(self, client_id: str):
        """Background thread: run Twitch OAuth flow."""
        from ..streaming.twitch_auth import (
            twitch_login, save_twitch_token,
            fetch_twitch_display_name, save_twitch_display_name,
        )
        token = twitch_login(client_id)
        if token:
            save_twitch_token(token)
            self._twitch_token = token
            # Fetch and cache display name
            name = fetch_twitch_display_name(token, client_id)
            if name:
                save_twitch_display_name(name)
                self._twitch_display_name = name
            self._twitch_login_done.emit()

    def _reconnect_chat_authenticated(self):
        """Main-thread: reconnect chat with the new OAuth token."""
        if self._current_channel:
            self._stop_chat()
            self._start_chat(self._current_channel, self._current_channel_id)
        self._chat_input.setVisible(True)
        self._twitch_login_btn.setToolTip("Connected to Twitch")
        self._twitch_login_btn.setIcon(
            svg_icon(
                '<path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4'
                ' 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>',
                ACCENT, 12,
            )
        )

    def _send_chat_message(self):
        """Send the chat input text as a Twitch message."""
        text = self._chat_input.text().strip()
        if not text or not self._chat_client:
            return
        self._chat_client.send_message(text)
        self._chat_input.clear()
        # Message will appear via echo-message capability — Twitch
        # sends it back as a normal PRIVMSG with full emote tags.

    # ------------------------------------------------------------------
    # Viewer count polling
    # ------------------------------------------------------------------

    def _poll_viewer_count(self):
        """Fetch current viewer count on a background thread."""
        if not self._nexus_client or not self._current_channel:
            return
        threading.Thread(
            target=self._fetch_viewer_count,
            daemon=True,
            name="poll-viewers",
        ).start()

    def _fetch_viewer_count(self):
        """Background thread: get viewer count for current channel."""
        try:
            creators = self._nexus_client.get_streams() or []
            for c in creators:
                name = c.get("name", "").lower()
                if name == self._current_channel.lower() and c.get("is_live"):
                    self._viewer_count_ready.emit(c.get("viewer_count", 0))
                    return
        except Exception:
            pass

    def _on_viewer_count_ready(self, count: int):
        """Main-thread: update the viewer count label."""
        self._viewer_label.setText(self._format_viewers(count))

    # ------------------------------------------------------------------
    # Avatar loading
    # ------------------------------------------------------------------

    def _load_avatar(self, name: str, url: str):
        """Load an avatar image on a background thread."""
        threading.Thread(
            target=self._fetch_avatar,
            args=(name, url),
            daemon=True,
            name=f"avatar-{name}",
        ).start()

    def _fetch_avatar(self, name: str, url: str):
        """Background thread: download avatar and emit signal."""
        try:
            import requests
            resp = requests.get(url, timeout=10)
            if resp.ok:
                pixmap = QPixmap()
                pixmap.loadFromData(resp.content)
                if not pixmap.isNull():
                    # Scale to 32x32
                    pixmap = pixmap.scaled(
                        32, 32,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self._avatar_ready.emit(name.lower(), pixmap)
        except Exception:
            pass

    def _on_avatar_ready(self, name: str, pixmap: QPixmap):
        """Main-thread: swap avatar pixmap on existing label."""
        lbl = self._avatar_labels.get(name)
        if lbl:
            lbl.setPixmap(pixmap)
            lbl.setText("")
            lbl.setStyleSheet(
                "background: transparent; border-radius: 16px;"
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_viewers(count: int) -> str:
        if count >= 1000:
            return f"{count / 1000:.1f}K"
        return str(count)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        self._stop_playback()
        super().closeEvent(event)
