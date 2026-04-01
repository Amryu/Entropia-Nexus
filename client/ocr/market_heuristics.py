"""
Heuristic confidence penalty for market price data.

Shared between the OCR detector and the clipboard monitor.
Checks data consistency (sales monotonicity, markup stability)
and returns a multiplicative penalty factor in (0, 1].
"""

PERIODS = ["1d", "7d", "30d", "365d", "3650d"]

# Minimum sales volume (PED) for markup comparisons to be meaningful
_HEURISTIC_MIN_SALES = 0.10

# Markup ratio thresholds per transition (1d→7d, 7d→30d, 30d→365d, 365d→3650d)
_MARKUP_SUSPECT_RATIO = [20.0, 10.0, 5.0, 5.0]
_MARKUP_STRONG_RATIO = [100.0, 50.0, 20.0, 20.0]


def heuristic_confidence_penalty(data: dict) -> float:
    """Compute a multiplicative penalty based on data consistency heuristics.

    Returns a factor in (0, 1] to multiply with ocr_confidence.
    1.0 = no penalty (data looks consistent), lower = suspicious.

    Checks:
    1. Sales monotonicity: longer time spans must have >= sales than
       shorter spans.  Violations strongly indicate OCR misreads.
    2. Markup stability: large markup swings between neighboring periods
       are suspicious, especially when both periods have enough sales
       to establish reliable pricing.  Daily markup can be an outlier
       (one expensive sale), so 1d->7d is very lenient.
    """
    penalty = 1.0

    # Collect sales and markup values
    sales: list[float | None] = []
    markups: list[float | None] = []
    for period in PERIODS:
        s = data.get(f"sales_{period}")
        m = data.get(f"markup_{period}")
        sales.append(s)
        # Treat overflow sentinel (-1) as unknown for heuristic purposes
        markups.append(m if m is not None and m >= 0 else None)

    # --- Sales monotonicity ---
    for i in range(len(sales) - 1):
        shorter, longer = sales[i], sales[i + 1]
        if shorter is None or longer is None:
            continue
        if shorter <= 0 and longer <= 0:
            continue  # both zero is fine
        if shorter > longer + 0.01:
            # Violation: shorter period has more sales than longer
            if longer <= 0:
                # Impossible: shorter has sales but longer doesn't
                penalty *= 0.3
            else:
                ratio = shorter / longer
                if ratio > 2.0:
                    penalty *= 0.4
                elif ratio > 1.1:
                    penalty *= 0.6
                else:
                    penalty *= 0.85  # slight rounding near boundary

    # --- Markup magnitude stability ---
    mode = data.get("markup_mode", "percent")

    for i in range(len(markups) - 1):
        m_short, m_long = markups[i], markups[i + 1]
        s_short, s_long = sales[i], sales[i + 1]

        if m_short is None or m_long is None:
            continue
        if s_short is None or s_long is None:
            continue

        # Skip if either period has negligible sales
        min_sales = min(s_short, s_long)
        if min_sales < _HEURISTIC_MIN_SALES:
            continue

        # Compute ratio of "excess" markup between periods
        if mode == "percent":
            # Percentage markup: 100% = TT value, excess is what matters
            excess_short = max(m_short - 100, 0.01)
            excess_long = max(m_long - 100, 0.01)
        else:
            # Absolute markup
            excess_short = max(m_short, 0.01)
            excess_long = max(m_long, 0.01)

        ratio = max(excess_short, excess_long) / min(excess_short, excess_long)

        # Scale suspicion by sales volume: higher sales = more reliable,
        # so large swings are more meaningful.  Caps at 10 PED.
        volume_factor = min(min_sales / 10.0, 1.0)

        if ratio > _MARKUP_STRONG_RATIO[i]:
            penalty *= 1.0 - 0.3 * volume_factor
        elif ratio > _MARKUP_SUSPECT_RATIO[i]:
            penalty *= 1.0 - 0.15 * volume_factor

    return max(0.0, min(1.0, penalty))
