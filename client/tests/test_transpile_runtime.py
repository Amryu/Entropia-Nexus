import math
import unittest

from client.loadout.transpile.runtime import (
    UNDEFINED,
    JsMap,
    JsRegExp,
    JsSet,
    is_nullish,
    is_undefined,
    js_array,
    js_coalesce,
    js_concat,
    js_every,
    js_filter,
    js_find,
    js_find_index,
    js_for_each,
    js_get,
    js_includes,
    js_index_of,
    js_is_array,
    js_is_finite,
    js_is_nan,
    js_logical_and,
    js_logical_or,
    js_map,
    js_math_abs,
    js_math_ceil,
    js_math_floor,
    js_math_max,
    js_math_min,
    js_math_round,
    js_number,
    js_object_entries,
    js_object_keys,
    js_object_values,
    js_optional,
    js_slice,
    js_some,
    js_sort,
    js_spread_array,
    js_spread_object,
    js_string_includes,
    js_string_match,
    js_string_replace,
    js_string_split,
    js_template,
    js_truthy,
    js_typeof,
)


class UndefinedTests(unittest.TestCase):
    def test_singleton(self):
        from client.loadout.transpile.runtime import _Undefined
        self.assertIs(_Undefined(), UNDEFINED)

    def test_bool_is_false(self):
        self.assertFalse(bool(UNDEFINED))

    def test_equals_none_not_false(self):
        self.assertTrue(UNDEFINED == None)  # noqa: E711
        self.assertFalse(UNDEFINED == False)  # noqa: E712
        self.assertFalse(UNDEFINED == 0)

    def test_is_undefined_distinct_from_none(self):
        self.assertTrue(is_undefined(UNDEFINED))
        self.assertFalse(is_undefined(None))

    def test_is_nullish_accepts_both(self):
        self.assertTrue(is_nullish(None))
        self.assertTrue(is_nullish(UNDEFINED))
        self.assertFalse(is_nullish(0))
        self.assertFalse(is_nullish(""))
        self.assertFalse(is_nullish([]))


class TruthinessTests(unittest.TestCase):
    def test_falsy_values(self):
        for v in [False, 0, 0.0, -0.0, "", None, UNDEFINED, float("nan")]:
            self.assertFalse(js_truthy(v), msg=f"{v!r} should be falsy")

    def test_truthy_values(self):
        for v in [True, 1, -1, 0.5, "0", " ", [], {}, [0], {"a": 1}, object()]:
            self.assertTrue(js_truthy(v), msg=f"{v!r} should be truthy")


class NumberCoercionTests(unittest.TestCase):
    def test_number_of_primitives(self):
        self.assertEqual(js_number(5), 5.0)
        self.assertEqual(js_number("5"), 5.0)
        self.assertEqual(js_number("  3.5  "), 3.5)
        self.assertEqual(js_number(""), 0.0)
        self.assertEqual(js_number(None), 0.0)
        self.assertEqual(js_number(True), 1.0)
        self.assertEqual(js_number(False), 0.0)

    def test_number_of_undefined_is_nan(self):
        self.assertTrue(math.isnan(js_number(UNDEFINED)))

    def test_number_of_non_numeric_string_is_nan(self):
        self.assertTrue(math.isnan(js_number("abc")))

    def test_number_of_arrays(self):
        self.assertEqual(js_number([]), 0.0)
        self.assertEqual(js_number([7]), 7.0)
        self.assertTrue(math.isnan(js_number([1, 2])))

    def test_is_finite_no_coercion(self):
        self.assertTrue(js_is_finite(5))
        self.assertTrue(js_is_finite(5.5))
        self.assertFalse(js_is_finite(float("nan")))
        self.assertFalse(js_is_finite(float("inf")))
        self.assertFalse(js_is_finite("5"))
        self.assertFalse(js_is_finite(None))
        self.assertFalse(js_is_finite(True))

    def test_is_nan(self):
        self.assertTrue(js_is_nan(float("nan")))
        self.assertFalse(js_is_nan(5))
        self.assertFalse(js_is_nan("nan"))


class ArrayMethodTests(unittest.TestCase):
    def test_js_array_nullish_coerce(self):
        self.assertEqual(js_array(None), [])
        self.assertEqual(js_array(UNDEFINED), [])
        self.assertEqual(js_array([1, 2]), [1, 2])

    def test_find_returns_undefined_on_miss(self):
        result = js_find([1, 2, 3], lambda x: x > 10)
        self.assertIs(result, UNDEFINED)

    def test_find_returns_element(self):
        result = js_find([1, 2, 3], lambda x: x > 1)
        self.assertEqual(result, 2)

    def test_find_on_null(self):
        self.assertIs(js_find(None, lambda x: True), UNDEFINED)

    def test_find_index(self):
        self.assertEqual(js_find_index([1, 2, 3], lambda x: x == 2), 1)
        self.assertEqual(js_find_index([1, 2, 3], lambda x: x == 9), -1)

    def test_filter_map(self):
        self.assertEqual(js_filter([1, 2, 3, 4], lambda x: x % 2 == 0), [2, 4])
        self.assertEqual(js_map([1, 2, 3], lambda x: x * 2), [2, 4, 6])

    def test_filter_uses_js_truthy(self):
        # [] is truthy in JS — elements whose predicate returns [] must be kept
        self.assertEqual(js_filter([1, 2], lambda _: []), [1, 2])

    def test_for_each(self):
        seen: list = []
        js_for_each([1, 2, 3], lambda x: seen.append(x))
        self.assertEqual(seen, [1, 2, 3])

    def test_some_every(self):
        self.assertTrue(js_some([1, 2, 3], lambda x: x > 2))
        self.assertFalse(js_some([1, 2, 3], lambda x: x > 10))
        self.assertTrue(js_every([1, 2, 3], lambda x: x > 0))
        self.assertFalse(js_every([1, 2, 3], lambda x: x > 1))

    def test_includes(self):
        self.assertTrue(js_includes([1, 2, 3], 2))
        self.assertFalse(js_includes([1, 2, 3], 9))
        self.assertTrue(js_includes("hello", "ell"))
        self.assertFalse(js_includes(None, 1))

    def test_index_of(self):
        self.assertEqual(js_index_of([10, 20, 30], 20), 1)
        self.assertEqual(js_index_of([10, 20, 30], 99), -1)

    def test_slice(self):
        self.assertEqual(js_slice([1, 2, 3, 4, 5], 1, 4), [2, 3, 4])
        self.assertEqual(js_slice([1, 2, 3, 4, 5], -2), [4, 5])
        self.assertEqual(js_slice([1, 2, 3], UNDEFINED, UNDEFINED), [1, 2, 3])

    def test_concat(self):
        self.assertEqual(js_concat([1, 2], [3, 4], 5), [1, 2, 3, 4, 5])

    def test_is_array(self):
        self.assertTrue(js_is_array([1, 2]))
        self.assertFalse(js_is_array("abc"))
        self.assertFalse(js_is_array({"a": 1}))


class SortTests(unittest.TestCase):
    def test_sort_with_numeric_comparator(self):
        arr = [3, 1, 2]
        result = js_sort(arr, lambda a, b: a - b)
        self.assertEqual(result, [1, 2, 3])
        self.assertIs(result, arr)  # mutates in place

    def test_sort_stable(self):
        arr = [{"k": 1, "t": "a"}, {"k": 1, "t": "b"}, {"k": 0, "t": "c"}]
        js_sort(arr, lambda a, b: a["k"] - b["k"])
        self.assertEqual([x["t"] for x in arr], ["c", "a", "b"])

    def test_sort_default_stringwise(self):
        arr = [10, 2, 1]
        js_sort(arr)
        self.assertEqual(arr, [1, 10, 2])

    def test_comparator_returns_undefined_treated_as_zero(self):
        arr = [1, 2, 3]
        js_sort(arr, lambda a, b: UNDEFINED)
        self.assertEqual(arr, [1, 2, 3])


class MemberAccessTests(unittest.TestCase):
    def test_get_dict_key(self):
        self.assertEqual(js_get({"a": 1}, "a"), 1)

    def test_get_missing_is_undefined(self):
        self.assertIs(js_get({"a": 1}, "b"), UNDEFINED)

    def test_get_on_nullish(self):
        self.assertIs(js_get(None, "a"), UNDEFINED)
        self.assertIs(js_get(UNDEFINED, "a"), UNDEFINED)

    def test_get_list_index(self):
        self.assertEqual(js_get([10, 20, 30], 1), 20)
        self.assertEqual(js_get([10, 20, 30], "1"), 20)
        self.assertIs(js_get([10, 20], 5), UNDEFINED)

    def test_get_length(self):
        self.assertEqual(js_get([1, 2, 3], "length"), 3)
        self.assertEqual(js_get("hello", "length"), 5)

    def test_optional_short_circuits(self):
        self.assertIs(js_optional(None, "a"), UNDEFINED)
        self.assertIs(js_optional(UNDEFINED, "a"), UNDEFINED)
        self.assertEqual(js_optional({"a": 5}, "a"), 5)


class LogicalTests(unittest.TestCase):
    def test_coalesce_skips_nullish(self):
        self.assertEqual(js_coalesce(None, UNDEFINED, 0), 0)
        self.assertEqual(js_coalesce(None, "x"), "x")
        self.assertIs(js_coalesce(None, UNDEFINED), UNDEFINED)

    def test_logical_or_returns_first_truthy(self):
        self.assertEqual(js_logical_or(0, "", "hit"), "hit")
        self.assertEqual(js_logical_or(0, ""), "")  # last falsy

    def test_logical_or_returns_truthy_untouched(self):
        self.assertEqual(js_logical_or([], 5), [])  # [] is truthy in JS

    def test_logical_and_returns_first_falsy(self):
        self.assertEqual(js_logical_and(1, 0, 3), 0)
        self.assertEqual(js_logical_and(1, 2, 3), 3)


class SpreadTests(unittest.TestCase):
    def test_spread_object_merges_left_to_right(self):
        a = {"x": 1, "y": 2}
        b = {"y": 3, "z": 4}
        self.assertEqual(js_spread_object(a, b), {"x": 1, "y": 3, "z": 4})

    def test_spread_object_ignores_nullish(self):
        self.assertEqual(js_spread_object({"a": 1}, None, UNDEFINED), {"a": 1})

    def test_spread_array_concats(self):
        self.assertEqual(js_spread_array([1, 2], [3], 4), [1, 2, 3, 4])


class TemplateTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(js_template("Hello ", "world", "!"), "Hello world!")

    def test_formats_numbers(self):
        self.assertEqual(js_template("n=", 5), "n=5")
        self.assertEqual(js_template("n=", 5.5), "n=5.5")

    def test_formats_nullish(self):
        self.assertEqual(js_template("v=", None), "v=null")
        self.assertEqual(js_template("v=", UNDEFINED), "v=undefined")

    def test_formats_booleans(self):
        self.assertEqual(js_template("b=", True), "b=true")
        self.assertEqual(js_template("b=", False), "b=false")


class TypeofTests(unittest.TestCase):
    def test_typeof(self):
        self.assertEqual(js_typeof(UNDEFINED), "undefined")
        self.assertEqual(js_typeof(None), "object")
        self.assertEqual(js_typeof(True), "boolean")
        self.assertEqual(js_typeof(1), "number")
        self.assertEqual(js_typeof("x"), "string")
        self.assertEqual(js_typeof(lambda: 1), "function")
        self.assertEqual(js_typeof({"a": 1}), "object")
        self.assertEqual(js_typeof([1]), "object")


class ObjectHelperTests(unittest.TestCase):
    def test_keys_values_entries(self):
        d = {"a": 1, "b": 2}
        self.assertEqual(js_object_keys(d), ["a", "b"])
        self.assertEqual(js_object_values(d), [1, 2])
        self.assertEqual(js_object_entries(d), [["a", 1], ["b", 2]])

    def test_nullish(self):
        self.assertEqual(js_object_keys(None), [])
        self.assertEqual(js_object_values(UNDEFINED), [])
        self.assertEqual(js_object_entries(None), [])


class RegexTests(unittest.TestCase):
    def test_regex_test(self):
        rx = JsRegExp(r"\d+")
        self.assertTrue(rx.test("abc 42"))
        self.assertFalse(rx.test("abc"))

    def test_regex_flags(self):
        self.assertTrue(JsRegExp(r"hello", "i").test("HELLO"))
        self.assertFalse(JsRegExp(r"hello").test("HELLO"))

    def test_regex_exec_returns_groups(self):
        rx = JsRegExp(r"(\w+)=(\d+)")
        result = rx.exec("key=42")
        self.assertEqual(result, ["key=42", "key", "42"])

    def test_string_match(self):
        self.assertEqual(js_string_match("abc 42", JsRegExp(r"(\d+)")), ["42", "42"])
        self.assertIsNone(js_string_match("abc", JsRegExp(r"\d+")))
        self.assertIsNone(js_string_match(None, JsRegExp(r"\d+")))

    def test_string_replace(self):
        self.assertEqual(
            js_string_replace("abc 42", JsRegExp(r"\d+"), "X"), "abc X"
        )

    def test_string_replace_global(self):
        self.assertEqual(
            js_string_replace("a1 b2 c3", JsRegExp(r"\d", "g"), "X"), "aX bX cX"
        )

    def test_string_split_regex(self):
        self.assertEqual(
            js_string_split("a,b;c", JsRegExp(r"[,;]")), ["a", "b", "c"]
        )

    def test_string_includes(self):
        self.assertTrue(js_string_includes("hello world", "world"))
        self.assertFalse(js_string_includes("hello", "xyz"))
        self.assertFalse(js_string_includes(None, "x"))


class MathTests(unittest.TestCase):
    def test_max_min(self):
        self.assertEqual(js_math_max(1, 5, 3), 5)
        self.assertEqual(js_math_min(1, 5, 3), 1)

    def test_max_empty(self):
        self.assertEqual(js_math_max(), float("-inf"))
        self.assertEqual(js_math_min(), float("inf"))

    def test_max_with_nan(self):
        self.assertTrue(math.isnan(js_math_max(1, float("nan"), 3)))

    def test_floor_ceil_round(self):
        self.assertEqual(js_math_floor(1.7), 1.0)
        self.assertEqual(js_math_ceil(1.2), 2.0)
        self.assertEqual(js_math_round(1.5), 2.0)
        self.assertEqual(js_math_round(2.5), 3.0)
        self.assertEqual(js_math_round(-1.5), -1.0)  # JS rounds ties toward +Inf

    def test_abs(self):
        self.assertEqual(js_math_abs(-5), 5)
        self.assertEqual(js_math_abs("3"), 3)


class SetTests(unittest.TestCase):
    def test_add_has_size(self):
        s = JsSet([1, 2, 2, 3])
        self.assertEqual(s.size, 3)
        self.assertTrue(s.has(2))
        self.assertFalse(s.has(9))

    def test_delete(self):
        s = JsSet([1, 2, 3])
        self.assertTrue(s.delete(2))
        self.assertFalse(s.has(2))
        self.assertFalse(s.delete(99))

    def test_iteration_order(self):
        s = JsSet()
        s.add("c")
        s.add("a")
        s.add("b")
        self.assertEqual(list(s), ["c", "a", "b"])

    def test_init_from_none(self):
        s = JsSet(None)
        self.assertEqual(s.size, 0)


class MapTests(unittest.TestCase):
    def test_set_get(self):
        m = JsMap()
        m.set("a", 1).set("b", 2)
        self.assertEqual(m.get("a"), 1)
        self.assertEqual(m.size, 2)

    def test_get_missing_undefined(self):
        m = JsMap()
        self.assertIs(m.get("x"), UNDEFINED)

    def test_init_from_pairs(self):
        m = JsMap([["a", 1], ["b", 2]])
        self.assertEqual(m.get("b"), 2)

    def test_delete(self):
        m = JsMap([["a", 1]])
        self.assertTrue(m.delete("a"))
        self.assertFalse(m.has("a"))


if __name__ == "__main__":
    unittest.main()
