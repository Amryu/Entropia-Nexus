"""JS semantics shim used by transpiled loadout modules.

The transpiler emits calls into this module wherever JS and Python disagree:
truthiness, `undefined` vs `None`, Array.prototype methods, `Number()`
coercion, optional chaining, object spread, template literals, and regex.

Keep this file dependency-free (stdlib only) and self-contained: the
packaging step copies it verbatim into `client/loadout/generated/_runtime.py`
so frozen builds can run without `client.loadout.transpile` on sys.path.
"""

from __future__ import annotations

import inspect
import math
import re
from functools import cmp_to_key
from typing import Any, Callable, Iterable


def js_sanitize_for_json(value: Any) -> Any:
    """Walk a value tree and replace NaN/Infinity/UNDEFINED with None so
    `json.dumps` matches V8's `JSON.stringify` (which writes them as `null`).
    """
    if value is UNDEFINED:
        return None
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, dict):
        return {k: js_sanitize_for_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [js_sanitize_for_json(v) for v in value]
    if isinstance(value, tuple):
        return [js_sanitize_for_json(v) for v in value]
    return value


def _call_with_arity(fn: Callable, *args: Any) -> Any:
    """Call `fn` with as many leading args as its signature accepts.

    JS callbacks commonly ignore trailing arguments (e.g. `forEach` is
    spec'd to pass `(value, key, map)` but most callbacks take only
    `(value)`). Python errors on extra args, so trim to the callable's
    arity.
    """
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return fn(*args)
    params = sig.parameters
    if any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params.values()):
        return fn(*args)
    positional = [
        p
        for p in params.values()
        if p.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    take = min(len(args), len(positional))
    return fn(*args[:take])


class _Undefined:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "undefined"

    def __bool__(self) -> bool:
        return False

    def __eq__(self, other: object) -> bool:
        return other is self or other is None

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash("__js_undefined__")


UNDEFINED = _Undefined()


def is_undefined(value: Any) -> bool:
    return value is UNDEFINED


def is_nullish(value: Any) -> bool:
    """JS `value == null` — true for both `null` and `undefined`."""
    return value is None or value is UNDEFINED


def js_truthy(value: Any) -> bool:
    """JavaScript truthiness.

    Falsy: false, 0, -0, 0n, "", null, undefined, NaN.
    Everything else — including [] and {} — is truthy.
    """
    if value is None or value is UNDEFINED or value is False:
        return False
    if isinstance(value, (int, float)):
        if value == 0:
            return False
        if isinstance(value, float) and math.isnan(value):
            return False
        return True
    if isinstance(value, str):
        return len(value) > 0
    return True


def js_number(value: Any) -> Any:
    """Number() coercion.

    Preserves int-ness for whole values so JSON round-trips match V8's
    output: JS `Number(50)` serialises as `50`, not `50.0`. Returns NaN
    for anything non-convertible.
    """
    if value is None:
        return 0
    if value is UNDEFINED:
        return float("nan")
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        s = value.strip()
        if s == "":
            return 0
        try:
            return int(s)
        except ValueError:
            pass
        try:
            return float(s)
        except ValueError:
            return float("nan")
    if isinstance(value, (list, tuple)):
        if len(value) == 0:
            return 0
        if len(value) == 1:
            return js_number(value[0])
        return float("nan")
    return float("nan")


def _int_if_whole(x: Any) -> Any:
    """JS numbers are all doubles, but JSON.stringify emits `50` not `50.0`.

    Collapse float results that landed on a whole value back to int so
    downstream JSON matches V8's output.
    """
    if isinstance(x, float) and not math.isnan(x) and not math.isinf(x) and x.is_integer():
        return int(x)
    return x


def js_add(a: Any, b: Any) -> Any:
    """JS `+`. String concatenation if either operand is a string; else numeric."""
    if isinstance(a, str) or isinstance(b, str):
        return _js_to_string(a) + _js_to_string(b)
    return _int_if_whole(_as_num(a) + _as_num(b))


def js_sub(a: Any, b: Any) -> Any:
    return _int_if_whole(_as_num(a) - _as_num(b))


def js_mul(a: Any, b: Any) -> Any:
    return _int_if_whole(_as_num(a) * _as_num(b))


def js_div(a: Any, b: Any) -> Any:
    x, y = _as_num(a), _as_num(b)
    if isinstance(y, float) and math.isnan(y):
        return float("nan")
    if y == 0:
        if isinstance(x, float) and math.isnan(x):
            return float("nan")
        if x == 0:
            return float("nan")
        return float("inf") if x > 0 else float("-inf")
    return _int_if_whole(x / y)


def js_mod(a: Any, b: Any) -> Any:
    x, y = _as_num(a), _as_num(b)
    if y == 0:
        return float("nan")
    # JS `%` uses truncation toward zero, not floor like Python.
    result = math.fmod(x, y)
    if isinstance(x, int) and isinstance(y, int) and not isinstance(result, float):
        return int(result)
    # math.fmod returns float; preserve int-ness when exact
    if result == int(result):
        return int(result)
    return result


def js_pow(a: Any, b: Any) -> Any:
    return _int_if_whole(_as_num(a) ** _as_num(b))


def _as_num(v: Any) -> Any:
    if v is None or v is UNDEFINED:
        return 0 if v is None else float("nan")
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        return js_number(v)
    return float("nan")


def _js_to_string(v: Any) -> str:
    if v is None:
        return "null"
    if v is UNDEFINED:
        return "undefined"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        if math.isnan(v):
            return "NaN"
        if math.isinf(v):
            return "Infinity" if v > 0 else "-Infinity"
        if v.is_integer():
            return str(int(v))
        return repr(v)
    return str(v)


def js_is_finite(value: Any) -> bool:
    """`Number.isFinite` — true only for real finite numbers, no coercion."""
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return not (math.isnan(float(value)) or math.isinf(float(value)))
    return False


def js_is_nan(value: Any) -> bool:
    if isinstance(value, float):
        return math.isnan(value)
    return False


def js_array(value: Any) -> list:
    """Coerce `null`/`undefined` to [] so `(list || []).forEach(...)` works."""
    if is_nullish(value):
        return []
    if isinstance(value, list):
        return value
    return list(value) if isinstance(value, Iterable) and not isinstance(value, (str, dict)) else []


def js_is_array(value: Any) -> bool:
    return isinstance(value, list)


def js_find(arr: Any, predicate: Callable) -> Any:
    """Array.prototype.find — returns UNDEFINED on miss (not None)."""
    arr = js_array(arr)
    for i, item in enumerate(arr):
        if js_truthy(_call_with_arity(predicate, item, i, arr)):
            return item
    return UNDEFINED


def js_find_index(arr: Any, predicate: Callable) -> int:
    arr = js_array(arr)
    for i, item in enumerate(arr):
        if js_truthy(_call_with_arity(predicate, item, i, arr)):
            return i
    return -1


def js_filter(arr: Any, predicate: Callable) -> list:
    arr = js_array(arr)
    return [
        item for i, item in enumerate(arr)
        if js_truthy(_call_with_arity(predicate, item, i, arr))
    ]


def js_map(arr: Any, fn: Callable) -> list:
    arr = js_array(arr)
    return [_call_with_arity(fn, item, i, arr) for i, item in enumerate(arr)]


def js_for_each(arr: Any, fn: Callable) -> None:
    arr = js_array(arr)
    for i, item in enumerate(arr):
        _call_with_arity(fn, item, i, arr)


def js_some(arr: Any, predicate: Callable) -> bool:
    arr = js_array(arr)
    return any(
        js_truthy(_call_with_arity(predicate, item, i, arr))
        for i, item in enumerate(arr)
    )


def js_every(arr: Any, predicate: Callable) -> bool:
    arr = js_array(arr)
    return all(
        js_truthy(_call_with_arity(predicate, item, i, arr))
        for i, item in enumerate(arr)
    )


def js_includes(arr: Any, target: Any) -> bool:
    if isinstance(arr, str):
        return target in arr if isinstance(target, str) else False
    return target in js_array(arr)


def js_index_of(arr: Any, target: Any) -> int:
    try:
        return js_array(arr).index(target)
    except ValueError:
        return -1


def js_sort(arr: list, comparator: Callable[[Any, Any], Any] | None = None) -> list:
    """Array.prototype.sort — mutates `arr` in place and returns it.

    With a comparator, uses cmp_to_key. Without, sorts by string
    representation (JS default).
    """
    if comparator is None:
        arr.sort(key=lambda v: str(v) if v is not None and v is not UNDEFINED else "")
        return arr

    def _cmp(a: Any, b: Any) -> int:
        result = comparator(a, b)
        if result is None or result is UNDEFINED:
            return 0
        if isinstance(result, (int, float)):
            if result < 0:
                return -1
            if result > 0:
                return 1
            return 0
        return 0

    arr.sort(key=cmp_to_key(_cmp))
    return arr


def js_slice(arr: Any, start: Any = UNDEFINED, end: Any = UNDEFINED) -> list:
    source = js_array(arr)
    length = len(source)
    s = 0 if is_undefined(start) or start is None else int(start)
    e = length if is_undefined(end) or end is None else int(end)
    if s < 0:
        s = max(0, length + s)
    if e < 0:
        e = max(0, length + e)
    return source[s:e]


def js_concat(*arrs: Any) -> list:
    out: list = []
    for a in arrs:
        if isinstance(a, list):
            out.extend(a)
        else:
            out.append(a)
    return out


def js_get(obj: Any, key: Any) -> Any:
    """Member access with JS semantics: missing → UNDEFINED, nullish base → UNDEFINED."""
    if is_nullish(obj):
        return UNDEFINED
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        return UNDEFINED
    if isinstance(obj, list):
        if isinstance(key, str) and key == "length":
            return len(obj)
        try:
            idx = int(key)
        except (TypeError, ValueError):
            return UNDEFINED
        if 0 <= idx < len(obj):
            return obj[idx]
        return UNDEFINED
    if isinstance(obj, str):
        if key == "length":
            return len(obj)
        try:
            idx = int(key)
            return obj[idx] if 0 <= idx < len(obj) else UNDEFINED
        except (TypeError, ValueError):
            return UNDEFINED
    return getattr(obj, str(key), UNDEFINED)


def js_optional(obj: Any, key: Any) -> Any:
    """Optional-chain member access (`obj?.key`).

    If `obj` is nullish, returns UNDEFINED and short-circuits the rest of
    the chain. Otherwise behaves like `js_get`.
    """
    if is_nullish(obj):
        return UNDEFINED
    return js_get(obj, key)


def js_coalesce(*values: Any) -> Any:
    """Nullish coalescing chain: returns the first non-nullish value."""
    result: Any = UNDEFINED
    for value in values:
        result = value
        if not is_nullish(value):
            return value
    return result


def js_logical_or(*values: Any) -> Any:
    """`a || b || c` — returns first truthy, else the last value."""
    result: Any = None
    for value in values:
        result = value
        if js_truthy(value):
            return value
    return result


def js_logical_and(*values: Any) -> Any:
    """`a && b && c` — returns first falsy, else the last value."""
    result: Any = True
    for value in values:
        result = value
        if not js_truthy(value):
            return value
    return result


def js_spread_object(*parts: Any) -> dict:
    """`{...a, ...b, key: value}` — merge dicts left-to-right."""
    out: dict = {}
    for part in parts:
        if is_nullish(part):
            continue
        if isinstance(part, dict):
            out.update(part)
    return out


def js_spread_array(*parts: Any) -> list:
    """`[...a, ...b, x]` — concat iterables left-to-right."""
    out: list = []
    for part in parts:
        if is_nullish(part):
            continue
        if isinstance(part, list):
            out.extend(part)
        elif isinstance(part, (tuple, set)):
            out.extend(list(part))
        else:
            out.append(part)
    return out


def js_template(*parts: Any) -> str:
    """Template literal join. Called as `js_template(s0, expr0, s1, expr1, ...)`."""
    chunks: list[str] = []
    for part in parts:
        if is_nullish(part):
            chunks.append("undefined" if is_undefined(part) else "null")
        elif isinstance(part, bool):
            chunks.append("true" if part else "false")
        elif isinstance(part, float):
            if math.isnan(part):
                chunks.append("NaN")
            elif math.isinf(part):
                chunks.append("Infinity" if part > 0 else "-Infinity")
            elif part.is_integer():
                chunks.append(str(int(part)))
            else:
                chunks.append(repr(part))
        else:
            chunks.append(str(part))
    return "".join(chunks)


def js_typeof(value: Any) -> str:
    if value is UNDEFINED:
        return "undefined"
    if value is None:
        return "object"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if callable(value):
        return "function"
    return "object"


def js_object_keys(obj: Any) -> list:
    if is_nullish(obj) or not isinstance(obj, dict):
        return []
    return list(obj.keys())


def js_object_values(obj: Any) -> list:
    if is_nullish(obj) or not isinstance(obj, dict):
        return []
    return list(obj.values())


def js_object_entries(obj: Any) -> list:
    if is_nullish(obj) or not isinstance(obj, dict):
        return []
    return [[k, v] for k, v in obj.items()]


def js_object_from_entries(entries: Any) -> dict:
    out: dict = {}
    for pair in js_array(entries):
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            out[pair[0]] = pair[1]
    return out


def js_object_assign(target: Any, *sources: Any) -> dict:
    if not isinstance(target, dict):
        target = {}
    for s in sources:
        if isinstance(s, dict):
            target.update(s)
    return target


def js_array_from(iterable: Any, map_fn: Callable | None = None) -> list:
    if is_nullish(iterable):
        return []
    items = list(iterable) if hasattr(iterable, "__iter__") and not isinstance(iterable, (str, dict)) else []
    if isinstance(iterable, str):
        items = list(iterable)
    if isinstance(iterable, dict) and "length" in iterable:
        length = int(iterable.get("length", 0))
        items = [iterable.get(i) for i in range(length)]
    if map_fn is None:
        return items
    return [_call_with_arity(map_fn, v, i) for i, v in enumerate(items)]


def js_array_of(*items: Any) -> list:
    return list(items)


class JsRegExp:
    """Minimal `RegExp` shim covering `.test()`, `.exec()`, and String.match.

    Flags: 'i' (IGNORECASE), 'm' (MULTILINE), 's' (DOTALL), 'g' (global).
    """

    def __init__(self, pattern: str, flags: str = ""):
        self.source = pattern
        self.flags = flags
        py_flags = 0
        if "i" in flags:
            py_flags |= re.IGNORECASE
        if "m" in flags:
            py_flags |= re.MULTILINE
        if "s" in flags:
            py_flags |= re.DOTALL
        self._py_pattern = re.compile(_js_regex_to_python(pattern), py_flags)
        self._global = "g" in flags
        self.last_index = 0

    def test(self, string: Any) -> bool:
        if is_nullish(string):
            return False
        return self._py_pattern.search(str(string)) is not None

    def exec(self, string: Any):
        if is_nullish(string):
            return None
        m = self._py_pattern.search(str(string))
        if m is None:
            return None
        return [m.group(0), *m.groups()]


def _js_regex_to_python(pattern: str) -> str:
    """Best-effort translation of a JS regex body to a Python-compatible one.

    Handles the subset seen in the loadout JS files: character classes,
    escapes, groups. Complex JS-only features (lookbehind variants, \\p{...})
    are not covered and will surface as re.error — caller can fall back to
    LLM-translated helper functions for those.
    """
    return pattern.replace(r"\d", r"\d").replace(r"\w", r"\w").replace(r"\s", r"\s")


def js_string_match(string: Any, pattern: Any):
    """`str.match(regex)` — returns list of groups on hit, None on miss."""
    if is_nullish(string):
        return None
    if isinstance(pattern, JsRegExp):
        return pattern.exec(string)
    if isinstance(pattern, str):
        m = re.search(pattern, str(string))
        if m is None:
            return None
        return [m.group(0), *m.groups()]
    return None


def js_string_replace(string: Any, pattern: Any, replacement: Any) -> str:
    if is_nullish(string):
        return ""
    s = str(string)
    repl = "" if is_nullish(replacement) else str(replacement)
    if isinstance(pattern, JsRegExp):
        count = 0 if pattern._global else 1
        return pattern._py_pattern.sub(repl, s, count=count)
    if isinstance(pattern, str):
        return s.replace(pattern, repl, 1)
    return s


def js_string_split(string: Any, separator: Any) -> list:
    if is_nullish(string):
        return []
    s = str(string)
    if is_nullish(separator):
        return [s]
    if isinstance(separator, JsRegExp):
        return separator._py_pattern.split(s)
    return s.split(str(separator))


def js_string_includes(string: Any, substr: Any) -> bool:
    if is_nullish(string) or is_nullish(substr):
        return False
    return str(substr) in str(string)


def js_math_max(*values: Any) -> Any:
    nums = [js_number(v) for v in values]
    if not nums:
        return float("-inf")
    if any(isinstance(n, float) and math.isnan(n) for n in nums):
        return float("nan")
    return max(nums)


def js_math_min(*values: Any) -> Any:
    nums = [js_number(v) for v in values]
    if not nums:
        return float("inf")
    if any(isinstance(n, float) and math.isnan(n) for n in nums):
        return float("nan")
    return min(nums)


def js_math_floor(value: Any) -> Any:
    n = js_number(value)
    if isinstance(n, float):
        if math.isnan(n) or math.isinf(n):
            return n
    return math.floor(n)


def js_math_ceil(value: Any) -> Any:
    n = js_number(value)
    if isinstance(n, float):
        if math.isnan(n) or math.isinf(n):
            return n
    return math.ceil(n)


def js_math_round(value: Any) -> Any:
    """JS Math.round — ties go toward +Infinity, not banker's rounding."""
    n = js_number(value)
    if isinstance(n, float):
        if math.isnan(n) or math.isinf(n):
            return n
    return math.floor(n + 0.5)


def js_math_abs(value: Any) -> Any:
    return abs(js_number(value))


def js_math_sqrt(value: Any) -> Any:
    n = js_number(value)
    if isinstance(n, float):
        if math.isnan(n):
            return n
    if n < 0:
        return float("nan")
    return _int_if_whole(math.sqrt(n))


def js_math_pow(a: Any, b: Any) -> Any:
    return js_pow(a, b)


def js_math_imul(a: Any, b: Any) -> int:
    """Math.imul — 32-bit signed integer multiplication."""
    x = int(js_number(a)) & 0xFFFFFFFF
    y = int(js_number(b)) & 0xFFFFFFFF
    result = (x * y) & 0xFFFFFFFF
    if result >= 0x80000000:
        result -= 0x100000000
    return result


def js_math_random() -> float:
    import random
    return random.random()


class JsSet:
    """Minimal Set shim covering add/has/delete/size/iteration."""

    def __init__(self, iterable: Any = None):
        self._items: list = []
        self._lookup: set = set()
        if iterable is not None and not is_nullish(iterable):
            for item in js_array(iterable):
                self.add(item)

    @property
    def size(self) -> int:
        return len(self._items)

    def add(self, value: Any) -> "JsSet":
        key = self._key(value)
        if key not in self._lookup:
            self._lookup.add(key)
            self._items.append(value)
        return self

    def has(self, value: Any) -> bool:
        return self._key(value) in self._lookup

    def delete(self, value: Any) -> bool:
        key = self._key(value)
        if key in self._lookup:
            self._lookup.remove(key)
            self._items = [i for i in self._items if self._key(i) != key]
            return True
        return False

    def clear(self) -> None:
        self._items.clear()
        self._lookup.clear()

    def forEach(self, callback: Callable) -> None:
        for value in list(self._items):
            _call_with_arity(callback, value, value, self)

    def values(self) -> list:
        return list(self._items)

    def keys(self) -> list:
        return list(self._items)

    def __iter__(self):
        return iter(list(self._items))

    @staticmethod
    def _key(value: Any):
        try:
            hash(value)
            return ("h", value)
        except TypeError:
            return ("r", id(value))


_ARRAY_METHODS = {
    "filter": js_filter,
    "find": js_find,
    "findIndex": js_find_index,
    "map": js_map,
    "forEach": js_for_each,
    "some": js_some,
    "every": js_every,
    "includes": js_includes,
    "indexOf": js_index_of,
    "slice": js_slice,
    "concat": js_concat,
    "sort": js_sort,
}

_STRING_METHODS = {
    "match": js_string_match,
    "replace": js_string_replace,
    "split": js_string_split,
    "includes": js_string_includes,
}


def js_call(receiver: Any, method: str, *args: Any) -> Any:
    """Dynamic method dispatch: route `receiver.method(args)` to the right shim.

    Handles lists (JS arrays), strings, dicts, and wrapper classes (JsSet,
    JsMap, JsRegExp). Falls back to attribute lookup for everything else.
    """
    if isinstance(receiver, list):
        if method == "push":
            for a in args:
                receiver.append(a)
            return len(receiver)
        if method == "pop":
            return receiver.pop() if receiver else UNDEFINED
        if method == "shift":
            return receiver.pop(0) if receiver else UNDEFINED
        if method == "unshift":
            for a in reversed(args):
                receiver.insert(0, a)
            return len(receiver)
        if method == "join":
            sep = "," if not args or is_nullish(args[0]) else str(args[0])
            parts = []
            for v in receiver:
                if is_nullish(v):
                    parts.append("")
                elif isinstance(v, bool):
                    parts.append("true" if v else "false")
                elif isinstance(v, float) and v.is_integer():
                    parts.append(str(int(v)))
                else:
                    parts.append(str(v))
            return sep.join(parts)
        if method == "reverse":
            receiver.reverse()
            return receiver
        if method in _ARRAY_METHODS:
            return _ARRAY_METHODS[method](receiver, *args)
    if isinstance(receiver, str):
        if method == "toLowerCase":
            return receiver.lower()
        if method == "toUpperCase":
            return receiver.upper()
        if method == "trim":
            return receiver.strip()
        if method == "trimStart":
            return receiver.lstrip()
        if method == "trimEnd":
            return receiver.rstrip()
        if method == "startsWith":
            return receiver.startswith(str(args[0])) if args else False
        if method == "endsWith":
            return receiver.endswith(str(args[0])) if args else False
        if method == "charAt":
            idx = int(args[0]) if args else 0
            return receiver[idx] if 0 <= idx < len(receiver) else ""
        if method == "indexOf":
            if not args:
                return -1
            return receiver.find(str(args[0]))
        if method == "slice":
            start = int(args[0]) if args and not is_nullish(args[0]) else 0
            end = int(args[1]) if len(args) > 1 and not is_nullish(args[1]) else len(receiver)
            return receiver[start:end]
        if method in _STRING_METHODS:
            return _STRING_METHODS[method](receiver, *args)
    if isinstance(receiver, dict):
        attr = receiver.get(method, UNDEFINED)
        if callable(attr):
            return attr(*args)
        return UNDEFINED
    if is_nullish(receiver):
        return UNDEFINED
    fn = getattr(receiver, method, None)
    if callable(fn):
        return fn(*args)
    return UNDEFINED


class JsMap:
    """Minimal Map shim covering get/set/has/delete/size/iteration."""

    def __init__(self, iterable: Any = None):
        self._data: dict = {}
        self._order: list = []
        if iterable is not None and not is_nullish(iterable):
            for pair in js_array(iterable):
                if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                    self.set(pair[0], pair[1])

    @property
    def size(self) -> int:
        return len(self._order)

    def get(self, key: Any) -> Any:
        if key in self._data:
            return self._data[key]
        return UNDEFINED

    def set(self, key: Any, value: Any) -> "JsMap":
        if key not in self._data:
            self._order.append(key)
        self._data[key] = value
        return self

    def has(self, key: Any) -> bool:
        return key in self._data

    def delete(self, key: Any) -> bool:
        if key in self._data:
            del self._data[key]
            self._order = [k for k in self._order if k != key]
            return True
        return False

    def clear(self) -> None:
        self._data.clear()
        self._order.clear()

    def forEach(self, callback: Callable) -> None:
        for key in list(self._order):
            value = self._data.get(key)
            _call_with_arity(callback, value, key, self)

    def values(self) -> list:
        return [self._data[k] for k in self._order]

    def keys(self) -> list:
        return list(self._order)

    def entries(self) -> list:
        return [[k, self._data[k]] for k in self._order]

    def __iter__(self):
        return iter(self.entries())
