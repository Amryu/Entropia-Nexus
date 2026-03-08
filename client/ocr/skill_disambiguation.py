"""Skill scanner digit disambiguation heuristics.

Provides tiebreaker heuristics for digit pairs (0/9, 5/6, 3/8, 0/6) that
look similar in the game's Scaleform font.  These operate on normalized
4-bit grids and are used by the skill scanner's font_matcher.
"""

from typing import Optional

import numpy as np

from ..core.logger import get_logger

log = get_logger("Disambiguation")


# ---------------------------------------------------------------------------
# Margin constants — maximum score difference to trigger each tiebreaker
# ---------------------------------------------------------------------------

# 0-vs-9: asymmetric margins (HDR glow shifts scores for 0→9 more)
ZERO_NINE_MAX_MARGIN_0TO9 = 100
ZERO_NINE_MAX_MARGIN_9TO0 = 30

# 5-vs-6
FIVE_SIX_MAX_MARGIN = 30

# 3-vs-8 (wider margin: HDR glow fills left-side gaps of '3')
THREE_EIGHT_MAX_MARGIN = 100

# 0-vs-6
ZERO_SIX_MAX_MARGIN = 30
ZERO_SIX_CENTER_SUM_MIN = 80


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

def get_content_bounds(grid: np.ndarray):
    """Find tight bounding box of non-zero content in a grid.

    Returns (col_l, col_r, row_t, row_b) or None if empty.
    """
    content_cols = np.any(grid > 0, axis=0)
    content_rows = np.any(grid > 0, axis=1)
    if not content_cols.any() or not content_rows.any():
        return None

    col_l = int(np.argmax(content_cols))
    col_r = int(len(content_cols) - 1 - np.argmax(content_cols[::-1]))
    row_t = int(np.argmax(content_rows))
    row_b = int(len(content_rows) - 1 - np.argmax(content_rows[::-1]))
    return col_l, col_r, row_t, row_b


def normalize_blob(
    intensity_4bit: np.ndarray,
    x0: int, x1: int,
    text_top: int, text_h: int,
    grid_w: int, grid_h: int,
    right_align: bool = True,
) -> np.ndarray:
    """Place a blob into a grid at the correct alignment position.

    Extracts the tight content bounding box from the blob region,
    then places it aligned + bottom-aligned in the target grid.
    No stretching — pixel-exact placement.
    """
    rows = min(text_h, intensity_4bit.shape[0] - text_top)
    cols = min(x1 + 1, intensity_4bit.shape[1])
    region = intensity_4bit[text_top:text_top + rows, x0:cols]

    content_mask = region > 0
    if not content_mask.any():
        return np.zeros((grid_h, grid_w), dtype=np.uint8)

    row_has = np.any(content_mask, axis=1)
    col_has = np.any(content_mask, axis=0)
    ct = int(np.argmax(row_has))
    cb = int(len(row_has) - 1 - np.argmax(row_has[::-1]))
    cl = int(np.argmax(col_has))
    cr = int(len(col_has) - 1 - np.argmax(col_has[::-1]))

    content = region[ct:cb + 1, cl:cr + 1]
    ch, cw = content.shape

    if right_align:
        gx = max(grid_w - cw, 0)
    else:
        gx = 0
    gy = max(grid_h - ch, 0)

    pw = min(cw, grid_w - gx)
    ph = min(ch, grid_h - gy)

    grid = np.zeros((grid_h, grid_w), dtype=np.uint8)
    grid[gy:gy + ph, gx:gx + pw] = content[:ph, :pw]
    return grid


# ---------------------------------------------------------------------------
# Individual digit tiebreakers
# ---------------------------------------------------------------------------

def disambiguate_zero_nine(grid: np.ndarray) -> Optional[int]:
    """Resolve 0/9 ambiguity using bridge-row detection.

    '9' has a solid "bridge row" in its middle (where the loop closes
    into the tail), while '0' has a hollow center.

    Returns 0, 9, or None.
    """
    bounds = get_content_bounds(grid)
    if bounds is None:
        return None
    col_l, col_r, row_t, row_b = bounds
    cw = col_r - col_l + 1
    ch = row_b - row_t + 1
    if cw < 3 or ch < 5:
        return None

    mid_start = row_t + ch // 3
    mid_end = row_t + 2 * ch // 3
    for r in range(mid_start, mid_end + 1):
        row_pixels = grid[r, col_l:col_r + 1]
        if np.count_nonzero(row_pixels) >= 0.75 * len(row_pixels):
            return 9
    return 0


def disambiguate_five_six(grid: np.ndarray) -> Optional[int]:
    """Resolve 5/6 ambiguity using top-bar detection.

    '5' has a flat top bar filling the top row(s) of the grid,
    while '6' has a curved top leaving the top row empty.

    Returns 5, 6, or None.
    """
    top_sum = int(np.sum(grid[0, :]))
    if top_sum == 0:
        return 6
    return 5


def disambiguate_three_eight(grid: np.ndarray) -> Optional[int]:
    """Resolve 3/8 ambiguity using left-side content detection.

    '8' has content on the left side of its upper half (closed loop),
    while '3' is open on the left throughout.

    Returns 3, 8, or None.
    """
    bounds = get_content_bounds(grid)
    if bounds is None:
        return None
    col_l, col_r, row_t, row_b = bounds
    ch = row_b - row_t + 1
    if ch < 5:
        return None

    upper_end = row_t + ch // 3
    left_zone = grid[row_t:upper_end + 1, col_l:col_l + 2]
    left_sum = int(np.sum(left_zone))

    if left_sum > 0:
        return 8
    return 3


def disambiguate_zero_six(grid: np.ndarray) -> Optional[int]:
    """Resolve 0/6 ambiguity using center-core density.

    The center of '6' is denser than '0' because the upper bowl closes
    into a mid-band stroke; '0' keeps a clearer hollow center.

    Returns 0, 6, or None.
    """
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
# Confusable pair definitions
# ---------------------------------------------------------------------------

# (char_a, char_b, disambiguator_func) — disambiguator returns char_a or char_b
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


# ---------------------------------------------------------------------------
# High-level dispatcher
# ---------------------------------------------------------------------------

def apply_digit_tiebreakers(
    classified: list[dict],
    intensity_4bit: np.ndarray,
    text_top: int,
    text_h: int,
    grid_w: int,
    grid_h: int,
) -> None:
    """Apply all digit tiebreakers to a list of classified blobs (in-place).

    Each item in *classified* must have:
        digit: int (0-9)
        score: float
        scores: list[float] of length 10 (index = digit)
        x0, x1: int blob column bounds
    """
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
