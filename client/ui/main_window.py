"""Main application window — frameless, dark themed, sidebar navigation."""

import ctypes
import sys
from dataclasses import dataclass
from typing import Any

from PyQt6.QtWidgets import (
    QStackedWidget, QSystemTrayIcon, QMenu, QApplication,
    QWidget, QVBoxLayout, QHBoxLayout, QMessageBox,
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, QPoint, QEvent, QObject

from .signals import AppSignals
from .icons import nexus_logo_icon
from .widgets.title_bar import CustomTitleBar
from .widgets.sidebar import IconSidebar
from .widgets.status_bar import StatusBar
from .pages.dashboard import DashboardPage


GRIP = 6  # pixels from edge that trigger resize


class _ResizeGrip(QWidget):
    """Invisible widget along a window edge that initiates system resize on press."""

    def __init__(self, parent, edges):
        super().__init__(parent)
        self._edges = edges
        self.setCursor(self._cursor_for(edges))
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background: transparent;")

    @staticmethod
    def _cursor_for(edges):
        left = bool(edges & Qt.Edge.LeftEdge)
        right = bool(edges & Qt.Edge.RightEdge)
        top = bool(edges & Qt.Edge.TopEdge)
        bot = bool(edges & Qt.Edge.BottomEdge)
        if (top and left) or (bot and right):
            return Qt.CursorShape.SizeFDiagCursor
        if (top and right) or (bot and left):
            return Qt.CursorShape.SizeBDiagCursor
        if left or right:
            return Qt.CursorShape.SizeHorCursor
        return Qt.CursorShape.SizeVerCursor

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            window = self.window().windowHandle()
            if window:
                window.startSystemResize(self._edges)
            event.accept()


# Page indices (must match sidebar PAGE_ICONS order)
PAGE_DASHBOARD = 0
PAGE_WIKI = 1
PAGE_MAPS = 2
PAGE_SKILLS = 3
PAGE_LOADOUT = 4
PAGE_HUNT = 5
PAGE_INVENTORY = 6
PAGE_SETTINGS = 7


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

        self._wiki_page = None
        self._markup_resolver = None

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle("Entropia Nexus")
        self.setWindowIcon(nexus_logo_icon(32))
        self.setMinimumSize(960, 640)

        # Navigation history
        self._nav_back: list[NavState] = []
        self._nav_forward: list[NavState] = []
        self._nav_current = NavState(page=PAGE_DASHBOARD)
        self._applying_nav = False

        # Place window at default size on the last-used monitor
        screen = self._find_saved_screen(config.main_window_screen_center)
        avail = screen.availableGeometry()
        w = min(1100, avail.width())
        h = min(700, avail.height())
        x = avail.x() + (avail.width() - w) // 2
        y = avail.y() + (avail.height() - h) // 2
        self.setGeometry(x, y, w, h)

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
        self._status_bar = StatusBar(signals=signals)
        self._status_bar.update_restart_clicked.connect(self._on_update_restart)
        outer.addWidget(self._status_bar)

        # --- Pages: only DashboardPage is created eagerly (shown at startup).
        # Other pages use placeholder widgets and are created on first visit. ---
        dashboard = DashboardPage(signals=signals, db=db,
                                  nexus_client=nexus_client,
                                  data_client=data_client,
                                  config=config)
        dashboard.navigation_changed.connect(self._on_dashboard_nav_changed)
        self._pages.addWidget(dashboard)
        self._page_created: set[int] = {PAGE_DASHBOARD}
        for _ in range(PAGE_SETTINGS - PAGE_DASHBOARD):
            self._pages.addWidget(QWidget())  # placeholders for indices 1–6

        self._page_factories: dict[int, callable] = {
            PAGE_WIKI: self._create_wiki_page,
            PAGE_MAPS: self._create_maps_page,
            PAGE_SKILLS: self._create_skills_page,
            PAGE_LOADOUT: self._create_loadout_page,
            PAGE_HUNT: self._create_hunt_page,
            PAGE_INVENTORY: self._create_inventory_page,
            PAGE_SETTINGS: self._create_settings_page,
        }

        # Listen for API scope errors (403 from missing OAuth scopes)
        signals.api_scope_error.connect(self._on_api_scope_error)

        # Inventory → Wiki navigation
        signals.inventory_open_wiki.connect(self._on_inventory_open_wiki)

        self._create_resize_grips()

    def _refresh_markup_caches(self):
        """Refresh exchange and inventory markup caches (runs in background)."""
        if self._markup_resolver is None:
            return
        self._markup_resolver.refresh_exchange_cache()
        self._markup_resolver.refresh_inventory_markups()

    # --- Lazy page creation ---

    def _ensure_page(self, index: int) -> QWidget:
        """Create the page at *index* on first access, replacing its placeholder."""
        if index in self._page_created:
            return self._pages.widget(index)
        factory = self._page_factories.get(index)
        if factory is None:
            return self._pages.widget(index)
        page = factory()
        placeholder = self._pages.widget(index)
        self._pages.removeWidget(placeholder)
        placeholder.deleteLater()
        self._pages.insertWidget(index, page)
        self._page_created.add(index)
        return page

    def _create_wiki_page(self):
        from .pages.wiki_page import WikiPage
        page = WikiPage(signals=self._signals, data_client=self._data_client,
                        config=self._config, config_path=self._config_path,
                        nexus_client=self._nexus_client)
        page.navigation_changed.connect(self._on_wiki_nav_changed)
        self._wiki_page = page
        return page

    def _create_maps_page(self):
        from .pages.maps_page import MapsPage
        return MapsPage(data_client=self._data_client, config=self._config)

    def _create_skills_page(self):
        from .pages.skills_page import SkillsPage
        return SkillsPage(signals=self._signals, oauth=self._oauth,
                          nexus_client=self._nexus_client,
                          data_client=self._data_client)

    def _create_loadout_page(self):
        from .pages.loadout_page import LoadoutPage
        return LoadoutPage(signals=self._signals, config=self._config,
                           config_path=self._config_path, oauth=self._oauth,
                           nexus_client=self._nexus_client,
                           data_client=self._data_client,
                           event_bus=self._event_bus)

    def _create_hunt_page(self):
        from .pages.hunt_page import HuntPage
        from ..hunt.markup_resolver import MarkupResolver
        self._markup_resolver = MarkupResolver(
            self._db, self._nexus_client, self._data_client,
        )
        page = HuntPage(signals=self._signals, db=self._db,
                        event_bus=self._event_bus, config=self._config,
                        config_path=self._config_path,
                        markup_resolver=self._markup_resolver)
        import threading
        threading.Thread(
            target=self._refresh_markup_caches, daemon=True,
        ).start()
        return page

    def _create_inventory_page(self):
        from .pages.inventory_page import InventoryPage
        return InventoryPage(signals=self._signals, oauth=self._oauth,
                             nexus_client=self._nexus_client)

    def _create_settings_page(self):
        from .pages.settings_page import SettingsPage
        return SettingsPage(config=self._config, config_path=self._config_path,
                            event_bus=self._event_bus, signals=self._signals,
                            oauth=self._oauth)

    def _on_update_restart(self):
        """User clicked the update restart button in the status bar."""
        from ..core.constants import EVENT_UPDATE_APPLY
        result = QMessageBox.question(
            self,
            "Update Ready",
            "The update has been downloaded and is ready to install.\n\n"
            "The application will close and restart automatically.\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if result == QMessageBox.StandardButton.Yes:
            self._event_bus.publish(EVENT_UPDATE_APPLY, None)

    def _on_api_scope_error(self, data):
        """Handle 403 Forbidden — ask user to re-login for updated permissions."""
        result = QMessageBox.warning(
            self,
            "Permissions Update Required",
            "The app has been updated with new features that require "
            "additional permissions.\n\n"
            "Please log in again to grant the new permissions.",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Ok,
        )
        if result == QMessageBox.StandardButton.Ok:
            self._oauth.logout()
            self._oauth.login()

    # Item type → wiki category path mapping
    _WIKI_PATHS: dict[str, list[str]] = {
        'Weapon': ['Weapons'],
        'Armor': ['Armor Sets'],
        'ArmorSet': ['Armor Sets'],
        'Clothing': ['Clothing'],
        'WeaponAmplifier': ['Attachments', 'Weapon Amplifiers'],
        'WeaponVisionAttachment': ['Attachments', 'Sights/Scopes'],
        'Absorber': ['Attachments', 'Absorbers'],
        'FinderAmplifier': ['Attachments', 'Finder Amplifiers'],
        'ArmorPlating': ['Attachments', 'Armor Platings'],
        'Enhancer': ['Attachments', 'Enhancers'],
        'MindforceImplant': ['Attachments', 'Mindforce Implants'],
        'MedicalTool': ['Medical Tools', 'Medical Tools'],
        'MedicalChip': ['Medical Tools', 'Medical Chips'],
        'Refiner': ['Tools', 'Refiners'],
        'Scanner': ['Tools', 'Scanners'],
        'Finder': ['Tools', 'Finders'],
        'Excavator': ['Tools', 'Excavators'],
        'TeleportationChip': ['Tools', 'Teleportation Chips'],
        'EffectChip': ['Tools', 'Effect Chips'],
        'MiscTool': ['Tools', 'Misc. Tools'],
        'Material': ['Materials'],
        'Blueprint': ['Blueprints'],
        'BlueprintBook': ['Blueprints'],
        'Consumable': ['Consumables', 'Stimulants'],
        'Capsule': ['Consumables', 'Creature Control Capsules'],
        'Vehicle': ['Vehicles'],
        'Pet': ['Pets'],
        'Furniture': ['Furnishings', 'Furniture'],
        'Decoration': ['Furnishings', 'Decorations'],
        'StorageContainer': ['Furnishings', 'Storage Containers'],
        'Sign': ['Furnishings', 'Signs'],
        'Strongbox': ['Strongboxes'],
    }

    def _on_inventory_open_wiki(self, item_id: int, item_type: str):
        """Navigate to the wiki category page for the given item type."""
        path = self._WIKI_PATHS.get(item_type, [])
        if not path:
            return
        self._applying_nav = True
        self._ensure_page(PAGE_WIKI)
        self._sidebar.set_active_no_emit(PAGE_WIKI)
        self._pages.setCurrentIndex(PAGE_WIKI)
        self._applying_nav = False
        self._wiki_page.navigate_to(list(path))

    # --- Page navigation ---

    def _on_page_changed(self, index: int):
        self._ensure_page(index)
        self._pages.setCurrentIndex(index)
        if not self._applying_nav:
            self._push_navigation(NavState(page=index))

    def _on_wiki_nav_changed(self, path: list[str]):
        if not self._applying_nav:
            self._push_navigation(NavState(page=PAGE_WIKI, sub_state=list(path)))

    def _on_dashboard_nav_changed(self, sub_state):
        if not self._applying_nav:
            self._push_navigation(NavState(page=PAGE_DASHBOARD, sub_state=sub_state))

    def _on_search_submitted(self, query: str, results: list[dict]):
        """Title bar search Enter → switch to wiki, show search results."""
        self._applying_nav = True
        self._ensure_page(PAGE_WIKI)
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
        self._ensure_page(state.page)
        self._sidebar.set_active_no_emit(state.page)
        self._pages.setCurrentIndex(state.page)
        page_widget = self._pages.widget(state.page)
        if hasattr(page_widget, 'set_sub_state'):
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
        for i in self._page_created:
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
        center = self.geometry().center()
        self._config.main_window_screen_center = [center.x(), center.y()]
        save_config(self._config, self._config_path)

    @staticmethod
    def _find_saved_screen(center_xy):
        """Find the screen containing the saved center point, or primary."""
        screens = QApplication.screens()
        primary = QApplication.primaryScreen()
        if center_xy and screens:
            pt = QPoint(center_xy[0], center_xy[1])
            for s in screens:
                if s.availableGeometry().contains(pt):
                    return s
        return primary or (screens[0] if screens else None)

    def closeEvent(self, event):
        """Minimize to tray instead of closing."""
        event.ignore()
        self._save_geometry()
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
        """Sync title bar maximize icon and resize grips when window state changes."""
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange:
            if hasattr(self, '_title_bar'):
                self._title_bar.update_maximize_icon()
            if hasattr(self, '_grips'):
                self._update_grip_positions()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_grips'):
            self._update_grip_positions()

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

    # --- Resize grips ---

    def _create_resize_grips(self):
        """Create invisible resize grip widgets along each edge and corner."""
        self._grips = []
        edge_combos = [
            Qt.Edge.TopEdge,
            Qt.Edge.BottomEdge,
            Qt.Edge.LeftEdge,
            Qt.Edge.RightEdge,
            Qt.Edge.TopEdge | Qt.Edge.LeftEdge,
            Qt.Edge.TopEdge | Qt.Edge.RightEdge,
            Qt.Edge.BottomEdge | Qt.Edge.LeftEdge,
            Qt.Edge.BottomEdge | Qt.Edge.RightEdge,
        ]
        for edges in edge_combos:
            grip = _ResizeGrip(self, edges)
            self._grips.append((grip, edges))
        self._update_grip_positions()

    def _update_grip_positions(self):
        w, h = self.width(), self.height()
        g = GRIP
        maximized = self.isMaximized()
        for grip, edges in self._grips:
            if maximized:
                grip.hide()
                continue
            grip.show()
            top = bool(edges & Qt.Edge.TopEdge)
            bottom = bool(edges & Qt.Edge.BottomEdge)
            left = bool(edges & Qt.Edge.LeftEdge)
            right = bool(edges & Qt.Edge.RightEdge)
            if top and left:
                grip.setGeometry(0, 0, g, g)
            elif top and right:
                grip.setGeometry(w - g, 0, g, g)
            elif bottom and left:
                grip.setGeometry(0, h - g, g, g)
            elif bottom and right:
                grip.setGeometry(w - g, h - g, g, g)
            elif top:
                grip.setGeometry(g, 0, w - 2 * g, g)
            elif bottom:
                grip.setGeometry(g, h - g, w - 2 * g, g)
            elif left:
                grip.setGeometry(0, g, g, h - 2 * g)
            elif right:
                grip.setGeometry(w - g, g, g, h - 2 * g)
            grip.raise_()

    # --- Application event filter ---

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Handle back/forward mouse button navigation."""
        if event.type() == QEvent.Type.MouseButtonPress:
            # Only handle events from this window's widget tree
            if not isinstance(obj, QWidget) or (obj is not self and not self.isAncestorOf(obj)):
                return False
            if event.button() == Qt.MouseButton.BackButton:
                self._navigate_back()
                return True
            elif event.button() == Qt.MouseButton.ForwardButton:
                self._navigate_forward()
                return True
        return False
