"""Loadout package.

Importing this package runs `ensure_transpiled()` so the generated Python
ports in `client/loadout/generated/` stay in sync with the canonical JS
sources in `nexus/src/lib/utils/`. If Node is not available at startup we
log a warning and fall back to whatever's already on disk — that covers
release builds, where the files were baked in at package time.
"""

from __future__ import annotations

import os
import sys


def _bootstrap_transpile() -> None:
    if os.environ.get("ENTROPIA_SKIP_TRANSPILE") == "1":
        return
    try:
        from .transpile import ensure_transpiled
        from .transpile.parser import NodeUnavailable
    except Exception as exc:
        sys.stderr.write(f"[loadout] transpile bootstrap skipped: {exc}\n")
        return
    try:
        ensure_transpiled()
    except NodeUnavailable:
        # Release builds commit generated files into the frozen binary, so
        # a missing Node runtime on the user's machine is fine.
        pass
    except Exception as exc:
        sys.stderr.write(f"[loadout] transpile failed at startup: {exc}\n")


_bootstrap_transpile()
