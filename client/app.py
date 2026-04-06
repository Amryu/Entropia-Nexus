"""Entropia Nexus Desktop Client - Entry Point.

Usage:
    python -m client                  # Run with GUI
    python -m client --parse          # Batch parse existing chat.log, then exit
    python -m client --headless       # Run without GUI (chat watcher + OCR only)
    python -m client --config X       # Use custom config file
    python -m client --verbose        # Enable verbose logging
    python -m client --allow-multiple # Allow multiple instances
    python -m client --minimized      # Start minimized to system tray
"""

import argparse
import os
import signal
import sys
import threading
import time
import traceback

from .core.config import load_config
from .core.build_flags import is_dev_build
from .core.constants import (
    EVENT_AUTH_STATE_CHANGED,
    EVENT_CLIP_SAVED,
    EVENT_CONFIG_CHANGED,
    EVENT_MARKET_PRICE_SCAN,
    EVENT_OCR_MANUAL_TRIGGER,
    EVENT_SCREENSHOT_SAVED,
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
    parser.add_argument("--minimized", action="store_true", help="Start minimized to system tray")
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

    # Prune old data in background to avoid blocking startup
    def _background_prune():
        pruned = db.prune_old_data()
        if pruned:
            log.info("Pruned old data: %s", ", ".join(f"{t}: {n:,}" for t, n in pruned.items()))
            total = sum(pruned.values())
            if total > 10_000:
                log.info("Running VACUUM to reclaim disk space...")
                db.vacuum()
                log.info("VACUUM complete")

    threading.Thread(target=_background_prune, daemon=True, name="db-prune").start()

    # Batch parse mode
    if args.parse:
        _run_batch_parse(config, event_bus, db)
        db.close()
        return

    if args.headless:
        _run_headless(config, event_bus, db)
    else:
        _run_gui(config, event_bus, db, args.config,
                allow_multiple=args.allow_multiple,
                start_minimized=args.minimized or config.start_minimized)


_SINGLE_INSTANCE_SERVER_NAME = "EntropiaNexus-SingleInstance"


def _run_gui(config, event_bus, db, config_path, *, allow_multiple=False,
             start_minimized=False):
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
    _sigint_extras = {}  # populated later with objects that need stopping

    def _on_sigint(*_):
        nonlocal _sigint_count
        _sigint_count += 1
        if _sigint_count >= 2:
            os._exit(1)
        _start_shutdown_watchdog()
        # Stop workers and extras immediately — don't wait for app.exec()
        # to return, because on Windows it may never return after app.quit().
        def _signal_cleanup():
            fd = _sigint_extras.get("freeze_detector")
            if fd:
                fd.stop()
            mw = _sigint_extras.get("main_window")
            if mw:
                mw.cleanup()
            om = _sigint_extras.get("overlay_manager")
            if om:
                om.stop()
            _cleanup_workers(list(workers))
            db.close()
            # app.exec() may never return on Windows after app.quit(),
            # so force-exit once cleanup is done.
            os._exit(0)
        kill_timer = threading.Timer(5.0, lambda: os._exit(1))
        kill_timer.daemon = True
        kill_timer.start()
        threading.Thread(
            target=_signal_cleanup, daemon=True, name="signal-cleanup",
        ).start()
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
    app.setWindowIcon(nexus_logo_icon())

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

    # Launch loading splash in a separate process so it keeps animating
    # smoothly while the main process is blocked on heavy widget construction.
    # Skip the splash entirely when starting minimized — there's nothing to show.
    import subprocess
    _splash_proc = None
    if not start_minimized:
        try:
            splash_cmd = [sys.executable, "-m", "client.splash_loader"]
            # Pass saved screen center so the splash appears on the same monitor
            # the main window will use.
            sc = config.main_window_screen_center
            if sc and len(sc) >= 2:
                splash_cmd += ["--screen-center", str(int(sc[0])), str(int(sc[1]))]
            _splash_proc = subprocess.Popen(
                splash_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=os.path.dirname(os.path.dirname(__file__)),
            )
        except Exception as e:
            log.warning("Loading splash failed to start: %s", e)

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

    # Exchange stores — lightweight Python objects needed by the exchange page.
    # Must be assigned before prewarm_all_pages() creates the exchange page.
    from .exchange.exchange_store import ExchangeStore
    from .exchange.favourites_store import FavouritesStore
    _exchange_store = ExchangeStore(nexus_client, event_bus)
    _exchange_store.load_items()
    _favourites_store = FavouritesStore(nexus_client)
    main_window._exchange_store = _exchange_store
    main_window._favourites_store = _favourites_store
    main_window.connect_exchange_store(_exchange_store)

    # Build all pages synchronously while the loading splash covers the screen.
    main_window.prewarm_all_pages()

    # Load skills data synchronously during splash so the heavy card-widget
    # creation can happen before the user sees the main window.
    from .ui.main_window import PAGE_SKILLS
    _skills_page = main_window._pages.widget(PAGE_SKILLS)
    _skills_page.prewarm_data()

    # Overlay manager (focus detection, widget registry, snap) — lightweight,
    # needed before building overlay widgets below.
    from .overlay.overlay_manager import OverlayManager
    overlay_manager = OverlayManager(config=config, event_bus=event_bus)

    # Heavy overlay widgets — created lazily on first use.
    # See _ensure_*_overlay() in _create_overlays().
    _map_overlay = None
    _exchange_overlay = None
    _notifications_overlay = None
    _recording_bar = None
    _gallery_overlay = None
    _stream_overlay = None
    _custom_grid_overlays: dict = {}
    _grid_manager_dialog = None

    # Pre-import detail_overlay during splash — compiling this large module
    # takes ~0.6s and would freeze the main thread if deferred to _create_overlays.
    from .overlay import detail_overlay as _detail_overlay_mod  # noqa: F811

    # Overlay widgets and review dialog — created in _create_overlays() after
    # splash closes.  Declared here so the outer scope can reference them.
    _search_overlay = None
    _scan_summary = None

    if start_minimized:
        # Show briefly off-screen so Qt initialises native handles and
        # geometry, then immediately hide to tray.
        main_window.show()
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        _skills_page.flush_prewarm()
        main_window.hide()
        log.info("Started minimized to system tray")
    else:
        # Show the main window BEFORE closing the splash so Qt computes real
        # widget geometry.  The splash process has WindowStaysOnTopHint, so the
        # main window appears behind it and the user doesn't see anything yet.
        main_window.show()

        # If we came from the login splash, show the main window on the same monitor
        if splash_screen is not None:
            main_window.bring_to_front_on_screen(splash_screen)

        # Force Qt to process layout events so viewports have their real sizes.
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

        # Build deferred skill/profession grids synchronously.  This is the
        # expensive card-widget creation (~0.6s) that would otherwise freeze the
        # main thread after the splash closes.  The splash still covers the screen.
        _skills_page.flush_prewarm()

        # NOW close the loading splash — the main window is fully rendered.
        if _splash_proc is not None:
            try:
                _splash_proc.stdin.write(b"close\n")
                _splash_proc.stdin.flush()
                _splash_proc.wait(timeout=3)
            except Exception:
                _splash_proc.kill()
            _splash_proc = None

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
            signals.auth_state_changed.disconnect(_on_deauth)
            _show_splash_over_main(main_window, oauth, event_bus)

        signals.auth_state_changed.connect(_on_deauth)
        oauth.refresh_in_background()
    else:
        # Not authenticated — still re-emit so sidebar shows logged-out state
        event_bus.publish(EVENT_AUTH_STATE_CHANGED, oauth.auth_state)

    # Now start worker threads (safe — Qt platform integration is initialized)
    # Ingestion uploader must subscribe to EVENT_CATCHUP_COMPLETE BEFORE
    # the chat watcher starts its catchup thread, to avoid a race condition
    # where catchup finishes before the uploader exists.
    # Shared frame distributor — single capture thread pushes frames to all
    # OCR detectors at their declared rates (replaces SharedFrameCache).
    from .ocr.frame_distributor import FrameDistributor
    frame_distributor = FrameDistributor(capture_backend=config.ocr_capture_backend)

    def _sync_capture_settings(updated_config):
        if not updated_config:
            return
        frame_distributor.set_capture_backend(
            getattr(updated_config, "ocr_capture_backend", "auto"),
        )
        frame_distributor.set_hdr_mode(
            getattr(updated_config, "hdr_compatibility_mode", False),
        )

    event_bus.subscribe(EVENT_CONFIG_CHANGED, _sync_capture_settings)

    # Apply initial HDR mode from config
    frame_distributor.set_hdr_mode(getattr(config, "hdr_compatibility_mode", False))

    workers = []
    workers.extend(_start_ingestion(config, event_bus, nexus_client, db))
    workers.extend(_start_skill_data_collector(
        config, event_bus, nexus_client, db, config_path, oauth))
    # Hunt tracker must subscribe to EVENT_CATCHUP_COMPLETE before the chat
    # watcher starts, otherwise a fast catchup (empty log) can race ahead.
    if is_dev_build():
        workers.extend(_start_hunt_tracker(config, event_bus, db, data_client))
    workers.extend(_start_chat_watcher(config, event_bus, db, authenticated=oauth.is_authenticated(), data_client=data_client))
    workers.extend(_start_ocr_pipeline(config, event_bus, db, frame_distributor))
    workers.extend(_start_hotkey_manager(config, event_bus))
    workers.extend(_start_update_checker(config, event_bus))
    _tl_workers = _start_target_lock_detector(config, event_bus, frame_distributor)
    _ps_workers = _start_player_status_detector(config, event_bus, frame_distributor, data_client)
    _mp_workers = _start_market_price_detector(config, event_bus, frame_distributor, data_client)
    _mc_workers = _start_market_clipboard_monitor(config, event_bus)
    workers.extend(_tl_workers)
    workers.extend(_ps_workers)
    workers.extend(_mp_workers)
    workers.extend(_mc_workers)
    # workers.extend(_start_radar_detector(config, event_bus, frame_distributor, config_path))

    frame_distributor.start()
    workers.append(frame_distributor)

    # Wire config changes to start/stop detectors dynamically
    _detector_refs = {
        "target_lock": (_tl_workers[0] if _tl_workers else None,
                        "target_lock_enabled",
                        lambda: _start_target_lock_detector(config, event_bus, frame_distributor)),
        "player_status": (_ps_workers[0] if _ps_workers else None,
                          "player_status_enabled",
                          lambda: _start_player_status_detector(config, event_bus, frame_distributor, data_client)),
        "market_price": (_mp_workers[0] if _mp_workers else None,
                         "market_price_enabled",
                         lambda: _start_market_price_detector(config, event_bus, frame_distributor, data_client)),
        "market_clipboard": (_mc_workers[0] if _mc_workers else None,
                             "market_clipboard_enabled",
                             lambda: _start_market_clipboard_monitor(config, event_bus)),
    }

    def _on_detector_config_changed(new_config):
        nonlocal workers
        cfg = new_config if not callable(new_config) else config
        for key, (detector, cfg_field, factory) in list(_detector_refs.items()):
            enabled = getattr(cfg, cfg_field, False)
            if enabled and detector is None:
                # Start detector that wasn't running
                new_workers = factory()
                if new_workers:
                    workers.extend(new_workers)
                    _detector_refs[key] = (new_workers[0], cfg_field, factory)
                    log.info("Started %s detector (config toggled on)", key)
            elif not enabled and detector is not None:
                # Stop running detector
                try:
                    detector.stop()
                    log.info("Stopped %s detector (config toggled off)", key)
                except Exception as e:
                    log.error("Failed to stop %s detector: %s", key, e)
                _detector_refs[key] = (None, cfg_field, factory)

    event_bus.subscribe(EVENT_CONFIG_CHANGED, _on_detector_config_changed)

    # Expose on main_window so dialogs can discover it via topLevelWidgets()
    main_window._frame_distributor = frame_distributor

    # Capture manager — screenshot and video clip recording
    from .capture.capture_manager import CaptureManager
    capture_manager = CaptureManager(
        config=config, event_bus=event_bus,
        frame_distributor=frame_distributor, oauth=oauth,
    )
    capture_manager.start()
    workers.append(capture_manager)

    # Register screenshots/clips in the local database
    def _on_capture_saved(data):
        from .core.database import compute_file_hash
        file_type = "clip" if "duration" in data else "screenshot"
        path = data.get("path", "")
        ts = data.get("timestamp", "")
        ge = data.get("global_event")
        global_id = None
        if ge:
            global_id = db.find_recent_own_global(
                ts or ge.get("timestamp", ""),
                ge["player_name"], ge["target_name"],
            )
        # Compute hash for screenshots inline (small files).
        # For clips, compute in a background thread (large files).
        if file_type == "clip":
            row_id = db.insert_screenshot(path, file_type, ts, global_id)
            import threading
            def _hash_clip():
                fh = compute_file_hash(path)
                if fh and row_id:
                    db.update_screenshot_hash(row_id, fh)
            threading.Thread(target=_hash_clip, daemon=True,
                             name="clip-hash").start()
        else:
            fh = compute_file_hash(path)
            db.insert_screenshot(path, file_type, ts, global_id,
                                 file_hash=fh)

    event_bus.subscribe(EVENT_SCREENSHOT_SAVED, _on_capture_saved)
    event_bus.subscribe(EVENT_CLIP_SAVED, _on_capture_saved)

    # Defer overlay wiring so the main window renders first.
    # Heavy overlay widgets are created lazily on first use via _ensure_*_overlay().
    def _create_overlays():
        nonlocal _search_overlay, _scan_summary

        # Toast manager (lightweight widget)
        from .overlay.toast_widget import ToastManager
        toast_manager = ToastManager(config=config)
        main_window.set_overlay_manager(overlay_manager)
        main_window.set_toast_manager(toast_manager)
        overlay_manager.game_focus_changed.connect(toast_manager.set_visible)

        # Search overlay
        try:
            from .overlay.search_overlay import SearchOverlayWidget
            _search_overlay = SearchOverlayWidget(
                config=config, config_path=config_path,
                data_client=data_client, manager=overlay_manager,
            )
        except Exception as e:
            log.warning("Search overlay failed: %s", e)

        # Scan summary overlay
        try:
            from .overlay.scan_summary_overlay import ScanSummaryOverlay
            from .ui.main_window import PAGE_SKILLS

            def _get_skill_values():
                if PAGE_SKILLS in main_window._page_created:
                    page = main_window._pages.widget(PAGE_SKILLS)
                    return page._manager.get_all_values()
                return {}

            _scan_summary = ScanSummaryOverlay(
                config=config, config_path=config_path,
                event_bus=event_bus, manager=overlay_manager,
                skill_values_fn=_get_skill_values,
            )
            overlay_manager._scan_summary = _scan_summary
        except Exception as e:
            log.warning("Scan summary overlay failed: %s", e)

        # --- Lazy overlay factories ---

        def _ensure_map_overlay():
            nonlocal _map_overlay
            if _map_overlay is not None:
                return _map_overlay
            from .overlay.map_overlay import MapOverlay
            _map_overlay = MapOverlay(
                config=config, config_path=config_path,
                data_client=data_client, manager=overlay_manager,
            )
            return _map_overlay

        def _ensure_exchange_overlay():
            nonlocal _exchange_overlay
            if _exchange_overlay is not None:
                return _exchange_overlay
            from .overlay.exchange_overlay import ExchangeOverlay
            _exchange_overlay = ExchangeOverlay(
                config=config, config_path=config_path,
                store=_exchange_store, favourites=_favourites_store,
                manager=overlay_manager,
            )
            _exchange_overlay.open_entity.connect(_on_overlay_result_selected)
            return _exchange_overlay

        def _ensure_notifications_overlay():
            nonlocal _notifications_overlay
            if _notifications_overlay is not None:
                return _notifications_overlay
            from .overlay.notifications_overlay import NotificationsOverlay
            _notifications_overlay = NotificationsOverlay(
                config=config, config_path=config_path,
                notif_manager=main_window._notif_manager,
                manager=overlay_manager,
            )
            _notifications_overlay.read_state_changed.connect(
                main_window._update_badge
            )
            return _notifications_overlay

        # --- Toggle functions ---

        def _toggle_map_overlay():
            overlay = _ensure_map_overlay()
            if not overlay.isVisible():
                overlay.set_wants_visible(True)
                overlay.raise_()
            else:
                overlay.set_wants_visible(False)

        def _open_map_overlay_at(planet_name: str, location_id: int):
            _ensure_map_overlay().open_at_location(planet_name, location_id)

        def _toggle_exchange_overlay():
            overlay = _ensure_exchange_overlay()
            if not overlay.isVisible():
                overlay.set_wants_visible(True)
                overlay.raise_()
            else:
                overlay.set_wants_visible(False)

        def _toggle_notifications_overlay():
            overlay = _ensure_notifications_overlay()
            if not overlay.isVisible():
                overlay.set_wants_visible(True)
                overlay.raise_()
            else:
                overlay.set_wants_visible(False)

        def _ensure_recording_bar():
            nonlocal _recording_bar
            if _recording_bar is not None:
                return _recording_bar
            from .overlay.recording_bar_overlay import RecordingBarOverlay
            _recording_bar = RecordingBarOverlay(
                config=config, config_path=config_path,
                event_bus=event_bus, signals=signals,
                capture_manager=capture_manager,
                manager=overlay_manager,
            )
            _recording_bar.open_settings.connect(
                main_window.open_video_settings
            )
            _recording_bar.open_gallery.connect(_toggle_gallery_overlay)
            return _recording_bar

        def _ensure_gallery_overlay():
            nonlocal _gallery_overlay
            if _gallery_overlay is not None:
                return _gallery_overlay
            from .overlay.gallery_overlay import GalleryOverlay
            _gallery_overlay = GalleryOverlay(
                config=config, config_path=config_path,
                signals=signals, manager=overlay_manager,
                db=db, nexus_client=nexus_client,
            )
            return _gallery_overlay

        def _ensure_stream_overlay():
            nonlocal _stream_overlay
            if _stream_overlay is not None:
                return _stream_overlay
            from .overlay.stream_overlay import StreamOverlay
            _stream_overlay = StreamOverlay(
                config=config, config_path=config_path,
                nexus_client=nexus_client, manager=overlay_manager,
            )
            return _stream_overlay

        # Hunt overlay — auto-shows on session start, hidden otherwise (dev only).
        if is_dev_build():
            from .overlay.hunt_overlay import HuntOverlay
            _hunt_overlay = HuntOverlay(
                signals=signals, config=config, config_path=config_path,
                manager=overlay_manager,
            )

        def _ensure_custom_grid(grid_id: str):
            """Return (and lazily create) the overlay instance for grid_id."""
            nonlocal _custom_grid_overlays
            if grid_id in _custom_grid_overlays:
                return _custom_grid_overlays[grid_id]
            from .overlay.custom_grid_overlay import CustomGridOverlay
            overlay = CustomGridOverlay(
                grid_id=grid_id,
                config=config, config_path=config_path,
                event_bus=event_bus,
                data_client=data_client,
                exchange_store=_exchange_store,
                hunt_tracker=None,
                manager=overlay_manager,
            )
            _custom_grid_overlays[grid_id] = overlay
            return overlay

        def _delete_custom_grid(grid_id: str) -> None:
            nonlocal _custom_grid_overlays
            overlay = _custom_grid_overlays.pop(grid_id, None)
            if overlay is not None:
                overlay.set_wants_visible(False)
                try:
                    for slot in list(overlay._grid_canvas._slots):
                        slot.grid_widget.teardown()
                except Exception:
                    pass
                overlay.close()
            config.custom_grids = [g for g in config.custom_grids if g.get("id") != grid_id]
            from .core.config import save_config
            save_config(config, config_path)

        def _toggle_custom_grid_overlay():
            nonlocal _grid_manager_dialog
            from .overlay.custom_grid.grid_manager_dialog import CustomGridManagerDialog
            from .core.config import save_config as _save_config
            if _grid_manager_dialog is not None and _grid_manager_dialog.isVisible():
                _grid_manager_dialog.raise_()
                _grid_manager_dialog.activateWindow()
                return
            _grid_manager_dialog = CustomGridManagerDialog(
                config=config,
                save_fn=lambda: _save_config(config, config_path),
                parent=None,
            )
            def _on_open(grid_id: str):
                overlay = _ensure_custom_grid(grid_id)
                overlay.set_wants_visible(True)
                overlay.raise_()
                _grid_manager_dialog._refresh_rows()
            def _on_close(grid_id: str):
                overlay = _custom_grid_overlays.get(grid_id)
                if overlay:
                    overlay.set_wants_visible(False)
                _grid_manager_dialog._refresh_rows()
            def _on_delete(grid_id: str):
                _delete_custom_grid(grid_id)
                _grid_manager_dialog._refresh_rows()
            def _on_rename(grid_id: str, name: str):
                overlay = _custom_grid_overlays.get(grid_id)
                if overlay:
                    overlay.rename(name)
            def _on_open_status(grid_id: str) -> bool:
                ov = _custom_grid_overlays.get(grid_id)
                return ov is not None and ov.wants_visible
            _grid_manager_dialog.open_grid.connect(_on_open)
            _grid_manager_dialog.close_grid.connect(_on_close)
            _grid_manager_dialog.grid_deleted.connect(_on_delete)
            _grid_manager_dialog.grid_renamed.connect(_on_rename)
            _grid_manager_dialog._is_open_fn = _on_open_status
            _grid_manager_dialog._refresh_rows()
            _grid_manager_dialog.show()

        def _toggle_recording_bar():
            overlay = _ensure_recording_bar()
            if not overlay.isVisible():
                overlay.set_wants_visible(True)
                overlay.raise_()
            else:
                overlay.set_wants_visible(False)

        def _toggle_gallery_overlay():
            overlay = _ensure_gallery_overlay()
            if not overlay.isVisible():
                overlay.set_wants_visible(True)
                overlay.raise_()
            else:
                overlay.set_wants_visible(False)

        def _toggle_stream_overlay():
            overlay = _ensure_stream_overlay()
            if not overlay.isVisible():
                overlay.set_wants_visible(True)
                overlay.raise_()
            else:
                overlay.set_wants_visible(False)

        # Auto-show recording bar when recording starts
        def _auto_show_recording_bar(data):
            bar = _ensure_recording_bar()
            if not bar.isVisible():
                bar.set_wants_visible(True)
                bar.raise_()
        signals.recording_started.connect(_auto_show_recording_bar)

        overlay_manager.map_hotkey_pressed.connect(_toggle_map_overlay)
        overlay_manager.exchange_hotkey_pressed.connect(_toggle_exchange_overlay)
        overlay_manager.notifications_hotkey_pressed.connect(
            _toggle_notifications_overlay
        )
        overlay_manager.recording_bar_hotkey_pressed.connect(_toggle_recording_bar)
        overlay_manager.gallery_hotkey_pressed.connect(_toggle_gallery_overlay)

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
                elif action_data == "streams":
                    _toggle_stream_overlay()

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

            # Route MobMaturity → open parent mob detail overlay
            if item.get("Type") == "MobMaturity":
                mob_name = item.get("MobName") or item.get("Name", "")
                item = {"Type": "Mob", "Name": mob_name}
                if force_new:
                    item["_force_new"] = True

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
                    overlay = _ensure_exchange_overlay()
                    overlay.set_wants_visible(True)
                    overlay.raise_()
                    overlay.navigate_to_order_book(item_id)

                overlay.open_exchange.connect(_open_exchange_orderbook)
                _current_profile_overlay = overlay
                return

            # Route Map type to map overlay
            if item.get("Type") == "Map":
                import re
                overlay = _ensure_map_overlay()
                overlay._ensure_expanded()
                overlay.set_wants_visible(True)
                overlay.raise_()
                slug = re.sub(r'[^0-9a-zA-Z]', '', item.get("Name", "")).lower()
                overlay.navigate_to_planet(slug)
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

        if _search_overlay:
            _search_overlay.result_selected.connect(_on_overlay_result_selected)

            # Logo click — focus client on the overlay's monitor
            from PyQt6.QtWidgets import QApplication
            _search_overlay.logo_clicked.connect(
                lambda: main_window.bring_to_front_on_screen(
                    QApplication.screenAt(_search_overlay.geometry().center())
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
                elif action == "recording":
                    _toggle_recording_bar()
                elif action == "gallery":
                    _toggle_gallery_overlay()
                elif action == "custom_grid":
                    _toggle_custom_grid_overlay()
                elif action == "streams":
                    _toggle_stream_overlay()

            _search_overlay.menu_action.connect(_on_search_menu_action)

            # Notification badge on logo
            main_window.set_search_overlay(_search_overlay)

        def _create_scan_overlays():
            # Scan highlight overlay
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

            # Scan summary overlay signal wiring (widget built during splash)
            if _scan_summary is not None:
                from .ui.main_window import PAGE_SKILLS

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
                                name="skill-sync",
                            ).start()
                        )
                        dialog.set_wants_visible(True)
                    else:
                        threading.Thread(target=do_sync, daemon=True, name="skill-sync").start()

                _scan_summary.scan_marked_complete.connect(
                    _on_scan_marked_complete
                )
                _scan_summary.scan_entries_cleared.connect(
                    _clear_scan_selection
                )

        # Scan highlight overlay (click-through, shows scanned rows + target lock)
        _create_scan_overlays()

        # All overlay wiring is complete — start the focus-detection timer.
        # This is deferred from OverlayManager.__init__ to avoid showing
        # overlay HWNDs (with a possible bordered-window flash) during the
        # splash phase.
        overlay_manager.start_focus_polling()

    QTimer.singleShot(0, _create_overlays)

    # Freeze detector — monitors main thread responsiveness.
    # Pages are already prewarmed before show(), so arm immediately.
    from .core.freeze_detector import FreezeDetector
    freeze_detector = FreezeDetector()
    freeze_detector.start()
    freeze_detector.arm()
    _sigint_extras.update(
        freeze_detector=freeze_detector,
        main_window=main_window,
        overlay_manager=overlay_manager,
    )

    exit_code = app.exec()

    # Hard deadline — start BEFORE any cleanup so a blocking stop()
    # (e.g. keyboard library lock contention) can never hang the process.
    def force_exit():
        log.error("Shutdown timed out, forcing exit")
        os._exit(exit_code or 1)

    kill_timer = threading.Timer(5.0, force_exit)
    kill_timer.daemon = True
    kill_timer.start()
    _start_shutdown_watchdog()

    freeze_detector.stop()
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

        threading.Thread(target=do_login, daemon=True, name="oauth-login").start()

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

    log.info("Auth: %s", "authenticated" if oauth.is_authenticated() else "offline")
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

        threading.Thread(target=do_login, daemon=True, name="oauth-relogin").start()

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

    log.info("Splash dismissed — auth: %s",
                "authenticated" if oauth.is_authenticated() else "offline")


def _run_headless(config, event_bus, db):
    """Run without GUI — chat watcher + OCR only (original behavior)."""
    from .api.data_client import DataClient

    shutdown_event = threading.Event()

    def on_signal(signum, frame):
        _start_shutdown_watchdog()
        # Stop workers immediately so background threads don't keep running
        # while the main loop is still draining.
        threading.Thread(
            target=_cleanup_workers, args=(list(workers),),
            daemon=True, name="signal-cleanup",
        ).start()
        shutdown_event.set()

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    data_client = DataClient(config)

    workers = []
    if is_dev_build():
        workers.extend(_start_hunt_tracker(config, event_bus, db, data_client))
    workers.extend(_start_chat_watcher(config, event_bus, db, data_client=data_client))
    workers.extend(_start_ocr_pipeline(config, event_bus, db))
    workers.extend(_start_hotkey_manager(config, event_bus))

    log.info("Running headless... Press Ctrl+C to stop.")
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

    log.info("Shutting down...")
    _start_shutdown_watchdog()
    data_client.close()
    _cleanup_workers(workers)
    db.close()
    kill_timer.cancel()
    log.info("Goodbye")


def _start_chat_watcher(config, event_bus, db, *, authenticated=False, data_client=None):
    """Start the chat log watcher. Returns list of stoppable workers."""
    workers = []
    try:
        from .chat_parser.watcher import ChatLogWatcher
        from .hunt.entity_resolver import EntityResolver

        watcher = ChatLogWatcher(config, event_bus, db, authenticated=authenticated)

        # Wire item ID resolver so loot_events can store IDs instead of names
        resolver = EntityResolver(data_client)
        resolver.warmup()
        watcher.set_item_resolver(resolver.resolve_item)

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
            if orchestrator._current_window_bounds is not None:
                # Monitor loop is active — request a re-scan of the current
                # page without tearing down and restarting the pipeline.
                orchestrator._rescan_requested.set()
            else:
                # No active monitor loop — wake the OCR thread to start
                # a fresh scan (e.g. manual mode first trigger).
                orchestrator._stop_event.set()
                manual_trigger.set()

        def _on_config_changed(_data=None):
            orchestrator.set_capture_backend(
                getattr(config, "ocr_capture_backend", "auto"),
            )
            orchestrator.set_trace_enabled(
                getattr(config, "ocr_trace_enabled", False),
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
    except Exception:
        log.exception("Hunt tracker failed to start")
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


def _start_player_status_detector(config, event_bus, frame_cache=None, data_client=None):
    """Start the player status (heart) detector. Returns list of stoppable workers."""
    workers = []
    if not getattr(config, "player_status_enabled", True):
        return workers
    try:
        from .ocr.player_status_detector import PlayerStatusDetector
        if frame_cache is None:
            from .ocr.capturer import ScreenCapturer
            frame_cache = ScreenCapturer(capture_backend=config.ocr_capture_backend)
        detector = PlayerStatusDetector(config, event_bus, frame_cache, data_client=data_client)
        detector.start()
        workers.append(detector)
        log.info("Player status detector started")
    except Exception as e:
        log.error("Player status detector failed to start: %s", e)
    return workers


def _start_market_price_detector(config, event_bus, frame_cache=None, data_client=None):
    """Start the market price detector. Returns list of stoppable workers."""
    workers = []
    if not getattr(config, "market_price_enabled", True):
        return workers
    try:
        from .ocr.market_price_detector import MarketPriceDetector
        if frame_cache is None:
            from .ocr.capturer import ScreenCapturer
            frame_cache = ScreenCapturer(capture_backend=config.ocr_capture_backend)
        detector = MarketPriceDetector(config, event_bus, frame_cache, data_client)
        if getattr(config, "ocr_trace_enabled", False):
            from .ocr.trace import OcrTracer
            tracer = OcrTracer()
            tracer.set_enabled(True)
            detector.set_tracer(tracer)
        detector.start()
        workers.append(detector)
        log.info("Market price detector started")
    except Exception as e:
        log.error("Market price detector failed to start: %s", e)
    return workers


def _start_market_clipboard_monitor(config, event_bus):
    """Start the clipboard monitor for copied market data. Returns list of stoppable workers."""
    workers = []
    if not getattr(config, "market_clipboard_enabled", True):
        return workers
    try:
        from .ocr.market_clipboard import MarketClipboardMonitor
        monitor = MarketClipboardMonitor(event_bus)
        monitor.start()
        workers.append(monitor)
    except Exception as e:
        log.error("Market clipboard monitor failed to start: %s", e)
    return workers


def _radar_feature_enabled(config) -> bool:
    """Radar OCR is a dev-only feature, with an additional runtime toggle."""
    return is_dev_build() and getattr(config, "radar_enabled", True)


def _start_radar_detector(config, event_bus, frame_cache=None, config_path="config.json"):
    """Start the radar coordinate detector. Returns list of stoppable workers."""
    workers = []
    if not _radar_feature_enabled(config):
        if not is_dev_build():
            log.info("Radar detector disabled in production builds")
        return workers
    try:
        from .ocr.radar_detector import RadarDetector
        if frame_cache is None:
            from .ocr.capturer import ScreenCapturer
            frame_cache = ScreenCapturer(capture_backend=config.ocr_capture_backend)
        detector = RadarDetector(config, event_bus, frame_cache, config_path=config_path)
        detector.start()
        workers.append(detector)
        log.info("Radar detector started")
    except Exception as e:
        log.error("Radar detector failed to start: %s", e)
    return workers


def _start_skill_data_collector(config, event_bus, nexus_client, db, config_path, oauth):
    """Start the anonymized skill data collector. Returns list of stoppable workers."""
    try:
        from .skills.skill_data_collector import SkillDataCollector
        collector = SkillDataCollector(
            event_bus=event_bus, nexus_client=nexus_client,
            config=config, db=db, config_path=config_path, oauth=oauth,
        )
        collector.start()
        return [collector]
    except Exception as e:
        log.error("Skill data collector failed to start: %s", e)
        return []


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


_shutdown_watchdog_started = False


def _start_shutdown_watchdog():
    """Log threads that are still running during shutdown.

    Takes a snapshot of all threads (except main and itself) at call time,
    then periodically logs which of those are still alive.  Safe to call
    multiple times — only the first call has any effect.
    """
    global _shutdown_watchdog_started
    if _shutdown_watchdog_started:
        return
    _shutdown_watchdog_started = True

    main = threading.main_thread()
    # Snapshot threads that exist right now — these are the ones we expect
    # to wind down during shutdown.  Threads spawned later (stop-worker,
    # force-exit timer) are not our concern.
    watched = [
        t for t in threading.enumerate()
        if t is not main and t.name != "shutdown-watchdog"
    ]
    if not watched:
        return

    def _watch():
        while True:
            time.sleep(2)
            alive = [t for t in watched if t.is_alive()]
            if not alive:
                return
            names = ", ".join(t.name for t in alive)
            log.warning("Shutdown watchdog: still running: %s", names)

    threading.Thread(target=_watch, daemon=True, name="shutdown-watchdog").start()


def _cleanup_workers(workers):
    """Stop all workers in parallel to minimize total shutdown time."""
    threads = []
    for worker in workers:
        def _stop(w=worker):
            try:
                w.stop()
            except Exception as e:
                log.error("Error stopping %s: %s", w.__class__.__name__, e)
        t = threading.Thread(target=_stop, daemon=True, name="stop-worker")
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

    log.info("Batch parsing: %s", config.chat_log_path)
    watcher = ChatLogWatcher(config, event_bus, db)
    watcher.parse_file()
    log.info("Batch parse complete")


if __name__ == "__main__":
    main()
