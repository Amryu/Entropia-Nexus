"""Tests for item_name_matcher.py — Levenshtein matching, ambiguity detection,
and confidence adjustment edge cases.

Run with: python -m pytest client/ocr/test_item_name_matcher.py -v
"""

from __future__ import annotations

import pytest

from .item_name_matcher import (
    ItemNameMatcher,
    MatchResult,
    _compute_skeleton,
    _find_group_differentiating_positions,
    _levenshtein,
    _max_edit_distance,
    _normalize_for_matching,
    AMBIGUITY_CONFIDENCE_THRESHOLD,
    AMBIGUITY_PENALTY,
    PENALTY_PER_EDIT,
)


# ======================================================================
# Helpers
# ======================================================================

class MockDataClient:
    """Configurable mock data client for testing."""

    def __init__(self, items: list[dict]):
        self._items = items

    def get_items(self) -> list[dict]:
        return self._items


def make_matcher(names: list[str]) -> ItemNameMatcher:
    """Create a matcher with a given list of item names."""
    items = [{"Name": n} for n in names]
    m = ItemNameMatcher(MockDataClient(items))
    m._refresh_if_needed()
    return m


def high_scores(n: int, value: float = 0.95) -> list[float]:
    """Generate n high-confidence per-character scores."""
    return [value] * n


def scores_with_low_at(n: int, positions: list[int],
                       high: float = 0.95, low: float = 0.50) -> list[float]:
    """Generate scores with low confidence at specific positions."""
    s = [high] * n
    for p in positions:
        if p < n:
            s[p] = low
    return s


# ======================================================================
# Levenshtein distance
# ======================================================================

class TestLevenshtein:
    def test_identical(self):
        assert _levenshtein("abc", "abc", 5) == 0

    def test_empty_strings(self):
        assert _levenshtein("", "", 5) == 0
        assert _levenshtein("abc", "", 5) == 3
        assert _levenshtein("", "xyz", 5) == 3

    def test_single_substitution(self):
        assert _levenshtein("abc", "axc", 5) == 1

    def test_single_insertion(self):
        assert _levenshtein("abc", "abxc", 5) == 1

    def test_single_deletion(self):
        assert _levenshtein("abxc", "abc", 5) == 1

    def test_classic_kitten_sitting(self):
        assert _levenshtein("kitten", "sitting", 10) == 3

    def test_early_termination(self):
        """When distance exceeds max_dist, returns max_dist + 1."""
        assert _levenshtein("abc", "xyz", 1) == 2
        assert _levenshtein("abcdef", "xyzwvu", 2) == 3

    def test_length_filter(self):
        """Length difference > max_dist triggers early return."""
        assert _levenshtein("a", "abcde", 2) == 3  # diff=4 > max_dist=2


# ======================================================================
# Normalization
# ======================================================================

class TestNormalization:
    def test_lowercase(self):
        assert _normalize_for_matching("Soft Hide") == "soft hide"

    def test_comma_to_period(self):
        assert _normalize_for_matching("Item, Name") == "item. name"

    def test_underscore_to_space(self):
        assert _normalize_for_matching("Item_Name") == "item name"

    def test_collapse_whitespace(self):
        assert _normalize_for_matching("a   b") == "a b"

    def test_combined(self):
        assert _normalize_for_matching("Foo_Bar, Baz") == "foo bar. baz"


# ======================================================================
# Skeleton computation
# ======================================================================

class TestSkeleton:
    def test_single_digit(self):
        assert _compute_skeleton("item 5") == "item #"

    def test_multi_digit(self):
        assert _compute_skeleton("armatrix lr-105 (l)") == "armatrix lr-# (l)"

    def test_multiple_digit_groups(self):
        assert _compute_skeleton("x10 y20 z30") == "x# y# z#"

    def test_no_digits(self):
        assert _compute_skeleton("soft hide") == "soft hide"


# ======================================================================
# Differentiating positions
# ======================================================================

class TestDifferentiatingPositions:
    def test_simple_series(self):
        names = ["ArMatrix LR-10 (L)", "ArMatrix LR-15 (L)"]
        result = _find_group_differentiating_positions(names)
        # Positions 12,13 are where '10' vs '15' differ (in normalized form)
        norm_10 = _normalize_for_matching("ArMatrix LR-10 (L)")
        norm_15 = _normalize_for_matching("ArMatrix LR-15 (L)")
        # Find actual differing positions
        expected_diff = {i for i in range(min(len(norm_10), len(norm_15)))
                        if norm_10[i] != norm_15[i]}
        assert result["ArMatrix LR-10 (L)"] == expected_diff
        assert result["ArMatrix LR-15 (L)"] == expected_diff

    def test_different_lengths(self):
        """Items differing in digit count (e.g., 5 vs 10) have extra positions."""
        names = ["Item 5", "Item 10"]
        result = _find_group_differentiating_positions(names)
        # "item 5" (len=6) vs "item 10" (len=7) — differ at pos 5, and pos 6 is extra
        assert len(result["Item 5"]) > 0
        assert len(result["Item 10"]) > 0

    def test_three_way(self):
        """Three items: each pair differs at the digit positions."""
        names = ["X-10", "X-20", "X-30"]
        result = _find_group_differentiating_positions(names)
        # All three have differentiating positions at the digit location
        for name in names:
            assert len(result[name]) > 0


# ======================================================================
# Exact matching
# ======================================================================

class TestExactMatch:
    def test_exact_case_insensitive(self):
        m = make_matcher(["Soft Hide", "Hard Rock"])
        r = m.match("Soft Hide", high_scores(9), 0.93)
        assert r.matched_name == "Soft Hide"
        assert r.edit_distance == 0
        assert r.confidence == pytest.approx(0.93)

    def test_comma_period_equivalence(self):
        """Comma in OCR matches period in DB at distance 0."""
        m = make_matcher(["Nanochip 15, Perfected"])
        r = m.match("Nanochip 15. Perfected", high_scores(22), 0.93)
        assert r.matched_name == "Nanochip 15, Perfected"
        assert r.edit_distance == 0

    def test_underscore_space_equivalence(self):
        """Underscore in OCR matches space in DB at distance 0."""
        m = make_matcher(["Long Item Name"])
        r = m.match("Long_Item_Name", high_scores(14), 0.93)
        assert r.matched_name == "Long Item Name"
        assert r.edit_distance == 0


# ======================================================================
# Fuzzy matching
# ======================================================================

class TestFuzzyMatch:
    def test_single_char_difference(self):
        m = make_matcher(["Soft Hide"])
        r = m.match("Soft Hids", high_scores(9), 0.93)
        assert r.matched_name == "Soft Hide"
        assert r.edit_distance == 1
        expected_conf = 0.93 * (1.0 - PENALTY_PER_EDIT)
        assert r.confidence == pytest.approx(expected_conf, abs=0.01)

    def test_two_char_difference(self):
        m = make_matcher(["Traeskeron Skin"])
        r = m.match("Traeskeron Skxn", high_scores(15), 0.93)
        # edit distance 1 (x->i)
        assert r.matched_name == "Traeskeron Skin"
        assert r.edit_distance == 1

    def test_no_match_beyond_threshold(self):
        """Items too different get no match — original name returned."""
        m = make_matcher(["Soft Hide"])
        r = m.match("Completely Different", high_scores(20), 0.93)
        assert r.matched_name == "Completely Different"
        assert r.edit_distance > _max_edit_distance("completely different")

    def test_short_name_strict_threshold(self):
        """Short names (<=8 chars) only allow distance 1."""
        m = make_matcher(["Oil"])
        r = m.match("Oxx", high_scores(3), 0.93)
        # edit dist 2 > max_dist 1 for 3-char name
        assert r.matched_name == "Oxx"  # no match

    def test_empty_item_list(self):
        """Graceful degradation with no items."""
        m = make_matcher([])
        r = m.match("Soft Hide", high_scores(9), 0.93)
        assert r.matched_name == "Soft Hide"
        assert r.confidence == 0.93


# ======================================================================
# Ambiguity detection
# ======================================================================

class TestAmbiguityDetection:
    @pytest.fixture
    def armatrix_matcher(self):
        """Matcher with ArMatrix series — classic ambiguity scenario."""
        names = [f"ArMatrix LR-{n} (L)" for n in
                 [10, 15, 20, 25, 30, 35, 40, 45, 50,
                  55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105]]
        return make_matcher(names)

    def test_high_confidence_no_penalty(self, armatrix_matcher):
        """High confidence at digit positions → no ambiguity penalty."""
        name = "Armatrix Lr-35 (L)"
        scores = high_scores(len(_normalize_for_matching(name)))
        r = armatrix_matcher.match(name, scores, 0.93)
        assert r.matched_name == "ArMatrix LR-35 (L)"
        assert r.confidence == pytest.approx(0.93)
        assert not r.ambiguous

    def test_low_confidence_penalty(self, armatrix_matcher):
        """Low confidence at digit positions → ambiguity penalty applied."""
        name = "Armatrix Lr-35 (L)"
        norm = _normalize_for_matching(name)
        # Find digit positions
        digit_pos = [i for i, c in enumerate(norm) if c.isdigit()]
        scores = scores_with_low_at(len(norm), digit_pos)
        r = armatrix_matcher.match(name, scores, 0.93)
        assert r.matched_name == "ArMatrix LR-35 (L)"
        assert r.ambiguous
        assert r.confidence == pytest.approx(0.93 * AMBIGUITY_PENALTY, abs=0.01)

    def test_borderline_confidence(self, armatrix_matcher):
        """Confidence exactly at threshold → no penalty (>= threshold)."""
        name = "Armatrix Lr-35 (L)"
        norm = _normalize_for_matching(name)
        digit_pos = [i for i, c in enumerate(norm) if c.isdigit()]
        scores = scores_with_low_at(
            len(norm), digit_pos,
            low=AMBIGUITY_CONFIDENCE_THRESHOLD)  # exactly at threshold
        r = armatrix_matcher.match(name, scores, 0.93)
        assert r.confidence == pytest.approx(0.93)
        assert not r.ambiguous

    def test_just_below_threshold(self, armatrix_matcher):
        """Confidence just below threshold → penalty applies."""
        name = "Armatrix Lr-35 (L)"
        norm = _normalize_for_matching(name)
        digit_pos = [i for i, c in enumerate(norm) if c.isdigit()]
        scores = scores_with_low_at(
            len(norm), digit_pos,
            low=AMBIGUITY_CONFIDENCE_THRESHOLD - 0.01)
        r = armatrix_matcher.match(name, scores, 0.93)
        assert r.ambiguous
        assert r.confidence < 0.93

    def test_non_ambiguous_item_unaffected(self):
        """Items not in any ambiguity group get no ambiguity penalty."""
        m = make_matcher(["Soft Hide", "Hard Rock", "ArMatrix LR-10 (L)"])
        # Soft Hide is unique — no sibling items
        scores = [0.50] * 9  # even with terrible scores
        r = m.match("Soft Hide", scores, 0.93)
        assert r.confidence == pytest.approx(0.93)
        assert not r.ambiguous

    def test_no_per_char_scores_penalizes_ambiguous(self, armatrix_matcher):
        """Without per-char scores, ambiguous items always get penalized."""
        r = armatrix_matcher.match("Armatrix Lr-35 (L)", None, 0.93)
        assert r.ambiguous
        assert r.confidence == pytest.approx(0.93 * AMBIGUITY_PENALTY, abs=0.01)

    def test_different_digit_count_in_group(self):
        """Items with different digit lengths in same skeleton group."""
        names = ["Item 5 (L)", "Item 10 (L)", "Item 100 (L)"]
        m = make_matcher(names)
        # These all have skeleton "item # (l)"
        assert len(m._ambiguity_groups) == 1

        # Match "Item 10 (L)" with high confidence
        norm = _normalize_for_matching("Item 10 (L)")
        scores = high_scores(len(norm))
        r = m.match("Item 10 (L)", scores, 0.93)
        assert r.matched_name == "Item 10 (L)"

    def test_single_digit_difference(self):
        """Two items differing by exactly 1 digit character."""
        m = make_matcher(["Weapon X5", "Weapon X0"])
        # Both have skeleton "weapon x#"
        norm = _normalize_for_matching("Weapon X5")
        # High confidence at the digit position
        scores = high_scores(len(norm))
        r = m.match("Weapon X5", scores, 0.93)
        assert r.matched_name == "Weapon X5"
        assert not r.ambiguous

        # Low confidence at the digit position (last char = index 8)
        scores = scores_with_low_at(len(norm), [8])  # '5' position
        r = m.match("Weapon X5", scores, 0.93)
        assert r.ambiguous

    def test_alpha_core_cards(self):
        """Large ambiguity group (Alpha Core Cards #1-#31)."""
        names = [f"Alpha Core Card #{i}" for i in range(1, 32)]
        m = make_matcher(names)
        # All 31 items share skeleton "alpha core card ##"
        groups = {k: v for k, v in m._ambiguity_groups.items()
                  if "alpha core card" in k}
        assert len(groups) == 1
        group = list(groups.values())[0]
        assert len(group) == 31


# ======================================================================
# Edge cases
# ======================================================================

class TestEdgeCases:
    def test_empty_ocr_name(self):
        m = make_matcher(["Soft Hide"])
        r = m.match("", [], 0.0)
        assert r.matched_name == ""

    def test_single_character_item(self):
        m = make_matcher(["X"])
        r = m.match("X", [0.95], 0.95)
        assert r.matched_name == "X"
        assert r.edit_distance == 0

    def test_case_differences_dont_count(self):
        """Case is normalized — 'SOFT HIDE' matches 'Soft Hide' at dist 0."""
        m = make_matcher(["Soft Hide"])
        r = m.match("SOFT HIDE", high_scores(9), 0.93)
        assert r.matched_name == "Soft Hide"
        assert r.edit_distance == 0

    def test_multiple_normalizations_combined(self):
        """Comma→period + underscore→space + case — all at distance 0."""
        m = make_matcher(["Item, Name Here"])
        r = m.match("ITEM._NAME_HERE", high_scores(15), 0.93)
        # normalized: "item. name here" matches "item. name here"
        assert r.matched_name == "Item, Name Here"
        assert r.edit_distance == 0

    def test_fuzzy_match_picks_closest(self):
        """When multiple items exist, picks the one with smallest distance."""
        m = make_matcher(["Abc", "Abx", "Xyz"])
        r = m.match("Aby", high_scores(3), 0.93)
        # "Aby" is dist 1 from both "Abc" and "Abx", dist 3 from "Xyz"
        assert r.edit_distance == 1
        assert r.matched_name in ("Abc", "Abx")

    def test_ambiguity_with_fuzzy_match(self):
        """Fuzzy match that finds multiple candidates at same distance."""
        m = make_matcher(["Cat", "Car", "Cap"])
        r = m.match("Cax", high_scores(3), 0.93)
        # "Cax" is dist 1 from Cat, Car, Cap — ambiguous fuzzy match
        assert r.edit_distance == 1
        assert r.ambiguous
        assert len(r.candidates) == 3

    def test_per_char_scores_shorter_than_name(self):
        """Per-char scores list shorter than name (truncated OCR)."""
        m = make_matcher(["ArMatrix LR-10 (L)", "ArMatrix LR-15 (L)"])
        # Only 5 scores for a 18-char name
        r = m.match("Armatrix Lr-10 (L)", [0.95] * 5, 0.93)
        assert r.matched_name == "ArMatrix LR-10 (L)"
        # Ambiguous positions at 12,13 are beyond score list → treated as low
        assert r.ambiguous

    def test_data_client_failure_graceful(self):
        """If data client throws, matcher degrades gracefully."""
        class FailingClient:
            def get_items(self):
                raise ConnectionError("Network down")

        m = ItemNameMatcher(FailingClient())
        r = m.match("Soft Hide", high_scores(9), 0.93)
        assert r.matched_name == "Soft Hide"
        assert r.confidence == 0.93

    def test_confidence_penalty_stacks_with_edit_distance(self):
        """Ambiguity penalty compounds with edit distance penalty."""
        names = [f"Item {n}" for n in range(10, 100, 5)]
        m = make_matcher(names)
        # Fuzzy match at dist 1 + ambiguity
        norm = _normalize_for_matching("Item 11")  # dist 1 from "Item 10" and "Item 15"
        scores = [0.50] * len(norm)  # low confidence everywhere
        r = m.match("Item 11", scores, 0.93)
        # Should have both edit distance penalty AND ambiguity penalty
        edit_penalty = 1.0 - PENALTY_PER_EDIT * r.edit_distance
        max_possible = 0.93 * edit_penalty * AMBIGUITY_PENALTY
        assert r.confidence <= max_possible + 0.01
