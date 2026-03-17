"""Reusable STPK-based per-character text reader.

Extracted from MarketPriceDetector to avoid duplicating the blob-based
STPK matching pipeline. Provides configurable blob segmentation, 4-bit
grid matching, and space detection via inter-blob gap analysis.

Used by:
  - MarketPriceDetector (Quicksand Bold, size 12/14)
  - PlayerStatusDetector tool name OCR (Arial Unicode MS, size 12)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

from .skill_disambiguation import normalize_blob
from .stpk import read_stpk
from ..core.logger import get_logger

log = get_logger("StpkTextReader")

# Default constants (calibrated for market price text)
_DEFAULT_BRIGHTNESS_THRESHOLD = 80
_DEFAULT_MIN_COL_DENSITY = 2
_DEFAULT_VALLEY_THRESHOLD = 23
_DEFAULT_MAX_SINGLE_CHAR_W = 10
_DEFAULT_MIN_SUB_BLOB_W = 3
_DEFAULT_MIN_MATCH_SCORE = 0.4


class StpkTextReader:
    """Reads text from BGR image regions using STPK template matching.

    Pipeline:
      1. Extract text intensity (threshold dark bg, normalize, re-threshold)
      2. Quantize to 4-bit lightness
      3. Find text vertical bounds
      4. Segment into blobs (contiguous column groups with density >= min_col_density)
      5. Split wide blobs at intensity valleys
      6. Match each blob against STPK entries using 4-bit soft-overlap scoring
      7. Detect spaces via inter-blob gap analysis
    """

    def __init__(
        self,
        entries: list[dict],
        grid_w: int,
        grid_h: int,
        *,
        brightness_threshold: int = _DEFAULT_BRIGHTNESS_THRESHOLD,
        min_col_density: int = _DEFAULT_MIN_COL_DENSITY,
        valley_threshold: int = _DEFAULT_VALLEY_THRESHOLD,
        max_single_char_w: int = _DEFAULT_MAX_SINGLE_CHAR_W,
        min_sub_blob_w: int = _DEFAULT_MIN_SUB_BLOB_W,
        min_match_score: float = _DEFAULT_MIN_MATCH_SCORE,
        right_align: bool = False,
        allowed_chars: set[str] | None = None,
    ):
        self._grid_w = grid_w
        self._grid_h = grid_h
        self._brightness_threshold = brightness_threshold
        self._min_col_density = min_col_density
        self._valley_threshold = valley_threshold
        self._max_single_char_w = max_single_char_w
        self._min_sub_blob_w = min_sub_blob_w
        self._min_match_score = min_match_score
        self._right_align = right_align

        # Filter entries to allowed characters if specified
        if allowed_chars is not None:
            self._entries = [
                e for e in entries
                if e.get("text", "") in allowed_chars
            ]
        else:
            self._entries = list(entries)

        # Pre-split into single-char and multi-char entries
        self._single_entries = [
            e for e in self._entries if e.get("content_w", 0) <= grid_w
        ]
        self._multi_entries = [
            e for e in self._entries
            if len(e.get("text", "")) > 1 and e.get("content_w", 0) > 0
        ]

    @classmethod
    def from_stpk(
        cls,
        stpk_path: str | Path,
        **kwargs,
    ) -> "StpkTextReader":
        """Create a reader from an STPK file path.

        Applies grid floor cleanup: zeroes faint anti-aliased template
        pixels that fall below the brightness threshold after 4-bit
        quantization. Without this, template content_h can be inflated
        by sub-threshold edge pixels, causing alignment mismatches in
        normalize_blob (bottom-aligned placement).
        """
        header, entries = read_stpk(stpk_path)
        brightness = kwargs.get(
            "brightness_threshold", _DEFAULT_BRIGHTNESS_THRESHOLD
        )
        grid_floor = int(brightness / 16)
        for e in entries:
            g = e.get("grid")
            if g is not None:
                e["grid"] = np.where(g >= grid_floor, g, 0).astype(np.uint8)
        return cls(
            entries,
            header["grid_w"],
            header["grid_h"],
            right_align=header.get("right_align", False),
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read_text(
        self, region_bgr: np.ndarray,
    ) -> tuple[str, float, list[float]]:
        """Read text from a BGR image region.

        Returns:
            (text, min_confidence, per_char_scores) where:
            - text: matched string with spaces
            - min_confidence: minimum per-character score (0.0 if empty)
            - per_char_scores: parallel to text chars (1.0 for spaces)
        """
        if not self._entries:
            return "", 0.0, []

        text, scores, _blob_texts = self._match_blobs(region_bgr)

        # Expand per-blob scores to per-character (spaces get 1.0)
        per_char: list[float] = []
        score_idx = 0
        for ch in text:
            if ch == " ":
                per_char.append(1.0)
            elif score_idx < len(scores):
                per_char.append(scores[score_idx])
                score_idx += 1
            else:
                per_char.append(0.0)

        return text, (min(scores) if scores else 0.0), per_char

    # ------------------------------------------------------------------
    # Intensity extraction
    # ------------------------------------------------------------------

    def _extract_text_intensity(self, region: np.ndarray) -> np.ndarray:
        """Extract text pixel intensity from a BGR region.

        Pipeline:
          1. Zero pixels below brightness floor (suppress background bleed)
          2. Normalize surviving pixels to full 0-255 range
          3. Re-threshold to clean up residual noise
        """
        if len(region.shape) == 3:
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        else:
            gray = region

        threshold = self._brightness_threshold

        # 1. Background floor
        intensity = gray.copy()
        intensity[intensity < threshold] = 0

        # 2. Contrast normalization
        if intensity.max() > 0:
            intensity = cv2.normalize(
                intensity, None, 0, 255,
                cv2.NORM_MINMAX, dtype=cv2.CV_8U,
            )

        # 3. Re-threshold
        intensity[intensity < threshold] = 0
        return intensity

    # ------------------------------------------------------------------
    # Blob matching pipeline
    # ------------------------------------------------------------------

    def _match_blobs(
        self, region: np.ndarray,
    ) -> tuple[str, list[float], list[str]]:
        """Full blob-based STPK matching pipeline.

        Returns (joined_text, per_blob_scores, blob_texts) where
        blob_texts are the non-space entries parallel to scores.
        """
        intensity = self._extract_text_intensity(region)

        # Quantize to 4-bit lightness
        intensity_4bit = np.minimum(
            intensity.astype(np.float32) / 16, 15
        ).astype(np.uint8)

        # Find text vertical bounds
        rows_with_content = np.any(intensity_4bit > 0, axis=1)
        if not rows_with_content.any():
            return "", [], []

        text_top = int(np.argmax(rows_with_content))
        text_bot = int(
            len(rows_with_content) - 1 - np.argmax(rows_with_content[::-1])
        )
        text_h = text_bot - text_top + 1
        if text_h < 3:
            return "", [], []

        # Find blobs: contiguous column ranges with sufficient text density
        text_region = intensity_4bit[text_top:text_bot + 1, :]
        col_density = np.sum(text_region > 0, axis=0)
        col_has = col_density >= self._min_col_density
        blobs: list[tuple[int, int]] = []
        start = -1
        for col in range(len(col_has) + 1):
            has = col < len(col_has) and col_has[col]
            if has and start < 0:
                start = col
            elif not has and start >= 0:
                blobs.append((start, col - 1))
                start = -1

        if not blobs:
            return "", [], []

        # Split wide blobs at intensity valleys
        blobs = self._split_blobs_at_valleys(
            intensity_4bit, blobs, text_top, text_h,
        )
        # Merge narrow pairs (e.g. '"' rendered as two tick marks)
        blobs = _merge_narrow_pairs(blobs)

        # Compute median inter-blob gap to detect word spaces
        gaps = []
        for j in range(1, len(blobs)):
            gap = blobs[j][0] - blobs[j - 1][1] - 1
            if gap > 0:
                gaps.append(gap)
        if gaps:
            median_gap = float(sorted(gaps)[len(gaps) // 2])
            space_threshold = max(median_gap * 2, 4)
        else:
            space_threshold = 4

        # Match each blob against STPK entries
        result_chars: list[str] = []
        result_scores: list[float] = []
        grid_w = self._grid_w
        grid_h = self._grid_h
        right_align = self._right_align
        min_score = self._min_match_score

        i = 0
        while i < len(blobs):
            x0, x1 = blobs[i]
            blob_w = x1 - x0 + 1

            # Insert space if gap from previous blob is large enough
            if i > 0:
                gap = x0 - blobs[i - 1][1] - 1
                if gap >= space_threshold:
                    result_chars.append(" ")

            # Try multi-character entries that span consecutive blobs
            best_multi_score = -1.0
            best_multi_text = None
            best_multi_span = 0
            for entry in self._multi_entries:
                cw = entry.get("content_w", 0)
                if cw == 0:
                    continue
                span_x1 = x0 + cw - 1
                span_count = 0
                for j in range(i, len(blobs)):
                    if blobs[j][0] <= span_x1:
                        span_count = j - i + 1
                    else:
                        break
                if span_count < 2:
                    continue
                actual_x1 = blobs[i + span_count - 1][1]
                actual_w = actual_x1 - x0 + 1
                if abs(actual_w - cw) > 5:
                    continue
                entry_grid = entry.get("grid")
                if entry_grid is not None:
                    candidate = normalize_blob(
                        intensity_4bit, x0, actual_x1,
                        text_top, text_h, grid_w, grid_h, right_align,
                    )
                    score = score_grid(candidate, entry_grid)
                    if score > best_multi_score:
                        best_multi_score = score
                        best_multi_text = entry.get("text", "")
                        best_multi_span = span_count

            if best_multi_score > min_score and best_multi_text:
                result_chars.append(best_multi_text)
                result_scores.append(best_multi_score)
                i += best_multi_span
                continue

            # Auto-detect baseline periods (right-aligned digit mode only)
            if right_align and blob_w <= 2:
                region_slice = intensity_4bit[
                    text_top:text_top + text_h, x0:x1 + 1
                ]
                content_rows = np.any(region_slice > 0, axis=1)
                if content_rows.any():
                    first_content = int(np.argmax(content_rows))
                    if first_content >= text_h - 3:
                        result_chars.append(".")
                        result_scores.append(0.9)
                        i += 1
                        continue

            # Single-blob matching
            best_score = -1.0
            best_text = None

            candidate = normalize_blob(
                intensity_4bit, x0, x1,
                text_top, text_h, grid_w, grid_h, right_align,
            )
            for entry in self._single_entries:
                entry_grid = entry.get("grid")
                if entry_grid is None:
                    continue
                score = score_grid(candidate, entry_grid)
                if score > best_score:
                    best_score = score
                    best_text = entry.get("text", "")

            if best_score > min_score and best_text:
                result_chars.append(best_text)
                result_scores.append(best_score)

            i += 1

        blob_texts = [c for c in result_chars if c != " "]
        return "".join(result_chars), result_scores, blob_texts

    # ------------------------------------------------------------------
    # Blob splitting
    # ------------------------------------------------------------------

    def _split_blobs_at_valleys(
        self,
        intensity_4bit: np.ndarray,
        blobs: list[tuple[int, int]],
        text_top: int,
        text_h: int,
    ) -> list[tuple[int, int]]:
        """Split wide blobs at low-intensity column valleys."""
        result: list[tuple[int, int]] = []
        rows = min(text_h, intensity_4bit.shape[0] - text_top)
        max_single_w = self._max_single_char_w
        valley_threshold = self._valley_threshold
        min_sub_w = self._min_sub_blob_w

        for x0, x1 in blobs:
            w = x1 - x0 + 1
            if w <= max_single_w:
                result.append((x0, x1))
                continue

            region = intensity_4bit[text_top:text_top + rows, x0:x1 + 1]
            col_sums = region.sum(axis=0)

            sub_start = 0
            i = 0
            sub_blobs: list[tuple[int, int]] = []
            while i < len(col_sums):
                if col_sums[i] < valley_threshold:
                    if i > sub_start:
                        sub_blobs.append((x0 + sub_start, x0 + i - 1))
                    while (i < len(col_sums)
                           and col_sums[i] < valley_threshold):
                        i += 1
                    sub_start = i
                else:
                    i += 1

            if sub_start < len(col_sums):
                sub_blobs.append((x0 + sub_start, x1))

            if len(sub_blobs) > 1:
                narrow = sum(
                    1 for sb in sub_blobs
                    if sb[1] - sb[0] + 1 < min_sub_w
                )
                if narrow > 1:
                    result.append((x0, x1))
                else:
                    result.extend(sub_blobs)
            else:
                result.append((x0, x1))

        # Force-split blobs still too wide for a single character
        force_split_w = int(max_single_w * 1.6)
        if not any((x1 - x0 + 1) >= force_split_w for x0, x1 in result):
            return result

        final: list[tuple[int, int]] = []
        for sx0, sx1 in result:
            sw = sx1 - sx0 + 1
            if sw >= force_split_w:
                region_slice = intensity_4bit[
                    text_top:text_top + rows, sx0:sx1 + 1
                ]
                col_sums = region_slice.sum(axis=0).astype(np.int32)
                margin = min_sub_w
                if sw > margin * 2 + 1:
                    zone = col_sums[margin:sw - margin]
                    if len(zone) > 0:
                        min_idx = int(np.argmin(zone)) + margin
                        left_end = sx0 + min_idx - 1
                        right_start = sx0 + min_idx + 1
                        if (left_end - sx0 + 1 >= min_sub_w
                                and sx1 - right_start + 1 >= min_sub_w):
                            final.append((sx0, left_end))
                            final.append((right_start, sx1))
                            continue
            final.append((sx0, sx1))
        return final


# ======================================================================
# Module-level utilities
# ======================================================================

def _merge_narrow_pairs(
    blobs: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Merge pairs of very narrow, closely-spaced blobs.

    Characters like '"' are rendered as two separate tick marks with a
    small gap. Merges adjacent blobs where both are <= 2px wide and
    the gap between them is <= 2px.
    """
    if len(blobs) < 2:
        return blobs

    MAX_TICK_W = 2
    MAX_GAP = 2

    result: list[tuple[int, int]] = []
    i = 0
    while i < len(blobs):
        if i + 1 < len(blobs):
            x0a, x1a = blobs[i]
            x0b, x1b = blobs[i + 1]
            wa = x1a - x0a + 1
            wb = x1b - x0b + 1
            gap = x0b - x1a - 1
            if wa <= MAX_TICK_W and wb <= MAX_TICK_W and gap <= MAX_GAP:
                result.append((x0a, x1b))
                i += 2
                continue
        result.append(blobs[i])
        i += 1
    return result


def score_grid_raw(candidate: np.ndarray, template: np.ndarray) -> float:
    """Score a candidate grid against a template using soft overlap.

    Formula: 6 * sum(min(obs, tmpl)) - 2 * sum(tmpl) - sum(obs)
    Normalized by 3 * sum(tmpl).
    """
    if candidate.shape != template.shape:
        return -1.0
    c = candidate.astype(np.int32)
    t = template.astype(np.int32)
    overlap = int(np.sum(np.minimum(c, t)))
    t_sum = int(np.sum(t))
    c_sum = int(np.sum(c))
    if t_sum == 0:
        return 0.0
    raw = 6 * overlap - 2 * t_sum - c_sum
    max_possible = 3 * t_sum
    if max_possible <= 0:
        return 0.0
    return float(raw) / float(max_possible)


def score_grid(candidate: np.ndarray, template: np.ndarray) -> float:
    """Shift-tolerant grid scoring.

    Tries horizontal shifts of -1, 0, +1 to handle subpixel positioning
    differences and returns the best score.
    """
    best = score_grid_raw(candidate, template)
    h, w = candidate.shape
    for shift in (-1, 1):
        shifted = np.zeros_like(candidate)
        if shift > 0:
            shifted[:, shift:] = candidate[:, :-shift]
        else:
            shifted[:, :w + shift] = candidate[:, -shift:]
        s = score_grid_raw(shifted, template)
        if s > best:
            best = s
    return best
