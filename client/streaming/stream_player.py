"""Stream player — wraps streamlink + mpv for live Twitch stream playback.

mpv is embedded into a Qt widget via its native window handle (HWND on Windows).
All heavy I/O (URL resolution) runs on background threads.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal

from ..core.logger import get_logger

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

log = get_logger("StreamPlayer")

# --- mpv DLL search & download ---

_USER_BIN_DIR = Path.home() / ".entropia-nexus" / "bin"
_MPV_DLL_NAME = "mpv-2.dll"
_LIBMPV_DLL_NAME = "libmpv-2.dll"  # name used in dev builds

# GitHub API to find the latest mpv-dev build (contains mpv-2.dll).
# zhongfly/mpv-winbuild publishes nightly builds as .7z archives.
_MPV_RELEASES_API = (
    "https://api.github.com/repos/zhongfly/mpv-winbuild/releases/latest"
)
# Asset name prefix to match (x86_64, non-debug, non-lgpl, dev build)
_MPV_ASSET_PREFIX = "mpv-dev-x86_64-"

# Try importing optional dependencies
_MPV_AVAILABLE = False
_STREAMLINK_AVAILABLE = False
_MPV_DLL_MISSING = False


def _add_mpv_paths():
    """Add common mpv locations to PATH before importing."""
    if sys.platform != "win32":
        return
    search_dirs = [
        str(_USER_BIN_DIR),
        os.path.join(os.path.dirname(sys.executable), "mpv"),
        os.path.dirname(sys.executable),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "mpv"),
        os.path.join(os.environ.get("ProgramFiles", ""), "mpv"),
        os.path.join(os.path.dirname(__file__), "..", "assets", "mpv"),
    ]
    for d in search_dirs:
        if os.path.isdir(d):
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")


def find_mpv_dll() -> str | None:
    """Return path to mpv-2.dll or libmpv-2.dll if found, else None."""
    if sys.platform != "win32":
        return shutil.which("mpv")
    # Check user bin (both names)
    for dll_name in (_MPV_DLL_NAME, _LIBMPV_DLL_NAME):
        user_path = _USER_BIN_DIR / dll_name
        if user_path.is_file():
            return str(user_path)
    # Check PATH
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    for d in path_dirs:
        for dll_name in (_MPV_DLL_NAME, _LIBMPV_DLL_NAME):
            p = os.path.join(d, dll_name)
            if os.path.isfile(p):
                return p
    return None


def _find_7z() -> str | None:
    """Find 7z.exe on the system."""
    # Check PATH
    sz = shutil.which("7z")
    if sz:
        return sz
    # Common install locations
    for base in [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    ]:
        p = os.path.join(base, "7-Zip", "7z.exe")
        if os.path.isfile(p):
            return p
    # Check for standalone 7za.exe in user bin
    p = _USER_BIN_DIR / "7za.exe"
    if p.is_file():
        return str(p)
    return None


def _ensure_7z() -> str | None:
    """Find or download 7z for archive extraction."""
    sz = _find_7z()
    if sz:
        return sz
    # Download standalone 7za.exe (~600 KB)
    import requests
    url = "https://www.7-zip.org/a/7za920.zip"
    log.info("Downloading 7za.exe from %s", url)
    try:
        import zipfile, io
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        _USER_BIN_DIR.mkdir(parents=True, exist_ok=True)
        target = _USER_BIN_DIR / "7za.exe"
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            for name in zf.namelist():
                if name.endswith("7za.exe"):
                    with zf.open(name) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    log.info("7za.exe saved to %s", target)
                    return str(target)
    except Exception as exc:
        log.error("Failed to download 7za.exe: %s", exc)
    return None


def download_mpv_dll(progress_callback=None) -> str | None:
    """Download mpv-2.dll to the user bin directory (~30 MB).

    Uses the GitHub API to find the latest mpv-dev build from
    zhongfly/mpv-winbuild, downloads the .7z archive, and extracts
    mpv-2.dll using 7z.

    Args:
        progress_callback: Optional callable(downloaded_bytes, total_bytes).

    Returns the path to the DLL, or None on failure.
    """
    if sys.platform != "win32":
        log.warning("mpv auto-download is only supported on Windows")
        return None

    import requests

    # Ensure we have 7z for extraction
    sz_path = _ensure_7z()
    if not sz_path:
        log.error("7-Zip not found and could not be downloaded")
        return None

    target_dir = _USER_BIN_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / _MPV_DLL_NAME

    try:
        # 1. Find the download URL via GitHub API
        log.info("Querying GitHub for latest mpv-dev release...")
        api_resp = requests.get(_MPV_RELEASES_API, timeout=15)
        api_resp.raise_for_status()
        release = api_resp.json()

        download_url = None
        for asset in release.get("assets", []):
            name = asset.get("name", "")
            # Match e.g. "mpv-dev-x86_64-20260316-git-b51131d.7z"
            # but NOT "mpv-dev-x86_64-v3-..." (AVX-optimised, less compatible)
            if (name.startswith(_MPV_ASSET_PREFIX)
                    and name.endswith(".7z")
                    and "-v3-" not in name
                    and "-lgpl-" not in name):
                download_url = asset.get("browser_download_url")
                break

        if not download_url:
            log.error("No matching mpv-dev asset found in latest release")
            return None

        # 2. Download the archive to a temp file
        log.info("Downloading %s", download_url)
        resp = requests.get(download_url, stream=True, timeout=30)
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0

        tmp_7z = os.path.join(tempfile.gettempdir(), "nexus_mpv_dev.7z")
        with open(tmp_7z, "wb") as f:
            for chunk in resp.iter_content(chunk_size=256 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total:
                    progress_callback(downloaded, total)

        # 3. Extract mpv-2.dll using 7z subprocess
        tmp_extract = os.path.join(tempfile.gettempdir(), "nexus_mpv_extract")
        os.makedirs(tmp_extract, exist_ok=True)

        # Extract either mpv-2.dll or libmpv-2.dll (dev builds use the latter)
        result = subprocess.run(
            [sz_path, "e", tmp_7z, f"-o{tmp_extract}",
             _MPV_DLL_NAME, _LIBMPV_DLL_NAME, "-r", "-y"],
            capture_output=True, text=True, timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        if result.returncode != 0:
            log.error("7z extraction failed (rc=%d): %s",
                      result.returncode, result.stderr)
            return None

        # Find the extracted DLL (could be either name)
        extracted = os.path.join(tmp_extract, _MPV_DLL_NAME)
        if not os.path.isfile(extracted):
            extracted = os.path.join(tmp_extract, _LIBMPV_DLL_NAME)
        if not os.path.isfile(extracted):
            log.error("DLL not found after extraction")
            return None

        # python-mpv searches for mpv-2.dll, mpv-1.dll, or libmpv-2.dll
        # so either name works — keep the original name
        final_name = os.path.basename(extracted)
        target_path = target_dir / final_name
        shutil.move(extracted, str(target_path))

        # Clean up temp files
        try:
            os.remove(tmp_7z)
            shutil.rmtree(tmp_extract, ignore_errors=True)
        except OSError:
            pass

        log.info("mpv-2.dll downloaded to %s", target_path)
        return str(target_path)

    except Exception as e:
        log.error("Failed to download mpv: %s", e)
        return None


def _try_import_mpv():
    """Attempt to import mpv, updating global state."""
    global _MPV_AVAILABLE, _MPV_DLL_MISSING
    _add_mpv_paths()
    try:
        import mpv as _mpv_mod  # noqa: F401
        _MPV_AVAILABLE = True
        _MPV_DLL_MISSING = False
        return True
    except ImportError:
        return False
    except OSError:
        _MPV_DLL_MISSING = True
        return False


# Initial import attempt
_add_mpv_paths()

try:
    import mpv as _mpv_mod  # noqa: F401
    _MPV_AVAILABLE = True
except ImportError:
    pass
except OSError:
    _MPV_DLL_MISSING = True

try:
    import streamlink as _streamlink_mod  # noqa: F401
    _STREAMLINK_AVAILABLE = True
except ImportError:
    pass


def is_available() -> bool:
    """Return True if both streamlink and mpv are importable."""
    return _MPV_AVAILABLE and _STREAMLINK_AVAILABLE


def is_mpv_dll_missing() -> bool:
    """Return True if python-mpv is installed but the DLL is missing."""
    return _MPV_DLL_MISSING


def missing_components() -> list[str]:
    """Return list of missing component names."""
    missing = []
    if not _STREAMLINK_AVAILABLE:
        missing.append("streamlink (pip install streamlink)")
    if not _MPV_AVAILABLE and not _MPV_DLL_MISSING:
        missing.append("python-mpv (pip install python-mpv)")
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
        """Toggle pause. Returns new paused state.

        On unpause, seeks to the live edge so playback catches up
        instead of playing through the stale buffer.
        """
        self._paused = not self._paused
        if self._player is not None:
            try:
                if self._paused:
                    self._player.pause = True
                else:
                    # Seek to live edge before unpausing
                    self._player.pause = False
                    self._player.seek(100, "absolute-percent")
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

        # Widget must have a valid native HWND (set at build time via
        # WA_NativeWindow).  Verify it's ready.
        wid = str(int(self._widget.winId()))
        if wid == "0":
            log.error("Video widget has no valid HWND yet")
            self.stream_error.emit("Video widget not ready")
            return

        def _mpv_log(loglevel, component, message):
            log.debug("[mpv/%s] %s: %s", loglevel, component, message)

        self._player = mpv.MPV(
            wid=wid,
            loglevel="warn",
            log_handler=_mpv_log,
            ytdl=False,
            input_default_bindings=False,
            # Use gpu-next with d3d11 context — works with native child
            # windows inside layered (WA_TranslucentBackground) parents.
            gpu_context="d3d11",
        )
        self._player.volume = self._volume
        self._player.mute = self._muted

        # Marshal mpv events to Qt signals
        @self._player.event_callback("end-file")
        def _on_end_file(event):
            try:
                reason = getattr(event, "reason", None)
                if reason is not None and "error" in str(reason).lower():
                    self.stream_error.emit("Stream playback error")
            except Exception:
                pass
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
            log.error("Stream resolution failed for %s: %s", channel, exc)
            self.stream_error.emit(str(exc))
            self._resolving = False

    def _on_url_resolved(self, url: str):
        """Main-thread handler: start mpv playback with the resolved URL.

        Defers actual playback by one event-loop cycle to ensure the
        video widget has been shown and its HWND is fully realized.
        """
        self._resolving = False
        self._pending_url = url
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._start_mpv_playback)

    def _start_mpv_playback(self):
        """Actually create mpv and start playing (deferred from _on_url_resolved)."""
        url = getattr(self, "_pending_url", "")
        if not url:
            return
        self._pending_url = ""
        try:
            self._ensure_player()
            if self._player is None:
                return
            self._player.play(url)
            self._paused = False
            self.stream_started.emit()
        except Exception as exc:
            log.error("mpv play failed: %s", exc)
            self.stream_error.emit(str(exc))
