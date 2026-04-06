"""Per-thread CPU profiler.

Samples ``psutil.Process.threads()`` every REPORT_INTERVAL seconds and
logs the threads that consumed the most CPU time since the last report.
Helps identify busy loops and hot threads in production.
"""

import threading
import time

from .logger import get_logger

log = get_logger("ThreadProfiler")

REPORT_INTERVAL = 30  # seconds between reports
MIN_CPU_PCT = 1.0     # only report threads using more than this % of one core


def _get_thread_module(tid: int) -> str:
    """Try to identify which DLL/module a native thread belongs to.

    Uses NtQueryInformationThread to get the start address, then
    GetModuleHandleEx + GetModuleFileName to resolve the module.
    """
    import sys
    if sys.platform != "win32":
        return ""
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        ntdll = ctypes.windll.ntdll

        THREAD_QUERY_INFORMATION = 0x0040
        handle = kernel32.OpenThread(THREAD_QUERY_INFORMATION, False, tid)
        if not handle:
            return f"(OpenThread failed: {ctypes.get_last_error()})"

        try:
            # NtQueryInformationThread class 9 = ThreadQuerySetWin32StartAddress
            start_addr = ctypes.c_void_p()
            status = ntdll.NtQueryInformationThread(
                handle, 9, ctypes.byref(start_addr),
                ctypes.sizeof(start_addr), None,
            )
            if status != 0:
                return f"(NtQuery failed: 0x{status:08x})"

            addr = start_addr.value
            if not addr:
                return "(start address is NULL)"

            # GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS = 4
            mod_handle = wintypes.HMODULE()
            ok = kernel32.GetModuleHandleExW(
                4, ctypes.c_void_p(addr), ctypes.byref(mod_handle),
            )
            if not ok or not mod_handle:
                return f"(module not found for addr 0x{addr:016x})"

            buf = ctypes.create_unicode_buffer(260)
            kernel32.GetModuleFileNameW(mod_handle, buf, 260)
            kernel32.FreeLibrary(mod_handle)
            return f"start=0x{addr:016x} module={buf.value}"
        finally:
            kernel32.CloseHandle(handle)
    except Exception as e:
        return f"(error: {e})"


class ThreadProfiler:
    """Background thread that logs per-thread CPU usage."""

    def __init__(self):
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, name="ThreadProfiler", daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _run(self) -> None:
        try:
            import psutil
        except ImportError:
            log.debug("psutil not available — thread profiling disabled")
            return

        proc = psutil.Process()
        py_threads = {t.ident: t.name for t in threading.enumerate()}

        # Take initial snapshot
        prev: dict[int, tuple[float, float]] = {}
        try:
            for t in proc.threads():
                prev[t.id] = (t.user_time, t.system_time)
        except Exception:
            return

        prev_time = time.monotonic()
        first_report = True

        while self._running:
            time.sleep(REPORT_INTERVAL)
            if not self._running:
                break

            now = time.monotonic()
            elapsed = now - prev_time
            if elapsed < 1.0:
                continue

            # Refresh Python thread name mapping
            py_threads = {t.ident: t.name for t in threading.enumerate()}

            try:
                curr: dict[int, tuple[float, float]] = {}
                for t in proc.threads():
                    curr[t.id] = (t.user_time, t.system_time)
            except Exception:
                prev_time = now
                continue

            # Compute deltas
            entries = []
            for tid, (u2, s2) in curr.items():
                u1, s1 = prev.get(tid, (0.0, 0.0))
                du = u2 - u1
                ds = s2 - s1
                total = du + ds
                pct = (total / elapsed) * 100.0
                if pct >= MIN_CPU_PCT:
                    name = py_threads.get(tid, f"TID-{tid}")
                    entries.append((name, tid, du, ds, pct, u2, s2))

            if entries:
                entries.sort(key=lambda e: -e[4])
                lines = [f"Thread CPU usage ({elapsed:.0f}s window):"]
                for name, tid, du, ds, pct, u_total, s_total in entries:
                    lines.append(
                        f"  {name:30s}  TID {tid:6d}  "
                        f"user={du:.2f}s  sys={ds:.2f}s  ({pct:.1f}%)  "
                        f"[total: user={u_total:.1f}s sys={s_total:.1f}s]"
                    )
                log.info("\n".join(lines))

            if first_report:
                first_report = False
                all_tids = set(curr.keys())
                py_tids = set(py_threads.keys())
                native_tids = all_tids - py_tids
                # Try to resolve the module for hot native threads
                hot_tid = entries[0][1] if entries and entries[0][1] not in py_tids else None
                mod_info = ""
                if hot_tid:
                    mod_info = _get_thread_module(hot_tid)
                lines = [f"Thread inventory: {len(all_tids)} total, "
                         f"{len(py_tids)} Python, {len(native_tids)} native"]
                if mod_info:
                    lines.append(f"  HOT TID {hot_tid}: {mod_info}")
                for tid in sorted(native_tids):
                    u, s = curr.get(tid, (0, 0))
                    lines.append(f"  native TID {tid:6d}  "
                                 f"user={u:.1f}s  sys={s:.1f}s")
                log.info("\n".join(lines))

            prev = curr
            prev_time = now
