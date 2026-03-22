"""Tests for fancy_table smart filter: _matches_filter, _tokenize_filter, _eval_filter_term."""

import unittest

from client.ui.widgets.fancy_table import _matches_filter, _tokenize_filter, _eval_filter_term


def m(value, filter_text):
    """Shorthand: test _matches_filter with string value."""
    raw = value
    display = str(value) if value is not None else ""
    return _matches_filter(raw, display, filter_text)


def mn(num, filter_text):
    """Shorthand: test _matches_filter with numeric raw value."""
    return _matches_filter(num, str(num), filter_text)


# ---------------------------------------------------------------------------
# Basic operator tests (pre-existing behaviour, sanity checks)
# ---------------------------------------------------------------------------
class TestBasicOperators(unittest.TestCase):

    def test_plain_contains(self):
        self.assertTrue(m("Hello World", "hello"))
        self.assertTrue(m("Hello World", "world"))
        self.assertFalse(m("Hello World", "xyz"))

    def test_not_operator(self):
        self.assertTrue(m("Hello World", "!xyz"))
        self.assertFalse(m("Hello World", "!hello"))

    def test_equals_operator(self):
        self.assertTrue(m("hello", "=hello"))
        self.assertFalse(m("hello world", "=hello"))

    def test_gt_operator(self):
        self.assertTrue(mn(15, ">10"))
        self.assertFalse(mn(5, ">10"))

    def test_lt_operator(self):
        self.assertTrue(mn(5, "<10"))
        self.assertFalse(mn(15, "<10"))

    def test_gte_operator(self):
        self.assertTrue(mn(10, ">=10"))
        self.assertTrue(mn(15, ">=10"))
        self.assertFalse(mn(5, ">=10"))

    def test_lte_operator(self):
        self.assertTrue(mn(10, "<=10"))
        self.assertTrue(mn(5, "<=10"))
        self.assertFalse(mn(15, "<=10"))

    def test_regex(self):
        self.assertTrue(m("Hello World", "/^hello/"))
        self.assertFalse(m("Hello World", "/^world/"))
        self.assertTrue(m("Test 123", "/\\d+/"))


# ---------------------------------------------------------------------------
# AND / OR chaining
# ---------------------------------------------------------------------------
class TestLogicOperators(unittest.TestCase):

    def test_and_symbol(self):
        self.assertTrue(m("Hello World", "hello & world"))
        self.assertFalse(m("Hello World", "hello & xyz"))

    def test_or_symbol(self):
        self.assertTrue(m("Hello World", "hello | xyz"))
        self.assertTrue(m("Hello World", "xyz | hello"))
        self.assertFalse(m("Hello World", "abc | xyz"))

    def test_and_keyword(self):
        self.assertTrue(m("Hello World", "hello and world"))
        self.assertFalse(m("Hello World", "hello and xyz"))

    def test_or_keyword(self):
        self.assertTrue(m("Hello World", "hello or xyz"))
        self.assertFalse(m("Hello World", "abc or xyz"))

    def test_precedence_and_over_or(self):
        # "a | b & c" → a | (b & c)
        self.assertTrue(m("alpha", "alpha | beta & gamma"))
        self.assertFalse(m("beta", "alpha | beta & gamma"))
        self.assertTrue(m("beta gamma", "alpha | beta & gamma"))

    def test_multiple_and(self):
        self.assertTrue(m("alpha beta gamma", "alpha & beta & gamma"))
        self.assertFalse(m("alpha beta", "alpha & beta & gamma"))

    def test_multiple_or(self):
        self.assertTrue(m("alpha", "alpha | beta | gamma"))
        self.assertTrue(m("gamma", "alpha | beta | gamma"))
        self.assertFalse(m("delta", "alpha | beta | gamma"))

    def test_numeric_range_with_and(self):
        self.assertTrue(mn(15, ">10 & <20"))
        self.assertFalse(mn(5, ">10 & <20"))
        self.assertFalse(mn(25, ">10 & <20"))


# ---------------------------------------------------------------------------
# Parentheses — the main bug fix
# ---------------------------------------------------------------------------
class TestParentheses(unittest.TestCase):

    def test_parens_without_operators_are_literal(self):
        """!(L) should mean NOT-contains '(l)', not grouping."""
        self.assertTrue(m("Adjusted Spear (L)", "(l)"))
        self.assertFalse(m("Adjusted Spear", "(l)"))

    def test_not_with_parens_literal(self):
        """!(L) should exclude items containing '(l)'."""
        self.assertFalse(m("Adjusted Spear (L)", "!(L)"))
        self.assertTrue(m("Adjusted Spear", "!(L)"))

    def test_bare_parens_are_literal(self):
        """(foo) without operators is a literal search for '(foo)'."""
        self.assertTrue(m("test (foo) bar", "(foo)"))
        self.assertFalse(m("test foo bar", "(foo)"))

    def test_parens_with_operators_are_grouping(self):
        """(a | b) & c — parens are grouping when operators exist."""
        self.assertTrue(m("alpha gamma", "(alpha | beta) & gamma"))
        self.assertTrue(m("beta gamma", "(alpha | beta) & gamma"))
        self.assertFalse(m("alpha", "(alpha | beta) & gamma"))
        self.assertFalse(m("gamma", "(alpha | beta) & gamma"))

    def test_not_parens_with_operator(self):
        """!foo & bar — NOT on a term works in expressions."""
        self.assertTrue(m("hello bar", "!foo & bar"))
        self.assertFalse(m("foo bar", "!foo & bar"))

    def test_multiple_parens_literal(self):
        """(S) or (M) without operators are literal."""
        self.assertTrue(m("Item (S)", "(S)"))
        self.assertFalse(m("Item (M)", "(S)"))

    def test_not_paren_with_operator(self):
        """!(L) & spear — NOT containing '(l)' AND containing 'spear'."""
        self.assertTrue(m("Adjusted Spear", "!(L) & spear"))
        self.assertFalse(m("Adjusted Spear (L)", "!(L) & spear"))
        self.assertFalse(m("Adjusted Sword", "!(L) & spear"))

    def test_not_paren_with_or(self):
        """!(L) | sword — NOT containing '(l)' OR containing 'sword'."""
        self.assertTrue(m("Adjusted Sword", "!(L) | sword"))
        # (L) matches but "sword" also matches → OR is True
        self.assertTrue(m("Short Sword (L)", "!(L) | sword"))
        # Neither clause: contains (L) AND doesn't contain "sword"
        self.assertFalse(m("Short Spear (L)", "!(L) | sword"))

    def test_nested_parens_grouping(self):
        """Nested parens with operators."""
        self.assertTrue(m("alpha beta gamma", "((alpha | beta) & gamma)"))
        self.assertFalse(m("alpha", "((alpha | beta) & gamma)"))


# ---------------------------------------------------------------------------
# Standalone ! as unary NOT prefix in parser
# ---------------------------------------------------------------------------
class TestUnaryNot(unittest.TestCase):

    def test_standalone_not_with_space(self):
        """! foo & bar — standalone ! with space acts as unary NOT."""
        self.assertTrue(m("hello bar", "! foo & bar"))
        self.assertFalse(m("foo bar", "! foo & bar"))

    def test_standalone_not_with_group(self):
        """! (foo | bar) & baz — NOT group."""
        self.assertTrue(m("hello baz", "! (foo | bar) & baz"))
        self.assertFalse(m("foo baz", "! (foo | bar) & baz"))
        self.assertFalse(m("bar baz", "! (foo | bar) & baz"))
        self.assertFalse(m("hello xyz", "! (foo | bar) & baz"))


# ---------------------------------------------------------------------------
# Backslash escaping
# ---------------------------------------------------------------------------
class TestBackslashEscaping(unittest.TestCase):

    # --- Escaping logic operators in expressions ---

    def test_escape_ampersand_in_word(self):
        r"""a\&b in an expression with real operators searches literal 'a&b'."""
        self.assertTrue(m("test a&b here", r"a\&b & test"))
        self.assertFalse(m("test ab here", r"a\&b & test"))

    def test_escape_pipe_in_word(self):
        r"""a\|b should be literal 'a|b' within a word."""
        self.assertTrue(m("a|b", r"a\|b"))
        self.assertFalse(m("a b", r"a\|b"))

    def test_escape_parens_in_word(self):
        r"""\(test\) in an expression keeps parens literal."""
        self.assertTrue(m("(test) and more", r"\(test\) & more"))
        self.assertFalse(m("test and more", r"\(test\) & more"))

    # --- Escaping term-level operators ---

    def test_escape_not_operator(self):
        r"""\!foo searches for literal '!foo'."""
        self.assertTrue(m("!foo bar", r"\!foo"))
        self.assertFalse(m("foo bar", r"\!foo"))

    def test_escape_gt_operator(self):
        r"""\>10 searches for literal '>10'."""
        self.assertTrue(m("value >10", r"\>10"))
        self.assertFalse(m("value 10", r"\>10"))

    def test_escape_lt_operator(self):
        r"""\<5 searches for literal '<5'."""
        self.assertTrue(m("x <5 y", r"\<5"))
        self.assertFalse(m("x 5 y", r"\<5"))

    def test_escape_eq_operator(self):
        r"""\=exact searches for literal '=exact'."""
        self.assertTrue(m("val =exact", r"\=exact"))
        self.assertFalse(m("val exact", r"\=exact"))

    # --- Fast path unescaping ---

    def test_escaped_ampersand_fast_path(self):
        r"""Lone \& (no real operators) should search for literal '&'."""
        self.assertTrue(m("Tom & Jerry", r"\&"))
        self.assertFalse(m("Tom Jerry", r"\&"))

    def test_escaped_pipe_fast_path(self):
        r"""Lone \| should search for literal '|'."""
        self.assertTrue(m("A|B", r"\|"))
        self.assertFalse(m("AB", r"\|"))

    def test_escaped_paren_fast_path(self):
        r"""Lone \( should search for literal '('."""
        self.assertTrue(m("foo(bar", r"\("))
        self.assertFalse(m("foobar", r"\("))

    def test_escape_not_in_expression(self):
        r"""\!foo & bar — escaped ! is literal, & is operator."""
        self.assertTrue(m("!foo bar", r"\!foo & bar"))
        self.assertFalse(m("foo bar", r"\!foo & bar"))
        self.assertFalse(m("!foo xyz", r"\!foo & bar"))


# ---------------------------------------------------------------------------
# Tokenizer unit tests
# ---------------------------------------------------------------------------
class TestTokenizer(unittest.TestCase):

    def test_simple_words(self):
        self.assertEqual(_tokenize_filter("hello world"), ["hello", "world"])

    def test_operators(self):
        self.assertEqual(_tokenize_filter("a & b"), ["a", "&", "b"])
        self.assertEqual(_tokenize_filter("a | b"), ["a", "|", "b"])

    def test_and_or_keywords(self):
        self.assertEqual(_tokenize_filter("a and b"), ["a", "&", "b"])
        self.assertEqual(_tokenize_filter("a or b"), ["a", "|", "b"])

    def test_parens(self):
        self.assertEqual(_tokenize_filter("(a | b) & c"), ["(", "a", "|", "b", ")", "&", "c"])

    def test_escaped_ampersand(self):
        self.assertEqual(_tokenize_filter(r"a\&b"), ["a&b"])

    def test_escaped_pipe(self):
        self.assertEqual(_tokenize_filter(r"a\|b"), ["a|b"])

    def test_escaped_parens(self):
        self.assertEqual(_tokenize_filter(r"\(test\)"), ["(test)"])

    def test_escape_mixed_with_operators(self):
        self.assertEqual(
            _tokenize_filter(r"\(x\) & y"),
            ["(x)", "&", "y"],
        )

    def test_regex_token(self):
        self.assertEqual(_tokenize_filter("/foo/ & bar"), ["/foo/", "&", "bar"])

    def test_regex_with_flags(self):
        self.assertEqual(_tokenize_filter("/foo/gi"), ["/foo/gi"])

    def test_not_paren_consumed_as_single_token(self):
        """!(L) in tokenizer should be a single token, not ! + ( + L + )."""
        self.assertEqual(_tokenize_filter("!(l) & foo"), ["!(l)", "&", "foo"])

    def test_not_paren_nested(self):
        """!((L)) consumed as single token including nested parens."""
        self.assertEqual(_tokenize_filter("!((l)) & foo"), ["!((l))", "&", "foo"])

    def test_not_paren_unclosed(self):
        """!( with no closing ) consumes to end."""
        self.assertEqual(_tokenize_filter("!(foo"), ["!(foo"])

    def test_standalone_not(self):
        """! followed by space produces standalone ! token."""
        self.assertEqual(_tokenize_filter("! foo & bar"), ["!", "foo", "&", "bar"])

    def test_regex_with_pipe_inside(self):
        """/a|b/ should be a single regex token, not split on |."""
        self.assertEqual(_tokenize_filter("/a|b/"), ["/a|b/"])
        self.assertEqual(_tokenize_filter("/a|b/ & c"), ["/a|b/", "&", "c"])

    def test_regex_with_ampersand_inside(self):
        """/a&b/ should be a single regex token."""
        self.assertEqual(_tokenize_filter("/a&b/ & c"), ["/a&b/", "&", "c"])


# ---------------------------------------------------------------------------
# eval_filter_term unit tests
# ---------------------------------------------------------------------------
class TestEvalFilterTerm(unittest.TestCase):

    def test_plain_contains(self):
        self.assertTrue(_eval_filter_term("hello", "hello world", None, "hello"))
        self.assertFalse(_eval_filter_term("hello", "hello world", None, "xyz"))

    def test_not(self):
        self.assertTrue(_eval_filter_term("hello", "hello world", None, "!xyz"))
        self.assertFalse(_eval_filter_term("hello", "hello world", None, "!hello"))

    def test_escaped_not(self):
        # \!foo → literal search for '!foo'
        self.assertTrue(_eval_filter_term("!foo", "!foo bar", None, r"\!foo"))
        self.assertFalse(_eval_filter_term("foo", "foo bar", None, r"\!foo"))

    def test_escaped_gt(self):
        self.assertTrue(_eval_filter_term(">10", ">10", None, r"\>10"))
        self.assertFalse(_eval_filter_term("10", "10", None, r"\>10"))

    def test_escaped_gte(self):
        self.assertTrue(_eval_filter_term(">=5", ">=5", None, r"\>=5"))
        self.assertFalse(_eval_filter_term("5", "5", None, r"\>=5"))

    def test_numeric_gt(self):
        self.assertTrue(_eval_filter_term(15, "15", 15.0, ">10"))
        self.assertFalse(_eval_filter_term(5, "5", 5.0, ">10"))


# ---------------------------------------------------------------------------
# Regex inside expressions
# ---------------------------------------------------------------------------
class TestRegexInExpressions(unittest.TestCase):

    def test_regex_with_pipe_not_logic_or(self):
        """/a|b/ — pipe inside regex is regex alternation, not logic OR."""
        self.assertTrue(m("a", "/a|b/"))
        self.assertTrue(m("b", "/a|b/"))
        self.assertFalse(m("c", "/a|b/"))

    def test_regex_with_and_operator(self):
        """/\\d+/ & foo — regex AND plain term."""
        self.assertTrue(m("foo 123", "/\\d+/ & foo"))
        self.assertFalse(m("foo bar", "/\\d+/ & foo"))
        self.assertFalse(m("123 bar", "/\\d+/ & foo"))

    def test_regex_or_plain(self):
        """/^test/ | foo — regex OR plain term."""
        self.assertTrue(m("testing", "/^test/ | foo"))
        self.assertTrue(m("foo", "/^test/ | foo"))
        self.assertFalse(m("bar", "/^test/ | foo"))


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
class TestEdgeCases(unittest.TestCase):

    def test_empty_filter(self):
        self.assertTrue(m("anything", ""))
        self.assertTrue(m("anything", "   "))

    def test_none_value(self):
        self.assertTrue(_matches_filter(None, "", ""))
        self.assertFalse(_matches_filter(None, "", "hello"))

    def test_trailing_backslash(self):
        """Trailing backslash is treated literally."""
        self.assertFalse(m("hello", "\\"))
        self.assertTrue(m("back\\slash", "\\"))

    def test_not_with_parens_and_operator(self):
        """!foo & (bar | baz) — NOT term with grouped OR."""
        self.assertTrue(m("hello bar", "!foo & (bar | baz)"))
        self.assertTrue(m("hello baz", "!foo & (bar | baz)"))
        self.assertFalse(m("foo bar", "!foo & (bar | baz)"))
        self.assertFalse(m("hello xyz", "!foo & (bar | baz)"))

    def test_case_insensitive(self):
        self.assertTrue(m("Hello WORLD", "hello"))
        self.assertTrue(m("Hello WORLD", "!xyz"))
        self.assertTrue(m("Hello WORLD", "hello & world"))

    def test_numeric_with_parens_literal(self):
        """Filter like (5) should search for literal '(5)'."""
        self.assertTrue(m("item (5)", "(5)"))
        self.assertFalse(m("item 5", "(5)"))

    def test_not_paren_empty(self):
        """!() — NOT empty parens → NOT contains '()'."""
        self.assertFalse(m("test ()", "!()"))
        self.assertTrue(m("test", "!()"))

    def test_unmatched_open_paren_literal(self):
        """Bare ( without close in fast path is literal."""
        self.assertTrue(m("foo(bar", "("))
        self.assertFalse(m("foobar", "("))

    def test_operator_at_end(self):
        """'foo &' — trailing operator, second operand defaults True."""
        self.assertTrue(m("foo", "foo &"))
        self.assertFalse(m("bar", "foo &"))

    def test_mixed_not_and_grouping(self):
        """!(L) & (sword | spear) — real-world combo."""
        self.assertTrue(m("Adjusted Sword", "!(L) & (sword | spear)"))
        self.assertTrue(m("Adjusted Spear", "!(L) & (sword | spear)"))
        self.assertFalse(m("Adjusted Sword (L)", "!(L) & (sword | spear)"))
        self.assertFalse(m("Adjusted Axe", "!(L) & (sword | spear)"))

    def test_double_not(self):
        """!!foo — fast path treats as NOT contains '!foo' (literal)."""
        self.assertTrue(m("foo", "!!foo"))
        # "bar" also doesn't contain "!foo" → True
        self.assertTrue(m("bar", "!!foo"))
        # Only a value containing literal "!foo" is excluded
        self.assertFalse(m("!foo", "!!foo"))

    def test_not_with_numeric_operator(self):
        """!>10 in fast path means NOT contains '>10' as text."""
        # In fast path (no logic ops), !>10 is handled by term evaluator
        # _OP_RE matches ! with operand >10 → NOT contains '>10'
        self.assertTrue(m("value 5", "!>10"))
        # '>10' is not in 'value 5', so NOT → True

    def test_realistic_entropia_filter(self):
        """Real-world: filter weapons excluding (L) variants containing 'sword'."""
        items = [
            "Adjusted Short Sword",
            "Adjusted Short Sword (L)",
            "Sollomate Opalo",
            "Sollomate Opalo (L)",
            "Isis LR53 (L)",
        ]
        filt = "!(L) & sword"
        results = [i for i in items if m(i, filt)]
        self.assertEqual(results, ["Adjusted Short Sword"])

    def test_realistic_or_filter(self):
        """Real-world: find items that are either swords or spears."""
        items = [
            "Adjusted Short Sword",
            "Adjusted Spear",
            "Sollomate Opalo",
        ]
        filt = "sword | spear"
        results = [i for i in items if m(i, filt)]
        self.assertEqual(results, ["Adjusted Short Sword", "Adjusted Spear"])


if __name__ == "__main__":
    unittest.main()
