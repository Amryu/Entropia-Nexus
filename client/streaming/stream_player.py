"""Stream player — wraps streamlink + mpv for live Twitch stream playback.

mpv is embedded into a Qt widget via its native window handle (HWND on Windows).
All heavy I/O (URL resolution) runs on background threads.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal

from ..core.logger import get_logger

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

log = get_logger("StreamPlayer")

# Try importing optional dependencies
_MPV_AVAILABLE = False
_STREAMLINK_AVAILABLE = False

try:
    import mpv as _mpv_mod  # noqa: F401
    _MPV_AVAILABLE = True
except (ImportError, OSError):
    pass

try:
    import streamlink as _streamlink_mod  # noqa: F401
    _STREAMLINK_AVAILABLE = True
except ImportError:
    pass


def is_available() -> bool:
    """Return True if both streamlink and mpv are importable."""
    return _MPV_AVAILABLE and _STREAMLINK_AVAILABLE


def missing_components() -> list[str]:
    """Return list of missing component names."""
    missing = []
    if not _STREAMLINK_AVAILABLE:
        missing.append("streamlink")
    if not _MPV_AVAILABLE:
        missing.append("python-mpv (+ mpv-2.dll)")
    return missing


class StreamPlayer(QObject):
    """Live stream player using streamlink + mpv.

    Signals:
        stream_started(): Playback began successfully
        stream_error(str): Error message
        stream_ended(): Stream ended or was stopped
    """

    stream_started = pyqtSignal()
    stream_error = pyqtSignal(str)
    stream_ended = pyqtSignal()

    # Internal signal for URL resolution (background → main thread)
    _url_resolved = pyqtSignal(str)

    def __init__(self, video_widget: QWidget, parent: QObject | None = None):
        super().__init__(parent)
        self._widget = video_widget
        self._player = None  # mpv.MPV instance, created lazily
        self._muted = False
        self._paused = False
        self._volume = 80
        self._current_channel = ""
        self._resolving = False

        self._url_resolved.connect(self._on_url_resolved)

    # ------------------------------------------------------------------
    # Public API (call from main thread)
    # ------------------------------------------------------------------

    def play_channel(self, channel: str, quality: str = "best"):
        """Start playing a Twitch channel. URL resolution runs on a background thread."""
        if not is_available():
            self.stream_error.emit(
                "Missing: " + ", ".join(missing_components())
            )
            return

        if self._resolving:
            return

        self._current_channel = channel
        self._resolving = True

        threading.Thread(
            target=self._resolve_stream_url,
            args=(channel, quality),
            daemon=True,
            name=f"resolve-{channel}",
        ).start()

    def stop(self):
        """Stop playback and clean up mpv."""
        self._current_channel = ""
        self._paused = False
        if self._player is not None:
            try:
                self._player.stop()
            except Exception:
                pass

    def set_volume(self, volume: int):
        """Set volume (0-100)."""
        self._volume = max(0, min(100, volume))
        if self._player is not None:
            try:
                self._player.volume = self._volume
            except Exception:
                pass

    def toggle_mute(self) -> bool:
        """Toggle mute state. Returns new muted state."""
        self._muted = not self._muted
        if self._player is not None:
            try:
                self._player.mute = self._muted
            except Exception:
                pass
        return self._muted

    def set_muted(self, muted: bool):
        """Set mute state explicitly."""
        self._muted = muted
        if self._player is not None:
            try:
                self._player.mute = self._muted
            except Exception:
                pass

    def toggle_pause(self) -> bool:
        """Toggle pause. Returns new paused state."""
        self._paused = not self._paused
        if self._player is not None:
            try:
                self._player.pause = self._paused
            except Exception:
                pass
        return self._paused

    @property
    def is_playing(self) -> bool:
        return self._player is not None and self._current_channel != ""

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def is_muted(self) -> bool:
        return self._muted

    def cleanup(self):
        """Release mpv resources. Call before widget destruction."""
        if self._player is not None:
            try:
                self._player.terminate()
            except Exception:
                pass
            self._player = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_player(self):
        """Create mpv instance on the main thread (requires valid HWND)."""
        if self._player is not None:
            return

        import mpv

        wid = str(int(self._widget.winId()))
        self._player = mpv.MPV(
            wid=wid,
            log_level="warn",
            ytdl=False,
            input_default_bindings=False,
            input_vo_keyboard=False,
        )
        self._player.volume = self._volume
        self._player.mute = self._muted

        # Marshal mpv events to Qt signals
        @self._player.event_callback("end-file")
        def _on_end_file(event):
            reason = event.get("event", {}).get("reason", "")
            if reason == "error":
                self.stream_error.emit("Stream playback error")
            self.stream_ended.emit()

    def _resolve_stream_url(self, channel: str, quality: str):
        """Resolve the Twitch stream URL via streamlink (background thread)."""
        try:
            import streamlink

            url = f"https://twitch.tv/{channel}"
            session = streamlink.Streamlink()
            streams = session.streams(url)

            if not streams:
                self.stream_error.emit(f"No streams found for {channel}")
                self._resolving = False
                return

            # Pick requested quality, fall back to best
            stream = streams.get(quality) or streams.get("best")
            if stream is None:
                self.stream_error.emit(f"Quality '{quality}' not available")
                self._resolving = False
                return

            stream_url = stream.url
            self._url_resolved.emit(stream_url)

        except Exception as exc:
            log.debug("Stream resolution failed for %s: %s", channel, exc)
            self.stream_error.emit(str(exc))
            self._resolving = False

    def _on_url_resolved(self, url: str):
        """Main-thread handler: start mpv playback with the resolved URL."""
        self._resolving = False
        try:
            self._ensure_player()
            self._player.play(url)
            self._paused = False
            self.stream_started.emit()
        except Exception as exc:
            log.debug("mpv play failed: %s", exc)
            self.stream_error.emit(str(exc))
