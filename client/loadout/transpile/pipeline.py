"""Orchestrates JS→Python regeneration.

Responsibilities:
    - Hash each source .js file
    - Compare against `.sources.sha256` in the generated dir
    - If stale (or `force=True`), re-parse via Node + walk the AST
    - Copy runtime.py into generated dir as `_runtime.py`
    - Update the sidecar

Startup calls `ensure_transpiled()` before the loadout package is used.
Build-time `python -m client.loadout.transpile --check` runs the same path
and exits non-zero if anything drifted without Node available.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from .parser import NodeUnavailable, ParseError, node_available, parse_js_file
from .walker import UnsupportedNode, Walker


REPO_ROOT = Path(__file__).resolve().parents[3]
GENERATED_DIR = Path(__file__).resolve().parent.parent / "generated"
RUNTIME_SRC = Path(__file__).resolve().parent / "runtime.py"
HELPERS_SRC = Path(__file__).resolve().parent / "_helpers.py"
SIDECAR = GENERATED_DIR / ".sources.sha256"


@dataclass(frozen=True)
class Source:
    js_path: Path
    module_name: str  # Python module basename (no .py)
    js_import_aliases: tuple[str, ...]  # JS import specifiers that point here


SOURCES: tuple[Source, ...] = (
    Source(
        js_path=REPO_ROOT / "nexus" / "src" / "lib" / "utils" / "loadoutCalculations.js",
        module_name="loadout_calculations",
        js_import_aliases=("$lib/utils/loadoutCalculations.js",),
    ),
    Source(
        js_path=REPO_ROOT / "nexus" / "src" / "lib" / "utils" / "loadoutEffects.js",
        module_name="loadout_effects",
        js_import_aliases=("$lib/utils/loadoutEffects.js",),
    ),
    Source(
        js_path=REPO_ROOT / "nexus" / "src" / "lib" / "utils" / "loadoutEvaluator.js",
        module_name="loadout_evaluator",
        js_import_aliases=("$lib/utils/loadoutEvaluator.js",),
    ),
    Source(
        js_path=REPO_ROOT / "common" / "itemTypes.js",
        module_name="item_types",
        js_import_aliases=("$common/itemTypes.js", "common/itemTypes.js"),
    ),
)


def _import_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for s in SOURCES:
        for alias in s.js_import_aliases:
            out[alias] = s.module_name
    # Imports pointing to JS files that are not themselves transpiled
    # resolve to `_helpers`, which ships hand-written Python ports.
    out["$lib/util.js"] = "_helpers"
    return out


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _load_sidecar() -> dict[str, str]:
    if not SIDECAR.exists():
        return {}
    try:
        return json.loads(SIDECAR.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_sidecar(data: dict[str, str]) -> None:
    SIDECAR.parent.mkdir(parents=True, exist_ok=True)
    SIDECAR.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _expected_hashes() -> dict[str, str]:
    return {s.module_name: _file_hash(s.js_path) for s in SOURCES}


def is_stale() -> bool:
    # Frozen builds bake the generated files and strip the JS sources. If
    # any source is missing, treat the port as "good as it gets" — the build
    # step is responsible for guaranteeing it was fresh at package time.
    try:
        expected = _expected_hashes()
    except FileNotFoundError:
        for s in SOURCES:
            if not (GENERATED_DIR / f"{s.module_name}.py").exists():
                return True
        return False
    recorded = _load_sidecar()
    if recorded != expected:
        return True
    for s in SOURCES:
        if not (GENERATED_DIR / f"{s.module_name}.py").exists():
            return True
    if not (GENERATED_DIR / "_runtime.py").exists():
        return True
    if not (GENERATED_DIR / "__init__.py").exists():
        return True
    return False


def ensure_transpiled(force: bool = False) -> None:
    """Regenerate the Python versions if any JS source hash changed.

    Raises `NodeUnavailable` if Node is required but missing. Callers on the
    startup path should catch this and continue with existing files.
    """
    if not force and not is_stale():
        return
    if not node_available():
        raise NodeUnavailable(
            "`node` is required to regenerate client/loadout/generated; "
            "install Node.js or run a build that produced fresh .py files."
        )
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    (GENERATED_DIR / "__init__.py").write_text(
        '"""Auto-generated Python ports of the loadout JS files. Do not edit."""\n',
        encoding="utf-8",
    )
    shutil.copyfile(RUNTIME_SRC, GENERATED_DIR / "_runtime.py")
    shutil.copyfile(HELPERS_SRC, GENERATED_DIR / "_helpers.py")

    import_map = _import_map()
    for source in SOURCES:
        ast = parse_js_file(source.js_path)
        walker = Walker(module_name=source.module_name, import_map=import_map)
        try:
            py_source = walker.walk(ast)
        except UnsupportedNode as exc:
            _handle_unsupported(source, exc, ast)
            raise
        out_path = GENERATED_DIR / f"{source.module_name}.py"
        out_path.write_text(py_source, encoding="utf-8")

    _write_sidecar(_expected_hashes())


def _handle_unsupported(source: Source, exc: UnsupportedNode, ast: dict) -> None:
    """Placeholder for LLM fallback. Filled in by step 3 of the plan."""
    sys.stderr.write(
        f"[transpile] unsupported node in {source.js_path.name}: "
        f"{exc.node_type} inside {exc.function_name or '<module>'}\n"
    )


def check_only() -> int:
    """CLI entry: `python -m client.loadout.transpile --check`.

    Returns 0 if in sync, 1 otherwise. Does not regenerate.
    """
    if is_stale():
        sys.stderr.write("[transpile] generated files are stale\n")
        return 1
    return 0
