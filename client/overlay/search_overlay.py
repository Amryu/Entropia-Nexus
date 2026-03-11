"""In-game search overlay — always-on-top search bar with flat results dropdown."""

from __future__ import annotations

import webbrowser
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QWidget,
    QDialog, QScrollArea,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor

from .overlay_widget import OverlayWidget
from ..ui.icons import nexus_logo_pixmap, svg_pixmap
from ..ui.widgets.fuzzy_line_edit import score_search
from ..ui.widgets.search_popup import get_type_name, get_display_type, CREATABLE_CATEGORIES

if TYPE_CHECKING:
    from ..api.data_client import DataClient
    from .overlay_manager import OverlayManager

from ..platform import backend as _platform

# Layout
SEARCH_WIDTH = 350
MAX_VISIBLE_RESULTS = 10
ROW_HEIGHT = 28

# Colors (overlay-specific — dark translucent theme)
BG_COLOR = "rgba(20, 20, 30, 220)"
INPUT_BG = "rgba(40, 40, 55, 230)"
INPUT_BORDER = "rgba(80, 80, 100, 180)"
INPUT_FOCUS_BORDER = "#00ccff"
ROW_HOVER_BG = "rgba(60, 60, 80, 200)"
ROW_HIGHLIGHT_BORDER = "#00ccff"
TEXT_COLOR = "#e0e0e0"
TEXT_DIM = "#888888"
BADGE_BG = "rgba(50, 50, 70, 200)"
ACCENT_COLOR = "#00ccff"

# Burger menu items: overlays that can be opened unconditionally
_HAMBURGER_SVG = (
    '<rect x="3" y="5" width="18" height="2" rx="1"/>'
    '<rect x="3" y="11" width="18" height="2" rx="1"/>'
    '<rect x="3" y="17" width="18" height="2" rx="1"/>'
)

_MENU_ITEMS = [
    {"label": "Map", "shortcut": "Ctrl+M", "action": "map"},
    {"label": "Exchange", "shortcut": "Ctrl+E", "action": "exchange"},
    {"label": "Notifications", "shortcut": "Ctrl+N", "action": "notifications"},
    {"label": "Recording", "shortcut": "Ctrl+R", "action": "recording"},
    {"label": "Gallery", "shortcut": "Ctrl+G", "action": "gallery"},
    {"label": "Custom Grid", "shortcut": "", "action": "custom_grid"},
]

_ROW_STYLE = (
    f"padding: 2px 8px; border: 2px solid transparent;"
    f" background-color: transparent;"
)
_ROW_HIGHLIGHT_STYLE = (
    f"padding: 2px 8px; border: 2px solid {ROW_HIGHLIGHT_BORDER};"
    f" background-color: {ROW_HOVER_BG};"
)


_NOTIF_DOT_SIZE = 8
_NOTIF_DOT_COLOR = "#e53935"


class _ClickableLabel(QLabel):
    """A QLabel that emits clicked signal."""

    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class _BadgeLabel(_ClickableLabel):
    """Clickable label with an optional notification dot badge."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._show_badge = False

    def set_badge_visible(self, visible: bool):
        if visible != self._show_badge:
            self._show_badge = visible
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._show_badge:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(_NOTIF_DOT_COLOR))
        painter.setPen(Qt.PenStyle.NoPen)
        x = self.width() - _NOTIF_DOT_SIZE - 1
        y = 1
        painter.drawEllipse(x, y, _NOTIF_DOT_SIZE, _NOTIF_DOT_SIZE)
        painter.end()


class CategoryPickerDialog(QDialog):
    """Modal dialog for picking a wiki category to create a new entry."""

    def __init__(self, base_url: str, parent=None):
        super().__init__(parent)
        self._base_url = base_url
        self._chosen_path: str | None = None
        self.setWindowTitle("Select a Category")
        self.setFixedWidth(300)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {BG_COLOR};
                border: 1px solid {INPUT_BORDER};
                border-radius: 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        title = QLabel("What category is this?")
        title.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 13px; font-weight: bold;"
            f" padding: 4px 4px 8px 4px; background: transparent;"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )
        scroll.setMaximumHeight(350)
        layout.addWidget(scroll)

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(0)
        inner_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        for section_name, entries in CREATABLE_CATEGORIES:
            header = QLabel(section_name)
            header.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 10px; font-weight: bold;"
                f" letter-spacing: 0.5px;"
                f" padding: 4px 8px; background: transparent;"
                f" border-bottom: 1px solid {INPUT_BORDER};"
            )
            inner_layout.addWidget(header)

            for display_name, url_path in entries:
                row = QWidget()
                row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
                row.setStyleSheet(_ROW_STYLE)
                row.setCursor(Qt.CursorShape.PointingHandCursor)

                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(8, 3, 8, 3)
                row_layout.setSpacing(0)

                lbl = QLabel(display_name)
                lbl.setStyleSheet(
                    f"color: {TEXT_COLOR}; font-size: 12px;"
                    f" background: transparent; border: none;"
                )
                lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                row_layout.addWidget(lbl, 1)

                # Make the row clickable via mouse press override
                row.mousePressEvent = self._make_click_handler(url_path)
                row.enterEvent = lambda e, r=row: r.setStyleSheet(_ROW_HIGHLIGHT_STYLE)
                row.leaveEvent = lambda e, r=row: r.setStyleSheet(_ROW_STYLE)

                inner_layout.addWidget(row)

        scroll.setWidget(inner)

    def _make_click_handler(self, url_path: str):
        def handler(event):
            if event.button() == Qt.MouseButton.LeftButton:
                self._chosen_path = url_path
                self.accept()
        return handler

    def chosen_url(self) -> str | None:
        if self._chosen_path:
            return self._base_url + self._chosen_path + "?mode=create"
        return None


class _ResultRow(QWidget):
    """Clickable result row inside the overlay dropdown."""

    def __init__(self, item: dict, overlay: SearchOverlayWidget):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._item = item
        self._overlay = overlay
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._overlay._hide_results()
            self._overlay._release_focus()
            self._overlay.result_selected.emit(self._item)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        try:
            idx = self._overlay._row_widgets.index(self)
            self._overlay._set_highlight(idx)
        except ValueError:
            pass
        super().enterEvent(event)


class _MenuRow(QWidget):
    """Clickable menu row inside the burger menu dropdown."""

    def __init__(self, item: dict, overlay: SearchOverlayWidget):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._item = item
        self._overlay = overlay
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._overlay._close_menu()
            self._overlay._release_focus()
            self._overlay.menu_action.emit(self._item["action"])
        super().mousePressEvent(event)

    def enterEvent(self, event):
        try:
            idx = self._overlay._row_widgets.index(self)
            self._overlay._set_highlight(idx)
        except ValueError:
            pass
        super().enterEvent(event)


class SearchOverlayWidget(OverlayWidget):
    """Overlay search bar with flat results dropdown (max 10 visible, then scroll)."""

    result_selected = pyqtSignal(dict)
    logo_clicked = pyqtSignal()
    menu_action = pyqtSignal(str)

    def __init__(
        self,
        *,
        config,
        config_path: str,
        data_client: DataClient,
        manager: OverlayManager | None = None,
    ):
        super().__init__(
            config=config,
            config_path=config_path,
            position_key="search_overlay_position",
            manager=manager,
        )
        self._data_client = data_client
        self._search_version = 0
        self._search_worker = None

        # Let the layout auto-resize the window to match content
        self.layout().setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)

        # Override container style for tighter padding
        self._container.setFixedWidth(SEARCH_WIDTH)
        self._container.setStyleSheet(
            f"background-color: {BG_COLOR}; border-radius: 8px;"
        )

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(0)

        # Search bar row: [logo] [search input] [burger menu]
        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(4)

        # Nexus logo button — click to focus client window
        self._logo_btn = _BadgeLabel()
        self._logo_btn.setFixedSize(26, 26)
        self._logo_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._logo_btn.setPixmap(nexus_logo_pixmap(18))
        self._logo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._logo_btn.setStyleSheet(
            "background: transparent; border: none; border-radius: 4px;"
            " padding: 0px;"
        )
        self._logo_btn.clicked.connect(self.logo_clicked.emit)
        search_row.addWidget(self._logo_btn)

        # Search input
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search...")
        self._search.setFixedHeight(26)
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background-color: {INPUT_BG};
                color: {TEXT_COLOR};
                border: 1px solid {INPUT_BORDER};
                border-radius: 4px;
                padding: 0px 8px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {INPUT_FOCUS_BORDER};
            }}
        """)
        search_row.addWidget(self._search, 1)

        # Burger menu button
        self._menu_btn = _ClickableLabel()
        self._menu_btn.setPixmap(svg_pixmap(_HAMBURGER_SVG, TEXT_DIM, 16))
        self._menu_btn.setFixedSize(26, 26)
        self._menu_btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._menu_btn.setStyleSheet(
            "background: transparent; border: none; border-radius: 4px; padding: 0px;"
        )
        self._menu_btn.clicked.connect(self._on_menu_clicked)
        search_row.addWidget(self._menu_btn)

        layout.addLayout(search_row)

        # Results container (hidden until we have results)
        self._results_area = QWidget()
        self._results_area.setStyleSheet("background: transparent;")
        self._results_area.setVisible(False)
        layout.addWidget(self._results_area)

        self._results_layout = QVBoxLayout(self._results_area)
        self._results_layout.setContentsMargins(0, 4, 0, 0)
        self._results_layout.setSpacing(0)
        self._results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._flat_results: list[dict] = []
        self._row_widgets: list[QWidget] = []
        self._highlighted_index: int = -1
        self._has_used_arrows: bool = False
        self._menu_open: bool = False

        # Debounce timer
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self._perform_search)
        self._search.textChanged.connect(self._on_text_changed)

        # Key handling
        self._search.installEventFilter(self)

        # Connect Ctrl+F hotkey from manager
        if manager:
            manager.search_hotkey_pressed.connect(self._focus_search)

        # Start visible and wanting to show
        self.set_wants_visible(True)

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setWidth(SEARCH_WIDTH)
        return hint

    def set_unread_count(self, count: int):
        """Show or hide the notification badge on the logo."""
        self._logo_btn.set_badge_visible(count > 0)

    def _focus_search(self):
        """Ctrl+F pressed — force-focus the search bar, stealing from the game."""
        if not self.isVisible():
            return
        self._force_activate()
        self._search.setFocus()
        self._search.selectAll()

    def _release_focus(self):
        """Give keyboard focus back to the game window."""
        self._search.clearFocus()
        from ..core.constants import GAME_TITLE_PREFIX
        _platform.release_focus_to(GAME_TITLE_PREFIX)

    def _force_activate(self):
        """Steal foreground focus to this overlay window."""
        wid = int(self.winId())
        if not _platform.bring_to_foreground(wid):
            # Fallback for platforms without native support
            self.raise_()
            self.activateWindow()
            return
        self.raise_()
        self.activateWindow()

    # --- Burger menu ---

    def _on_menu_clicked(self):
        """Toggle the burger menu in the results area."""
        if self._menu_open:
            self._close_menu()
            return
        self._show_menu()

    def _show_menu(self):
        """Show menu items in the results area."""
        self._close_menu()
        self._clear_results()
        self._menu_open = True

        for item in _MENU_ITEMS:
            row = _MenuRow(item, self)
            row.setStyleSheet(_ROW_STYLE)

            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(8, 2, 8, 2)
            row_layout.setSpacing(6)

            label = QLabel(item["label"])
            label.setStyleSheet(
                f"color: {TEXT_COLOR}; font-size: 12px; background: transparent;"
                " border: none;"
            )
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            row_layout.addWidget(label, 1)

            shortcut = item.get("shortcut")
            if shortcut:
                shortcut_badge = QLabel(shortcut)
                shortcut_badge.setStyleSheet(
                    f"color: {TEXT_DIM}; font-size: 11px;"
                    f" background-color: {BADGE_BG}; border-radius: 3px;"
                    f" padding: 2px 6px; border: none;"
                )
                shortcut_badge.setAttribute(
                    Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                row_layout.addWidget(shortcut_badge)

            self._results_layout.addWidget(row)
            self._flat_results.append(item)
            self._row_widgets.append(row)

        self._results_area.setVisible(True)

    def _close_menu(self):
        """Close the burger menu."""
        if not self._menu_open:
            return
        self._menu_open = False
        self._clear_results()

    # --- Search logic ---

    def _on_text_changed(self, text: str):
        if self._menu_open:
            self._close_menu()
        if len(text.strip()) < 2:
            self._clear_results()
            self._debounce.stop()
            return
        self._debounce.start()

    def _perform_search(self):
        query = self._search.text().strip()
        if len(query) < 2 or not self._data_client:
            self._hide_results()
            return
        self._search_version += 1
        version = self._search_version

        from PyQt6.QtCore import QThread

        class _Worker(QThread):
            finished = pyqtSignal(list, str, int)

            def __init__(self, dc, q, v):
                super().__init__()
                self._dc = dc
                self._q = q
                self._v = v

            def run(self):
                results = self._dc.search(self._q)
                self.finished.emit(results, self._q, self._v)

        worker = _Worker(self._data_client, query, version)
        worker.finished.connect(self._on_search_results)
        self._search_worker = worker
        worker.start()

    def _on_search_results(self, results: list[dict], query: str, version: int):
        if version != self._search_version:
            return

        # Score and sort
        scored: list[dict] = []
        for r in results:
            s = score_search(r.get("Name", ""), query)
            if s > 0:
                scored.append({**r, "_score": s})
        scored.sort(key=lambda r: (-r["_score"], len(r.get("Name", ""))))

        self._show_results(scored, query)

    # --- Results display ---

    def _show_results(self, scored: list[dict], query: str):
        self._highlighted_index = -1
        self._has_used_arrows = False
        self._flat_results.clear()
        self._row_widgets.clear()

        # Hide during rebuild to batch layout changes into a single resize
        self._results_area.setVisible(False)

        # Clear previous rows
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not scored:
            msg = QLabel(f'Can\'t find "{query}"?')
            msg.setStyleSheet(
                f"color: {TEXT_DIM}; font-size: 11px; padding: 6px 8px 0px 8px;"
                " background: transparent;"
            )
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._results_layout.addWidget(msg)

            prompt = _ClickableLabel("Add it to the wiki")
            prompt.setStyleSheet(
                f"color: {ACCENT_COLOR}; font-size: 11px; padding: 2px 8px 6px 8px;"
                " background: transparent;"
            )
            prompt.setAlignment(Qt.AlignmentFlag.AlignCenter)
            prompt.setCursor(Qt.CursorShape.PointingHandCursor)
            prompt.clicked.connect(self._open_category_picker)
            self._results_layout.addWidget(prompt)
        else:
            for item in scored[:MAX_VISIBLE_RESULTS]:
                row = self._make_row(item)
                self._results_layout.addWidget(row)
                self._flat_results.append(item)
                self._row_widgets.append(row)

        self._results_area.setVisible(True)

    def _hide_results(self):
        """Soft hide — keep data so FocusIn can re-show the same results."""
        if 0 <= self._highlighted_index < len(self._row_widgets):
            self._row_widgets[self._highlighted_index].setStyleSheet(_ROW_STYLE)
        self._results_area.setVisible(False)
        self._highlighted_index = -1

    def _clear_results(self):
        """Full clear — hide and discard all result data (Escape, empty text)."""
        self._results_area.setVisible(False)
        self._flat_results.clear()
        self._row_widgets.clear()
        self._highlighted_index = -1
        # Remove widgets from layout so FocusIn won't re-show stale rows
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _make_row(self, item: dict) -> QWidget:
        row = _ResultRow(item, self)
        row.setStyleSheet(_ROW_STYLE)

        layout = QHBoxLayout(row)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)

        name = QLabel(item.get("DisplayName") or item.get("Name", ""))
        name.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 12px; background: transparent;"
            " border: none;"
        )
        name.setWordWrap(True)
        name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(name, 1)

        type_badge = QLabel(get_display_type(item))
        type_badge.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 11px;"
            f" background-color: {BADGE_BG}; border-radius: 3px;"
            f" padding: 2px 6px; border: none;"
        )
        type_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(type_badge)

        return row

    def _set_highlight(self, index: int):
        if 0 <= self._highlighted_index < len(self._row_widgets):
            self._row_widgets[self._highlighted_index].setStyleSheet(_ROW_STYLE)
        self._highlighted_index = index
        if 0 <= index < len(self._row_widgets):
            self._row_widgets[index].setStyleSheet(_ROW_HIGHLIGHT_STYLE)

    def _open_category_picker(self):
        """Open the category picker dialog for adding a new wiki entry."""
        base_url = getattr(self._config, "nexus_base_url", "https://entropianexus.com")
        dialog = CategoryPickerDialog(base_url, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            url = dialog.chosen_url()
            if url:
                webbrowser.open(url)

    # --- Key handling ---

    def eventFilter(self, obj, event):
        if obj is not self._search:
            return super().eventFilter(obj, event)

        etype = event.type()

        if etype == event.Type.MouseButtonPress:
            # Ensure the overlay window is activated so the search input can
            # receive keyboard focus.  Tool windows shown with
            # WA_ShowWithoutActivating may not activate on the first click.
            self._force_activate()
            return False  # Let QLineEdit handle the click normally

        if etype == event.Type.FocusIn:
            self._search.selectAll()
            # Reshow results (or empty state) if the area has content
            # Don't reshow a closed menu
            if (not self._menu_open
                    and self._results_layout.count() > 0
                    and not self._results_area.isVisible()):
                self._results_area.setVisible(True)
            return False

        if etype == event.Type.FocusOut:
            # Collapse results / menu but keep search text
            if self._menu_open:
                self._close_menu()
            elif self._results_area.isVisible():
                self._results_area.setVisible(False)
            return False

        if etype == event.Type.KeyPress:
            key = event.key()

            if key == Qt.Key.Key_Down and self._results_area.isVisible():
                self._has_used_arrows = True
                if self._highlighted_index < len(self._flat_results) - 1:
                    self._set_highlight(self._highlighted_index + 1)
                return True

            if key == Qt.Key.Key_Up and self._results_area.isVisible():
                self._has_used_arrows = True
                if self._highlighted_index > 0:
                    self._set_highlight(self._highlighted_index - 1)
                return True

            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if (self._has_used_arrows
                        and 0 <= self._highlighted_index < len(self._flat_results)):
                    item = self._flat_results[self._highlighted_index]
                    if self._menu_open:
                        # Menu item selected
                        self._close_menu()
                        self._release_focus()
                        self.menu_action.emit(item["action"])
                    else:
                        # Search result selected
                        self._hide_results()
                        self._release_focus()
                        self.result_selected.emit(item)
                return True

            if key == Qt.Key.Key_Escape:
                self._clear_results()
                self._search.clear()
                self._release_focus()
                return True

        return super().eventFilter(obj, event)

    # --- Override drag to only start from container, not from search input ---

    def mousePressEvent(self, event):
        # Don't start drag if clicking inside interactive elements
        child = self.childAt(event.position().toPoint())
        if child in (self._search, self._logo_btn, self._menu_btn):
            return
        super().mousePressEvent(event)
