"""GIL yield helper for background threads.

Background threads running CPU-bound Python loops can starve the
keyboard hook thread (WH_KEYBOARD_LL has a ~300ms system timeout).
Use ``GilYielder`` to periodically release the GIL via time.sleep(0).
"""

import time

# Max time (seconds) to hold the GIL before yielding.
# 8ms matches 120fps frame budget and stays well under the 300ms hook timeout.
GIL_YIELD_BUDGET_S = 0.008


class GilYielder:
    """Lightweight time-gated GIL yield checkpoint.

    Usage::

        yielder = GilYielder()
        for item in big_list:
            do_work(item)
            yielder.yield_if_needed()
    """

    __slots__ = ("_budget", "_last_yield")

    def __init__(self, budget: float = GIL_YIELD_BUDGET_S):
        self._budget = budget
        self._last_yield = time.monotonic()

    def yield_if_needed(self) -> None:
        now = time.monotonic()
        if now - self._last_yield > self._budget:
            time.sleep(0)
            self._last_yield = time.monotonic()
