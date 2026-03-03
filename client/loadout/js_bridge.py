"""PyMiniRacer bridge for executing loadout calculation JS files."""

import json
import re
import sys
from pathlib import Path

from ..core.logger import get_logger

log = get_logger("JSBridge")

# Default path to the JS utils — use sys._MEIPASS in frozen builds
# so the path resolves correctly inside the PyInstaller bundle.
if getattr(sys, "frozen", False):
    _base = Path(sys._MEIPASS)
else:
    _base = Path(__file__).parent.parent.parent
DEFAULT_JS_PATH = _base / "nexus" / "src" / "lib" / "utils"

# JS files to load, in dependency order
JS_FILES = [
    "loadoutCalculations.js",
    "loadoutEffects.js",
    "loadoutEvaluator.js",
]


def _strip_esm(source: str) -> str:
    """Strip ES module syntax so the code runs in a plain V8 context.

    Transforms:
    - 'export function foo(...)' -> 'function foo(...)'
    - 'export const X = ...' -> 'const X = ...'
    - 'export { ... }' -> removed
    - 'import { ... } from ...' -> removed (already eval'd in shared context)
    - 'import * as X from ...' -> removed, and 'X.foo' references replaced with 'foo'
    """
    # Collect namespace imports (import * as X from '...') before removing them
    namespace_aliases = []
    for m in re.finditer(
        r'^import\s+\*\s+as\s+(\w+)\s+from\s+[\'"][^\'"]*[\'"];?\s*$',
        source, flags=re.MULTILINE
    ):
        namespace_aliases.append(m.group(1))

    # Remove import lines
    source = re.sub(r'^import\s+\{[^}]*\}\s+from\s+[\'"][^\'"]*[\'"];?\s*$', '', source, flags=re.MULTILINE)
    source = re.sub(r'^import\s+\w+\s+from\s+[\'"][^\'"]*[\'"];?\s*$', '', source, flags=re.MULTILINE)
    source = re.sub(r'^import\s+\*\s+as\s+\w+\s+from\s+[\'"][^\'"]*[\'"];?\s*$', '', source, flags=re.MULTILINE)

    # Replace namespace references (e.g. LoadoutCalc.foo -> foo)
    for alias in namespace_aliases:
        source = re.sub(rf'\b{alias}\.', '', source)

    # Remove 'export default' (keep the value)
    source = re.sub(r'^export\s+default\s+', '', source, flags=re.MULTILINE)

    # Remove 'export' keyword before function/const/let/var/class
    source = re.sub(r'^export\s+(function|const|let|var|class)\s', r'\1 ', source, flags=re.MULTILINE)

    # Remove bare 'export { ... }' blocks
    source = re.sub(r'^export\s*\{[^}]*\};?\s*$', '', source, flags=re.MULTILINE)

    return source


class LoadoutJSBridge:
    """Embeds V8 via PyMiniRacer and loads the loadout calculation JS files.

    Usage:
        bridge = LoadoutJSBridge()
        result = bridge.call("calculateTotalDamage", weapon_data, enhancers, ...)
    """

    def __init__(self, js_path: str | Path | None = None):
        try:
            from py_mini_racer import MiniRacer
        except ImportError:
            raise RuntimeError(
                "py-mini-racer is required for the loadout calculator. "
                "Install it with: pip install py-mini-racer"
            )

        self._ctx = MiniRacer()
        self._js_path = Path(js_path) if js_path else DEFAULT_JS_PATH
        self._load_files()

    def _load_files(self):
        """Load JS files into the V8 context in dependency order."""
        # Inject utility functions not bundled in the loadout JS files
        self._ctx.eval("""
function hasItemTag(currentName, tag) {
  if (!currentName) return false;
  var match = currentName.match(/^(.*) \\((.*)\\)$/);
  var existingTags = match ? match[2].split(',') : [];
  return existingTags.includes(tag);
}
""")

        for filename in JS_FILES:
            filepath = self._js_path / filename
            if not filepath.exists():
                log.warning("%s not found, skipping", filepath)
                continue

            source = filepath.read_text(encoding="utf-8")
            source = _strip_esm(source)

            try:
                self._ctx.eval(source)
            except Exception as e:
                log.error("Error loading %s: %s", filename, e)
                raise

        log.info("Loaded %d JS files from %s", len(JS_FILES), self._js_path)

    def call(self, fn_name: str, *args):
        """Call a JS function by name with the given arguments.

        Arguments are JSON-serialized and passed to the function.
        Return values are round-tripped through JSON so JS objects
        come back as plain Python dicts/lists/primitives.
        """
        args_json = json.dumps(args, default=str)
        expr = f"JSON.stringify({fn_name}(...{args_json}))"
        try:
            raw = self._ctx.eval(expr)
            return json.loads(raw) if isinstance(raw, str) else raw
        except Exception as e:
            log.error("Error calling %s: %s", fn_name, e)
            return None

    def eval(self, expression: str):
        """Evaluate an arbitrary JS expression."""
        return self._ctx.eval(expression)
