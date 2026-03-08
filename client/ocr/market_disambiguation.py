"""Market price scanner disambiguation heuristics.

Provides tiebreaker heuristics for text character pairs (5/S, D/O, etc.)
and digit pairs that are confusable in the game's market price window.
These operate on normalized 4-bit grids and are used exclusively by the
market price detector.

Digit tiebreakers are intentionally separate from the skill scanner's
version (skill_disambiguation.py) so each can be tuned independently.
"""

from typing import Optional

import numpy as np

from ..core.logger import get_logger
from .skill_disambiguation import normalize_blob, get_content_bounds

log = get_logger("MarketDisambiguation")


# ---------------------------------------------------------------------------
# Margin constants
# ---------------------------------------------------------------------------

# Digit margins (market-specific, can differ from skill scanner)
ZERO_NINE_MAX_MARGIN_0TO9 = 100
ZERO_NINE_MAX_MARGIN_9TO0 = 30
FIVE_SIX_MAX_MARGIN = 30
THREE_EIGHT_MAX_MARGIN = 100
ZERO_SIX_MAX_MARGIN = 30
ZERO_SIX_CENTER_SUM_MIN = 80

# Text disambiguation margin (grid score difference)
TEXT_DISAMBIGUATION_MARGIN = 0.15


# ---------------------------------------------------------------------------
# Digit tiebreakers (market-specific copies)
# ---------------------------------------------------------------------------

def disambiguate_zero_nine(grid: np.ndarray) -> Optional[int]:
    """Resolve 0/9 using bottom-left content.

    '0' closes symmetrically — strong bottom-left content.
    '9' has a tail on the right — sparse bottom-left.
    """
    bounds = get_content_bounds(grid)
    if bounds is None:
        return None
    col_l, col_r, row_t, row_b = bounds
    cw = col_r - col_l + 1
    ch = row_b - row_t + 1
    if cw < 3 or ch < 5:
        return None

    bot_start = row_b - max(2, ch // 4)
    mid_col = col_l + cw // 2
    bot_left = grid[bot_start:row_b + 1, col_l:mid_col]
    bot_left_sum = int(np.sum(bot_left))

    if bot_left_sum > 30:
        return 0
    if bot_left_sum < 10:
        return 9
    return None


def disambiguate_five_six(grid: np.ndarray) -> Optional[int]:
    """Resolve 5/6 using top-bar detection."""
    top_sum = int(np.sum(grid[0, :]))
    if top_sum == 0:
        return 6
    return 5


def disambiguate_three_eight(grid: np.ndarray) -> Optional[int]:
    """Resolve 3/8 using left-edge vertical coverage.

    '8' has left content on most rows (closed loops).
    '3' is open on the left — fewer rows with left content.
    """
    bounds = get_content_bounds(grid)
    if bounds is None:
        return None
    col_l, col_r, row_t, row_b = bounds
    cw = col_r - col_l + 1
    ch = row_b - row_t + 1
    if cw < 3 or ch < 5:
        return None

    left_edge = grid[row_t:row_b + 1, col_l:col_l + 2]
    rows_with_left = int(np.sum(np.any(left_edge > 0, axis=1)))
    left_coverage = rows_with_left / ch

    if left_coverage >= 0.70:
        return 8
    if left_coverage <= 0.45:
        return 3
    return None


def disambiguate_zero_six(grid: np.ndarray) -> Optional[int]:
    """Resolve 0/6 using center-core density."""
    bounds = get_content_bounds(grid)
    if bounds is None:
        return None
    col_l, col_r, row_t, row_b = bounds
    cw = col_r - col_l + 1
    ch = row_b - row_t + 1
    if cw < 3 or ch < 5:
        return None

    mid_row_start = row_t + ch // 3
    mid_row_end = row_t + 2 * ch // 3
    mid_col_start = col_l + cw // 3
    mid_col_end = col_l + 2 * cw // 3
    if mid_row_end < mid_row_start or mid_col_end < mid_col_start:
        return None

    center_sum = int(np.sum(
        grid[mid_row_start:mid_row_end + 1, mid_col_start:mid_col_end + 1]
    ))
    return 6 if center_sum >= ZERO_SIX_CENTER_SUM_MIN else 0


# ---------------------------------------------------------------------------
# Text tiebreakers
# ---------------------------------------------------------------------------

def disambiguate_five_s(grid: np.ndarray) -> Optional[str]:
    """Resolve '5' vs 'S' using bottom-half rightward extent.

    'S' extends further right in its bottom half (the S-curve pushes
    rightward).  '5' has roughly equal extent in both halves.
    """
    bounds = get_content_bounds(grid)
    if bounds is None:
        return None
    col_l, col_r, row_t, row_b = bounds
    cw = col_r - col_l + 1
    ch = row_b - row_t + 1
    if cw < 3 or ch < 5:
        return None

    mid = row_t + ch // 2
    top_half = grid[row_t:mid, col_l:col_r + 1]
    bot_half = grid[mid:row_b + 1, col_l:col_r + 1]

    top_cols = np.any(top_half > 0, axis=0)
    bot_cols = np.any(bot_half > 0, axis=0)

    top_right_ext = 0
    for c in range(len(top_cols) - 1, -1, -1):
        if top_cols[c]:
            top_right_ext = c
            break

    bot_right_ext = 0
    for c in range(len(bot_cols) - 1, -1, -1):
        if bot_cols[c]:
            bot_right_ext = c
            break

    if bot_right_ext > top_right_ext:
        return "S"
    if bot_right_ext <= top_right_ext - 1:
        return "5"
    return None


def disambiguate_d_o(grid: np.ndarray) -> Optional[str]:
    """Resolve 'D' vs 'O' using left-edge vertical stroke.

    'D' has a vertical stroke spanning nearly the full height on the
    left side; 'O' has content only in the middle rows on the left.
    """
    bounds = get_content_bounds(grid)
    if bounds is None:
        return None
    col_l, col_r, row_t, row_b = bounds
    ch = row_b - row_t + 1
    if ch < 5:
        return None

    left_edge = grid[row_t:row_b + 1, col_l:col_l + 2]
    rows_with_left = int(np.sum(np.any(left_edge > 0, axis=1)))
    left_coverage = rows_with_left / ch

    if left_coverage > 0.85:
        return "D"
    if left_coverage < 0.75:
        return "O"
    return None


def disambiguate_zero_o(grid: np.ndarray) -> Optional[str]:
    """Resolve '0' vs 'O' using aspect ratio.

    'O' is squarer (wider); '0' is taller/narrower.
    """
    bounds = get_content_bounds(grid)
    if bounds is None:
        return None
    col_l, col_r, row_t, row_b = bounds
    cw = col_r - col_l + 1
    ch = row_b - row_t + 1
    if cw < 3 or ch < 5:
        return None

    aspect = cw / ch
    if aspect >= 0.78:
        return "O"
    if aspect <= 0.65:
        return "0"
    return None


def disambiguate_one_i(grid: np.ndarray) -> Optional[str]:
    """Resolve '1' vs 'I' using top-left diagonal stroke.

    '1' has an angled serif/stroke at the top-left; 'I' is a clean bar.
    """
    bounds = get_content_bounds(grid)
    if bounds is None:
        return None
    col_l, col_r, row_t, row_b = bounds
    cw = col_r - col_l + 1
    ch = row_b - row_t + 1
    if ch < 5:
        return None

    top_rows = min(3, ch // 3)
    top_zone = grid[row_t:row_t + top_rows, col_l:col_l + max(2, cw // 2)]
    top_left_sum = int(np.sum(top_zone))

    bottom_row = grid[row_b, col_l:col_r + 1]
    bottom_coverage = np.count_nonzero(bottom_row) / max(cw, 1)

    if top_left_sum > 15 or (cw >= 4 and bottom_coverage > 0.7):
        return "1"
    if cw <= 3 and top_left_sum < 10:
        return "I"
    return None


def disambiguate_eight_b(grid: np.ndarray) -> Optional[str]:
    """Resolve '8' vs 'B' using left-edge symmetry.

    'B' has a solid left vertical stroke; '8' has equal left/right curves.
    """
    bounds = get_content_bounds(grid)
    if bounds is None:
        return None
    col_l, col_r, row_t, row_b = bounds
    cw = col_r - col_l + 1
    ch = row_b - row_t + 1
    if cw < 3 or ch < 5:
        return None

    left_edge = grid[row_t:row_b + 1, col_l:col_l + 2]
    rows_with_left = int(np.sum(np.any(left_edge > 0, axis=1)))
    left_coverage = rows_with_left / ch

    right_edge = grid[row_t:row_b + 1, col_r - 1:col_r + 1]
    rows_with_right = int(np.sum(np.any(right_edge > 0, axis=1)))
    right_coverage = rows_with_right / ch

    if left_coverage > 0.85 and left_coverage - right_coverage > 0.1:
        return "B"
    if abs(left_coverage - right_coverage) < 0.1:
        return "8"
    return None


def disambiguate_r_p(grid: np.ndarray) -> Optional[str]:
    """Resolve 'R' vs 'P' using bottom-right content.

    'R' has a diagonal leg in the bottom-right quadrant.
    'P' has only a vertical stem on the left — empty bottom-right.
    """
    bounds = get_content_bounds(grid)
    if bounds is None:
        return None
    col_l, col_r, row_t, row_b = bounds
    cw = col_r - col_l + 1
    ch = row_b - row_t + 1
    if cw < 4 or ch < 5:
        return None

    bot_start = row_b - min(3, ch // 3)
    mid_col = col_l + cw // 2
    bot_right = grid[bot_start:row_b + 1, mid_col:col_r + 1]
    bot_right_sum = int(np.sum(bot_right))

    if bot_right_sum > 30:
        return "R"
    if bot_right_sum < 10:
        return "P"
    return None


def disambiguate_c_o(grid: np.ndarray) -> Optional[str]:
    """Resolve 'C' vs 'O' using right-side openness.

    'O' is a closed loop — right side has content in the middle rows.
    'C' is open on the right — middle rows have no right-side content.
    """
    bounds = get_content_bounds(grid)
    if bounds is None:
        return None
    col_l, col_r, row_t, row_b = bounds
    cw = col_r - col_l + 1
    ch = row_b - row_t + 1
    if cw < 4 or ch < 5:
        return None

    mid_start = row_t + ch // 3
    mid_end = row_t + 2 * ch // 3
    right_mid = grid[mid_start:mid_end + 1, col_r - 1:col_r + 1]
    right_mid_sum = int(np.sum(right_mid))

    if right_mid_sum > 25:
        return "O"
    if right_mid_sum < 10:
        return "C"
    return None


def disambiguate_d_c(grid: np.ndarray) -> Optional[str]:
    """Resolve 'D' vs 'C' using left-edge vertical stroke.

    'D' has a solid left vertical stroke; 'C' curves — less left coverage.
    """
    bounds = get_content_bounds(grid)
    if bounds is None:
        return None
    col_l, col_r, row_t, row_b = bounds
    ch = row_b - row_t + 1
    if ch < 5:
        return None

    left_edge = grid[row_t:row_b + 1, col_l:col_l + 2]
    rows_with_left = int(np.sum(np.any(left_edge > 0, axis=1)))
    left_coverage = rows_with_left / ch

    if left_coverage > 0.85:
        return "D"
    if left_coverage < 0.75:
        return "C"
    return None


def disambiguate_apostrophe_backtick(grid: np.ndarray) -> Optional[str]:
    """Resolve apostrophe vs backtick using stroke direction.

    Apostrophe (') tapers top-right to bottom-left.
    Backtick (`) tapers top-left to bottom-right.
    """
    bounds = get_content_bounds(grid)
    if bounds is None:
        return None
    col_l, col_r, row_t, row_b = bounds
    cw = col_r - col_l + 1
    ch = row_b - row_t + 1
    if cw < 1 or ch < 2:
        return None

    top_half = max(1, ch // 2)
    top_region = grid[row_t:row_t + top_half, col_l:col_r + 1]

    left_sum = int(np.sum(top_region[:, :max(1, cw // 2)]))
    right_sum = int(np.sum(top_region[:, max(1, cw // 2):]))

    if right_sum > left_sum * 1.3:
        return "'"
    if left_sum > right_sum * 1.3:
        return "`"
    return None


# ---------------------------------------------------------------------------
# Confusable pair definitions
# ---------------------------------------------------------------------------

DIGIT_TIEBREAKER_PAIRS = [
    (0, 9, disambiguate_zero_nine),
    (5, 6, disambiguate_five_six),
    (3, 8, disambiguate_three_eight),
    (0, 6, disambiguate_zero_six),
]

DIGIT_TIEBREAKER_MARGINS = {
    (0, 9): (ZERO_NINE_MAX_MARGIN_0TO9, ZERO_NINE_MAX_MARGIN_9TO0),
    (5, 6): (FIVE_SIX_MAX_MARGIN, FIVE_SIX_MAX_MARGIN),
    (3, 8): (THREE_EIGHT_MAX_MARGIN, THREE_EIGHT_MAX_MARGIN),
    (0, 6): (ZERO_SIX_MAX_MARGIN, ZERO_SIX_MAX_MARGIN),
}

TEXT_TIEBREAKER_PAIRS = [
    ("5", "S", disambiguate_five_s),
    ("D", "O", disambiguate_d_o),
    ("0", "O", disambiguate_zero_o),
    ("1", "I", disambiguate_one_i),
    ("8", "B", disambiguate_eight_b),
    ("R", "P", disambiguate_r_p),
    ("C", "O", disambiguate_c_o),
    ("D", "C", disambiguate_d_c),
    ("'", "`", disambiguate_apostrophe_backtick),
]


# ---------------------------------------------------------------------------
# High-level dispatchers
# ---------------------------------------------------------------------------

def apply_digit_tiebreakers(
    classified: list[dict],
    intensity_4bit: np.ndarray,
    text_top: int,
    text_h: int,
    grid_w: int,
    grid_h: int,
) -> None:
    """Apply market-specific digit tiebreakers (in-place)."""
    for char_a, char_b, disambiguator in DIGIT_TIEBREAKER_PAIRS:
        margins = DIGIT_TIEBREAKER_MARGINS[(char_a, char_b)]
        for c in classified:
            if c["digit"] not in (char_a, char_b):
                continue
            margin = abs(c["scores"][char_a] - c["scores"][char_b])
            max_margin = margins[0] if c["digit"] == char_a else margins[1]
            if margin > max_margin:
                continue

            grid = normalize_blob(
                intensity_4bit, c["x0"], c["x1"],
                text_top, text_h, grid_w, grid_h,
                right_align=True,
            )
            resolved = disambiguator(grid)
            if resolved is not None and resolved != c["digit"]:
                log.debug("%d→%d override: x%d-%d margin=%.1f",
                          c["digit"], resolved, c["x0"], c["x1"], margin)
                c["digit"] = resolved
                c["score"] = c["scores"][resolved]


def apply_text_tiebreakers(
    result_chars: list[str],
    result_scores: list[float],
    all_scores: list[dict[str, float]],
    intensity_4bit: np.ndarray,
    blob_positions: list[tuple[int, int]],
    text_top: int,
    text_h: int,
    grid_w: int,
    grid_h: int,
) -> None:
    """Apply market-specific text disambiguation (in-place)."""
    # Build index mapping: score_idx -> char_idx (skipping spaces)
    score_idx = 0
    char_to_score: dict[int, int] = {}
    for ci, ch in enumerate(result_chars):
        if ch != " ":
            char_to_score[ci] = score_idx
            score_idx += 1

    for char_a, char_b, disambiguator in TEXT_TIEBREAKER_PAIRS:
        for ci, ch in enumerate(result_chars):
            if ch not in (char_a, char_b):
                continue
            si = char_to_score.get(ci)
            if si is None or si >= len(all_scores):
                continue

            scores = all_scores[si]
            score_a = scores.get(char_a, -999.0)
            score_b = scores.get(char_b, -999.0)
            margin = abs(score_a - score_b)
            if margin > TEXT_DISAMBIGUATION_MARGIN:
                continue

            x0, x1 = blob_positions[si]
            grid = normalize_blob(
                intensity_4bit, x0, x1,
                text_top, text_h, grid_w, grid_h,
                right_align=False,
            )
            resolved = disambiguator(grid)
            if resolved is not None and resolved != ch:
                log.debug("'%s'→'%s' override: x%d-%d margin=%.3f",
                          ch, resolved, x0, x1, margin)
                result_chars[ci] = resolved
                if si < len(result_scores):
                    result_scores[si] = scores.get(resolved, result_scores[si])
