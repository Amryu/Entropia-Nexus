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

            prev = curr
            prev_time = now
