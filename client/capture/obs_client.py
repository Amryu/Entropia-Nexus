"""OBS Studio WebSocket client — delegates capture to OBS via obs-websocket v5.

Handles connection lifecycle, automatic reconnection with exponential backoff,
and request dispatching.  Publishes events via the shared EventBus so the rest
of the application (recording bar, gallery, settings) reacts identically to
internal-capture events.

Requires ``obsws-python >= 1.6`` (lazy-imported so the app still works without it).
"""

import threading
import time
from ..core.constants import (
    EVENT_CAPTURE_ERROR,
    EVENT_CLIP_ENCODING_STARTED,
    EVENT_CLIP_SAVED,
    EVENT_OBS_CONNECTED,
    EVENT_OBS_DISCONNECTED,
    EVENT_OBS_ERROR,
    EVENT_RECORDING_STARTED,
    EVENT_RECORDING_STOPPED,
)
from ..core.logger import get_logger

log = get_logger("OBSClient")

# Keyring constants (shared with token_store)
_SERVICE_NAME = "EntropiaNexusClient"
_OBS_PASSWORD_KEY = "obs_password"

# Reconnection backoff
_RECONNECT_MIN_S = 2
_RECONNECT_MAX_S = 30


def _is_request_error(exc: Exception) -> bool:
    """Return True if *exc* is an OBS SDK request error (not a connection loss)."""
    return "returned code" in str(exc).lower()


def _read_obs_password() -> str:
    """Read the OBS password from the system keyring (best-effort)."""
    try:
        import keyring
        return keyring.get_password(_SERVICE_NAME, _OBS_PASSWORD_KEY) or ""
    except Exception:
        return ""


def save_obs_password(password: str) -> None:
    """Persist *password* to the system keyring, or delete if empty."""
    try:
        import keyring
        if password:
            keyring.set_password(_SERVICE_NAME, _OBS_PASSWORD_KEY, password)
        else:
            try:
                keyring.delete_password(_SERVICE_NAME, _OBS_PASSWORD_KEY)
            except Exception:
                pass
    except Exception as exc:
        log.warning("Could not save OBS password to keyring: %s", exc)


class OBSClient:
    """Thin wrapper around *obsws-python* for the Entropia Nexus client.

    All public methods are safe to call from any thread.  Heavy work (connect,
    reconnect) runs on daemon threads.  The ``EventClient`` callback also fires
    on its own background thread — all downstream communication goes through
    ``event_bus.publish()`` which is thread-safe.
    """

    def __init__(self, *, event_bus, config):
        self._event_bus = event_bus
        self._config = config

        self._req = None        # obsws_python.ReqClient
        self._evt = None        # obsws_python.EventClient
        self._connected = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._reconnect_thread: threading.Thread | None = None

        # Track pending global events for replay buffer saves.
        # OBS processes replay saves sequentially so a simple queue suffices.
        self._pending_globals: list[dict | None] = []
        self._pending_lock = threading.Lock()

        # Local state caches (avoids round-trips on every query)
        self._recording = False
        self._replay_buffer_active = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """Try to connect to OBS.  Returns True on success.

        On failure, starts the background reconnection loop and returns False.
        """
        try:
            import obsws_python as obsws
        except ImportError:
            log.warning("obsws-python is not installed — OBS integration unavailable")
            self._event_bus.publish(EVENT_OBS_ERROR, {
                "error": "obsws-python library not installed. "
                         "Install with: pip install obsws-python",
            })
            return False

        host = self._config.obs_host or "localhost"
        port = self._config.obs_port or 4455
        password = _read_obs_password()

        try:
            req = obsws.ReqClient(
                host=host, port=port, password=password, timeout=5,
            )
        except Exception as exc:
            log.warning("OBS connection failed (%s:%d): %s", host, port, exc)
            self._event_bus.publish(EVENT_OBS_ERROR, {
                "error": f"Cannot connect to OBS at {host}:{port} — {exc}",
            })
            self._start_reconnect_loop()
            return False

        # Connection OK — set up the event listener.
        # obsws-python matches callbacks by function name (on_<snake_event>),
        # so we use named wrappers instead of bound methods with a _ prefix.
        def on_replay_buffer_saved(event):
            self._handle_replay_buffer_saved(event)

        def on_replay_buffer_state_changed(event):
            self._handle_replay_buffer_state_changed(event)

        def on_record_state_changed(event):
            self._handle_record_state_changed(event)

        try:
            evt = obsws.EventClient(
                host=host, port=port, password=password,
            )
            evt.callback.register([
                on_replay_buffer_saved,
                on_replay_buffer_state_changed,
                on_record_state_changed,
            ])
        except Exception as exc:
            log.warning("OBS event client failed: %s", exc)
            try:
                req.disconnect()
            except Exception:
                pass
            self._start_reconnect_loop()
            return False

        with self._lock:
            self._req = req
            self._evt = evt
            self._connected = True

        # Set recording directory so OBS saves where the user expects
        clip_dir = self._config.clip_directory
        if clip_dir:
            try:
                req.set_record_directory(clip_dir)
            except Exception as exc:
                log.debug("Could not set OBS record directory: %s", exc)

        # Sync local state caches with OBS
        self._sync_state(req)

        log.info("Connected to OBS at %s:%d", host, port)
        self._event_bus.publish(EVENT_OBS_CONNECTED, {
            "host": host, "port": port,
        })
        return True

    def disconnect(self) -> None:
        """Cleanly disconnect from OBS."""
        self._stop_event.set()

        with self._lock:
            req, evt = self._req, self._evt
            self._req = None
            self._evt = None
            self._connected = False

        for client in (evt, req):
            if client is not None:
                try:
                    client.disconnect()
                except Exception:
                    pass

        self._event_bus.publish(EVENT_OBS_DISCONNECTED, {"reason": "client stopped"})
        log.info("Disconnected from OBS")

    def _mark_disconnected(self, reason: str) -> None:
        """Mark as disconnected and start reconnection (called on errors)."""
        was_connected = False
        with self._lock:
            if self._connected:
                was_connected = True
                self._connected = False
                # Try to close stale clients
                for client in (self._evt, self._req):
                    if client is not None:
                        try:
                            client.disconnect()
                        except Exception:
                            pass
                self._req = None
                self._evt = None

        if was_connected:
            log.warning("OBS connection lost: %s", reason)
            self._event_bus.publish(EVENT_OBS_DISCONNECTED, {"reason": reason})
            self._start_reconnect_loop()

    def _start_reconnect_loop(self) -> None:
        """Start a background reconnection loop (if not already running)."""
        if self._stop_event.is_set():
            return
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            return

        self._reconnect_thread = threading.Thread(
            target=self._reconnect_loop, daemon=True, name="obs-reconnect",
        )
        self._reconnect_thread.start()

    def _reconnect_loop(self) -> None:
        delay = _RECONNECT_MIN_S
        while not self._stop_event.is_set():
            self._stop_event.wait(delay)
            if self._stop_event.is_set():
                break
            if self.connect():
                return  # success
            delay = min(delay * 2, _RECONNECT_MAX_S)

    # ------------------------------------------------------------------
    # State sync (called on connect)
    # ------------------------------------------------------------------

    def _sync_state(self, req) -> None:
        """Query OBS for current recording / replay buffer state."""
        try:
            resp = req.get_record_status()
            self._recording = getattr(resp, "output_active", False)
        except Exception:
            self._recording = False

        try:
            resp = req.get_replay_buffer_status()
            self._replay_buffer_active = getattr(resp, "output_active", False)
        except Exception:
            self._replay_buffer_active = False

        log.info("OBS state synced: recording=%s, replay_buffer=%s",
                 self._recording, self._replay_buffer_active)

    # ------------------------------------------------------------------
    # Replay buffer lifecycle
    # ------------------------------------------------------------------

    @property
    def replay_buffer_active(self) -> bool:
        return self._replay_buffer_active

    def start_replay_buffer(self) -> bool:
        """Start the OBS replay buffer."""
        with self._lock:
            req = self._req
        if not req or not self._connected:
            return False

        if self._replay_buffer_active:
            return True  # already running

        try:
            req.start_replay_buffer()
        except Exception as exc:
            if _is_request_error(exc):
                log.debug("Replay buffer start rejected: %s", exc)
            else:
                self._mark_disconnected(str(exc))
            return False

        self._replay_buffer_active = True
        log.info("OBS replay buffer started")
        return True

    def stop_replay_buffer(self) -> bool:
        """Stop the OBS replay buffer."""
        with self._lock:
            req = self._req
        if not req or not self._connected:
            return False

        if not self._replay_buffer_active:
            return True  # already stopped

        try:
            req.stop_replay_buffer()
        except Exception as exc:
            if _is_request_error(exc):
                self._replay_buffer_active = False
            else:
                self._mark_disconnected(str(exc))
            return False

        self._replay_buffer_active = False
        log.info("OBS replay buffer stopped")
        return True

    def _handle_replay_buffer_state_changed(self, event) -> None:
        """Track replay buffer state from OBS events."""
        active = getattr(event, "output_active", None)
        if active is not None:
            self._replay_buffer_active = active

    # ------------------------------------------------------------------
    # Replay buffer (clip saves)
    # ------------------------------------------------------------------

    def save_replay_buffer(self, *, global_event: dict | None = None) -> bool:
        """Trigger an OBS replay buffer save.

        *global_event* (if given) is attached to the resulting
        ``EVENT_CLIP_SAVED`` so the gallery can display context.
        """
        with self._lock:
            req = self._req
        if not req or not self._connected:
            self._event_bus.publish(EVENT_CAPTURE_ERROR, {
                "error": "OBS not connected — clip not saved",
            })
            return False

        if not self._replay_buffer_active:
            self._event_bus.publish(EVENT_OBS_ERROR, {
                "error": "Replay Buffer is not active in OBS. "
                         "Enable it in OBS → Settings → Output → Replay Buffer.",
            })
            return False

        try:
            req.save_replay_buffer()
        except Exception as exc:
            err = str(exc)
            if _is_request_error(exc):
                self._replay_buffer_active = False
                msg = ("Replay Buffer is not active in OBS. "
                       "Enable it in OBS → Settings → Output → Replay Buffer.")
            else:
                msg = f"OBS replay buffer save failed: {err}"
                self._mark_disconnected(err)
            self._event_bus.publish(EVENT_OBS_ERROR, {"error": msg})
            return False

        with self._pending_lock:
            self._pending_globals.append(global_event)

        # Publish encoding-started so the UI shows the progress placeholder
        self._event_bus.publish(EVENT_CLIP_ENCODING_STARTED, {
            "path": "", "frames": 0, "obs": True,
        })
        return True

    def _handle_replay_buffer_saved(self, _event) -> None:
        """Called by obsws EventClient when OBS finishes saving the replay."""
        path = ""
        with self._lock:
            req = self._req
        if req:
            try:
                resp = req.get_last_replay_buffer_replay()
                path = getattr(resp, "saved_replay_path", "") or ""
            except Exception as exc:
                log.debug("Could not get last replay path: %s", exc)

        # Pop the corresponding global_event
        global_event = None
        with self._pending_lock:
            if self._pending_globals:
                global_event = self._pending_globals.pop(0)

        self._event_bus.publish(EVENT_CLIP_SAVED, {
            "path": path,
            "timestamp": time.strftime("%Y-%m-%d_%H-%M-%S"),
            "duration": 0,
            "frames": 0,
            "obs": True,
            "global_event": global_event,
        })
        log.info("OBS replay saved: %s", path)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def start_record(self) -> bool:
        with self._lock:
            req = self._req
        if not req or not self._connected:
            self._event_bus.publish(EVENT_CAPTURE_ERROR, {
                "error": "OBS not connected — cannot start recording",
            })
            return False

        if self._recording:
            return True  # already recording

        try:
            req.start_record()
        except Exception as exc:
            err = str(exc)
            self._event_bus.publish(EVENT_OBS_ERROR, {
                "error": f"OBS start recording failed: {err}",
            })
            if _is_request_error(exc):
                self._recording = True  # OBS says already recording
            else:
                self._mark_disconnected(err)
            return False

        self._recording = True
        self._event_bus.publish(EVENT_RECORDING_STARTED, {"path": "", "obs": True})
        log.info("OBS recording started")
        return True

    def stop_record(self) -> bool:
        with self._lock:
            req = self._req
        if not req or not self._connected:
            self._event_bus.publish(EVENT_CAPTURE_ERROR, {
                "error": "OBS not connected — cannot stop recording",
            })
            return False

        if not self._recording:
            return True  # already stopped

        try:
            resp = req.stop_record()
            output_path = getattr(resp, "output_path", "") or ""
        except Exception as exc:
            err = str(exc)
            self._event_bus.publish(EVENT_OBS_ERROR, {
                "error": f"OBS stop recording failed: {err}",
            })
            if _is_request_error(exc):
                self._recording = False  # OBS says not recording
            else:
                self._mark_disconnected(err)
            return False

        self._recording = False
        self._event_bus.publish(EVENT_RECORDING_STOPPED, {
            "path": output_path,
            "duration": 0,
            "obs": True,
        })
        log.info("OBS recording stopped: %s", output_path)
        return True

    def is_recording(self) -> bool:
        """Return whether OBS is currently recording.

        Uses a cached value updated by events, with a fallback query.
        """
        return self._recording

    def _handle_record_state_changed(self, event) -> None:
        """Track recording state from OBS events."""
        state = getattr(event, "output_state", "")
        if state == "OBS_WEBSOCKET_OUTPUT_STARTED":
            self._recording = True
        elif state == "OBS_WEBSOCKET_OUTPUT_STOPPED":
            self._recording = False

    # ------------------------------------------------------------------
    # Directory management
    # ------------------------------------------------------------------

    def update_record_directory(self, directory: str) -> None:
        """Update the OBS recording output directory."""
        with self._lock:
            req = self._req
        if not req or not self._connected:
            return
        try:
            req.set_record_directory(directory)
        except Exception as exc:
            log.debug("Could not update OBS record directory: %s", exc)
