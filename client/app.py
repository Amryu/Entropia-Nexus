"""Entropia Nexus Desktop Client - Entry Point.

Usage:
    python -m client              # Run with GUI
    python -m client --parse      # Batch parse existing chat.log, then exit
    python -m client --headless   # Run without GUI (chat watcher + OCR only)
    python -m client --config X   # Use custom config file
    python -m client --verbose    # Enable verbose logging
"""

import argparse
import os
import signal
import sys
import threading
import traceback

from .core.config import load_config
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
    args = parser.parse_args()

    init_logging(verbose=args.verbose)

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
        _run_gui(config, event_bus, db, args.config)


def _run_gui(config, event_bus, db, config_path):
    """Run the full GUI application with Qt event loop."""
    from PyQt6.QtWidgets import QApplication
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
    nexus_client = NexusClient(config, oauth)
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

    # Now start worker threads (safe — Qt platform integration is initialized)
    workers = []
    workers.extend(_start_chat_watcher(config, event_bus, db))
    # workers.extend(_start_ocr_pipeline(config, event_bus, db))  # disabled for debugging
    workers.extend(_start_hunt_tracker(config, event_bus, db, data_client))
    workers.extend(_start_hotkey_manager(config, event_bus))

    # Qt overlays (always-on-top, draggable, position persisted)
    try:
        from .overlay.hunt_overlay import HuntOverlay
        hunt_overlay = HuntOverlay(
            signals=signals, config=config, config_path=config_path,
        )
    except Exception as e:
        log.warning("Hunt overlay failed: %s", e)

    try:
        from .overlay.progress_overlay import ProgressOverlay
        progress_overlay = ProgressOverlay(
            config=config, config_path=config_path, event_bus=event_bus,
        )
    except Exception as e:
        log.warning("Progress overlay failed: %s", e)

    # Start legacy tkinter overlays in daemon threads (ScanOverlay only)
    _start_legacy_overlays(config, event_bus)

    exit_code = app.exec()

    # Cleanup — close HTTP sessions first to unblock any in-flight requests
    # on daemon threads, then stop workers.
    nexus_client.close()
    data_client.close()
    _cleanup_workers(workers)
    db.close()
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


def _start_chat_watcher(config, event_bus, db):
    """Start the chat log watcher. Returns list of stoppable workers."""
    workers = []
    try:
        from .chat_parser.watcher import ChatLogWatcher
        watcher = ChatLogWatcher(config, event_bus, db)
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
