"""Custom slim title bar with drag, back/forward nav, search, minimize, maximize/restore, close."""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QLineEdit, QStyleOption, QStyle, QApplication
from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal, QEvent
from PyQt6.QtGui import QCursor, QPainter

from ..theme import (
    MAIN_DARK, SECONDARY, TEXT_MUTED, TEXT, HOVER, BORDER, ACCENT, DISABLED,
    TITLE_BAR_HEIGHT, TITLE_BAR_CLOSE_HOVER,
)
from ..icons import nexus_logo_pixmap
from .search_popup import SearchResultsPopup
from .fuzzy_line_edit import score_search

SNAP_THRESHOLD = 8  # pixels from screen edge to trigger snap
SEARCH_MIN_WIDTH = 300
SEARCH_WIDTH_RATIO = 0.3  # 30% of window width


class CustomTitleBar(QWidget):
    """32px custom title bar with navigation, search, and window controls."""

    back_clicked = pyqtSignal()
    forward_clicked = pyqtSignal()
    search_submitted = pyqtSignal(str, list)  # query, scored results
    result_selected = pyqtSignal(dict)        # individual search result picked

    def __init__(self, parent_window, *, data_client=None):
        super().__init__(parent_window)
        self._window = parent_window
        self._data_client = data_client
        self._drag_pos = None
        self._pre_snap_geometry = None  # saved geometry before side-snapping
        self._search_version = 0

        self.setFixedHeight(TITLE_BAR_HEIGHT)
        self.setStyleSheet(f"""
            CustomTitleBar {{
                background-color: {MAIN_DARK};
                border-bottom: 1px solid {BORDER};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(0)

        # App icon (Nexus logo)
        icon_label = QLabel()
        icon_label.setPixmap(nexus_logo_pixmap(16))
        icon_label.setFixedSize(16, 16)
        icon_label.setStyleSheet("background: transparent;")
        layout.addWidget(icon_label)

        # Title
        title = QLabel("Entropia Nexus")
        title.setStyleSheet(f"""
            color: {TEXT_MUTED};
            font-size: 12px;
            padding-left: 8px;
            background: transparent;
        """)
        layout.addWidget(title)

        layout.addStretch()

        # --- Navigation buttons ---
        nav_btn_style = f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: {TEXT_MUTED};
                font-size: 14px;
                min-width: 28px;
                max-width: 28px;
                min-height: {TITLE_BAR_HEIGHT}px;
                max-height: {TITLE_BAR_HEIGHT}px;
                border-radius: 0px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {HOVER};
                color: {TEXT};
            }}
            QPushButton:disabled {{
                color: {DISABLED};
            }}
        """

        self._back_btn = QPushButton("\u2190")  # ←
        self._back_btn.setStyleSheet(nav_btn_style)
        self._back_btn.setEnabled(False)
        self._back_btn.setToolTip("Back")
        self._back_btn.clicked.connect(self.back_clicked.emit)
        layout.addWidget(self._back_btn)

        self._fwd_btn = QPushButton("\u2192")  # →
        self._fwd_btn.setStyleSheet(nav_btn_style)
        self._fwd_btn.setEnabled(False)
        self._fwd_btn.setToolTip("Forward")
        self._fwd_btn.clicked.connect(self.forward_clicked.emit)
        layout.addWidget(self._fwd_btn)

        # --- Search bar ---
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search Entropia Nexus...")
        self._search.setFixedHeight(22)
        self._search.setMinimumWidth(SEARCH_MIN_WIDTH)
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background-color: {SECONDARY};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 3px;
                padding: 0px 8px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {ACCENT};
            }}
        """)
        # Initialize fields needed by eventFilter before installing it
        self._watched_window = None
        self._search_popup = SearchResultsPopup()
        self._search_popup.search_submitted.connect(self._on_search_enter)
        self._search_popup.result_selected.connect(self._on_result_selected)
        self._last_scored: list[dict] = []
        self._suppress_reshow = False
        self._search.installEventFilter(self)
        layout.addWidget(self._search)

        layout.addStretch()

        # --- Window control buttons ---
        btn_style = f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: {TEXT_MUTED};
                font-size: 13px;
                min-width: 46px;
                max-width: 46px;
                min-height: {TITLE_BAR_HEIGHT}px;
                max-height: {TITLE_BAR_HEIGHT}px;
                border-radius: 0px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {HOVER};
                color: {TEXT};
            }}
        """

        close_style = f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                color: {TEXT_MUTED};
                font-size: 13px;
                min-width: 46px;
                max-width: 46px;
                min-height: {TITLE_BAR_HEIGHT}px;
                max-height: {TITLE_BAR_HEIGHT}px;
                border-radius: 0px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {TITLE_BAR_CLOSE_HOVER};
                color: white;
            }}
        """

        self._min_btn = QPushButton("\u2014")  # em dash
        self._min_btn.setStyleSheet(btn_style)
        self._min_btn.clicked.connect(self._window.showMinimized)
        layout.addWidget(self._min_btn)

        max_style = btn_style.replace("font-size: 13px;", "font-size: 16px;")
        self._max_btn = QPushButton("\u25a1")  # square
        self._max_btn.setStyleSheet(max_style)
        self._max_btn.clicked.connect(self._toggle_maximize)
        layout.addWidget(self._max_btn)

        self._close_btn = QPushButton("\u2715")  # X
        self._close_btn.setStyleSheet(close_style)
        self._close_btn.clicked.connect(self._window.close)
        layout.addWidget(self._close_btn)

        # --- Search debounce timer ---
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._perform_search)
        self._search.textChanged.connect(self._on_search_text_changed)

        # (search popup + watched_window initialized earlier, before installEventFilter)

    # --- Public API ---

    def set_nav_enabled(self, *, back: bool, forward: bool):
        """Enable or disable the navigation buttons."""
        self._back_btn.setEnabled(back)
        self._fwd_btn.setEnabled(forward)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_search_width()

    def _update_search_width(self):
        """Set search bar to 30% of window width, with a minimum of 300px."""
        w = max(SEARCH_MIN_WIDTH, int(self._window.width() * SEARCH_WIDTH_RATIO))
        self._search.setFixedWidth(w)

    def update_maximize_icon(self):
        """Sync the maximize button icon with the window state."""
        if self._window.isMaximized():
            self._max_btn.setText("\u2750")  # overlapping squares
        else:
            self._max_btn.setText("\u25a1")  # square

    # --- Search ---

    def _on_search_text_changed(self, text: str):
        if len(text.strip()) < 2:
            self._search_popup.hide()
            self._search_timer.stop()
            return
        self._search_timer.start()

    def _perform_search(self):
        query = self._search.text().strip()
        if len(query) < 2 or not self._data_client:
            self._search_popup.hide()
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
        # Keep reference so thread isn't GC'd
        self._search_worker = worker
        worker.start()

    def _on_search_results(self, results: list[dict], query: str, version: int):
        if version != self._search_version:
            return  # stale
        # Re-score client-side
        scored: list[dict] = []
        for r in results:
            s = score_search(r.get("Name", ""), query)
            if s > 0:
                scored.append({**r, "_score": s})
        scored.sort(key=lambda r: (-r["_score"], len(r.get("Name", ""))))

        self._last_scored = scored
        self._search_popup.set_results(scored, query)
        self._position_popup()
        self._search_popup.show()
        self._search_popup.raise_()

        # Watch window for move/resize
        win = self._window
        if win and win is not self._watched_window:
            if self._watched_window:
                self._watched_window.removeEventFilter(self)
            win.installEventFilter(self)
            self._watched_window = win

    def _position_popup(self):
        pos = self._search.mapToGlobal(QPoint(0, self._search.height() + 2))
        self._search_popup.setFixedWidth(self._search.width())
        # Auto-size height: use content size, capped to available screen space
        content_h = self._search_popup._inner.sizeHint().height() + 4
        screen = self._search.screen()
        if screen:
            screen_bottom = screen.availableGeometry().bottom()
            max_h = screen_bottom - pos.y() - 8
        else:
            max_h = 400
        max_h = min(max_h, int(self._window.height() * 0.6))
        self._search_popup.setFixedHeight(max(60, min(content_h, max_h)))
        self._search_popup.move(pos.x(), pos.y())

    def _on_search_enter(self, query: str):
        """User pressed Enter in search — open full results in wiki."""
        self._suppress_reshow = True
        self._search_popup.hide()
        self.search_submitted.emit(query, self._last_scored)

    def _on_result_selected(self, item: dict):
        """User clicked or pressed Enter on a specific result."""
        self._suppress_reshow = True
        self._search_popup.hide()
        self.result_selected.emit(item)

    # --- Event filter ---

    def eventFilter(self, obj, event):
        etype = event.type()

        if obj is self._search:
            # Forward key events from search bar to popup
            if etype == QEvent.Type.KeyPress:
                key = event.key()
                if self._search_popup.isVisible():
                    if self._search_popup.handle_key(key):
                        return True
                elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    query = self._search.text().strip()
                    if len(query) >= 2:
                        self._search_popup.hide()
                        self.search_submitted.emit(query, self._last_scored)
                        return True
            # Re-show popup when search bar regains focus with results
            elif etype == QEvent.Type.FocusIn:
                if self._suppress_reshow:
                    self._suppress_reshow = False
                elif self._last_scored and len(self._search.text().strip()) >= 2:
                    self._position_popup()
                    self._search_popup.show()
                    self._search_popup.raise_()
            # Hide popup when search bar loses focus
            elif etype == QEvent.Type.FocusOut:
                QTimer.singleShot(200, self._maybe_hide_popup)

        # Close popup on window move/resize/deactivation
        if obj is self._watched_window and etype in (
            QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.WindowStateChange,
            QEvent.Type.WindowDeactivate,
        ):
            self._search_popup.hide()

        return super().eventFilter(obj, event)

    # --- Window controls ---

    def _toggle_maximize(self):
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    # --- Drag handling + Aero Snap ---

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Don't start drag if click is on an interactive child
            child = self.childAt(event.position().toPoint())
            if child and child is not self:
                return
            self._drag_pos = event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is None or not (event.buttons() & Qt.MouseButton.LeftButton):
            return

        if self._window.isMaximized():
            # Proportional unmaximize: cursor stays at same relative X position
            proportion = event.position().x() / self.width() if self.width() > 0 else 0.5
            self._window.showNormal()
            # Restore pre-snap size if we had one
            if self._pre_snap_geometry is not None:
                self._window.resize(self._pre_snap_geometry.size())
                self._pre_snap_geometry = None
            new_x = int(event.globalPosition().toPoint().x() - self._window.width() * proportion)
            new_y = event.globalPosition().toPoint().y() - self._drag_pos.y()
            self._window.move(new_x, new_y)
            self._drag_pos = event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
        else:
            self._window.move(event.globalPosition().toPoint() - self._drag_pos)

        event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag_pos is not None:
            self._try_snap(event.globalPosition().toPoint())
        self._drag_pos = None
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Don't toggle maximize if double-clicking on a child widget
            child = self.childAt(event.position().toPoint())
            if child and child is not self:
                return
            self._toggle_maximize()
            event.accept()

    def _try_snap(self, global_pos):
        """Check if cursor is at a screen edge and snap the window."""
        screen = QApplication.screenAt(global_pos)
        if not screen or self._window.isMaximized():
            return
        avail = screen.availableGeometry()
        # Top edge → maximize
        if global_pos.y() <= avail.top() + SNAP_THRESHOLD:
            self._pre_snap_geometry = self._window.geometry()
            self._window.showMaximized()
        # Left edge → tile left half
        elif global_pos.x() <= avail.left() + SNAP_THRESHOLD:
            self._pre_snap_geometry = self._window.geometry()
            self._window.setGeometry(
                avail.left(), avail.top(),
                avail.width() // 2, avail.height(),
            )
        # Right edge → tile right half
        elif global_pos.x() >= avail.right() - SNAP_THRESHOLD:
            self._pre_snap_geometry = self._window.geometry()
            self._window.setGeometry(
                avail.left() + avail.width() // 2, avail.top(),
                avail.width() // 2, avail.height(),
            )

    def paintEvent(self, event):
        """Required for QWidget subclasses to honour stylesheet backgrounds/borders."""
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, opt, p, self)
        p.end()

    def _maybe_hide_popup(self):
        if not self._search.hasFocus() and not self._search_popup.underMouse():
            self._search_popup.hide()
