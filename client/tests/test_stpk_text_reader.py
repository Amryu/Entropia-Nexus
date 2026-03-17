"""Tests for the shared STPK text reader module."""

import numpy as np
import pytest

from client.ocr.stpk_text_reader import (
    StpkTextReader,
    score_grid,
    score_grid_raw,
    _merge_narrow_pairs,
)


# ---------------------------------------------------------------------------
# score_grid_raw / score_grid
# ---------------------------------------------------------------------------

class TestScoreGrid:
    """Tests for the 4-bit soft-overlap scoring function."""

    def test_identical_grids_score_high(self):
        grid = np.array([[0, 5, 10], [15, 8, 0]], dtype=np.uint8)
        assert score_grid_raw(grid, grid) > 0.9

    def test_empty_template_returns_zero(self):
        candidate = np.array([[5, 5], [5, 5]], dtype=np.uint8)
        template = np.zeros((2, 2), dtype=np.uint8)
        assert score_grid_raw(candidate, template) == 0.0

    def test_different_shapes_return_negative(self):
        a = np.zeros((3, 3), dtype=np.uint8)
        b = np.zeros((3, 4), dtype=np.uint8)
        assert score_grid_raw(a, b) == -1.0

    def test_disjoint_grids_score_low(self):
        candidate = np.array([[15, 0, 0], [0, 0, 0]], dtype=np.uint8)
        template = np.array([[0, 0, 15], [0, 0, 0]], dtype=np.uint8)
        assert score_grid_raw(candidate, template) < 0.0

    def test_shift_tolerance(self):
        """score_grid should handle ±1 column shifts."""
        template = np.zeros((5, 5), dtype=np.uint8)
        template[:, 2] = 10  # Vertical line at column 2

        shifted = np.zeros((5, 5), dtype=np.uint8)
        shifted[:, 3] = 10  # Shifted +1

        # Raw score should be poor (no overlap)
        raw = score_grid_raw(shifted, template)
        # Shift-tolerant score should be good
        tolerant = score_grid(shifted, template)
        assert tolerant > raw
        assert tolerant > 0.5


# ---------------------------------------------------------------------------
# _merge_narrow_pairs
# ---------------------------------------------------------------------------

class TestMergeNarrowPairs:
    def test_empty(self):
        assert _merge_narrow_pairs([]) == []

    def test_single_blob(self):
        assert _merge_narrow_pairs([(5, 10)]) == [(5, 10)]

    def test_merge_ticks(self):
        """Two narrow blobs with small gap should merge (e.g. double quote)."""
        blobs = [(10, 11), (14, 15)]  # w=2 each, gap=2
        result = _merge_narrow_pairs(blobs)
        assert result == [(10, 15)]

    def test_no_merge_wide_blobs(self):
        """Wide blobs should not merge."""
        blobs = [(10, 14), (17, 21)]
        result = _merge_narrow_pairs(blobs)
        assert result == [(10, 14), (17, 21)]

    def test_no_merge_large_gap(self):
        """Narrow blobs with large gap should not merge."""
        blobs = [(10, 11), (20, 21)]
        result = _merge_narrow_pairs(blobs)
        assert result == [(10, 11), (20, 21)]


# ---------------------------------------------------------------------------
# StpkTextReader construction
# ---------------------------------------------------------------------------

class TestStpkTextReader:
    def _make_entries(self, chars="ABC"):
        """Build fake STPK entries for testing."""
        entries = []
        for ch in chars:
            grid = np.zeros((10, 8), dtype=np.uint8)
            # Put some content so it's not all zeros
            grid[3:8, 1:6] = 10
            entries.append({
                "text": ch,
                "grid": grid,
                "bitmap": None,
                "bitmap_w": 0,
                "bitmap_h": 0,
                "content_w": 5,
                "content_h": 5,
            })
        return entries

    def test_init_with_entries(self):
        entries = self._make_entries("ABC")
        reader = StpkTextReader(entries, 8, 10)
        assert len(reader._entries) == 3
        assert len(reader._single_entries) == 3
        assert len(reader._multi_entries) == 0

    def test_allowed_chars_filter(self):
        entries = self._make_entries("ABCDE")
        reader = StpkTextReader(entries, 8, 10, allowed_chars={"A", "C", "E"})
        assert len(reader._entries) == 3
        texts = {e["text"] for e in reader._entries}
        assert texts == {"A", "C", "E"}

    def test_from_stpk_loads_file(self):
        """Test loading from the actual tool_text.stpk file."""
        import os
        stpk_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "assets", "stpk", "tool_text.stpk",
        )
        if not os.path.exists(stpk_path):
            pytest.skip("tool_text.stpk not found")

        reader = StpkTextReader.from_stpk(stpk_path, brightness_threshold=80)
        assert len(reader._entries) == 74
        assert reader._grid_w == 12
        assert reader._grid_h == 13

    def test_empty_region_returns_empty(self):
        entries = self._make_entries("ABC")
        reader = StpkTextReader(entries, 8, 10)
        # All-black region
        region = np.zeros((14, 100, 3), dtype=np.uint8)
        text, conf, scores = reader.read_text(region)
        assert text == ""
        assert conf == 0.0
        assert scores == []
