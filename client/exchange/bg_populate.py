"""Background populate helper for exchange/inventory UI components."""

import logging
import threading

from ..core.thread_utils import invoke_on_main

log = logging.getLogger(__name__)


def populate_in_background(owner, version_attr, compute_fn, apply_fn,
                           loading_label=None, tree=None):
    """Run *compute_fn* in a background thread, then *apply_fn* on the main thread.

    Uses a version counter on *owner* (attribute *version_attr*) to discard
    stale results when the user triggers a new populate before the previous
    one finishes.

    *loading_label* (QLabel) is shown while the background work runs.
    *tree* (QTreeWidget) is hidden while loading and shown again when done.
    """
    current = getattr(owner, version_attr, 0) + 1
    setattr(owner, version_attr, current)

    if loading_label is not None:
        loading_label.show()
    if tree is not None:
        tree.hide()

    def _worker():
        try:
            rows = compute_fn()
        except Exception:
            log.exception("bg_populate compute error")
            rows = []
        invoke_on_main(lambda: _on_done(rows))

    def _on_done(rows):
        try:
            if getattr(owner, version_attr, 0) != current:
                return  # stale
        except RuntimeError:
            return  # widget destroyed

        if loading_label is not None:
            loading_label.hide()
        if tree is not None:
            tree.show()

        try:
            apply_fn(rows)
        except RuntimeError:
            pass  # widget destroyed during apply

    threading.Thread(target=_worker, daemon=True, name="exch-bg-populate").start()
