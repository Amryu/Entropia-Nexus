"""CLI entry for the loadout transpiler.

Usage:
    python -m client.loadout.transpile            # regenerate if stale
    python -m client.loadout.transpile --force    # always regenerate
    python -m client.loadout.transpile --check    # exit 1 if stale (no writes)
"""

from __future__ import annotations

import argparse
import sys

from . import ensure_transpiled
from .parser import NodeUnavailable
from .pipeline import check_only


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="client.loadout.transpile")
    parser.add_argument(
        "--force", action="store_true", help="Regenerate even when sources are unchanged"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if generated files are stale. No writes.",
    )
    args = parser.parse_args(argv)

    if args.check:
        return check_only()
    try:
        ensure_transpiled(force=args.force)
    except NodeUnavailable as exc:
        sys.stderr.write(f"[transpile] {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
