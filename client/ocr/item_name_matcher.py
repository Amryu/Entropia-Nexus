"""Client-side item name matching for market price OCR.

Matches OCR-read item names against the known item database using
Levenshtein distance. Handles:
  - Confidence penalty proportional to edit distance
  - Normalized character equivalences (comma/period, space/underscore)
    excluded from distance calculation
  - Ambiguity detection for item series that differ by few characters
    (e.g., ArMatrix LR-10 vs LR-15) — requires high per-character
    confidence at the differentiating positions before committing
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field

from ..core.logger import get_logger

log = get_logger("ItemMatcher")

# --- Thresholds ---

# Max Levenshtein distance allowed by name length (after normalization)
MAX_DIST_SHORT = 1    # names <= 8 chars
MAX_DIST_MEDIUM = 2   # names <= 16 chars
MAX_DIST_LONG = 3     # names > 16 chars

# Confidence penalty per unit of edit distance
PENALTY_PER_EDIT = 0.15

# Per-character confidence threshold at ambiguous positions.
# If OCR confidence at a differentiating position is below this,
# the match is considered unreliable and gets a heavy penalty.
AMBIGUITY_CONFIDENCE_THRESHOLD = 0.80

# Multiplier applied to confidence when ambiguity cannot be resolved
AMBIGUITY_PENALTY = 0.50

# How often to rebuild the item index (seconds)
REFRESH_INTERVAL = 1800  # 30 min, matches DataClient cache TTL


@dataclass
class MatchResult:
    """Result of matching an OCR name against the item database."""

    matched_name: str        # Best guess from item database (or original if no match)
    ocr_name: str            # Original OCR-read name (after basic normalization)
    confidence: float        # Adjusted confidence (0.0–1.0)
    edit_distance: int       # Levenshtein distance to matched item (after normalization)
    ambiguous: bool = False  # True if multiple candidates at same distance
    candidates: list[str] = field(default_factory=list)  # All candidates at best distance


class ItemNameMatcher:
    """Matches OCR-read item names against the known item database.

    Uses Levenshtein distance with confidence adjustment and ambiguity
    detection for items with similar names (e.g., ArMatrix series).
    """

    def __init__(self, data_client):
        self._data_client = data_client

        # Lookup tables (rebuilt periodically)
        # normalized_lower -> original Name
        self._name_by_normalized: dict[str, str] = {}
        # All normalized names (for iteration during fuzzy search)
        self._all_normalized: list[str] = []
        # skeleton -> list of original names in that ambiguity group
        self._ambiguity_groups: dict[str, list[str]] = {}
        # original_name -> set of character positions that are ambiguous
        self._ambiguous_positions: dict[str, set[int]] = {}

        self._last_refresh = 0.0
        self._lock = threading.Lock()
        self._loaded = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def match(
        self,
        ocr_name: str,
        per_char_scores: list[float] | None = None,
        base_confidence: float = 1.0,
    ) -> MatchResult:
        """Match an OCR name against known items.

        Args:
            ocr_name: Item name from OCR (after _normalize_item_name).
            per_char_scores: Per-character OCR confidence (parallel to
                ocr_name characters, 1.0 for spaces/joins).
            base_confidence: The raw OCR confidence before item matching.

        Returns:
            MatchResult with the best match and adjusted confidence.
        """
        self._refresh_if_needed()

        if not self._all_normalized:
            # No items loaded — pass through unchanged
            return MatchResult(
                matched_name=ocr_name,
                ocr_name=ocr_name,
                confidence=base_confidence,
                edit_distance=0,
            )

        norm_ocr = _normalize_for_matching(ocr_name)
        max_dist = _max_edit_distance(norm_ocr)

        # --- Exact match (distance 0) ---
        if norm_ocr in self._name_by_normalized:
            original = self._name_by_normalized[norm_ocr]
            # Check ambiguity even at distance 0
            conf = self._apply_ambiguity_penalty(
                original, ocr_name, per_char_scores, base_confidence,
            )
            return MatchResult(
                matched_name=original,
                ocr_name=ocr_name,
                confidence=conf,
                edit_distance=0,
                ambiguous=conf < base_confidence,
            )

        # --- Fuzzy search ---
        best_dist = max_dist + 1
        best_candidates: list[str] = []

        for norm_item in self._all_normalized:
            # Quick length filter
            if abs(len(norm_item) - len(norm_ocr)) > max_dist:
                continue
            dist = _levenshtein(norm_ocr, norm_item, max_dist)
            if dist < best_dist:
                best_dist = dist
                best_candidates = [self._name_by_normalized[norm_item]]
            elif dist == best_dist:
                best_candidates.append(self._name_by_normalized[norm_item])

        if not best_candidates or best_dist > max_dist:
            # No match within threshold — return OCR name unchanged
            return MatchResult(
                matched_name=ocr_name,
                ocr_name=ocr_name,
                confidence=base_confidence,
                edit_distance=best_dist if best_candidates else 99,
            )

        # --- Single match ---
        if len(best_candidates) == 1:
            matched = best_candidates[0]
            penalty = PENALTY_PER_EDIT * best_dist
            conf = base_confidence * max(0.0, 1.0 - penalty)
            # Also check if this item is in an ambiguity group
            conf = self._apply_ambiguity_penalty(
                matched, ocr_name, per_char_scores, conf,
            )
            return MatchResult(
                matched_name=matched,
                ocr_name=ocr_name,
                confidence=conf,
                edit_distance=best_dist,
                ambiguous=len(best_candidates) > 1,
                candidates=best_candidates,
            )

        # --- Multiple matches at same distance ---
        # Pick the best one based on per-character confidence
        matched = self._pick_best_ambiguous(
            best_candidates, ocr_name, per_char_scores,
        )
        penalty = PENALTY_PER_EDIT * best_dist
        conf = base_confidence * max(0.0, 1.0 - penalty)
        conf = self._apply_ambiguity_penalty(
            matched, ocr_name, per_char_scores, conf,
        )
        return MatchResult(
            matched_name=matched,
            ocr_name=ocr_name,
            confidence=conf,
            edit_distance=best_dist,
            ambiguous=True,
            candidates=best_candidates,
        )

    # ------------------------------------------------------------------
    # Index building
    # ------------------------------------------------------------------

    def _refresh_if_needed(self):
        """Rebuild lookup tables if cache is stale."""
        now = time.monotonic()
        if self._loaded and (now - self._last_refresh) < REFRESH_INTERVAL:
            return

        with self._lock:
            # Double-check after acquiring lock
            if self._loaded and (now - self._last_refresh) < REFRESH_INTERVAL:
                return
            try:
                items = self._data_client.get_items()
                if items:
                    self._build_index(items)
                    self._last_refresh = time.monotonic()
                    self._loaded = True
            except Exception as e:
                log.warning("Failed to load items for name matching: %s", e)
                if not self._loaded:
                    # First load failed — try again next call
                    self._last_refresh = 0.0

    def _build_index(self, items: list[dict]):
        """Build normalized lookup and ambiguity group indices."""
        name_by_norm: dict[str, str] = {}
        skeletons: dict[str, list[str]] = {}

        for item in items:
            name = item.get("Name", "")
            if not name:
                continue
            norm = _normalize_for_matching(name)
            name_by_norm[norm] = name

            # Build skeleton groups for ambiguity detection
            skeleton = _compute_skeleton(norm)
            skeletons.setdefault(skeleton, []).append(name)

        # Identify ambiguity groups (2+ items with same skeleton)
        ambiguity_groups: dict[str, list[str]] = {}
        ambiguous_positions: dict[str, set[int]] = {}

        for skeleton, names in skeletons.items():
            if len(names) < 2:
                continue
            ambiguity_groups[skeleton] = names
            # Find differentiating positions within the group
            diff_pos = _find_group_differentiating_positions(names)
            for name in names:
                ambiguous_positions[name] = diff_pos.get(name, set())

        self._name_by_normalized = name_by_norm
        self._all_normalized = list(name_by_norm.keys())
        self._ambiguity_groups = ambiguity_groups
        self._ambiguous_positions = ambiguous_positions

        n_ambig = sum(len(v) for v in ambiguity_groups.values())
        log.info(
            "Item index built: %d items, %d in %d ambiguity groups",
            len(name_by_norm), n_ambig, len(ambiguity_groups),
        )

    # ------------------------------------------------------------------
    # Ambiguity handling
    # ------------------------------------------------------------------

    def _apply_ambiguity_penalty(
        self,
        matched_name: str,
        ocr_name: str,
        per_char_scores: list[float] | None,
        confidence: float,
    ) -> float:
        """Apply confidence penalty if the matched item is in an ambiguity group.

        Checks per-character OCR confidence at the positions where this
        item differs from its ambiguity siblings. If confidence is low
        at those positions, applies a heavy penalty.
        """
        amb_positions = self._ambiguous_positions.get(matched_name)
        if not amb_positions:
            return confidence

        if not per_char_scores:
            # No per-char data — always penalize ambiguous items
            return confidence * AMBIGUITY_PENALTY

        # Map ambiguous positions (in the matched name) to OCR char positions.
        # Both are title-cased versions of the same text, so positions align
        # when lengths match. When they don't (edit distance > 0), we use
        # a simple alignment.
        norm_matched = _normalize_for_matching(matched_name)
        norm_ocr = _normalize_for_matching(ocr_name)

        if len(norm_matched) == len(norm_ocr):
            # Same length — positions align directly
            ocr_positions = amb_positions
        else:
            # Different lengths — align via char-by-char comparison
            ocr_positions = _align_positions(
                norm_matched, norm_ocr, amb_positions,
            )

        if not ocr_positions:
            return confidence * AMBIGUITY_PENALTY

        # Check OCR confidence at each ambiguous position
        min_amb_conf = 1.0
        for pos in ocr_positions:
            if pos < len(per_char_scores):
                min_amb_conf = min(min_amb_conf, per_char_scores[pos])
            else:
                # Position out of range — treat as low confidence
                min_amb_conf = 0.0
                break

        if min_amb_conf < AMBIGUITY_CONFIDENCE_THRESHOLD:
            return confidence * AMBIGUITY_PENALTY

        return confidence

    def _pick_best_ambiguous(
        self,
        candidates: list[str],
        ocr_name: str,
        per_char_scores: list[float] | None,
    ) -> str:
        """Among equally-distant candidates, pick the best match.

        Prefers the candidate whose differentiating characters most
        closely match the OCR output (by normalized comparison).
        Falls back to the first candidate if no clear winner.
        """
        if not per_char_scores or len(candidates) < 2:
            return candidates[0]

        norm_ocr = _normalize_for_matching(ocr_name)
        best_score = -1.0
        best_name = candidates[0]

        for cand in candidates:
            norm_cand = _normalize_for_matching(cand)
            # Count matching characters weighted by OCR confidence
            score = 0.0
            for i, (a, b) in enumerate(zip(norm_ocr, norm_cand)):
                if a == b:
                    char_conf = (
                        per_char_scores[i]
                        if i < len(per_char_scores) else 0.5
                    )
                    score += char_conf
            if score > best_score:
                best_score = score
                best_name = cand

        return best_name


# ======================================================================
# Module-level utilities (stateless)
# ======================================================================

def _normalize_for_matching(name: str) -> str:
    """Normalize for comparison: lowercase, comma=period, underscore=space."""
    name = name.lower()
    name = name.replace(",", ".")
    name = name.replace("_", " ")
    return " ".join(name.split())  # collapse whitespace


def _max_edit_distance(name: str) -> int:
    """Maximum allowed edit distance based on name length."""
    n = len(name)
    if n <= 8:
        return MAX_DIST_SHORT
    if n <= 16:
        return MAX_DIST_MEDIUM
    return MAX_DIST_LONG


def _levenshtein(a: str, b: str, max_dist: int) -> int:
    """Levenshtein distance with early termination.

    Returns max_dist + 1 if the distance exceeds max_dist.
    """
    m, n = len(a), len(b)
    if abs(m - n) > max_dist:
        return max_dist + 1
    if m == 0:
        return n
    if n == 0:
        return m

    # Use single-row DP with early termination
    dp = list(range(m + 1))
    for j in range(1, n + 1):
        prev = dp[0]
        dp[0] = j
        row_min = dp[0]
        for i in range(1, m + 1):
            tmp = dp[i]
            if a[i - 1] == b[j - 1]:
                dp[i] = prev
            else:
                dp[i] = 1 + min(prev, dp[i], dp[i - 1])
            prev = tmp
            if dp[i] < row_min:
                row_min = dp[i]
        if row_min > max_dist:
            return max_dist + 1
    return dp[m]


def _compute_skeleton(name: str) -> str:
    """Replace digit sequences with '#' to group similar item series.

    E.g., 'armatrix lr-30 (l)' -> 'armatrix lr-# (l)'
    """
    return re.sub(r"\d+", "#", name)


def _find_group_differentiating_positions(
    names: list[str],
) -> dict[str, set[int]]:
    """Find character positions where items in an ambiguity group diverge.

    For each item, returns the set of character positions (in that item's
    normalized name) that differ from at least one other item in the group.
    """
    result: dict[str, set[int]] = {}
    normalized = [_normalize_for_matching(n) for n in names]

    for idx, (name, norm) in enumerate(zip(names, normalized)):
        diff_positions: set[int] = set()
        for other_idx, other_norm in enumerate(normalized):
            if idx == other_idx:
                continue
            # Compare character by character (same-length due to same skeleton)
            for pos in range(min(len(norm), len(other_norm))):
                if norm[pos] != other_norm[pos]:
                    diff_positions.add(pos)
            # If lengths differ, trailing positions are all different
            if len(norm) != len(other_norm):
                for pos in range(min(len(norm), len(other_norm)),
                                 max(len(norm), len(other_norm))):
                    if pos < len(norm):
                        diff_positions.add(pos)
        result[name] = diff_positions

    return result


def _align_positions(
    matched_norm: str,
    ocr_norm: str,
    positions: set[int],
) -> set[int]:
    """Map character positions from matched name to OCR name.

    Uses simple alignment: walk both strings, mapping indices.
    When lengths match, positions are identity-mapped.
    When they differ, uses DP traceback for alignment.
    """
    if len(matched_norm) == len(ocr_norm):
        return positions

    # Simple heuristic: for small length differences, offset positions
    # after the first insertion/deletion point
    m, n = len(matched_norm), len(ocr_norm)
    if abs(m - n) > 3:
        return set()  # too different, can't reliably align

    # Build edit path via DP
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if matched_norm[i - 1] == ocr_norm[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(
                    dp[i - 1][j - 1], dp[i - 1][j], dp[i][j - 1]
                )

    # Traceback to build position mapping (matched_pos -> ocr_pos)
    pos_map: dict[int, int] = {}
    i, j = m, n
    while i > 0 and j > 0:
        if matched_norm[i - 1] == ocr_norm[j - 1]:
            pos_map[i - 1] = j - 1
            i -= 1
            j -= 1
        elif dp[i - 1][j - 1] <= dp[i - 1][j] and dp[i - 1][j - 1] <= dp[i][j - 1]:
            pos_map[i - 1] = j - 1  # substitution
            i -= 1
            j -= 1
        elif dp[i - 1][j] <= dp[i][j - 1]:
            i -= 1  # deletion from matched
        else:
            j -= 1  # insertion in OCR

    return {pos_map[p] for p in positions if p in pos_map}
