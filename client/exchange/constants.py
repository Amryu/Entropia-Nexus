"""Exchange constants — ported from exchangeConstants.js."""

from __future__ import annotations

from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Staleness thresholds
# ---------------------------------------------------------------------------

STALE_DAYS = 3
EXPIRED_DAYS = 7
TERMINATED_DAYS = 30

# ---------------------------------------------------------------------------
# Order limits
# ---------------------------------------------------------------------------

MAX_SELL_ORDERS = 1000
MAX_BUY_ORDERS = 1000
MAX_ORDERS_PER_ITEM = 5

# ---------------------------------------------------------------------------
# Undercut system (2% relative)
# ---------------------------------------------------------------------------

UNDERCUT_PERCENT = 0.02
MIN_UNDERCUT = 0.01

# ---------------------------------------------------------------------------
# Default partial trade ratio
# ---------------------------------------------------------------------------

DEFAULT_PARTIAL_RATIO = 0.2

# ---------------------------------------------------------------------------
# Planets
# ---------------------------------------------------------------------------

PLANETS = [
    'Calypso', 'Arkadia', 'Cyrene', 'Rocktropia',
    'Next Island', 'Monria', 'Toulan', 'Howling Mine (Space)',
]

# ---------------------------------------------------------------------------
# Polling intervals (ms)
# ---------------------------------------------------------------------------

POLL_ORDERS_MS = 60_000
POLL_INVENTORY_MS = 120_000
POLL_TRADE_REQUESTS_MS = 60_000

# ---------------------------------------------------------------------------
# Status badge colors
# ---------------------------------------------------------------------------

STATUS_COLORS = {
    'active': '#4ade80',
    'stale': '#fbbf24',
    'expired': '#ef4444',
    'terminated': '#666666',
    'closed': '#666666',
}


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------


def compute_state(bumped_at: str | datetime | None) -> str:
    """Compute display state from bumped_at timestamp.

    Returns 'active', 'stale', 'expired', or 'terminated'.
    """
    if not bumped_at:
        return 'terminated'
    if isinstance(bumped_at, str):
        # Parse ISO 8601 string (handle both 'Z' suffix and +00:00)
        s = bumped_at.replace('Z', '+00:00')
        ts = datetime.fromisoformat(s)
    elif isinstance(bumped_at, datetime):
        ts = bumped_at
    else:
        return 'terminated'

    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    age = datetime.now(timezone.utc) - ts
    days = age.total_seconds() / 86400

    if days < STALE_DAYS:
        return 'active'
    if days < EXPIRED_DAYS:
        return 'stale'
    if days < TERMINATED_DAYS:
        return 'expired'
    return 'terminated'


def get_percent_undercut(markup: float) -> float:
    """Calculate undercut amount for percent-markup items.

    Formula: 2% × (markup - 100), floored at MIN_UNDERCUT.
    """
    base = max(0.0, markup - 100)
    return max(MIN_UNDERCUT, round(UNDERCUT_PERCENT * base * 100) / 100)


def get_absolute_undercut(markup: float) -> float:
    """Calculate undercut amount for absolute-markup items (+PED).

    Formula: 2% × markup, floored at MIN_UNDERCUT.
    """
    return max(MIN_UNDERCUT, round(UNDERCUT_PERCENT * markup * 100) / 100)
