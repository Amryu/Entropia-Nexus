"""Entropia Nexus Desktop Client - Entry Point.

Usage:
    python -m client                  # Run with GUI
    python -m client --parse          # Batch parse existing chat.log, then exit
    python -m client --headless       # Run without GUI (chat watcher + OCR only)
    python -m client --config X       # Use custom config file
    python -m client --verbose        # Enable verbose logging
    python -m client --allow-multiple # Allow multiple instances
"""

import argparse
import os
import signal
import sys
import threading
import time
import traceback

from .core.config import load_config
from .core.constants import (
    EVENT_AUTH_STATE_CHANGED,
    EVENT_CONFIG_CHANGED,
    EVENT_OCR_MANUAL_TRIGGER,
)
from .core.event_bus import EventBus
from .core.database import Database
from .core.logger import init as init_logging, get_logger

log = get_logger("App")


def _configure_dpi_awareness():
    """Enable per-monitor DPI awareness on Windows.

    Must be called before creating any windows (Qt, Tkinter, or Win32).
    Without this, Win32 APIs return virtualized coordinates on scaled
    displays, causing overlay misalignment on high-DPI monitors.
    """
    if sys.platform != "win32":
        return
    import ctypes
    user32 = ctypes.windll.user32
    shcore = getattr(ctypes.windll, "shcore", None)

    # Per-Monitor V2 (Win10 1703+) — best multi-monitor support.
    try:
        set_ctx = getattr(user32, "SetProcessDpiAwarenessContext", None)
        if set_ctx is not None and bool(set_ctx(ctypes.c_void_p(-4))):
            log.info("DPI awareness set: Per-Monitor V2")
            return
        if set_ctx is not None:
            log.warning("SetProcessDpiAwarenessContext failed; trying fallback APIs")
    except (AttributeError, OSError):
        pass

    # Fallback: Per-Monitor V1 (Win8.1+).
    if shcore is not None:
        try:
            hr = int(shcore.SetProcessDpiAwareness(2))
            if hr == 0:
                log.info("DPI awareness set: Per-Monitor V1")
                return
            log.warning("SetProcessDpiAwareness failed (HRESULT=0x%08X); trying legacy fallback",
                        hr & 0xFFFFFFFF)
        except (AttributeError, OSError):
            pass

    # Legacy fallback: system-DPI-aware.
    try:
        if bool(user32.SetProcessDPIAware()):
            log.info("DPI awareness set: System-aware (legacy)")
        else:
            log.warning("SetProcessDPIAware failed; mixed-DPI OCR may be inaccurate")
    except (AttributeError, OSError):
        pass


def main():
    _configure_dpi_awareness()

    parser = argparse.ArgumentParser(description="Entropia Nexus Desktop Client")
    parser.add_argument("--parse", action="store_true", help="Batch parse chat.log and exit")
    parser.add_argument("--headless", action="store_true", help="Run without GUI")
    parser.add_argument("--config", default="config.json", help="Path to config file")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--allow-multiple", action="store_true", help="Allow multiple instances")
    args = parser.parse_args()

    init_logging(verbose=args.verbose)

    from .core import crash_handler
    crash_handler.install()

    # Load config
    try:
        config = load_config(args.config)
    except Exception as e:
        log.error("Config load failed: %s", e)
        traceback.print_exc()
        sys.exit(1)

    event_bus = EventBus()
    db = Database(config.database_path)

    log.info("Database: %s", config.database_path)

    # Batch parse mode
    if args.parse:
        _run_batch_parse(config, event_bus, db)
        db.close()
        return

    if args.headless:
        _run_headless(config, event_bus, db)
    else:
        _run_gui(config, event_bus, db, args.config, allow_multiple=args.allow_multiple)


_SINGLE_INSTANCE_SERVER_NAME = "EntropiaNexus-SingleInstance"


def _run_gui(config, event_bus, db, config_path, *, allow_multiple=False):
    """Run the full GUI application with Qt event loop."""
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer
    from PyQt6.QtNetwork import QLocalServer, QLocalSocket
    from .ui.signals import AppSignals, wire_signals
    from .ui.main_window import MainWindow
    from .auth.oauth_client import OAuthClient
    from .auth.token_store import TokenStore
    from .api.nexus_client import NexusClient
    from .api.data_client import DataClient

    # Set AppUserModelID before QApplication so Windows uses our icon
    # instead of the default Python interpreter icon in the taskbar.
    from .platform import backend as _platform
    _platform.set_app_id("EntropiaNexus.Client.1")

    app = QApplication(sys.argv)
    app.setApplicationName("Entropia Nexus")
    app.setQuitOnLastWindowClosed(False)  # Keep running in system tray

    from .core.crash_handler import set_qt_app
    set_qt_app(app)

    # Ctrl+C in the console: on Windows, KeyboardInterrupt raised inside Qt's
    # C++ event loop is caught by SIP and swallowed.  Route SIGINT directly
    # to QApplication.quit().  Second Ctrl+C force-kills immediately.
    _sigint_count = 0

    def _on_sigint(*_):
        nonlocal _sigint_count
        _sigint_count += 1
        if _sigint_count >= 2:
            os._exit(1)
        app.quit()

    signal.signal(signal.SIGINT, _on_sigint)

    # On Windows, Python signal handlers only run when Python bytecode
    # executes.  Qt's C++ event loop never gives Python that chance, so
    # SIGINT is silently swallowed.  A periodic no-op timer forces the
    # interpreter to check for pending signals every 200 ms.
    _signal_timer = QTimer()
    _signal_timer.timeout.connect(lambda: None)
    _signal_timer.start(200)

    # Single-instance enforcement: try to reach an existing instance
    if not allow_multiple:
        sock = QLocalSocket()
        sock.connectToServer(_SINGLE_INSTANCE_SERVER_NAME)
        if sock.waitForConnected(500):
            # Another instance is running — ask it to foreground, then exit
            sock.write(b"show")
            sock.waitForBytesWritten(1000)
            sock.disconnectFromServer()
            log.info("Another instance is running — requesting foreground")
            db.close()
            return
        sock.close()

    # Create the local server so future instances can find us
    local_server = QLocalServer()
    QLocalServer.removeServer(_SINGLE_INSTANCE_SERVER_NAME)  # clean stale socket from crash
    local_server.listen(_SINGLE_INSTANCE_SERVER_NAME)

    from .ui.icons import nexus_logo_icon
    app.setWindowIcon(nexus_logo_icon(32))

    from PyQt6.QtWidgets import QStyleFactory
    app.setStyle(QStyleFactory.create("Fusion"))

    from .ui.theme import get_stylesheet
    app.setStyleSheet(get_stylesheet())

    # Terms of Service acceptance gate
    from PyQt6.QtWidgets import QDialog
    from .core.config import save_config
    from .ui.dialogs.tos_dialog import TosDialog, TOS_VERSION
    if config.tos_accepted_version != TOS_VERSION:
        tos = TosDialog()
        if tos.exec() != QDialog.DialogCode.Accepted:
            db.close()
            return
        config.tos_accepted_version = TOS_VERSION
        save_config(config, config_path)

    # Init auth early (needed to decide whether to show splash)
    token_store = TokenStore()
    oauth = OAuthClient(config, event_bus, token_store)
    # Show splash screen if not already authenticated
    splash_screen = None
    if not oauth.is_authenticated():
        splash_result = _show_splash(app, oauth, event_bus)
        if splash_result is True:
            db.close()
            return
        splash_screen = splash_result  # QScreen the splash was on

    # Init remaining services
    nexus_client = NexusClient(config, oauth, event_bus)
    data_client = DataClient(config)
    signals = AppSignals()
    wire_signals(event_bus, signals)

    # Create main window FIRST — before any background workers, because
    # worker threads (OCR, etc.) access Win32 display APIs that can race
    # with Qt's native window initialization and cause segfaults.
    main_window = MainWindow(
        config=config,
        config_path=config_path,
        event_bus=event_bus,
        db=db,
        signals=signals,
        oauth=oauth,
        nexus_client=nexus_client,
        data_client=data_client,
    )
    main_window.show()

    # If we came from the splash, show the main window on the same monitor
    if splash_screen is not None:
        main_window.bring_to_front_on_screen(splash_screen)

    # Wire single-instance IPC: when another instance connects, bring window to front
    def _handle_ipc_connection():
        conn = local_server.nextPendingConnection()
        if conn:
            conn.waitForReadyRead(1000)
            conn.close()
            main_window.bring_to_front()

    local_server.newConnection.connect(_handle_ipc_connection)

    # Refresh tokens + fetch user info in background now that UI is visible.
    # This replaces the synchronous network calls that used to block __init__
    # for up to 20s when the server is slow or unreachable.
    # Also serves as re-emit: the background thread will publish
    # EVENT_AUTH_STATE_CHANGED once user info is fetched.
    if oauth.is_authenticated():
        # Watch for background refresh discovering dead tokens (e.g. 400 from
        # server).  If auth drops to unauthenticated, show the splash so the
        # user can re-login immediately instead of seeing "Logged in as None".
        def _on_deauth(state):
            if state.authenticated:
                return
            event_bus.unsubscribe(EVENT_AUTH_STATE_CHANGED, _on_deauth)
            from PyQt6.QtCore import QMetaObject, Qt as QtNamespace
            QMetaObject.invokeMethod(
                main_window,
                lambda: _show_splash_over_main(main_window, oauth, event_bus),
                QtNamespace.ConnectionType.QueuedConnection,
            )
        event_bus.subscribe(EVENT_AUTH_STATE_CHANGED, _on_deauth)
        oauth.refresh_in_background()
    else:
        # Not authenticated — still re-emit so sidebar shows logged-out state
        event_bus.publish(EVENT_AUTH_STATE_CHANGED, oauth.auth_state)

    # Now start worker threads (safe — Qt platform integration is initialized)
    # Ingestion uploader must subscribe to EVENT_CATCHUP_COMPLETE BEFORE
    # the chat watcher starts its catchup thread, to avoid a race condition
    # where catchup finishes before the uploader exists.
    # Shared frame cache — all OCR detectors reuse the same PrintWindow captures
    from .ocr.frame_cache import SharedFrameCache
    frame_cache = SharedFrameCache(capture_backend=config.ocr_capture_backend)

    def _sync_capture_backend(updated_config):
        if not updated_config:
            return
        frame_cache.set_capture_backend(
            getattr(updated_config, "ocr_capture_backend", "auto"),
        )

    event_bus.subscribe(EVENT_CONFIG_CHANGED, _sync_capture_backend)

    workers = []
    workers.extend(_start_ingestion(config, event_bus, nexus_client, db))
    workers.extend(_start_chat_watcher(config, event_bus, db, authenticated=oauth.is_authenticated()))
    workers.extend(_start_ocr_pipeline(config, event_bus, db, frame_cache))
    # workers.extend(_start_hunt_tracker(config, event_bus, db, data_client))  # hunt disabled
    workers.extend(_start_hotkey_manager(config, event_bus))
    workers.extend(_start_update_checker(config, event_bus))
    workers.extend(_start_target_lock_detector(config, event_bus, frame_cache))
    workers.extend(_start_player_status_detector(config, event_bus, frame_cache))
    # Market price detector disabled — OCR not ready yet
    # workers.extend(_start_market_price_detector(config, event_bus, frame_cache))

    # Overlay manager (focus detection, widget registry, snap)
    from .overlay.overlay_manager import OverlayManager
    overlay_manager = OverlayManager(config=config, event_bus=event_bus)

    # Defer overlay widget creation so the main window renders first.
    # The OverlayManager itself is lightweight (timer + state); the actual
    # overlay widgets are heavy (Qt windows, stylesheets, layouts).
    def _create_overlays():
        # Qt overlays (always-on-top, draggable, position persisted)
        # Hunt overlay disabled
        # try:
        #     from .overlay.hunt_overlay import HuntOverlay
        #     HuntOverlay(
        #         signals=signals, config=config, config_path=config_path,
        #         manager=overlay_manager,
        #     )
        # except Exception as e:
        #     log.warning("Hunt overlay failed: %s", e)

        search_overlay = None
        try:
            from .overlay.search_overlay import SearchOverlayWidget
            search_overlay = SearchOverlayWidget(
                config=config, config_path=config_path,
                data_client=data_client, manager=overlay_manager,
            )
        except Exception as e:
            log.warning("Search overlay failed: %s", e)

        # Map overlay (singleton)
        _map_overlay = None

        def _toggle_map_overlay():
            nonlocal _map_overlay
            from .overlay.map_overlay import MapOverlay
            if _map_overlay is None or not _map_overlay.isVisible():
                if _map_overlay is None:
                    _map_overlay = MapOverlay(
                        config=config,
                        config_path=config_path,
                        data_client=data_client,
                        manager=overlay_manager,
                    )
                _map_overlay.set_wants_visible(True)
                _map_overlay.raise_()
            else:
                _map_overlay.set_wants_visible(False)

        def _open_map_overlay_at(planet_name: str, location_id: int):
            nonlocal _map_overlay
            from .overlay.map_overlay import MapOverlay
            if _map_overlay is None:
                _map_overlay = MapOverlay(
                    config=config,
                    config_path=config_path,
                    data_client=data_client,
                    manager=overlay_manager,
                )
            _map_overlay.open_at_location(planet_name, location_id)

        overlay_manager.map_hotkey_pressed.connect(_toggle_map_overlay)

        # Exchange overlay (singleton) + shared stores
        from .exchange.exchange_store import ExchangeStore
        from .exchange.favourites_store import FavouritesStore
        _exchange_store = ExchangeStore(nexus_client, event_bus)
        _exchange_store.load_items()
        _favourites_store = FavouritesStore(nexus_client)
        main_window._exchange_store = _exchange_store
        main_window._favourites_store = _favourites_store
        main_window.connect_exchange_store(_exchange_store)
        _exchange_overlay = None

        def _toggle_exchange_overlay():
            nonlocal _exchange_overlay
            from .overlay.exchange_overlay import ExchangeOverlay
            if _exchange_overlay is None or not _exchange_overlay.isVisible():
                if _exchange_overlay is None:
                    _exchange_overlay = ExchangeOverlay(
                        config=config,
                        config_path=config_path,
                        store=_exchange_store,
                        favourites=_favourites_store,
                        manager=overlay_manager,
                    )
                    _exchange_overlay.open_entity.connect(_on_overlay_result_selected)
                _exchange_overlay.set_wants_visible(True)
                _exchange_overlay.raise_()
            else:
                _exchange_overlay.set_wants_visible(False)

        overlay_manager.exchange_hotkey_pressed.connect(_toggle_exchange_overlay)

        # --- Toast manager (in-game toasts) ---
        from .overlay.toast_widget import ToastManager
        toast_manager = ToastManager(config=config)
        main_window.set_overlay_manager(overlay_manager)
        main_window.set_toast_manager(toast_manager)
        overlay_manager.game_focus_changed.connect(toast_manager.set_visible)

        # --- Notifications overlay (singleton) ---
        _notifications_overlay = None

        def _toggle_notifications_overlay():
            nonlocal _notifications_overlay
            from .overlay.notifications_overlay import NotificationsOverlay
            if _notifications_overlay is None or not _notifications_overlay.isVisible():
                if _notifications_overlay is None:
                    _notifications_overlay = NotificationsOverlay(
                        config=config,
                        config_path=config_path,
                        notif_manager=main_window._notif_manager,
                        manager=overlay_manager,
                    )
                    _notifications_overlay.read_state_changed.connect(
                        main_window._update_badge
                    )
                _notifications_overlay.set_wants_visible(True)
                _notifications_overlay.raise_()
            else:
                _notifications_overlay.set_wants_visible(False)

        overlay_manager.notifications_hotkey_pressed.connect(
            _toggle_notifications_overlay
        )

        # F2 toggles all overlay widgets (hides as if occluded)
        overlay_manager.overlay_toggle_hotkey_pressed.connect(
            overlay_manager.toggle_user_visible
        )

        # Toast action routing (url → browser, overlay → toggle)
        def _on_toast_action(action_type, action_data):
            if action_type == "url":
                from PyQt6.QtGui import QDesktopServices
                from PyQt6.QtCore import QUrl
                QDesktopServices.openUrl(QUrl(action_data))
            elif action_type == "overlay":
                if action_data == "exchange":
                    _toggle_exchange_overlay()
                elif action_data == "map":
                    _toggle_map_overlay()
                elif action_data == "notifications":
                    _toggle_notifications_overlay()

        toast_manager.toast_action_triggered.connect(_on_toast_action)

        # Expose map overlay opener for detail overlay map buttons
        from .overlay import detail_overlay as _detail_overlay_mod
        _detail_overlay_mod._map_overlay_callback = _open_map_overlay_at

        # Detail overlay: opened when a search result is selected
        _current_detail_overlay = None
        _current_profile_overlay = None
        _detail_overlays: list = []   # all open overlays (for offset stacking)

        _current_society_overlay = None

        def _on_overlay_result_selected(item):
            nonlocal _current_detail_overlay, _current_profile_overlay
            nonlocal _current_society_overlay
            from .overlay.detail_overlay import DetailOverlayWidget, STACK_OFFSET

            # Middle-click sets _force_new to always open a new window
            force_new = item.pop("_force_new", False)

            # Route Society type to society overlay
            if item.get("Type") == "Society":
                from .overlay.society_overlay import SocietyOverlayWidget
                if (not force_new
                        and _current_society_overlay
                        and _current_society_overlay.isVisible()
                        and not _current_society_overlay.pinned):
                    _current_society_overlay.close()
                overlay = SocietyOverlayWidget(
                    society_name=item.get("Name", ""),
                    config=config,
                    config_path=config_path,
                    nexus_client=nexus_client,
                    manager=overlay_manager,
                )
                overlay.open_entity.connect(_on_overlay_result_selected)
                _current_society_overlay = overlay
                return

            # Route User type to profile overlay
            if item.get("Type") == "User":
                from .overlay.profile_overlay import ProfileOverlayWidget
                if (not force_new
                        and _current_profile_overlay
                        and _current_profile_overlay.isVisible()
                        and not _current_profile_overlay.pinned):
                    _current_profile_overlay.close()
                overlay = ProfileOverlayWidget(
                    user_name=item.get("Name", ""),
                    config=config,
                    config_path=config_path,
                    nexus_client=nexus_client,
                    manager=overlay_manager,
                )
                overlay.open_profile_web.connect(main_window._on_search_result_selected)
                overlay.open_entity.connect(_on_overlay_result_selected)

                def _open_exchange_orderbook(item_id):
                    nonlocal _exchange_overlay
                    from .overlay.exchange_overlay import ExchangeOverlay
                    if _exchange_overlay is None:
                        _exchange_overlay = ExchangeOverlay(
                            config=config,
                            config_path=config_path,
                            store=_exchange_store,
                            favourites=_favourites_store,
                            manager=overlay_manager,
                        )
                        _exchange_overlay.open_entity.connect(
                            _on_overlay_result_selected
                        )
                    _exchange_overlay.set_wants_visible(True)
                    _exchange_overlay.raise_()
                    _exchange_overlay.navigate_to_order_book(item_id)

                overlay.open_exchange.connect(_open_exchange_orderbook)
                _current_profile_overlay = overlay
                return

            # Navigate in-place if there's an active unpinned overlay
            if (not force_new
                    and _current_detail_overlay
                    and _current_detail_overlay.isVisible()
                    and not _current_detail_overlay.pinned):
                _current_detail_overlay._navigate_to(item)
                return

            # Prune closed overlays from the list
            _detail_overlays[:] = [o for o in _detail_overlays if o.isVisible()]

            overlay = DetailOverlayWidget(
                item,
                config=config,
                config_path=config_path,
                data_client=data_client,
                nexus_client=nexus_client,
                manager=overlay_manager,
            )
            if config.auto_pin_detail_overlay:
                overlay.set_pinned(True)
            overlay.open_in_wiki.connect(main_window._on_search_result_selected)
            overlay.open_entity.connect(_on_overlay_result_selected)
            overlay.create_loadout.connect(lambda data: nexus_client.create_loadout(data))

            if _detail_overlays:
                # Offset from existing open overlays so they don't perfectly stack
                count = len(_detail_overlays)
                pos = overlay.pos()
                overlay.move(pos.x() + STACK_OFFSET * count, pos.y() + STACK_OFFSET * count)

            _detail_overlays.append(overlay)
            _current_detail_overlay = overlay

        # Expose detail overlay opener for map overlay mob clicks
        from .overlay import map_overlay as _map_overlay_mod
        _map_overlay_mod._open_entity_callback = _on_overlay_result_selected

        # Allow any page to open entity detail overlays via signals
        signals.open_entity_overlay.connect(_on_overlay_result_selected)

        if search_overlay:
            search_overlay.result_selected.connect(_on_overlay_result_selected)

            # Logo click — focus client on the overlay's monitor
            from PyQt6.QtWidgets import QApplication
            search_overlay.logo_clicked.connect(
                lambda: main_window.bring_to_front_on_screen(
                    QApplication.screenAt(search_overlay.geometry().center())
                )
            )

            # Burger menu actions
            def _on_search_menu_action(action):
                if action == "map":
                    _toggle_map_overlay()
                elif action == "exchange":
                    _toggle_exchange_overlay()
                elif action == "notifications":
                    _toggle_notifications_overlay()

            search_overlay.menu_action.connect(_on_search_menu_action)

            # Notification badge on logo
            main_window.set_search_overlay(search_overlay)

        # Scan highlight overlay (click-through, shows scanned rows + target lock)
        try:
            from .overlay.scan_highlight_overlay import ScanHighlightOverlay
            _scan_highlight_overlay = None

            def _ensure_scan_highlight_overlay():
                nonlocal _scan_highlight_overlay
                if _scan_highlight_overlay is not None:
                    return
                _scan_highlight_overlay = ScanHighlightOverlay(
                    config=config,
                    event_bus=event_bus,
                    manager=overlay_manager,
                )
                overlay_manager._scan_highlight = _scan_highlight_overlay

            def _destroy_scan_highlight_overlay():
                nonlocal _scan_highlight_overlay
                if _scan_highlight_overlay is None:
                    return
                _scan_highlight_overlay.stop()
                _scan_highlight_overlay.deleteLater()
                _scan_highlight_overlay = None
                overlay_manager._scan_highlight = None

            def _sync_scan_highlight_overlay(updated_config):
                if not updated_config:
                    return
                if getattr(updated_config, "scan_overlay_debug", False):
                    _ensure_scan_highlight_overlay()
                else:
                    _destroy_scan_highlight_overlay()

            # Never auto-open debug overlay on startup.
            if getattr(config, "scan_overlay_debug", False):
                config.scan_overlay_debug = False
                save_config(config, config_path)

            _sync_scan_highlight_overlay(config)
            event_bus.subscribe(EVENT_CONFIG_CHANGED, _sync_scan_highlight_overlay)

            # F3 toggles debug overlay mode (persists to config)
            def _toggle_debug_overlay():
                config.scan_overlay_debug = not config.scan_overlay_debug
                save_config(config, config_path)
                event_bus.publish(EVENT_CONFIG_CHANGED, config)

            overlay_manager.debug_overlay_hotkey_pressed.connect(
                _toggle_debug_overlay
            )
        except Exception as e:
            log.warning("Scan highlight overlay failed: %s", e)

        # Scan summary overlay (draggable panel, shows scan results + validation)
        try:
            from .overlay.scan_summary_overlay import ScanSummaryOverlay
            from .ui.main_window import PAGE_SKILLS

            def _get_skill_values():
                if PAGE_SKILLS in main_window._page_created:
                    page = main_window._pages.widget(PAGE_SKILLS)
                    return page._manager.get_all_values()
                return {}

            overlay_manager._scan_summary = ScanSummaryOverlay(
                config=config, config_path=config_path,
                event_bus=event_bus, manager=overlay_manager,
                skill_values_fn=_get_skill_values,
            )

            def _clear_scan_selection():
                if PAGE_SKILLS not in main_window._page_created:
                    return
                page = main_window._pages.widget(PAGE_SKILLS)
                if hasattr(page, "clear_scan_results"):
                    page.clear_scan_results()

            def _on_scan_marked_complete(skills: list):
                """Mark Complete: compute delta, warn on shrinkage, then sync."""
                if PAGE_SKILLS not in main_window._page_created:
                    return
                page = main_window._pages.widget(PAGE_SKILLS)
                manager = page._manager

                delta = manager.sync_scan_results(skills)

                if not delta["changes"]:
                    log.info("Scan complete — no changes to sync")
                    return

                def do_sync():
                    ok = manager.apply_scan_results(skills)
                    if ok:
                        log.info("Scan results synced: %d changes",
                                 len(delta["changes"]))
                    else:
                        log.error("Scan results sync failed")

                if delta["shrunk"]:
                    from .overlay.confirm_overlay import ConfirmOverlay
                    dialog = ConfirmOverlay(
                        config=config, config_path=config_path,
                        manager=overlay_manager,
                        title="Skill Points Decreased",
                        confirm_text="Sync Anyway",
                    )
                    dialog.set_shrinkage_warning(delta["shrunk"])
                    dialog.confirmed.connect(
                        lambda: threading.Thread(
                            target=do_sync, daemon=True,
                        ).start()
                    )
                    dialog.set_wants_visible(True)
                else:
                    threading.Thread(target=do_sync, daemon=True).start()

            overlay_manager._scan_summary.scan_marked_complete.connect(
                _on_scan_marked_complete
            )
            overlay_manager._scan_summary.scan_entries_cleared.connect(
                _clear_scan_selection
            )
        except Exception as e:
            log.warning("Scan summary overlay failed: %s", e)

    QTimer.singleShot(0, _create_overlays)

    exit_code = app.exec()

    # Hard deadline — start BEFORE any cleanup so a blocking stop()
    # (e.g. keyboard library lock contention) can never hang the process.
    def force_exit():
        log.error("Shutdown timed out, forcing exit")
        os._exit(exit_code or 1)

    kill_timer = threading.Timer(5.0, force_exit)
    kill_timer.daemon = True
    kill_timer.start()

    local_server.close()
    main_window.cleanup()
    overlay_manager.stop()
    nexus_client.close()
    data_client.close()
    _cleanup_workers(workers)
    db.close()
    kill_timer.cancel()
    os._exit(exit_code or 0)


def _show_splash(app, oauth, event_bus):
    """Show the splash screen and block until the user logs in or chooses offline.

    Returns True if user closed the splash (app should exit), or the QScreen
    the splash was on (so the main window can appear on the same monitor).
    """
    from PyQt6.QtCore import QEventLoop, QMetaObject, Qt as QtNamespace
    from PyQt6.QtWidgets import QApplication
    from .core.constants import EVENT_AUTH_STATE_CHANGED
    from .ui.widgets.splash_screen import SplashScreen

    splash = SplashScreen()
    loop = QEventLoop()

    def on_login():
        splash.show_login_progress()

        def do_login():
            try:
                result = oauth.login()
                if result is not True:
                    splash._login_error.emit(result if isinstance(result, str) else "Login failed")
            except Exception as e:
                splash._login_error.emit(str(e) or e.__class__.__name__)

        threading.Thread(target=do_login, daemon=True).start()

    def on_auth_changed(data):
        """Close splash when OAuth succeeds (called from background thread)."""
        QMetaObject.invokeMethod(
            loop, "quit",
            QtNamespace.ConnectionType.QueuedConnection,
        )

    closed = False

    def on_dismiss():
        loop.quit()

    def on_close():
        nonlocal closed
        closed = True
        loop.quit()

    splash.login_clicked.connect(on_login)
    splash.offline_clicked.connect(on_dismiss)
    splash.close_clicked.connect(on_close)
    event_bus.subscribe(EVENT_AUTH_STATE_CHANGED, on_auth_changed)

    splash.show()
    loop.exec()  # Blocks until splash is dismissed (without touching QApplication quit state)

    # Remember which screen the splash was on before hiding it
    splash_screen = QApplication.screenAt(splash.geometry().center())

    splash.hide()
    event_bus.unsubscribe(EVENT_AUTH_STATE_CHANGED, on_auth_changed)

    if closed:
        log.info("User closed splash — exiting")
        return True  # signal caller to exit

    log.warning("Auth: %s", "authenticated" if oauth.is_authenticated() else "offline")
    return splash_screen


def _show_splash_over_main(main_window, oauth, event_bus):
    """Show the splash as a modal overlay when background token refresh fails.

    Called on the Qt main thread when the auth state drops to unauthenticated
    after the main window is already visible (e.g. expired refresh token).
    """
    from PyQt6.QtCore import QEventLoop, QMetaObject, Qt as QtNamespace
    from .core.constants import EVENT_AUTH_STATE_CHANGED
    from .ui.widgets.splash_screen import SplashScreen

    log.warning("Session expired — showing login splash")

    splash = SplashScreen()
    loop = QEventLoop()

    def on_login():
        splash.show_login_progress()

        def do_login():
            try:
                result = oauth.login()
                if result is not True:
                    splash._login_error.emit(result if isinstance(result, str) else "Login failed")
            except Exception as e:
                splash._login_error.emit(str(e) or e.__class__.__name__)

        threading.Thread(target=do_login, daemon=True).start()

    def on_auth_changed(data):
        if not getattr(data, "authenticated", False):
            return
        QMetaObject.invokeMethod(
            loop, "quit",
            QtNamespace.ConnectionType.QueuedConnection,
        )

    def on_dismiss():
        loop.quit()

    def on_close():
        loop.quit()

    splash.login_clicked.connect(on_login)
    splash.offline_clicked.connect(on_dismiss)
    splash.close_clicked.connect(on_close)
    event_bus.subscribe(EVENT_AUTH_STATE_CHANGED, on_auth_changed)

    splash.show()
    loop.exec()

    splash.hide()
    event_bus.unsubscribe(EVENT_AUTH_STATE_CHANGED, on_auth_changed)

    log.warning("Splash dismissed — auth: %s",
                "authenticated" if oauth.is_authenticated() else "offline")


def _run_headless(config, event_bus, db):
    """Run without GUI — chat watcher + OCR only (original behavior)."""
    from .api.data_client import DataClient

    shutdown_event = threading.Event()

    def on_signal(signum, frame):
        shutdown_event.set()

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    data_client = DataClient(config)

    workers = []
    workers.extend(_start_chat_watcher(config, event_bus, db))
    workers.extend(_start_ocr_pipeline(config, event_bus, db))
    # workers.extend(_start_hunt_tracker(config, event_bus, db, data_client))  # hunt disabled
    workers.extend(_start_hotkey_manager(config, event_bus))

    log.warning("Running headless... Press Ctrl+C to stop.")
    sys.stdout.flush()
    try:
        while not shutdown_event.is_set():
            shutdown_event.wait(timeout=1.0)
    except KeyboardInterrupt:
        pass

    # Cleanup with hard deadline
    def force_exit():
        log.error("Shutdown timed out, forcing exit")
        os._exit(1)

    kill_timer = threading.Timer(3.0, force_exit)
    kill_timer.daemon = True
    kill_timer.start()

    log.warning("Shutting down...")
    data_client.close()
    _cleanup_workers(workers)
    db.close()
    kill_timer.cancel()
    log.info("Goodbye")


def _start_chat_watcher(config, event_bus, db, *, authenticated=False):
    """Start the chat log watcher. Returns list of stoppable workers."""
    workers = []
    try:
        from .chat_parser.watcher import ChatLogWatcher
        watcher = ChatLogWatcher(config, event_bus, db, authenticated=authenticated)
        watcher.start()
        workers.append(watcher)
        log.info("Chat watcher started: %s", config.chat_log_path)
    except Exception as e:
        log.error("Chat watcher failed to start: %s", e)
    return workers


def _start_ocr_pipeline(config, event_bus, db, frame_cache=None):
    """Start the OCR scan orchestrator. Returns list of stoppable workers."""
    workers = []
    try:
        from .ocr.orchestrator import ScanOrchestrator
        orchestrator = ScanOrchestrator(config, event_bus, db, frame_cache=frame_cache)
        log.info("OCR pipeline ready")
        manual_trigger = threading.Event()

        def _on_manual_trigger(_data=None):
            # Force the current OCR loop to restart so the visible page
            # is scanned again immediately.
            orchestrator._stop_event.set()
            manual_trigger.set()

        def _on_config_changed(_data=None):
            orchestrator.set_capture_backend(
                getattr(config, "ocr_capture_backend", "auto"),
            )
            # Wake OCR thread immediately when scan mode is toggled.
            orchestrator._stop_event.set()
            manual_trigger.set()

        event_bus.subscribe(EVENT_OCR_MANUAL_TRIGGER, _on_manual_trigger)
        event_bus.subscribe(EVENT_CONFIG_CHANGED, _on_config_changed)

        def run_ocr():
            while not orchestrator._shutdown:
                orchestrator._stop_event.clear()
                try:
                    auto_enabled = getattr(config, "ocr_auto_scan_enabled", True)
                    if not auto_enabled:
                        log.info("OCR auto-scan disabled; waiting for manual scan trigger")
                        while not orchestrator._shutdown:
                            if manual_trigger.wait(timeout=0.25):
                                manual_trigger.clear()
                                break
                        if orchestrator._shutdown:
                            break
                        # If auto-scan was enabled while waiting, restart loop in auto mode.
                        if getattr(config, "ocr_auto_scan_enabled", True):
                            continue
                        result = orchestrator.run_continuous(auto_resume=False)
                    else:
                        result = orchestrator.run_continuous(auto_resume=True)
                    if result:
                        log.info("OCR finished: %d/%d skills",
                                 result.total_found, result.total_expected)
                    else:
                        log.info("OCR: skills window not found")
                except Exception as e:
                    log.error("OCR error: %s", e)
                if not orchestrator._shutdown:
                    if getattr(config, "ocr_auto_scan_enabled", True):
                        log.info("OCR scan ended, will restart when "
                                 "SKILLS window reopens")
                    else:
                        log.info("Manual scan ended")

        ocr_thread = threading.Thread(target=run_ocr, daemon=True, name="ocr-scan")
        ocr_thread.start()
        workers.append(orchestrator)
    except Exception as e:
        log.error("OCR init failed: %s", e)
    return workers


def _start_hunt_tracker(config, event_bus, db, data_client=None):
    """Start the hunt session tracker. Returns list of stoppable workers."""
    workers = []
    try:
        from .hunt.tracker import HuntTracker
        tracker = HuntTracker(config, event_bus, db, data_client)
        workers.append(tracker)
        log.info("Hunt tracker ready")
    except Exception as e:
        log.error("Hunt tracker failed to start: %s", e)
    return workers


def _start_hotkey_manager(config, event_bus):
    """Start the global hotkey manager. Returns list of stoppable workers."""
    workers = []
    try:
        from .hotkeys.manager import HotkeyManager
        manager = HotkeyManager(config, event_bus)
        manager.start()
        workers.append(manager)
        log.info("Hotkey manager started")
    except Exception as e:
        log.error("Hotkey manager failed to start: %s", e)
    return workers


def _start_update_checker(config, event_bus):
    """Start the background update checker. Returns list of stoppable workers."""
    workers = []
    try:
        from .updater import UpdateChecker
        checker = UpdateChecker(config, event_bus)
        checker.start()
        workers.append(checker)
        log.info("Update checker started")
    except Exception as e:
        log.error("Update checker failed to start: %s", e)
    return workers


def _start_target_lock_detector(config, event_bus, frame_cache=None):
    """Start the target lock detector. Returns list of stoppable workers."""
    workers = []
    if not getattr(config, "target_lock_enabled", True):
        return workers
    try:
        from .ocr.target_lock_detector import TargetLockDetector
        if frame_cache is None:
            from .ocr.capturer import ScreenCapturer
            frame_cache = ScreenCapturer(capture_backend=config.ocr_capture_backend)
        detector = TargetLockDetector(config, event_bus, frame_cache)
        detector.start()
        workers.append(detector)
        log.info("Target lock detector started")
    except Exception as e:
        log.error("Target lock detector failed to start: %s", e)
    return workers


def _start_player_status_detector(config, event_bus, frame_cache=None):
    """Start the player status (heart) detector. Returns list of stoppable workers."""
    workers = []
    if not getattr(config, "player_status_enabled", True):
        return workers
    try:
        from .ocr.player_status_detector import PlayerStatusDetector
        if frame_cache is None:
            from .ocr.capturer import ScreenCapturer
            frame_cache = ScreenCapturer(capture_backend=config.ocr_capture_backend)
        detector = PlayerStatusDetector(config, event_bus, frame_cache)
        detector.start()
        workers.append(detector)
        log.info("Player status detector started")
    except Exception as e:
        log.error("Player status detector failed to start: %s", e)
    return workers


def _start_market_price_detector(config, event_bus, frame_cache=None):
    """Start the market price detector. Returns list of stoppable workers."""
    workers = []
    if not getattr(config, "market_price_enabled", True):
        return workers
    try:
        from .ocr.market_price_detector import MarketPriceDetector
        if frame_cache is None:
            from .ocr.capturer import ScreenCapturer
            frame_cache = ScreenCapturer(capture_backend=config.ocr_capture_backend)
        detector = MarketPriceDetector(config, event_bus, frame_cache)
        detector.start()
        workers.append(detector)
        log.info("Market price detector started")
    except Exception as e:
        log.error("Market price detector failed to start: %s", e)
    return workers


def _start_ingestion(config, event_bus, nexus_client, db=None):
    """Start the ingestion uploader and receiver. Returns list of stoppable workers."""
    workers = []
    if not getattr(config, "ingestion_enabled", True):
        return workers
    try:
        from .ingestion.uploader import IngestionUploader
        uploader = IngestionUploader(
            event_bus=event_bus, nexus_client=nexus_client, config=config, db=db,
        )
        uploader.start()
        workers.append(uploader)
    except Exception as e:
        log.error("Ingestion uploader failed to start: %s", e)
    try:
        from .ingestion.receiver import IngestionReceiver
        receiver = IngestionReceiver(
            event_bus=event_bus, nexus_client=nexus_client, config=config,
        )
        receiver.start()
        workers.append(receiver)
    except Exception as e:
        log.error("Ingestion receiver failed to start: %s", e)
    return workers


def _cleanup_workers(workers):
    """Stop all workers in parallel to minimize total shutdown time."""
    threads = []
    for worker in workers:
        def _stop(w=worker):
            try:
                w.stop()
            except Exception as e:
                log.error("Error stopping %s: %s", w.__class__.__name__, e)
        t = threading.Thread(target=_stop, daemon=True)
        t.start()
        threads.append(t)
    # Wait for all stop() calls, with a shared 4s budget (leaves 1s
    # headroom before the 5s force-exit timer).
    deadline = time.monotonic() + 4.0
    for t in threads:
        remaining = deadline - time.monotonic()
        if remaining > 0:
            t.join(timeout=remaining)


def _run_batch_parse(config, event_bus, db):
    """Parse the entire chat.log file from current offset and exit."""
    from .chat_parser.watcher import ChatLogWatcher

    log.warning("Batch parsing: %s", config.chat_log_path)
    watcher = ChatLogWatcher(config, event_bus, db)
    watcher.parse_file()
    log.warning("Batch parse complete")


if __name__ == "__main__":
    main()
