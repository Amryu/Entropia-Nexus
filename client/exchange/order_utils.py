"""Exchange-specific order utilities.

Re-exports common classification/formatting from inventory_utils and adds
exchange-specific helpers (tiering, gender, order value, age formatting).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from ..core.inventory_utils import (  # noqa: F401 — re-export
    STACKABLE_TYPES,
    CONDITION_TYPES,
    ABSOLUTE_MARKUP_MATERIAL_TYPES,
    PET_DEFAULT_MAX_TT,
    ITEM_TYPE_TOP_CATEGORY,
    ALL_CATEGORIES,
    PLANETS,
    is_limited,
    is_blueprint,
    is_blueprint_non_l,
    is_pet,
    is_stackable,
    is_percent_markup,
    is_absolute_markup,
    get_max_tt,
    get_unit_tt,
    compute_unit_price,
    get_top_category,
    format_ped,
    format_markup,
)
from .constants import compute_state

# ---------------------------------------------------------------------------
# Exchange-specific type sets
# ---------------------------------------------------------------------------

TIERABLE_TYPES = frozenset({
    'Weapon', 'Armor', 'ArmorSet', 'Finder', 'Excavator', 'MedicalTool',
})

GENDERED_TYPES = frozenset({'Armor', 'ArmorSet', 'Clothing'})

PLATE_SET_SIZE = 7

# ---------------------------------------------------------------------------
# Category ordering (matches web sidebar)
# ---------------------------------------------------------------------------

CATEGORY_ORDER = [
    'Weapons', 'Armor', 'Tools', 'Enhancers', 'Clothes',
    'Blueprints', 'Materials', 'Consumables', 'Vehicles', 'Pets',
    'Skill Implants', 'Furnishings', 'Strongboxes',
]


def get_category_order(category: str) -> int:
    """Get sort index for a category (matches exchange sidebar order)."""
    try:
        return CATEGORY_ORDER.index(category)
    except ValueError:
        return len(CATEGORY_ORDER)


# ---------------------------------------------------------------------------
# Item classification helpers
# ---------------------------------------------------------------------------


def _get_type(slim: dict | None) -> str | None:
    if slim is None:
        return None
    return slim.get('t') or None


def is_item_tierable(slim: dict | None) -> bool:
    """Check if item supports Tier/TiR fields."""
    return _get_type(slim) in TIERABLE_TYPES


def is_gendered(slim: dict | None) -> bool:
    """Check if item type requires gender selection."""
    return _get_type(slim) in GENDERED_TYPES


def item_has_condition(slim: dict | None) -> bool:
    """Check if item has condition (CurrentTT field relevant)."""
    if slim is None:
        return False
    if is_blueprint(slim) and is_limited(slim.get('n', '')):
        return False
    if is_blueprint(slim):
        return True
    return _get_type(slim) in CONDITION_TYPES


# ---------------------------------------------------------------------------
# Order value helpers
# ---------------------------------------------------------------------------


def get_order_value(slim: dict | None, order: dict | None = None) -> float | None:
    """Get display value for an order: CurrentTT from details if available, else getUnitTT."""
    if order:
        details = order.get('details') or {}
        raw = details.get('CurrentTT')
        if raw is not None:
            try:
                ct = float(raw)
                if not math.isnan(ct):
                    return ct
            except (TypeError, ValueError):
                pass
    return get_unit_tt(slim, order.get('details') if order else None)


def get_order_stack_value(slim: dict | None, order: dict | None = None) -> float | None:
    """Get total stack TT value for an order."""
    qty = (order.get('quantity') or 1) if order else 1

    # Stackable items: always MaxTT × qty
    if is_stackable(slim):
        max_tt = get_max_tt(slim)
        return max_tt * qty if max_tt is not None else None

    # Non-stackable: use CurrentTT if available, else unit TT
    details = (order.get('details') or {}) if order else {}
    unit_tt = None
    raw = details.get('CurrentTT')
    if raw is not None:
        try:
            ct = float(raw)
            if not math.isnan(ct):
                unit_tt = ct
        except (TypeError, ValueError):
            pass

    if unit_tt is None:
        unit_tt = get_unit_tt(slim, details)

    if unit_tt is None:
        return None

    # Armor plate sets: total value covers all 7 plates
    t = _get_type(slim)
    if t == 'ArmorPlating' and qty == PLATE_SET_SIZE:
        return unit_tt * PLATE_SET_SIZE

    return unit_tt


def compute_order_unit_price(
    slim: dict | None,
    markup: float | None,
    order: dict | None = None,
) -> float | None:
    """Compute unit price for an order, using CurrentTT from details if available."""
    if markup is None or slim is None:
        return None

    mu = float(markup)

    # Non-L blueprints: TT from QR + absolute markup
    if is_blueprint_non_l(slim):
        details = (order.get('details') or {}) if order else {}
        tt = get_unit_tt(slim, details)
        return (tt + mu) if tt is not None and tt > 0 else mu

    max_tt = get_max_tt(slim)
    if max_tt is None:
        return None

    # For non-stackable condition items, prefer CurrentTT from details
    tt = max_tt
    if not is_stackable(slim) and order:
        details = order.get('details') or {}
        raw = details.get('CurrentTT')
        if raw is not None:
            try:
                ct = float(raw)
                if not math.isnan(ct):
                    tt = ct
            except (TypeError, ValueError):
                pass

    # Armor plate sets
    t = _get_type(slim)
    if t == 'ArmorPlating' and order:
        qty = order.get('quantity') or 1
        if qty == PLATE_SET_SIZE:
            tt = tt * PLATE_SET_SIZE

    if is_absolute_markup(slim):
        return tt + mu
    else:
        return tt * (mu / 100)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def format_ped_value(value: float | None) -> str:
    """Format a PED value with ' PED' suffix."""
    if value is None or not math.isfinite(value):
        return 'N/A'
    return f"{format_ped(value)} PED"


def format_age(iso_str: str | None) -> str:
    """Format an ISO timestamp as a human-readable age string (e.g. '5m', '2h', '3d')."""
    if not iso_str or not isinstance(iso_str, str):
        return ''
    try:
        s = iso_str.replace('Z', '+00:00')
        ts = datetime.fromisoformat(s)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - ts
        total_seconds = delta.total_seconds()
        if total_seconds < 0:
            return 'now'
        minutes = total_seconds / 60
        if minutes < 60:
            return f"{int(minutes)}m"
        hours = minutes / 60
        if hours < 24:
            return f"{int(hours)}h"
        days = hours / 24
        if days < 30:
            return f"{int(days)}d"
        months = days / 30
        if months < 12:
            return f"{int(months)}mo"
        return f"{int(days / 365)}y"
    except (ValueError, TypeError):
        return ''


def smart_decimals(value: float) -> int:
    """Determine decimal places to show (2-4, or -1 for scientific notation)."""
    abs_val = abs(value)
    if abs_val > 0 and abs_val < 0.01:
        d = 2
        while d < 4 and abs_val * (10 ** d) < 1:
            d += 1
        if d >= 4 and abs_val * (10 ** 4) < 1:
            return -1
        return d
    return 2


# ---------------------------------------------------------------------------
# Order enrichment
# ---------------------------------------------------------------------------


def enrich_orders(
    orders: list[dict],
    item_lookup: dict[int, dict],
) -> list[dict]:
    """Enrich a list of orders with computed fields.

    Adds: _state, _slim, _category, _category_order, _value, _total, _is_absolute
    """
    result = []
    for order in orders:
        item_id = order.get('item_id', 0)
        slim = item_lookup.get(item_id)
        state = order.get('state', '')
        # Closed orders keep 'closed' state; active orders compute from bumped_at
        if state == 'closed':
            computed_state = 'closed'
        else:
            computed_state = compute_state(order.get('bumped_at'))

        category = get_top_category(_get_type(slim))
        value = get_order_value(slim, order)
        raw_markup = order.get('markup')
        try:
            markup = float(raw_markup) if raw_markup is not None else None
        except (TypeError, ValueError):
            markup = None
        unit_price = compute_order_unit_price(slim, markup, order) if markup is not None else None
        qty = order.get('quantity', 1) or 1
        total = None
        if unit_price is not None:
            total = unit_price * qty if is_stackable(slim) else unit_price

        enriched = {
            **order,
            '_state': computed_state,
            '_slim': slim,
            '_category': category,
            '_category_order': get_category_order(category),
            '_value': value,
            '_unit_price': unit_price,
            '_total': total,
            '_is_absolute': is_absolute_markup(slim) if slim else True,
            '_item_name': (slim.get('n', f'Item #{item_id}') + ('  [Set]' if slim.get('t') == 'ArmorSet' else '')) if slim else f'Item #{item_id}',
        }
        # Overwrite raw string markup with coerced float
        if markup is not None:
            enriched['markup'] = markup
        result.append(enriched)
    return result
