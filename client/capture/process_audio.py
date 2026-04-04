"""WASAPI Process Loopback audio capture (Windows 10 2004+).

Captures audio from a specific process (and its child process tree) using
the ``AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK`` API.  This is the
same mechanism OBS Studio uses for its "Application Audio Capture" source.

Uses ctypes for the ``ActivateAudioInterfaceAsync`` call and pycaw/comtypes
for IAudioClient/IAudioCaptureClient method calls (correct vtable layout).

Falls back gracefully: :func:`is_supported` returns False on older Windows
or non-Windows platforms so callers can use regular loopback instead.
"""

import ctypes
import ctypes.wintypes
import sys
import threading
import time
from collections import deque
from ctypes import POINTER

import numpy as np

from ..core.logger import get_logger
from .constants import AUDIO_CHANNELS, AUDIO_SAMPLE_RATE

log = get_logger("ProcessAudio")

_MIN_BUILD = 19041  # Windows 10 version 2004

LPVOID = ctypes.c_void_p
DWORD = ctypes.wintypes.DWORD
HRESULT = ctypes.HRESULT


def _get_windows_build() -> int:
    if sys.platform != "win32":
        return 0
    try:
        return sys.getwindowsversion().build
    except Exception:
        return 0


def is_supported() -> bool:
    """Return True if WASAPI process loopback is available."""
    if _get_windows_build() < _MIN_BUILD:
        return False
    try:
        import comtypes  # noqa: F401
        from pycaw.api.audioclient import IAudioClient  # noqa: F401
        return True
    except Exception:
        return False


def get_pid_for_hwnd(hwnd: int) -> int:
    """Return the process ID that owns *hwnd*."""
    pid = ctypes.wintypes.DWORD(0)
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


# ---------------------------------------------------------------------------
# Activation structures and constants
# ---------------------------------------------------------------------------

try:
    from comtypes import GUID
except ImportError:
    GUID = None  # is_supported() returns False

VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK = r"VAD\Process_Loopback"
AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK = 1
PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE = 0

# Stream flags for Initialize
AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
AUDCLNT_STREAMFLAGS_EVENTCALLBACK = 0x00040000
AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM = 0x80000000
AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY = 0x08000000


class PROPVARIANT(ctypes.Structure):
    _fields_ = [
        ("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort),
        ("r2", ctypes.c_ushort), ("r3", ctypes.c_ushort),
        ("sz", DWORD), ("ptr", LPVOID),
    ]


class ACTP(ctypes.Structure):
    _fields_ = [("Type", DWORD), ("Pid", DWORD), ("Mode", DWORD)]


# Completion handler vtable (pure ctypes — no comtypes COMObject needed)
_QI_T = ctypes.WINFUNCTYPE(HRESULT, LPVOID, LPVOID, POINTER(LPVOID))
_AR_T = ctypes.WINFUNCTYPE(ctypes.c_ulong, LPVOID)
_RL_T = ctypes.WINFUNCTYPE(ctypes.c_ulong, LPVOID)
_AC_T = ctypes.WINFUNCTYPE(HRESULT, LPVOID, LPVOID)


class _HandlerVtbl(ctypes.Structure):
    _fields_ = [("QI", _QI_T), ("AR", _AR_T), ("RL", _RL_T), ("AC", _AC_T)]


class _HandlerObj(ctypes.Structure):
    _fields_ = [("v", POINTER(_HandlerVtbl))]


def _create_completion_handler(event_handle):
    """Create a COM completion handler that signals *event_handle*."""
    _rc = ctypes.c_long(1)

    def qi(t, r, p):
        p[0] = t
        _rc.value += 1
        return 0

    def ar(t):
        _rc.value += 1
        return _rc.value

    def rl(t):
        _rc.value -= 1
        return _rc.value

    def ac(t, o):
        ctypes.windll.kernel32.SetEvent(event_handle)
        return 0

    cbs = (_QI_T(qi), _AR_T(ar), _RL_T(rl), _AC_T(ac))
    vtbl = _HandlerVtbl(*cbs)
    handler = _HandlerObj(ctypes.pointer(vtbl))
    return handler, vtbl, cbs  # must keep alive


def _raw_vtable_call(ptr, idx, restype, *typed_args):
    """Call a COM method by vtable index (used only for async op result)."""
    vpp = ctypes.cast(ptr, POINTER(LPVOID))
    vp = ctypes.cast(vpp[0], POINTER(LPVOID))
    types = [LPVOID] + [t for t, v in typed_args]
    values = [ptr] + [v for t, v in typed_args]
    return ctypes.WINFUNCTYPE(restype, *types)(vp[idx])(*values)


# ---------------------------------------------------------------------------
# Buffer constants
# ---------------------------------------------------------------------------

MAX_AUDIO_BUFFER_S = 65


# ---------------------------------------------------------------------------
# ProcessAudioBuffer
# ---------------------------------------------------------------------------

class ProcessAudioBuffer:
    """Captures audio from a specific process via WASAPI Process Loopback.

    Provides the same public interface as :class:`AudioBuffer`:
    ``start()``, ``stop()``, ``snapshot()``, ``clear()``.
    """

    def __init__(
        self,
        pid: int,
        sample_rate: int = AUDIO_SAMPLE_RATE,
        channels: int = AUDIO_CHANNELS,
    ):
        if not is_supported():
            raise RuntimeError(
                "WASAPI Process Loopback requires Windows 10 2004+ and pycaw"
            )
        self._pid = pid
        self._sample_rate = sample_rate
        self._channels = channels
        self._running = False
        self._started = threading.Event()  # set when capture is running
        self._init_error: str | None = None  # set if init fails
        self._capture_thread: threading.Thread | None = None
        self._client = None  # pycaw IAudioClient (comtypes pointer)
        self._event = None

        max_chunks = int(MAX_AUDIO_BUFFER_S * sample_rate / 1024) + 1
        self._buffer: deque[tuple[float, np.ndarray]] = deque(maxlen=max_chunks)
        self._lock = threading.Lock()

    @property
    def pid(self) -> int:
        return self._pid

    @property
    def channels(self) -> int:
        return self._channels

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._init_error = None
        self._started.clear()
        self._capture_thread = threading.Thread(
            target=self._capture_loop, daemon=True,
            name=f"process-audio-{self._pid}",
        )
        self._capture_thread.start()

    def wait_ready(self, timeout: float = 5.0) -> bool:
        """Block until capture is running or init fails. Returns True on success."""
        self._started.wait(timeout=timeout)
        if self._init_error:
            raise RuntimeError(self._init_error)
        return self._started.is_set()

    def stop(self) -> None:
        self._running = False
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=5)
        self._capture_thread = None

    def snapshot(self, start_time: float, end_time: float) -> np.ndarray | None:
        with self._lock:
            chunks = [d for ts, d in self._buffer
                      if start_time <= ts <= end_time]
        return np.concatenate(chunks, axis=0) if chunks else None

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()

    def set_device(self, device) -> None:
        pass  # no-op

    # ------------------------------------------------------------------
    # Capture loop
    # ------------------------------------------------------------------

    def _capture_loop(self) -> None:
        try:
            self._init_and_run()
        except Exception as e:
            self._init_error = str(e)
            self._started.set()  # unblock wait_ready
            log.exception("Process audio capture failed for PID %d", self._pid)
        finally:
            self._cleanup()

    def _init_and_run(self) -> None:
        from pycaw.api.audioclient import IAudioClient
        from pycaw.api.audioclient.depend import WAVEFORMATEX
        from comtypes import GUID as COMGUID, HRESULT as COMHRESULT, \
            COMMETHOD, IUnknown

        # --- IAudioCaptureClient (pycaw doesn't include it) ---
        class IAudioCaptureClient(IUnknown):
            _iid_ = COMGUID("{C8ADBD64-E71E-48a0-A4DE-185C395CD317}")
            _methods_ = [
                COMMETHOD([], COMHRESULT, "GetBuffer",
                          (["out"], POINTER(LPVOID)),
                          (["out"], POINTER(ctypes.c_uint)),
                          (["out"], POINTER(DWORD)),
                          (["out"], POINTER(ctypes.c_ulonglong)),
                          (["out"], POINTER(ctypes.c_ulonglong))),
                COMMETHOD([], COMHRESULT, "ReleaseBuffer",
                          (["in"], ctypes.c_uint)),
                COMMETHOD([], COMHRESULT, "GetNextPacketSize",
                          (["out"], POINTER(ctypes.c_uint))),
            ]

        # --- Get default output device format ---
        from pycaw.pycaw import AudioUtilities
        speaker = AudioUtilities.GetSpeakers()
        iid_ac = COMGUID("{1CB9AD4C-DBFA-4c32-B178-C2F568A703B2}")
        dev_iface = speaker._dev.Activate(iid_ac, 23, None)  # CLSCTX_ALL
        dev_client = dev_iface.QueryInterface(IAudioClient)
        dev_fmt_ptr = dev_client.GetMixFormat()
        dev_fmt = dev_fmt_ptr.contents

        self._sample_rate = dev_fmt.nSamplesPerSec
        self._channels = dev_fmt.nChannels
        bytes_per_frame = dev_fmt.nBlockAlign

        # Copy exact format bytes for later use
        fmt_size = ctypes.sizeof(WAVEFORMATEX) + dev_fmt.cbSize
        fmt_copy = (ctypes.c_byte * fmt_size)()
        ctypes.memmove(fmt_copy, dev_fmt_ptr, fmt_size)
        fmt_ptr = ctypes.cast(fmt_copy, POINTER(WAVEFORMATEX))

        dev_client.Release()
        max_chunks = int(MAX_AUDIO_BUFFER_S * self._sample_rate / 1024) + 1
        with self._lock:
            self._buffer = deque(self._buffer, maxlen=max_chunks)

        # --- Activate process loopback ---
        evt = ctypes.windll.kernel32.CreateEventW(None, True, False, None)
        handler, vtbl, cbs = _create_completion_handler(evt)

        ap = ACTP(AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK,
                   self._pid, PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE)
        pv = PROPVARIANT()
        pv.vt = 65  # VT_BLOB
        pv.sz = ctypes.sizeof(ap)
        pv.ptr = ctypes.cast(ctypes.pointer(ap), LPVOID)

        fn = ctypes.WinDLL("Mmdevapi.dll").ActivateAudioInterfaceAsync
        fn.restype = HRESULT
        aop = LPVOID()
        iid = COMGUID("{1CB9AD4C-DBFA-4c32-B178-C2F568A703B2}")
        hr = fn(ctypes.c_wchar_p(VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK),
                ctypes.byref(iid), ctypes.byref(pv),
                ctypes.byref(handler), ctypes.byref(aop))
        if hr != 0:
            ctypes.windll.kernel32.CloseHandle(evt)
            raise RuntimeError(f"ActivateAudioInterfaceAsync: 0x{hr & 0xFFFFFFFF:08X}")

        ctypes.windll.kernel32.WaitForSingleObject(evt, 5000)
        ctypes.windll.kernel32.CloseHandle(evt)

        # GetActivateResult (raw vtable — only for async op interface)
        ahr = HRESULT()
        aunk = LPVOID()
        _raw_vtable_call(aop, 3, HRESULT,
                         (POINTER(HRESULT), ctypes.pointer(ahr)),
                         (POINTER(LPVOID), ctypes.pointer(aunk)))
        _raw_vtable_call(aop, 2, ctypes.c_ulong)  # Release
        if ahr.value != 0 or not aunk.value:
            raise RuntimeError(
                f"Process loopback activation failed: 0x{ahr.value & 0xFFFFFFFF:08X}"
            )

        # --- Use pycaw's IAudioClient (comtypes — correct vtable) ---
        client = ctypes.cast(aunk.value, POINTER(IAudioClient))
        self._client = client

        stream_flags = (AUDCLNT_STREAMFLAGS_LOOPBACK |
                        AUDCLNT_STREAMFLAGS_EVENTCALLBACK |
                        AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM |
                        AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY)

        # Buffer duration 0 = let the engine choose
        client.Initialize(0, stream_flags, 0, 0, fmt_ptr, None)

        self._event = ctypes.windll.kernel32.CreateEventW(None, False, False, None)
        client.SetEventHandle(self._event)

        cc_iid = COMGUID("{C8ADBD64-E71E-48a0-A4DE-185C395CD317}")
        cc_ptr = client.GetService(ctypes.pointer(cc_iid))
        cc = ctypes.cast(cc_ptr, POINTER(IAudioCaptureClient))

        client.Start()
        log.info("Process audio capture started (PID=%d, rate=%d, ch=%d)",
                 self._pid, self._sample_rate, self._channels)
        self._started.set()  # signal success to wait_ready()

        # --- Read loop ---
        while self._running:
            ctypes.windll.kernel32.WaitForSingleObject(self._event, 100)
            if not self._running:
                break
            while True:
                try:
                    ps = cc.GetNextPacketSize()
                except Exception:
                    ps = 0
                if ps == 0:
                    break
                try:
                    data, frames, flags, pos, qpc = cc.GetBuffer()
                    if data and frames > 0:
                        if flags & 0x2:  # AUDCLNT_BUFFERFLAGS_SILENT
                            chunk = np.zeros((frames, self._channels),
                                             dtype=np.float32)
                        else:
                            buf = (ctypes.c_char * (frames * bytes_per_frame)
                                   ).from_address(data)
                            chunk = np.frombuffer(
                                bytes(buf), dtype=np.float32,
                            ).reshape(-1, self._channels).copy()
                        ts = time.monotonic()
                        with self._lock:
                            self._buffer.append((ts, chunk))
                    cc.ReleaseBuffer(frames)
                except Exception:
                    log.debug("Process audio read error", exc_info=True)
                    break

    def _cleanup(self) -> None:
        if self._client:
            try:
                self._client.Stop()
            except Exception:
                pass
            try:
                self._client.Release()
            except Exception:
                pass
            self._client = None
        if self._event:
            try:
                ctypes.windll.kernel32.CloseHandle(self._event)
            except Exception:
                pass
            self._event = None
