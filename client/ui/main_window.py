"""Main application window — frameless, dark themed, sidebar navigation."""

import ctypes
import sys
from dataclasses import dataclass, field
from typing import Any

from PyQt6.QtWidgets import (
    QStackedWidget, QSystemTrayIcon, QMenu, QApplication,
    QWidget, QVBoxLayout, QHBoxLayout,
)
from PyQt6.QtGui import QAction, QCursor
from PyQt6.QtCore import Qt, QPoint, QEvent, QObject

from .signals import AppSignals
from .icons import nexus_logo_icon
from .widgets.title_bar import CustomTitleBar
from .widgets.sidebar import IconSidebar
from .widgets.status_bar import StatusBar
from .pages.dashboard import DashboardPage
from .pages.settings_page import SettingsPage
from .pages.skills_page import SkillsPage
from .pages.loadout_page import LoadoutPage
from .pages.hunt_page import HuntPage
from .pages.inventory_page import InventoryPage
from .pages.wiki_page import WikiPage


GRIP = 6  # pixels from edge that trigger resize

# Page indices (must match sidebar PAGE_ICONS order)
PAGE_DASHBOARD = 0
PAGE_WIKI = 1
PAGE_SKILLS = 2
PAGE_LOADOUT = 3
PAGE_HUNT = 4
PAGE_INVENTORY = 5
PAGE_SETTINGS = 6


@dataclass
class NavState:
    """A single point in the navigation history."""
    page: int
    sub_state: Any = None

    def __eq__(self, other):
        if not isinstance(other, NavState):
            return False
        return self.page == other.page and self.sub_state == other.sub_state


class MainWindow(QWidget):
    """Frameless main window with custom title bar and sidebar navigation."""

    def __init__(self, *, config, config_path, event_bus, db, signals: AppSignals,
                 oauth, nexus_client, data_client):
        super().__init__()

        self._config = config
        self._config_path = config_path
        self._event_bus = event_bus
        self._db = db
        self._signals = signals
        self._oauth = oauth
        self._nexus_client = nexus_client
        self._data_client = data_client

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle("Entropia Nexus")
        self.setWindowIcon(nexus_logo_icon(32))
        self.setMinimumSize(960, 640)
        self.setMouseTracking(True)
        self._resize_cursor_active = False

        # Navigation history
        self._nav_back: list[NavState] = []
        self._nav_forward: list[NavState] = []
        self._nav_current = NavState(page=PAGE_DASHBOARD)
        self._applying_nav = False

        # Restore window geometry
        if config.main_window_geometry:
            try:
                from PyQt6.QtCore import QByteArray
                self.restoreGeometry(QByteArray.fromHex(config.main_window_geometry.encode()))
            except Exception:
                self.resize(1100, 700)
        else:
            self.resize(1100, 700)

        # --- Build layout: title bar | sidebar + content | status bar ---
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Custom title bar (with search and nav buttons)
        self._title_bar = CustomTitleBar(self, data_client=data_client)
        self._title_bar.back_clicked.connect(self._navigate_back)
        self._title_bar.forward_clicked.connect(self._navigate_forward)
        self._title_bar.search_submitted.connect(self._on_search_submitted)
        outer.addWidget(self._title_bar)

        # Middle row: sidebar + pages (direct children of outer)
        middle = QHBoxLayout()
        middle.setContentsMargins(0, 0, 0, 0)
        middle.setSpacing(0)

        # Sidebar
        self._sidebar = IconSidebar(signals=signals, config=config)
        self._sidebar.page_changed.connect(self._on_page_changed)
        middle.addWidget(self._sidebar)

        # Stacked pages
        self._pages = QStackedWidget()
        self._pages.setMouseTracking(True)
        middle.addWidget(self._pages)

        outer.addLayout(middle)

        # Status bar
        self._status_bar = StatusBar()
        outer.addWidget(self._status_bar)

        # --- Add pages (order must match sidebar PAGE_ICONS + settings) ---
        self._pages.addWidget(DashboardPage(signals=signals, db=db,
                                              nexus_client=nexus_client,
                                              data_client=data_client,
                                              config=config))

        self._wiki_page = WikiPage(signals=signals, data_client=data_client,
                                    config=config, config_path=config_path,
                                    nexus_client=nexus_client)
        self._wiki_page.navigation_changed.connect(self._on_wiki_nav_changed)
        self._pages.addWidget(self._wiki_page)

        self._pages.addWidget(SkillsPage(signals=signals, oauth=oauth,
                                         nexus_client=nexus_client))
        self._pages.addWidget(LoadoutPage(signals=signals, config=config,
                                          config_path=config_path, oauth=oauth,
                                          nexus_client=nexus_client,
                                          data_client=data_client,
                                          event_bus=event_bus))
        self._pages.addWidget(HuntPage(signals=signals, db=db,
                                       event_bus=event_bus, config=config,
                                       config_path=config_path))
        self._pages.addWidget(InventoryPage(signals=signals, oauth=oauth,
                                            nexus_client=nexus_client))
        self._pages.addWidget(SettingsPage(config=config, config_path=config_path,
                                           event_bus=event_bus, signals=signals,
                                           oauth=oauth))

    # --- Page navigation ---

    def _on_page_changed(self, index: int):
        self._pages.setCurrentIndex(index)
        if not self._applying_nav:
            self._push_navigation(NavState(page=index))

    def _on_wiki_nav_changed(self, path: list[str]):
        if not self._applying_nav:
            self._push_navigation(NavState(page=PAGE_WIKI, sub_state=list(path)))

    def _on_search_submitted(self, query: str, results: list[dict]):
        """Title bar search Enter → switch to wiki, show search results."""
        self._applying_nav = True
        self._sidebar.set_active_no_emit(PAGE_WIKI)
        self._pages.setCurrentIndex(PAGE_WIKI)
        self._applying_nav = False
        self._wiki_page.show_search_results(query, results)

    # --- Navigation history ---

    def _push_navigation(self, new_state: NavState):
        if new_state == self._nav_current:
            return
        self._nav_back.append(self._nav_current)
        self._nav_current = new_state
        self._nav_forward.clear()
        self._update_nav_buttons()

    def _navigate_back(self):
        if not self._nav_back:
            return
        self._nav_forward.append(self._nav_current)
        self._nav_current = self._nav_back.pop()
        self._apply_nav_state(self._nav_current)
        self._update_nav_buttons()

    def _navigate_forward(self):
        if not self._nav_forward:
            return
        self._nav_back.append(self._nav_current)
        self._nav_current = self._nav_forward.pop()
        self._apply_nav_state(self._nav_current)
        self._update_nav_buttons()

    def _apply_nav_state(self, state: NavState):
        self._applying_nav = True
        self._sidebar.set_active_no_emit(state.page)
        self._pages.setCurrentIndex(state.page)
        page_widget = self._pages.widget(state.page)
        if hasattr(page_widget, 'set_sub_state') and state.sub_state is not None:
            page_widget.set_sub_state(state.sub_state)
        self._applying_nav = False

    def _update_nav_buttons(self):
        self._title_bar.set_nav_enabled(
            back=len(self._nav_back) > 0,
            forward=len(self._nav_forward) > 0,
        )

    # --- System tray ---

    def _setup_tray(self):
        self._tray = QSystemTrayIcon(self)
        self._tray.setToolTip("Entropia Nexus")
        self._tray.setIcon(nexus_logo_icon(32))

        tray_menu = QMenu(self)

        show_action = QAction("Show", self)
        show_action.triggered.connect(self._show_window)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit)
        tray_menu.addAction(quit_action)

        self._tray.setContextMenu(tray_menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.messageClicked.connect(self._on_tray_message_clicked)
        self._tray.show()

        # News notifications
        self._signals.new_news_post.connect(self._on_new_news_post)

    def _show_window(self):
        self.showNormal()
        self.activateWindow()

    def _quit(self):
        self._save_geometry()
        # Stop page timers so background threads finish promptly
        for i in range(self._pages.count()):
            page = self._pages.widget(i)
            if hasattr(page, "cleanup"):
                page.cleanup()
        QApplication.quit()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self._show_window()

    def _on_new_news_post(self, title: str, summary: str):
        self._tray.showMessage(
            title,
            summary[:200] if summary else "",
            QSystemTrayIcon.MessageIcon.Information,
            5000,
        )

    def _on_tray_message_clicked(self):
        self._show_window()
        self._sidebar.set_active_no_emit(PAGE_DASHBOARD)
        self._pages.setCurrentIndex(PAGE_DASHBOARD)

    def _save_geometry(self):
        from ..core.config import save_config
        self._config.main_window_geometry = bytes(self.saveGeometry().toHex()).decode()
        save_config(self._config, self._config_path)

    def closeEvent(self, event):
        """Minimize to tray instead of closing."""
        event.ignore()
        self.hide()
        self._tray.showMessage(
            "Entropia Nexus",
            "Running in background. Right-click tray icon to quit.",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )

    # --- Frameless window support ---

    def showEvent(self, event):
        """Apply DWM shadow and system tray on first show."""
        super().showEvent(event)
        if not hasattr(self, '_shadow_applied'):
            self._shadow_applied = True
            self._setup_tray()
            self._enable_shadow()
            QApplication.instance().installEventFilter(self)

    def changeEvent(self, event):
        """Sync title bar maximize icon when window state changes."""
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange:
            self._title_bar.update_maximize_icon()

    def _enable_shadow(self):
        """Use DWM to add a drop shadow to the frameless window."""
        if sys.platform != "win32":
            return
        try:
            hwnd = int(self.winId())
            MARGINS = ctypes.c_int * 4
            margins = MARGINS(1, 1, 1, 1)
            ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))
        except Exception:
            pass

    # --- Edge resize (application-level event filter) ---

    def _edge_at_global(self, global_pos: QPoint):
        """Return Qt.Edge flags if global_pos is within GRIP of the window edges."""
        if self.isMaximized():
            return Qt.Edge(0)
        local = self.mapFromGlobal(global_pos)
        w, h = self.width(), self.height()
        x, y = local.x(), local.y()
        edges = Qt.Edge(0)
        if x < GRIP:
            edges |= Qt.Edge.LeftEdge
        elif x > w - GRIP:
            edges |= Qt.Edge.RightEdge
        if y < GRIP:
            edges |= Qt.Edge.TopEdge
        elif y > h - GRIP:
            edges |= Qt.Edge.BottomEdge
        return edges

    @staticmethod
    def _cursor_for_edges(edges):
        left = bool(edges & Qt.Edge.LeftEdge)
        right = bool(edges & Qt.Edge.RightEdge)
        top = bool(edges & Qt.Edge.TopEdge)
        bottom = bool(edges & Qt.Edge.BottomEdge)
        if (top and left) or (bottom and right):
            return Qt.CursorShape.SizeFDiagCursor
        if (top and right) or (bottom and left):
            return Qt.CursorShape.SizeBDiagCursor
        if left or right:
            return Qt.CursorShape.SizeHorCursor
        return Qt.CursorShape.SizeVerCursor

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Intercept mouse events on any child to show resize cursors at edges."""
        # Only handle events from this window's own widget tree — skip other
        # top-level windows (e.g. hunt overlay) so they can handle their own input.
        if obj is not self and (not isinstance(obj, QWidget) or not self.isAncestorOf(obj)):
            return False

        etype = event.type()

        if etype == QEvent.Type.MouseMove:
            edges = self._edge_at_global(QCursor.pos())
            if edges:
                desired = self._cursor_for_edges(edges)
                if not self._resize_cursor_active:
                    QApplication.setOverrideCursor(desired)
                    self._resize_cursor_active = True
                else:
                    QApplication.changeOverrideCursor(QCursor(desired))
            elif self._resize_cursor_active:
                QApplication.restoreOverrideCursor()
                self._resize_cursor_active = False

        elif etype == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                edges = self._edge_at_global(QCursor.pos())
                if edges:
                    if self._resize_cursor_active:
                        QApplication.restoreOverrideCursor()
                        self._resize_cursor_active = False
                    window = self.windowHandle()
                    if window:
                        window.startSystemResize(edges)
                    return True
            elif event.button() == Qt.MouseButton.BackButton:
                self._navigate_back()
                return True
            elif event.button() == Qt.MouseButton.ForwardButton:
                self._navigate_forward()
                return True

        elif etype == QEvent.Type.Leave:
            if self._resize_cursor_active:
                QApplication.restoreOverrideCursor()
                self._resize_cursor_active = False

        return False
