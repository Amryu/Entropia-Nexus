"""Parity tests: generated Python vs V8-executed JS.

These compare `client/loadout/generated/*.py` against the original JS
executed in a local V8 context. They're the safety net that catches
drift in the transpiler or runtime shim — run them whenever either is
touched.

Requirements (test-time only; not shipped with the client):
    - Node.js on PATH (for the transpile step)
    - `pip install py-mini-racer` (for the V8 reference side)

Both are optional — the test class is skipped cleanly if missing.
"""

from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOADOUTS_FIXTURE = REPO_ROOT / "client" / "data" / "cache" / "loadouts.json"


def _normalize(value):
    """Collapse NaN/Infinity/UNDEFINED to None so JSON dumps match V8."""
    from client.loadout.generated._runtime import js_sanitize_for_json
    return js_sanitize_for_json(value)


def _json_stable(value) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _build_v8_bridge():
    """Spin up a local V8 context with the loadout JS files loaded.

    Lives here (not in production code) so the client package itself
    does not ship `py-mini-racer`. Mirrors the legacy `LoadoutJSBridge`
    loader from before the transpiler existed.
    """
    import json as _json
    import re as _re

    from py_mini_racer import MiniRacer

    js_root = REPO_ROOT / "nexus" / "src" / "lib" / "utils"
    files = ["loadoutCalculations.js", "loadoutEffects.js", "loadoutEvaluator.js"]

    def strip_esm(source: str) -> str:
        namespace_aliases = [
            m.group(1)
            for m in _re.finditer(
                r'^import\s+\*\s+as\s+(\w+)\s+from\s+[\'"][^\'"]*[\'"];?\s*$',
                source,
                flags=_re.MULTILINE,
            )
        ]
        source = _re.sub(
            r'^import\s+\{[^}]*\}\s+from\s+[\'"][^\'"]*[\'"];?\s*$', '', source, flags=_re.MULTILINE
        )
        source = _re.sub(
            r'^import\s+\w+\s+from\s+[\'"][^\'"]*[\'"];?\s*$', '', source, flags=_re.MULTILINE
        )
        source = _re.sub(
            r'^import\s+\*\s+as\s+\w+\s+from\s+[\'"][^\'"]*[\'"];?\s*$', '', source, flags=_re.MULTILINE
        )
        for alias in namespace_aliases:
            source = _re.sub(rf"\b{alias}\.", "", source)
        source = _re.sub(r"^export\s+default\s+", "", source, flags=_re.MULTILINE)
        source = _re.sub(
            r"^export\s+(function|const|let|var|class)\s", r"\1 ", source, flags=_re.MULTILINE
        )
        source = _re.sub(r"^export\s*\{[^}]*\};?\s*$", "", source, flags=_re.MULTILINE)
        return source

    ctx = MiniRacer()
    ctx.eval("""
function hasItemTag(currentName, tag) {
  if (!currentName) return false;
  var match = currentName.match(/^(.*) \\((.*)\\)$/);
  var existingTags = match ? match[2].split(',') : [];
  return existingTags.includes(tag);
}
""")
    for name in files:
        source = (js_root / name).read_text(encoding="utf-8")
        ctx.eval(strip_esm(source))

    class Bridge:
        def call(self, fn_name, *args):
            args_json = _json.dumps(args, default=str)
            raw = ctx.eval(f"JSON.stringify({fn_name}(...{args_json}))")
            return _json.loads(raw) if isinstance(raw, str) else raw

        def eval(self, expression):
            return ctx.eval(expression)

    return Bridge()


@unittest.skipUnless(shutil.which("node"), "node not on PATH")
class TranspileParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import py_mini_racer  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("py-mini-racer not installed (pip install py-mini-racer)")

        from client.loadout.transpile import ensure_transpiled
        ensure_transpiled(force=True)

        cls.bridge = _build_v8_bridge()

        from client.loadout.generated import (
            item_types as py_it,
            loadout_calculations as py_lc,
            loadout_effects as py_le,
            loadout_evaluator as py_lv,
        )
        cls.py_it = py_it
        cls.py_lc = py_lc
        cls.py_le = py_le
        cls.py_lv = py_lv

    def _assert_parity(self, label: str, fn_name: str, py_fn, *args):
        js_result = self.bridge.call(fn_name, *args)
        py_result = py_fn(*args)
        js_s = _json_stable(js_result)
        py_s = _json_stable(_normalize(py_result))
        self.assertEqual(js_s, py_s, msg=f"{label}: divergence\n  js={js_s[:400]}\n  py={py_s[:400]}")

    def test_clamp(self):
        for args in [(5, 0, 10), (-1, 0, 10), (15, 0, 10), (5.5, 0, 5), (0, 0, 0)]:
            self._assert_parity(f"clamp{args}", "clamp", self.py_lc.clamp, *args)

    def test_build_effect_caps_empty(self):
        self._assert_parity("buildEffectCaps([])", "buildEffectCaps", self.py_le.buildEffectCaps, [])

    def test_build_effect_caps_limits(self):
        catalog = [
            {"Name": "Damage Done Increased",
             "Properties": {"Limits": {"Item": 50, "Action": 100, "Total": 150}}},
            {"Name": "Health Added",
             "Properties": {"Description": "equipment cap: 200 total cap: 400"}},
            {"Name": "Crit Chance Added", "Properties": {}},
        ]
        self._assert_parity(
            "buildEffectCaps limits+desc", "buildEffectCaps", self.py_le.buildEffectCaps, catalog
        )

    def test_summarize_effects_simple(self):
        catalog = [{"Name": "Damage Done Increased",
                    "Properties": {"Limits": {"Item": 50, "Action": 100, "Total": 150}}}]
        arg = {
            "itemEffects": [{"Name": "Damage Done Increased", "Values": {"Strength": 5}}],
            "actionEffects": [],
            "bonusEffects": [],
        }
        opts = {"effectsCatalog": catalog, "effectCaps": {}}
        self._assert_parity(
            "summarizeEffects simple", "summarizeEffects", self.py_le.summarizeEffects, arg, opts
        )

    def test_evaluate_loadout_empty_inputs(self):
        opts = {"effectsCatalog": [], "effectCaps": {}}
        for loadout in [None, {}, {"Gear": {}}, {"Gear": {"Weapon": {"Name": "A"}}}]:
            with self.subTest(loadout=loadout):
                js = self.bridge.call("evaluateLoadout", loadout, {}, opts)
                py = self.py_lv.evaluateLoadout(loadout, {}, opts)
                self.assertEqual(_json_stable(js), _json_stable(_normalize(py)))

    @unittest.skipUnless(LOADOUTS_FIXTURE.exists(), "loadouts.json fixture missing")
    def test_evaluate_loadout_real_fixtures(self):
        """Feed the user's cached loadouts through both paths."""
        with LOADOUTS_FIXTURE.open(encoding="utf-8") as f:
            loadouts = json.load(f)
        opts = {"effectsCatalog": [], "effectCaps": {}}
        for i, loadout in enumerate(loadouts):
            with self.subTest(index=i):
                js = self.bridge.call("evaluateLoadout", loadout, {}, opts)
                py = self.py_lv.evaluateLoadout(loadout, {}, opts)
                self.assertEqual(_json_stable(js), _json_stable(_normalize(py)))


@unittest.skipUnless(shutil.which("node"), "node not on PATH")
class ItemTypesParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from py_mini_racer import MiniRacer  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("py-mini-racer not installed")

        from client.loadout.transpile import ensure_transpiled
        ensure_transpiled(force=True)

        from py_mini_racer import MiniRacer
        src_path = REPO_ROOT / "common" / "itemTypes.js"
        source = src_path.read_text(encoding="utf-8")
        import re as _re
        source = _re.sub(
            r"^export\s+(function|const|let|var|class)\s",
            r"\1 ",
            source,
            flags=_re.MULTILINE,
        )
        cls._ctx = MiniRacer()
        cls._ctx.eval(source)

        from client.loadout.generated import item_types as py_it
        cls.py_it = py_it

    def test_is_percent_markup_type(self):
        cases = [
            ("Weapon", "Korss H400", None),
            ("Attachment", "Scope A103", None),
            ("Material", "Sweat", None),
            ("Material", "Sweat", "Ore"),
            ("Consumable", "Health Potion", None),
            ("Blueprint", "Weapon Blueprint", None),
        ]
        for (t, name, sub) in cases:
            with self.subTest(args=(t, name, sub)):
                args_js = ", ".join(json.dumps(x) for x in (t, name, sub))
                js_result = self._ctx.eval(f"isPercentMarkupType({args_js})")
                py_result = self.py_it.isPercentMarkupType(t, name, sub)
                self.assertEqual(bool(js_result), bool(py_result))


if __name__ == "__main__":
    unittest.main()
