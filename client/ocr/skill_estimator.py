"""Skill point estimation and validation using rank thresholds + rank bar.

Given a SkillReading with rank name and rank_bar_percent, computes the
estimated decimal-precision skill points and validates against the OCR'd
integer value.
"""

from __future__ import annotations

from .models import SkillReading

# Tolerance: allow |estimated - current_points| <= max(ABS, REL * estimated)
VALIDATION_ABS_TOLERANCE = 7
VALIDATION_REL_TOLERANCE = 0.01

# From "Great Master" (10000) onward the rank progress bar is always empty,
# so rank-bar-based estimation and mismatch checks are skipped.
RANK_BAR_EMPTY_THRESHOLD = 10000


def enrich_skill_reading(
    reading: SkillReading,
    ranks: list[dict],
) -> None:
    """Populate estimated_points, rank_threshold, and is_mismatch on a SkillReading.

    Args:
        reading: The SkillReading to enrich (mutated in place).
        ranks: Sorted list of {"name": str, "threshold": int} from skill_ranks.json.
    """
    if not ranks or not reading.rank:
        return

    rank_lower = reading.rank.strip().lower()

    # Find current rank threshold and next threshold
    current_threshold = 0
    next_threshold = 0
    found = False
    for i, r in enumerate(ranks):
        if r["name"].lower() == rank_lower:
            current_threshold = r["threshold"]
            next_threshold = (
                ranks[i + 1]["threshold"] if i + 1 < len(ranks) else current_threshold
            )
            found = True
            break

    if not found:
        return

    reading.rank_threshold = current_threshold

    # From Great Master onward the rank bar is always empty — skip estimation
    if current_threshold >= RANK_BAR_EMPTY_THRESHOLD:
        reading.estimated_points = float(current_threshold)
        return

    # Estimate: threshold + rank_bar_progress * range
    rank_range = next_threshold - current_threshold
    if rank_range > 0:
        reading.estimated_points = (
            current_threshold + rank_range * reading.rank_bar_percent / 100.0
        )
    else:
        reading.estimated_points = float(current_threshold)

    # Flag mismatch when estimated and OCR'd points diverge beyond tolerance
    reading.is_mismatch = (
        abs(reading.estimated_points - reading.current_points) > VALIDATION_ABS_TOLERANCE
    )
