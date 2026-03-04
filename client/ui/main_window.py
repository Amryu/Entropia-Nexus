"""Main application window — frameless, dark themed, sidebar navigation."""

from dataclasses import dataclass
from typing import Any

from PyQt6.QtWidgets import (
    QStackedWidget, QSystemTrayIcon, QMenu, QApplication,
    QWidget, QVBoxLayout, QHBoxLayout, QMessageBox,
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, QPoint, QEvent, QObject, QTimer

from .signals import AppSignals
from .icons import nexus_logo_icon
from .widgets.title_bar import CustomTitleBar
from .widgets.sidebar import IconSidebar
from .widgets.status_bar import StatusBar
from .pages.dashboard import DashboardPage
from ..core.logger import get_logger
from ..platform import backend as _platform

log = get_logger("MainWindow")


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
PAGE_INVENTORY = 5
PAGE_EXCHANGE = 6
PAGE_SETTINGS = 7


@dataclass
class NavState:
    """A single point in the navigation history."""
    page: int
    sub_state: Any = None
    scroll_pos: int = 0

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
        self._quitting = False

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
        self._title_bar.result_selected.connect(self._on_search_result_selected)
        self._title_bar.create_requested.connect(self._on_create_requested)
        self._title_bar.update_clicked.connect(self._on_update_icon_clicked)
        outer.addWidget(self._title_bar)

        # Update system state
        self._pending_update: dict | None = None
        self._update_dialog = None
        self._update_download_progress: dict | None = None  # last progress event
        self._update_download_ready: dict | None = None     # set when download completes
        self._update_download_error: dict | None = None     # set on download failure
        self._user_wants_update = False                     # user clicked "Update Now"

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
        dashboard.open_settings.connect(self._open_dashboard_settings)
        dashboard.open_notifications.connect(self._show_notification_rules)
        self._pages.addWidget(dashboard)
        self._page_created: set[int] = {PAGE_DASHBOARD}
        for _ in range(PAGE_SETTINGS - PAGE_DASHBOARD):
            self._pages.addWidget(QWidget())  # placeholders for indices 1–7

        self._page_factories: dict[int, callable] = {
            PAGE_WIKI: self._create_wiki_page,
            PAGE_MAPS: self._create_maps_page,
            PAGE_SKILLS: self._create_skills_page,
            PAGE_LOADOUT: self._create_loadout_page,
            PAGE_INVENTORY: self._create_inventory_page,
            PAGE_EXCHANGE: self._create_exchange_page,
            PAGE_SETTINGS: self._create_settings_page,
        }

        # Listen for API scope errors (403 from missing OAuth scopes)
        signals.api_scope_error.connect(self._on_api_scope_error)

        # Inventory → Wiki navigation
        signals.inventory_open_wiki.connect(self._on_inventory_open_wiki)

        # --- Notification system ---
        self._setup_notifications()

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
        try:
            page = factory()
        except Exception:
            log.error("Failed to create page %d", index, exc_info=True)
            page = QWidget()
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
        page = SkillsPage(signals=self._signals, oauth=self._oauth,
                          nexus_client=self._nexus_client,
                          data_client=self._data_client,
                          config=self._config,
                          config_path=self._config_path,
                          event_bus=self._event_bus,
                          db=self._db)
        page.navigation_changed.connect(self._on_skills_nav_changed)
        return page

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
                             nexus_client=self._nexus_client, db=self._db,
                             config=self._config,
                             config_path=self._config_path)

    def _create_exchange_page(self):
        from .pages.exchange_page import ExchangePage
        return ExchangePage(
            signals=self._signals,
            exchange_store=self._exchange_store,
            favourites_store=self._favourites_store,
            config=self._config,
        )

    def _create_settings_page(self):
        from .pages.settings_page import SettingsPage
        return SettingsPage(config=self._config, config_path=self._config_path,
                            event_bus=self._event_bus, signals=self._signals,
                            oauth=self._oauth,
                            on_show_changelog=self.open_changelog_dialog)

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

    # --- Notification system ---

    def _setup_notifications(self):
        from ..notifications.manager import NotificationManager
        from .widgets.notification_center import NotificationCenter

        self._notif_manager = NotificationManager(
            config=self._config,
            event_bus=self._event_bus,
            nexus_client=self._nexus_client,
        )

        # Floating panel (child of this window, hidden by default)
        self._notification_center = NotificationCenter(
            manager=self._notif_manager,
            config=self._config,
            config_path=self._config_path,
            parent=self,
        )
        self._notification_center.hide()

        # Sidebar bell → toggle panel
        self._sidebar.notification_clicked.connect(self._toggle_notification_center)

        # Enable notification processing after chat-log catchup
        self._signals.catchup_complete.connect(self._notif_manager.set_live)

        # Bridge: manager callback → EventBus → Qt signal (thread-safe)
        from ..core.constants import EVENT_NOTIFICATION
        self._notif_manager.on_notification(
            lambda notif: self._event_bus.publish(EVENT_NOTIFICATION, notif)
        )
        self._signals.notification.connect(self._on_new_notification)

        # Badge updates when read state changes in the notification center
        self._notification_center.read_state_changed.connect(self._update_badge)

        # Server notification poll timer (every 2 minutes)
        self._notif_poll_timer = QTimer(self)
        self._notif_poll_timer.timeout.connect(self._poll_server_notifications)
        self._notif_poll_timer.start(120_000)

        # Stream poll timer (every 3 minutes)
        self._stream_poll_timer = QTimer(self)
        self._stream_poll_timer.timeout.connect(self._poll_streams)
        self._stream_poll_timer.start(180_000)

    def connect_exchange_store(self, store):
        """Wire exchange store items to notification center for keyword search."""
        def _on_items():
            self._notification_center.set_exchange_items(store.items)
        store.items_changed.connect(_on_items)
        if store.items:
            _on_items()

    def _toggle_notification_center(self):
        if self._notification_center.isVisible():
            self._notification_center.hide()
            return
        # Position: bottom-left of content area, flush with sidebar right edge
        from .theme import SIDEBAR_WIDTH, STATUS_BAR_HEIGHT, TITLE_BAR_HEIGHT
        panel_h = self._notification_center.height()
        x = SIDEBAR_WIDTH
        y = self.height() - STATUS_BAR_HEIGHT - panel_h
        y = max(TITLE_BAR_HEIGHT, y)
        self._notification_center.move(x, y)
        self._notification_center.show()
        self._notification_center.raise_()

    def _show_notification_rules(self):
        """Open the notification center on the Rules tab."""
        self._notification_center.show_rules_tab()
        if not self._notification_center.isVisible():
            self._toggle_notification_center()

    def _open_dashboard_settings(self):
        """Navigate to the settings page filtered to the Dashboard section."""
        page = self._ensure_page(PAGE_SETTINGS)
        page.set_search("Dashboard")
        self._sidebar.set_active_no_emit(PAGE_SETTINGS)
        self._pages.setCurrentIndex(PAGE_SETTINGS)

    def set_search_overlay(self, overlay):
        """Store reference to the search overlay for notification badge updates."""
        self._search_overlay = overlay

    def set_overlay_manager(self, manager):
        """Store reference to overlay manager for game-focus checks."""
        self._overlay_manager = manager

    def set_toast_manager(self, toast_manager):
        """Store reference to toast manager for in-game notifications."""
        self._toast_manager = toast_manager

    def _update_badge(self):
        """Update the sidebar bell badge and search overlay with the current unread count."""
        count = self._notif_manager.get_unread_count()
        self._sidebar.set_unread_count(count)
        if hasattr(self, "_search_overlay") and self._search_overlay:
            self._search_overlay.set_unread_count(count)

    def _on_new_notification(self, notif):
        self._update_badge()

        # Refresh panel if visible
        self._notification_center.refresh()

        # Flash taskbar if window is not in the foreground
        if not self.isActiveWindow():
            self._flash_taskbar()

        # Toast routing: in-game overlay toast or OS system tray toast
        if getattr(self._config, "notification_toast_enabled", True):
            overlay_mgr = getattr(self, "_overlay_manager", None)
            toast_mgr = getattr(self, "_toast_manager", None)
            if overlay_mgr and overlay_mgr.game_focused and toast_mgr:
                toast_mgr.show_toast(notif)
            elif hasattr(self, "_tray"):
                self._tray.showMessage(
                    notif.title,
                    notif.body[:200] if notif.body else "",
                    QSystemTrayIcon.MessageIcon.Information,
                    5000,
                )

        # Notification sound
        if getattr(self._config, "notification_sound_enabled", True):
            self._play_notification_sound()

    def _flash_taskbar(self):
        """Flash the taskbar icon until the window is brought to the foreground."""
        _platform.flash_taskbar(int(self.winId()))
        # Qt fallback sets _NET_WM_STATE_DEMANDS_ATTENTION on X11
        QApplication.alert(self, 0)

    def _play_notification_sound(self):
        if not hasattr(self, "_sound_effect"):
            try:
                from PyQt6.QtMultimedia import QSoundEffect
                from PyQt6.QtCore import QUrl
                import os
                sound_path = os.path.join(
                    os.path.dirname(__file__), "..", "assets", "notification.wav"
                )
                sound_path = os.path.abspath(sound_path)
                if not os.path.exists(sound_path):
                    self._sound_effect = None
                    return
                self._sound_effect = QSoundEffect()
                self._sound_effect.setSource(QUrl.fromLocalFile(sound_path))
                self._sound_effect.setVolume(0.5)
            except ImportError:
                self._sound_effect = None
                return
        if self._sound_effect:
            self._sound_effect.play()

    def _poll_server_notifications(self):
        import threading
        threading.Thread(
            target=self._notif_manager.poll_server_notifications,
            daemon=True,
        ).start()

    def _poll_streams(self):
        import threading
        threading.Thread(
            target=self._notif_manager.poll_streams,
            daemon=True,
        ).start()

    def _on_inventory_open_wiki(self, item_id: int, item_type: str,
                                item_name: str):
        """Navigate to the wiki page for the given item."""
        from .widgets.search_popup import WIKI_PATHS
        path = WIKI_PATHS.get(item_type, [])
        if not path:
            return
        self._applying_nav = True
        self._ensure_page(PAGE_WIKI)
        self._sidebar.set_active_no_emit(PAGE_WIKI)
        self._pages.setCurrentIndex(PAGE_WIKI)
        self._applying_nav = False
        nav_path = list(path)
        if item_name:
            nav_path.append(item_name)
        self._wiki_page.navigate_to(nav_path)

    # --- Page navigation ---

    def _on_page_changed(self, index: int):
        page = self._ensure_page(index)
        self._pages.setCurrentIndex(index)
        if index == PAGE_SETTINGS and hasattr(page, 'set_search'):
            page.set_search("")
        if not self._applying_nav:
            self._push_navigation(NavState(page=index))

    def _on_wiki_nav_changed(self, path: list[str]):
        if not self._applying_nav:
            self._push_navigation(NavState(page=PAGE_WIKI, sub_state=list(path)))

    def _on_dashboard_nav_changed(self, sub_state):
        if not self._applying_nav:
            self._push_navigation(NavState(page=PAGE_DASHBOARD, sub_state=sub_state))

    def _on_skills_nav_changed(self, sub_state):
        if not self._applying_nav:
            self._push_navigation(NavState(page=PAGE_SKILLS, sub_state=sub_state))

    def _on_search_submitted(self, query: str, results: list[dict]):
        """Title bar search Enter → switch to wiki, show search results."""
        self._applying_nav = True
        self._ensure_page(PAGE_WIKI)
        self._sidebar.set_active_no_emit(PAGE_WIKI)
        self._pages.setCurrentIndex(PAGE_WIKI)
        self._applying_nav = False
        self._wiki_page.show_search_results(query, results)

    def _on_search_result_selected(self, item: dict):
        """Title bar search result clicked → navigate wiki or open browser."""
        import webbrowser
        from urllib.parse import quote as url_quote
        from .widgets.search_popup import WIKI_PATHS

        # Ensure main window is visible (e.g. when triggered from an overlay)
        if not self.isVisible():
            self.show()
        self.activateWindow()
        self.raise_()

        item_type = item.get("Type", "")
        item_name = item.get("Name", "")
        if not item_name:
            return

        if item_type in ("User", "Society"):
            prefix = "/users/" if item_type == "User" else "/societies/"
            url = self._config.nexus_base_url + prefix + url_quote(item_name)
            webbrowser.open(url)
            return

        path = WIKI_PATHS.get(item_type)
        if path:
            self._applying_nav = True
            self._ensure_page(PAGE_WIKI)
            self._sidebar.set_active_no_emit(PAGE_WIKI)
            self._pages.setCurrentIndex(PAGE_WIKI)
            self._applying_nav = False
            self._wiki_page.navigate_to(list(path) + [item_name])

    def _on_create_requested(self, url_path: str):
        """Title bar 'add to wiki' category picked → open browser with ?mode=create."""
        import webbrowser
        webbrowser.open(self._config.nexus_base_url + url_path + "?mode=create")

    # --- Navigation history ---

    def _capture_scroll_pos(self) -> int:
        """Read the scroll position from the current page (if it supports it)."""
        page = self._pages.widget(self._nav_current.page)
        if hasattr(page, 'get_scroll_position'):
            return page.get_scroll_position()
        return 0

    def _push_navigation(self, new_state: NavState):
        if new_state == self._nav_current:
            return
        self._nav_current.scroll_pos = self._capture_scroll_pos()
        self._nav_back.append(self._nav_current)
        self._nav_current = new_state
        self._nav_forward.clear()
        self._update_nav_buttons()

    def _navigate_back(self):
        if not self._nav_back:
            return
        self._nav_current.scroll_pos = self._capture_scroll_pos()
        self._nav_forward.append(self._nav_current)
        self._nav_current = self._nav_back.pop()
        self._apply_nav_state(self._nav_current)
        self._update_nav_buttons()

    def _navigate_forward(self):
        if not self._nav_forward:
            return
        self._nav_current.scroll_pos = self._capture_scroll_pos()
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
        if state.scroll_pos and hasattr(page_widget, 'set_scroll_position'):
            QTimer.singleShot(0, lambda: page_widget.set_scroll_position(state.scroll_pos))
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

        # Update notifications
        self._signals.update_available.connect(self._on_update_available)
        self._signals.update_progress.connect(self._on_update_progress)
        self._signals.update_ready.connect(self._on_update_ready)
        self._signals.update_error.connect(self._on_update_error)

        # Remind-later timer
        self._remind_timer = QTimer(self)
        self._remind_timer.setSingleShot(True)
        self._remind_timer.timeout.connect(self._send_update_reminder_toast)

        # Check for pending remind-at on startup
        self._check_pending_remind()

    def _show_window(self):
        self.showNormal()
        self.activateWindow()

    def bring_to_front(self):
        """Bring window to foreground (called by single-instance IPC)."""
        self.showNormal()
        self.raise_()
        self.activateWindow()
        _platform.bring_to_foreground(int(self.winId()))

    def bring_to_front_on_screen(self, screen=None):
        """Bring window to foreground, moving to *screen* if provided.

        If the main window is currently on a different screen, it is
        repositioned to the center of the target screen before activating.
        """
        if screen is not None:
            current_screen = self.screen()
            if current_screen is not screen:
                geo = screen.availableGeometry()
                w, h = self.width(), self.height()
                x = geo.x() + (geo.width() - w) // 2
                y = geo.y() + (geo.height() - h) // 2
                self.move(x, y)
        self.bring_to_front()

    def _quit(self):
        try:
            self._save_geometry()
        except Exception:
            pass  # Shutdown must not be blocked by geometry save failure
        # Tell closeEvent to accept (not hide-to-tray) so Qt's quit
        # sequence isn't cancelled by the rejected close event.
        self._quitting = True
        # Defer quit so it runs after the tray context menu's nested event
        # loop closes — QApplication.quit() called inside the menu handler
        # only exits the menu's loop, not the outer app.exec().
        QTimer.singleShot(0, QApplication.quit)

    def cleanup(self):
        """Stop page timers and background threads. Called during shutdown."""
        for i in self._page_created:
            page = self._pages.widget(i)
            if hasattr(page, "cleanup"):
                page.cleanup()
        if hasattr(self, "_notif_manager"):
            self._notif_manager.cleanup()

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

    # --- Update system ---

    def _check_pending_remind(self):
        """On startup, check if a remind-at time is still pending."""
        remind_at = getattr(self._config, "update_remind_at", "")
        if not remind_at:
            return
        from datetime import datetime, timezone
        try:
            target = datetime.fromisoformat(remind_at)
            now = datetime.now(timezone.utc)
            remaining_ms = int((target - now).total_seconds() * 1000)
            if remaining_ms > 0:
                self._remind_timer.start(remaining_ms)
            # If in the past, the next update_available event will handle it
        except (ValueError, TypeError):
            pass

    def _on_update_available(self, data):
        """Handle EVENT_UPDATE_AVAILABLE — show icon + toast."""
        self._pending_update = data
        version = data.get("version", "")

        # Skip if user dismissed this exact version
        if getattr(self._config, "update_dismissed_version", "") == version:
            return

        # Check remind-at: if in the future, schedule timer and skip
        remind_at = getattr(self._config, "update_remind_at", "")
        if remind_at:
            from datetime import datetime, timezone
            try:
                target = datetime.fromisoformat(remind_at)
                now = datetime.now(timezone.utc)
                if target > now:
                    remaining_ms = int((target - now).total_seconds() * 1000)
                    self._remind_timer.start(remaining_ms)
                    return
            except (ValueError, TypeError):
                pass

        self._show_update_indicator(version)

    def _show_update_indicator(self, version: str):
        """Show the title bar icon and fire a system toast."""
        self._title_bar.show_update_available(version)

        if hasattr(self, "_tray"):
            self._tray.showMessage(
                "Update Available",
                f"Entropia Nexus v{version} is ready to install.",
                QSystemTrayIcon.MessageIcon.Information,
                8000,
            )

    def _on_update_progress(self, data):
        self._update_download_progress = data
        if self._update_dialog and self._update_dialog.isVisible():
            self._update_dialog.on_update_progress(data)

    def _on_update_ready(self, data):
        self._update_download_ready = data
        if self._update_dialog and self._update_dialog.isVisible():
            self._update_dialog.on_update_ready(data)
        # Auto-apply only if user already clicked "Update Now"
        if self._user_wants_update:
            from ..core.constants import EVENT_UPDATE_APPLY
            QTimer.singleShot(500, lambda: self._event_bus.publish(EVENT_UPDATE_APPLY, None))

    def _on_update_error(self, data):
        self._update_download_error = data
        if self._update_dialog and self._update_dialog.isVisible():
            self._update_dialog.on_update_error(data)
        if data.get("critical") and hasattr(self, "_tray"):
            self._tray.showMessage(
                "Update Check Failed",
                data.get("error", "Update checks are failing. "
                          "You may need to download the latest version manually."),
                QSystemTrayIcon.MessageIcon.Warning,
                10000,
            )

    def _on_update_icon_clicked(self):
        """Title bar update icon was clicked — open the update dialog."""
        if not self._pending_update:
            return
        self._open_update_dialog()

    def _open_update_dialog(self, changelog_only=False):
        """Open the update dialog."""
        from .dialogs.update_dialog import UpdateDialog

        dlg = UpdateDialog(
            update_data=self._pending_update or {},
            changelog_only=changelog_only,
            parent=self,
        )
        self._update_dialog = dlg

        # Replay current download state (events may have fired before dialog opened)
        if self._update_download_error:
            dlg.on_update_error(self._update_download_error)
        elif self._update_download_ready:
            dlg.on_update_ready(self._update_download_ready)
        elif self._update_download_progress:
            dlg.on_update_progress(self._update_download_progress)

        dlg.update_requested.connect(self._on_dialog_update)
        dlg.remind_requested.connect(self._on_dialog_remind)
        dlg.dismiss_requested.connect(self._on_dialog_dismiss)
        dlg.exec()
        self._update_dialog = None

    def open_changelog_dialog(self):
        """Open the update dialog in changelog-only mode (from settings)."""
        self._open_update_dialog(changelog_only=True)

    def _on_dialog_update(self):
        """User clicked 'Update Now' — apply if ready, otherwise apply when download finishes."""
        self._user_wants_update = True
        from ..core.constants import EVENT_UPDATE_APPLY
        if self._update_download_ready:
            # Download already done — apply immediately
            QTimer.singleShot(500, lambda: self._event_bus.publish(EVENT_UPDATE_APPLY, None))

    def _on_dialog_remind(self):
        """User clicked 'Remind Later' — schedule toast in 6 hours."""
        self._title_bar.hide_update_indicator()

        from datetime import datetime, timezone, timedelta
        from ..core.config import save_config
        remind_at = datetime.now(timezone.utc) + timedelta(hours=6)
        self._config.update_remind_at = remind_at.isoformat()
        save_config(self._config, self._config_path)

        REMIND_MS = 6 * 60 * 60 * 1000  # 6 hours
        self._remind_timer.start(REMIND_MS)

    def _on_dialog_dismiss(self, version: str):
        """User clicked 'Dismiss' — don't show again for this version."""
        self._title_bar.hide_update_indicator()

        from ..core.config import save_config
        self._config.update_dismissed_version = version
        self._config.update_remind_at = ""
        save_config(self._config, self._config_path)

    def _send_update_reminder_toast(self):
        """Timer fired — re-show update indicator and toast."""
        from ..core.config import save_config
        self._config.update_remind_at = ""
        save_config(self._config, self._config_path)

        if self._pending_update:
            version = self._pending_update.get("version", "")
            self._show_update_indicator(version)

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
        """Minimize to tray instead of closing (unless quitting)."""
        if self._quitting:
            event.accept()
            return
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
        # Reposition floating notification center if visible
        if hasattr(self, '_notification_center') and self._notification_center.isVisible():
            from .theme import SIDEBAR_WIDTH, STATUS_BAR_HEIGHT, TITLE_BAR_HEIGHT
            panel_h = self._notification_center.height()
            x = SIDEBAR_WIDTH
            y = self.height() - STATUS_BAR_HEIGHT - panel_h
            self._notification_center.move(x, max(TITLE_BAR_HEIGHT, y))

    def _enable_shadow(self):
        """Add a drop shadow to the frameless window (DWM on Windows, compositor on Linux)."""
        _platform.enable_shadow(int(self.winId()))

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
        """Handle back/forward mouse button navigation and notification panel dismiss."""
        if event.type() == QEvent.Type.MouseButtonPress:
            # Only handle events from this window's widget tree
            if not isinstance(obj, QWidget) or (obj is not self and not self.isAncestorOf(obj)):
                return False

            # Dismiss notification center when clicking outside it
            if (hasattr(self, "_notification_center")
                    and self._notification_center.isVisible()
                    and not self._notification_center.isAncestorOf(obj)
                    and obj is not self._notification_center):
                # Don't close if clicking the bell button (toggle handles it)
                bell = getattr(self._sidebar, "_bell_btn", None)
                if obj is not bell and (bell is None or not bell.isAncestorOf(obj)):
                    self._notification_center.hide()

            # Unfocus search bar when clicking outside it
            search = self._title_bar._search
            if search.hasFocus() and obj is not search:
                search.clearFocus()

            if event.button() == Qt.MouseButton.BackButton:
                self._navigate_back()
                return True
            elif event.button() == Qt.MouseButton.ForwardButton:
                self._navigate_forward()
                return True
        return False
