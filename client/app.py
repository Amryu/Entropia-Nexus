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
import traceback

from .core.config import load_config
from .core.constants import EVENT_AUTH_STATE_CHANGED
from .core.event_bus import EventBus
from .core.database import Database
from .core.logger import init as init_logging, get_logger

log = get_logger("App")


def main():
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
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "EntropiaNexus.Client.1"
        )

    app = QApplication(sys.argv)
    app.setApplicationName("Entropia Nexus")
    app.setQuitOnLastWindowClosed(False)  # Keep running in system tray

    from .core.crash_handler import set_qt_app
    set_qt_app(app)

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

    # Init auth early (needed to decide whether to show splash)
    token_store = TokenStore()
    oauth = OAuthClient(config, event_bus, token_store)
    # Show splash screen if not already authenticated
    if not oauth.is_authenticated():
        if _show_splash(app, oauth, event_bus):
            db.close()
            return

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
        oauth.refresh_in_background()
    else:
        # Not authenticated — still re-emit so sidebar shows logged-out state
        event_bus.publish(EVENT_AUTH_STATE_CHANGED, oauth.auth_state)

    # Now start worker threads (safe — Qt platform integration is initialized)
    # Ingestion uploader must subscribe to EVENT_CATCHUP_COMPLETE BEFORE
    # the chat watcher starts its catchup thread, to avoid a race condition
    # where catchup finishes before the uploader exists.
    workers = []
    workers.extend(_start_ingestion(config, event_bus, nexus_client, db))
    workers.extend(_start_chat_watcher(config, event_bus, db, authenticated=oauth.is_authenticated()))
    # workers.extend(_start_ocr_pipeline(config, event_bus, db))  # disabled for debugging
    workers.extend(_start_hunt_tracker(config, event_bus, db, data_client))
    workers.extend(_start_hotkey_manager(config, event_bus))
    workers.extend(_start_update_checker(config, event_bus))

    # Overlay manager (focus detection, widget registry, snap)
    from .overlay.overlay_manager import OverlayManager
    overlay_manager = OverlayManager(config=config)

    # Defer overlay widget creation so the main window renders first.
    # The OverlayManager itself is lightweight (timer + state); the actual
    # overlay widgets are heavy (Qt windows, stylesheets, layouts).
    def _create_overlays():
        # Qt overlays (always-on-top, draggable, position persisted)
        try:
            from .overlay.hunt_overlay import HuntOverlay
            HuntOverlay(
                signals=signals, config=config, config_path=config_path,
                manager=overlay_manager,
            )
        except Exception as e:
            log.warning("Hunt overlay failed: %s", e)

        try:
            from .overlay.progress_overlay import ProgressOverlay
            ProgressOverlay(
                config=config, config_path=config_path, event_bus=event_bus,
                manager=overlay_manager,
            )
        except Exception as e:
            log.warning("Progress overlay failed: %s", e)

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

        # Expose map overlay opener for detail overlay map buttons
        from .overlay import detail_overlay as _detail_overlay_mod
        _detail_overlay_mod._map_overlay_callback = _open_map_overlay_at

        # Detail overlay: opened when a search result is selected
        _current_detail_overlay = None
        _detail_overlays: list = []   # all open overlays (for offset stacking)

        def _on_overlay_result_selected(item):
            nonlocal _current_detail_overlay
            from .overlay.detail_overlay import DetailOverlayWidget, STACK_OFFSET

            # Close current unpinned overlay
            if _current_detail_overlay and not _current_detail_overlay.pinned:
                _current_detail_overlay.close()

            # Prune closed overlays from the list
            _detail_overlays[:] = [o for o in _detail_overlays if o.isVisible()]

            overlay = DetailOverlayWidget(
                item,
                config=config,
                config_path=config_path,
                data_client=data_client,
                manager=overlay_manager,
            )
            if config.auto_pin_detail_overlay:
                overlay.set_pinned(True)
            overlay.open_in_wiki.connect(main_window._on_search_result_selected)
            overlay.open_entity.connect(_on_overlay_result_selected)
            overlay.create_loadout.connect(lambda data: nexus_client.create_loadout(data))

            # Offset from existing open overlays so they don't perfectly stack
            if _detail_overlays:
                count = len(_detail_overlays)
                pos = overlay.pos()
                overlay.move(pos.x() + STACK_OFFSET * count, pos.y() + STACK_OFFSET * count)

            _detail_overlays.append(overlay)
            _current_detail_overlay = overlay

        if search_overlay:
            search_overlay.result_selected.connect(_on_overlay_result_selected)

        # Start legacy tkinter overlays in daemon threads (ScanOverlay only)
        _start_legacy_overlays(config, event_bus)

    QTimer.singleShot(0, _create_overlays)

    exit_code = app.exec()

    local_server.close()

    # Tear down system-wide hooks immediately so mouse/keyboard input
    # is no longer gated on the Python GIL during cleanup.
    overlay_manager.stop()

    # Hard deadline for remaining cleanup — daemon threads are killed
    # automatically on exit, so this only guards against blocking I/O.
    def force_exit():
        log.error("Shutdown timed out, forcing exit")
        os._exit(exit_code or 1)

    kill_timer = threading.Timer(3.0, force_exit)
    kill_timer.daemon = True
    kill_timer.start()

    nexus_client.close()
    data_client.close()
    _cleanup_workers(workers)
    db.close()
    kill_timer.cancel()
    sys.exit(exit_code)


def _show_splash(app, oauth, event_bus):
    """Show the splash screen and block until the user logs in or chooses offline."""
    from PyQt6.QtCore import QEventLoop, QMetaObject, Qt as QtNamespace
    from .core.constants import EVENT_AUTH_STATE_CHANGED
    from .ui.widgets.splash_screen import SplashScreen

    splash = SplashScreen()
    loop = QEventLoop()

    def on_login():
        splash.show_login_progress()

        def do_login():
            try:
                success = oauth.login()
                if not success:
                    splash._login_error.emit("Login failed — check logs for details")
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

    splash.hide()
    event_bus.unsubscribe(EVENT_AUTH_STATE_CHANGED, on_auth_changed)

    if closed:
        log.info("User closed splash — exiting")
        return True  # signal caller to exit

    log.warning("Auth: %s", "authenticated" if oauth.is_authenticated() else "offline")
    return False


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
    workers.extend(_start_hunt_tracker(config, event_bus, db, data_client))
    workers.extend(_start_hotkey_manager(config, event_bus))
    _start_legacy_overlays(config, event_bus)

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


def _start_ocr_pipeline(config, event_bus, db):
    """Start the OCR scan orchestrator. Returns list of stoppable workers."""
    workers = []
    try:
        from .ocr.orchestrator import ScanOrchestrator
        orchestrator = ScanOrchestrator(config, event_bus, db)
        log.info("OCR pipeline ready")

        def run_ocr():
            try:
                result = orchestrator.run_continuous()
                if result:
                    log.info("OCR finished: %d/%d skills",
                             result.total_found, result.total_expected)
                else:
                    log.info("OCR: skills window not found")
            except Exception as e:
                log.error("OCR error: %s", e)

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


def _start_legacy_overlays(config, event_bus):
    """Start tkinter-based overlays in daemon threads."""
    overlay_specs = [
        ("Scan overlay", "client.overlay.scan_overlay", "ScanOverlay", (event_bus,)),
    ]
    for name, module_path, class_name, init_args in overlay_specs:
        try:
            mod = __import__(module_path, fromlist=[class_name])
            cls = getattr(mod, class_name)
            overlay = cls(*init_args)
            overlay.start_background()
            log.info("%s started", name)
        except Exception as e:
            log.info("%s failed to start: %s", name, e)


def _cleanup_workers(workers):
    """Stop all workers that have a stop() method."""
    for worker in workers:
        try:
            worker.stop()
        except Exception as e:
            log.error("Error stopping %s: %s", worker.__class__.__name__, e)


def _run_batch_parse(config, event_bus, db):
    """Parse the entire chat.log file from current offset and exit."""
    from .chat_parser.watcher import ChatLogWatcher

    log.warning("Batch parsing: %s", config.chat_log_path)
    watcher = ChatLogWatcher(config, event_bus, db)
    watcher.parse_file()
    log.warning("Batch parse complete")


if __name__ == "__main__":
    main()
