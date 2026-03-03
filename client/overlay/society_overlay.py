"""Society overlay — always-on-top overlay showing a Nexus society."""

from __future__ import annotations

import threading
import webbrowser
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QWidget, QPushButton,
    QScrollArea, QStackedWidget, QTextEdit, QLineEdit, QCheckBox,
)
from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal

from .overlay_widget import OverlayWidget
from ..ui.icons import svg_icon

if TYPE_CHECKING:
    from .overlay_manager import OverlayManager

# --- Layout ---
SOCIETY_WIDTH = 460
BODY_HEIGHT = 420
TAB_STRIP_W = 28
TAB_BTN_SIZE = 22

# --- Colors (overlay dark theme — matches profile_overlay) ---
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

# --- SVG icon paths (24x24 viewBox) ---
_PIN_SVG = '<path d="M16 12V4h1V2H7v2h1v8l-2 2v2h5v6l1 1 1-1v-6h5v-2z"/>'

_CLOSE_SVG = (
    '<path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59'
    ' 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>'
)

# Tab icons
_TAB_GENERAL_SVG = (
    '<path d="M12 12.75c1.63 0 3.07.39 4.24.9 1.08.48 1.76 1.56 1.76 2.73V18H6v-1.61'
    'c0-1.18.68-2.26 1.76-2.73 1.17-.52 2.61-.91 4.24-.91zM4 13c1.1 0 2-.9 2-2s-.9-2-2-2'
    '-2 .9-2 2 .9 2 2 2zm1.13 1.1c-.37-.06-.74-.1-1.13-.1-.99 0-1.93.21-2.78.58A2.01 2.01 0'
    ' 0 0 0 16.43V18h4.5v-1.61c0-.83-.52-1.58-1.37-1.92zM20 13c1.1 0 2-.9 2-2s-.9-2-2-2'
    '-2 .9-2 2 .9 2 2 2zm4 3.43c0-.81-.48-1.53-1.22-1.85A6.95 6.95 0 0 0 20 14c-.39 0-.76.04-1.13.1'
    '.85.34 1.37 1.09 1.37 1.92V18h3.5v-1.57zM12 6c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3'
    ' 1.34-3 3-3z"/>'
)

_TAB_MEMBERS_SVG = (
    '<path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3z'
    'm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7'
    ' 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97'
    ' 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/>'
)

_TAB_REQUESTS_SVG = (
    '<path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z'
    'm-2 10h-4v4h-2v-4H7v-2h4V7h2v4h4v2z"/>'
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

# Leader crown icon (small, inline)
_CROWN_SVG = (
    '<path d="M5 16h14v2H5zm14-5.5l-3.5 2-3.5-4-3.5 4L5 10.5 6.5 18h11z"/>'
)

# --- Tab IDs ---
TAB_GENERAL = "general"
TAB_MEMBERS = "members"
TAB_REQUESTS = "requests"
TAB_SETTINGS = "settings"

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


# --- Helpers ---

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


def _get_society_tabs(data: dict) -> list[tuple[str, str, str]]:
    """Return (svg_path, tooltip, tab_id) for each tab based on society data."""
    tabs = [
        (_TAB_GENERAL_SVG, "General", TAB_GENERAL),
        (_TAB_MEMBERS_SVG, "Members", TAB_MEMBERS),
    ]
    if data.get("isLeader") and data.get("pendingCount", 0) > 0:
        tabs.append((_TAB_REQUESTS_SVG, "Requests", TAB_REQUESTS))
    if data.get("isLeader"):
        tabs.append((_TAB_SETTINGS_SVG, "Settings", TAB_SETTINGS))
    return tabs


class SocietyOverlayWidget(OverlayWidget):
    """Always-on-top overlay showing a Nexus society."""

    open_entity = pyqtSignal(dict)
    _society_loaded = pyqtSignal(object)        # dict or None
    _save_result = pyqtSignal(bool, str)         # (success, error_msg)
    _request_result = pyqtSignal(int, bool, str)  # (request_id, success, error_msg)

    def __init__(
        self,
        society_name: str,
        *,
        config,
        config_path: str,
        nexus_client,
        manager: OverlayManager | None = None,
    ):
        super().__init__(
            config=config,
            config_path=config_path,
            position_key="society_overlay_position",
            manager=manager,
        )
        self._society_name = society_name
        self._nexus_client = nexus_client
        self._society_data: dict | None = None
        self._pinned = False
        self._click_origin = None
        self._load_gen = 0
        self._request_rows: dict[int, QWidget] = {}

        # Auto-resize to content
        self.layout().setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        self._container.setFixedWidth(SOCIETY_WIDTH)
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
        self._society_loaded.connect(self._on_society_loaded)
        self._save_result.connect(self._on_save_result)
        self._request_result.connect(self._on_request_result)

        self._settings_widgets: dict = {}

        # Start visible
        self.set_wants_visible(True)
        self.activateWindow()

        # Fetch society in background
        self._fetch_society()

    # --- Properties ---

    @property
    def pinned(self) -> bool:
        return self._pinned

    def set_pinned(self, value: bool):
        self._pinned = value
        self._update_pin_icon()

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
        self._name_label = _ElidedLabel(self._society_name)
        self._name_label.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 13px; font-weight: bold;"
            " background: transparent;"
        )
        self._name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self._name_label, 1, Qt.AlignmentFlag.AlignVCenter)

        # Type badge
        badge = QLabel("Society")
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

        open_btn = QPushButton("Open on Website")
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

    def _open_in_browser(self):
        base = self._nexus_client._config.nexus_base_url.rstrip("/")
        encoded = self._society_name.replace(" ", "~")
        webbrowser.open(f"{base}/societies/{encoded}")

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

    def _fetch_society(self):
        self._load_gen += 1
        gen = self._load_gen
        nc = self._nexus_client
        name = self._society_name

        def _worker():
            data = nc.get_society(name)
            if gen == self._load_gen:
                self._society_loaded.emit(data)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_society_loaded(self, data):
        if data is None:
            self._show_error("Failed to load society", retry=True)
            return

        self._society_data = data
        society = data.get("society", {})

        # Update title
        soc_name = society.get("name", self._society_name)
        self._name_label.set_text(soc_name)

        # Build tabs based on data
        tab_defs = _get_society_tabs(data)
        self._rebuild_tab_strip(tab_defs)

        # Build content for each tab
        self._build_general_tab(data)
        self._build_members_tab(data)

        if TAB_REQUESTS in self._tab_ids:
            self._build_requests_tab(data.get("pending", []))
        if TAB_SETTINGS in self._tab_ids:
            self._build_settings_tab(data)

        self._switch_tab(0)

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
        while self._content_stack.count():
            w = self._content_stack.widget(0)
            self._content_stack.removeWidget(w)
            w.deleteLater()
        self._init_loading_tab()
        self._switch_tab(0)
        self._fetch_society()

    # --- General tab ---

    def _build_general_tab(self, data: dict):
        society = data.get("society", {})
        members = data.get("members", [])

        scroll = self._make_scroll()
        layout = scroll.widget().layout()

        # Society name + abbreviation
        soc_name = society.get("name", "")
        soc_abbr = society.get("abbreviation", "")
        title_text = f"{soc_name} [{soc_abbr}]" if soc_abbr else soc_name
        title_lbl = QLabel(title_text)
        title_lbl.setStyleSheet(
            f"color: {TEXT_BRIGHT}; font-size: 14px; font-weight: bold;"
            " background: transparent;"
        )
        title_lbl.setWordWrap(True)
        layout.addWidget(title_lbl)

        # Leader
        leader_id = society.get("leader_id")
        leader_name = ""
        for m in members:
            if m.get("id") == leader_id:
                leader_name = m.get("eu_name") or m.get("global_name") or m.get("username", "")
                break

        if leader_name:
            leader_row = QWidget()
            leader_row.setStyleSheet("background: transparent;")
            lr_layout = QHBoxLayout(leader_row)
            lr_layout.setContentsMargins(0, 2, 0, 2)
            lr_layout.setSpacing(4)

            leader_label = QLabel("Leader:")
            leader_label.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
            )
            lr_layout.addWidget(leader_label)

            leader_btn = QPushButton(leader_name)
            leader_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            leader_btn.setStyleSheet(
                f"color: {ACCENT}; font-size: 12px; background: transparent;"
                " border: none; padding: 0; text-align: left;"
            )
            leader_btn.clicked.connect(
                lambda _, n=leader_name: self.open_entity.emit({"Name": n, "Type": "User"})
            )
            lr_layout.addWidget(leader_btn, 1)
            layout.addWidget(leader_row)

        # Member count
        layout.addWidget(_stat_row("Members", str(len(members))))

        # Description
        description = society.get("description", "")
        if description and description.strip():
            layout.addWidget(_separator())
            layout.addWidget(_section_label("DESCRIPTION"))
            desc_lbl = QLabel(description)
            desc_lbl.setTextFormat(Qt.TextFormat.RichText)
            desc_lbl.setWordWrap(True)
            desc_lbl.setOpenExternalLinks(True)
            desc_lbl.setStyleSheet(
                f"color: {TEXT_COLOR}; font-size: 12px; background: transparent;"
                " line-height: 1.4;"
            )
            layout.addWidget(desc_lbl)

        # Discord invite
        discord_code = society.get("discord_code", "")
        discord_public = society.get("discord_public", False)
        # Show discord if public, or if user is a member
        show_discord = discord_code and (discord_public or data.get("isMember"))
        if show_discord:
            layout.addWidget(_separator())
            layout.addWidget(_section_label("DISCORD"))
            discord_btn = QPushButton(f"discord.gg/{discord_code}")
            discord_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            discord_btn.setStyleSheet(
                f"color: {ACCENT}; font-size: 12px; background: transparent;"
                " border: none; padding: 2px 0; text-align: left;"
            )
            discord_btn.clicked.connect(
                lambda: webbrowser.open(f"https://discord.gg/{discord_code}")
            )
            layout.addWidget(discord_btn)

        layout.addStretch()
        self._content_stack.addWidget(scroll)

    # --- Members tab ---

    def _build_members_tab(self, data: dict):
        society = data.get("society", {})
        members = data.get("members", [])
        leader_id = society.get("leader_id")

        scroll = self._make_scroll()
        layout = scroll.widget().layout()
        layout.addWidget(_section_label(f"MEMBERS ({len(members)})"))

        # Sort: leader first, then alphabetical
        def sort_key(m):
            is_leader = 0 if m.get("id") == leader_id else 1
            name = (m.get("eu_name") or m.get("global_name") or m.get("username", "")).lower()
            return (is_leader, name)

        for member in sorted(members, key=sort_key):
            name = member.get("eu_name") or member.get("global_name") or member.get("username", "")
            is_leader = member.get("id") == leader_id

            row = QWidget()
            row.setStyleSheet("background: transparent;")
            r_layout = QHBoxLayout(row)
            r_layout.setContentsMargins(0, 2, 0, 2)
            r_layout.setSpacing(4)

            name_btn = QPushButton(name)
            name_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            name_btn.setStyleSheet(
                f"color: {ACCENT}; font-size: 12px; background: transparent;"
                " border: none; padding: 0; text-align: left;"
            )
            name_btn.clicked.connect(
                lambda _, n=name: self.open_entity.emit({"Name": n, "Type": "User"})
            )
            r_layout.addWidget(name_btn, 1)

            if is_leader:
                crown = QLabel()
                crown.setPixmap(svg_icon(_CROWN_SVG, "#fbbf24", 14).pixmap(14, 14))
                crown.setFixedSize(14, 14)
                crown.setToolTip("Leader")
                crown.setStyleSheet("background: transparent;")
                r_layout.addWidget(crown, 0, Qt.AlignmentFlag.AlignVCenter)

            layout.addWidget(row)

        layout.addStretch()
        self._content_stack.addWidget(scroll)

    # --- Requests tab (leader only) ---

    def _build_requests_tab(self, pending: list[dict]):
        scroll = self._make_scroll()
        layout = scroll.widget().layout()
        layout.addWidget(_section_label(f"PENDING REQUESTS ({len(pending)})"))

        self._request_rows.clear()

        if not pending:
            lbl = QLabel("No pending requests")
            lbl.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 12px; background: transparent;"
            )
            layout.addWidget(lbl)
        else:
            for req in pending:
                req_id = req.get("id")
                user_name = req.get("eu_name") or req.get("global_name") or ""
                created = req.get("created_at", "")[:10]  # date only

                row = QWidget()
                row.setStyleSheet("background: transparent;")
                r_layout = QHBoxLayout(row)
                r_layout.setContentsMargins(0, 3, 0, 3)
                r_layout.setSpacing(4)

                # User name (clickable)
                name_btn = QPushButton(user_name)
                name_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                name_btn.setStyleSheet(
                    f"color: {ACCENT}; font-size: 12px; background: transparent;"
                    " border: none; padding: 0; text-align: left;"
                )
                name_btn.clicked.connect(
                    lambda _, n=user_name: self.open_entity.emit({"Name": n, "Type": "User"})
                )
                r_layout.addWidget(name_btn, 1)

                # Date
                if created:
                    date_lbl = QLabel(created)
                    date_lbl.setStyleSheet(
                        f"color: {TEXT_DIM}; font-size: 10px; background: transparent;"
                    )
                    r_layout.addWidget(date_lbl)

                # Approve button
                approve_btn = QPushButton("Approve")
                approve_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                approve_btn.setStyleSheet(
                    f"color: {SUCCESS_COLOR}; font-size: 10px;"
                    " background: transparent; border: 1px solid rgba(22,163,74,150);"
                    " border-radius: 3px; padding: 2px 6px;"
                )
                approve_btn.clicked.connect(
                    lambda _, rid=req_id: self._handle_request(rid, "approve")
                )
                r_layout.addWidget(approve_btn)

                # Reject button
                reject_btn = QPushButton("Reject")
                reject_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                reject_btn.setStyleSheet(
                    f"color: {ERROR_COLOR}; font-size: 10px;"
                    " background: transparent; border: 1px solid rgba(239,68,68,150);"
                    " border-radius: 3px; padding: 2px 6px;"
                )
                reject_btn.clicked.connect(
                    lambda _, rid=req_id: self._handle_request(rid, "reject")
                )
                r_layout.addWidget(reject_btn)

                layout.addWidget(row)
                self._request_rows[req_id] = row

        layout.addStretch()
        self._content_stack.addWidget(scroll)

    def _handle_request(self, request_id: int, action: str):
        nc = self._nexus_client

        def _worker():
            result = nc.handle_join_request(request_id, action)
            self._request_result.emit(
                request_id, result is not None,
                "" if result else f"Failed to {action}",
            )

        threading.Thread(target=_worker, daemon=True).start()

    def _on_request_result(self, request_id: int, success: bool, error: str):
        row = self._request_rows.get(request_id)
        if not row:
            return

        if success:
            # Replace row content with status
            layout = row.layout()
            while layout.count():
                item = layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
            done_lbl = QLabel("Done")
            done_lbl.setStyleSheet(
                f"color: {SUCCESS_COLOR}; font-size: 11px; background: transparent;"
            )
            layout.addWidget(done_lbl)
            # Fade out after delay
            QTimer.singleShot(2000, lambda: row.setVisible(False))
        else:
            # Show error inline (briefly highlight)
            row.setStyleSheet(f"background: rgba(239,68,68,30);")
            QTimer.singleShot(2000, lambda: row.setStyleSheet("background: transparent;"))

    # --- Settings tab (leader only) ---

    def _build_settings_tab(self, data: dict):
        society = data.get("society", {})

        scroll = self._make_scroll()
        layout = scroll.widget().layout()

        # Description
        layout.addWidget(_section_label("DESCRIPTION"))
        self._desc_edit = QTextEdit()
        self._desc_edit.setMaximumHeight(80)
        self._desc_edit.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 12px;"
            " background: rgba(40, 40, 55, 200); border: 1px solid rgba(100,100,120,150);"
            " border-radius: 3px; padding: 4px;"
        )
        self._desc_edit.setPlainText(society.get("description", "") or "")
        layout.addWidget(self._desc_edit)

        layout.addWidget(_separator())

        # Discord invite code
        layout.addWidget(_section_label("DISCORD INVITE CODE"))
        self._discord_input = QLineEdit()
        self._discord_input.setPlaceholderText("e.g. hBGKyJ6EDr")
        self._discord_input.setText(society.get("discord_code", "") or "")
        self._discord_input.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 12px;"
            " background: rgba(40, 40, 55, 200); border: 1px solid rgba(100,100,120,150);"
            " border-radius: 3px; padding: 4px 6px;"
        )
        layout.addWidget(self._discord_input)

        # Discord public toggle
        self._discord_public_cb = QCheckBox("Discord link visible to everyone")
        self._discord_public_cb.setChecked(society.get("discord_public", False))
        self._discord_public_cb.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 12px; background: transparent;"
            " spacing: 6px;"
        )
        layout.addWidget(self._discord_public_cb)

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

    def _on_save_settings(self):
        if not self._society_data:
            return

        desc = self._desc_edit.toPlainText().strip()
        discord = self._discord_input.text().strip()
        discord_public = self._discord_public_cb.isChecked()

        payload = {
            "description": desc,
            "discord": discord,
            "discordPublic": discord_public,
        }

        save_btn = self._settings_widgets.get("save_btn")
        if save_btn:
            save_btn.setEnabled(False)
            save_btn.setText("Saving...")

        nc = self._nexus_client
        name = self._society_name

        def _worker():
            result = nc.update_society(name, payload)
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
        hint.setWidth(SOCIETY_WIDTH)
        return hint
