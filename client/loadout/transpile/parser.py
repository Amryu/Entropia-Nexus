"""Thin wrapper around the Node helper that parses a JS file via acorn.

The helper (`parse_js.mjs`) requires Node on PATH and resolves `acorn`
from `nexus/node_modules`. Python-native parsers (pyjsparser, esprima-python)
are stuck at ES2017-ish and choke on optional chaining, so Node is the
practical way to get an ES2022 AST.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

HELPER = Path(__file__).parent / "parse_js.mjs"


class ParseError(RuntimeError):
    pass


class NodeUnavailable(RuntimeError):
    """Raised when `node` is not on PATH. Callers can fall back to cached output."""


def node_available() -> bool:
    return shutil.which("node") is not None


def parse_js_file(path: Path) -> dict:
    """Run the Node helper on `path` and return the acorn AST as a dict."""
    if not node_available():
        raise NodeUnavailable("`node` not found on PATH")
    result = subprocess.run(
        ["node", str(HELPER), str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        creationflags=_no_window_flag(),
    )
    if result.returncode != 0:
        raise ParseError(f"parse failed for {path}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def _no_window_flag() -> int:
    """On Windows, suppress the subprocess console window flash."""
    try:
        import subprocess as _sp
        return getattr(_sp, "CREATE_NO_WINDOW", 0)
    except Exception:
        return 0
