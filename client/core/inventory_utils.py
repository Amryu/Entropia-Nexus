"""Inventory value calculation utilities.

Ported from nexus/src/routes/market/exchange/orderUtils.ts
and nexus/src/lib/common/itemTypes.js to maintain parity
with the web frontend's inventory page.
"""

from __future__ import annotations

import math
import re

# ---------------------------------------------------------------------------
# Item type constants (from itemTypes.js)
# ---------------------------------------------------------------------------

STACKABLE_TYPES = frozenset({
    'Material', 'Consumable', 'Capsule', 'Enhancer', 'Strongbox',
})

CONDITION_TYPES = frozenset({
    'Weapon', 'Armor', 'ArmorPlating', 'ArmorSet', 'Vehicle',
    'WeaponAmplifier', 'WeaponVisionAttachment', 'Absorber',
    'Finder', 'FinderAmplifier', 'Excavator', 'Refiner', 'Scanner',
    'TeleportationChip', 'EffectChip', 'MedicalChip',
    'MiscTool', 'MedicalTool', 'MindforceImplant', 'Pet', 'Clothing',
})

ABSOLUTE_MARKUP_MATERIAL_TYPES = frozenset({'Deed', 'Token', 'Share'})

PET_DEFAULT_MAX_TT = 100

_LIMITED_RE = re.compile(r'\(.*L.*\)')

# ---------------------------------------------------------------------------
# Category mapping (from orderUtils.ts ITEM_TYPE_TOP_CATEGORY)
# ---------------------------------------------------------------------------

ITEM_TYPE_TOP_CATEGORY: dict[str, str] = {
    'Weapon': 'Weapons',
    'WeaponAmplifier': 'Weapons',
    'WeaponVisionAttachment': 'Weapons',
    'Absorber': 'Weapons',
    'MindforceImplant': 'Weapons',
    'Armor': 'Armor',
    'ArmorSet': 'Armor',
    'ArmorPlating': 'Armor',
    'MedicalTool': 'Tools',
    'MedicalChip': 'Tools',
    'Finder': 'Tools',
    'FinderAmplifier': 'Tools',
    'Excavator': 'Tools',
    'Scanner': 'Tools',
    'MiscTool': 'Tools',
    'Tool': 'Tools',
    'EffectChip': 'Tools',
    'TeleportationChip': 'Tools',
    'Refiner': 'Tools',
    'Enhancer': 'Enhancers',
    'Clothing': 'Clothes',
    'Blueprint': 'Blueprints',
    'BlueprintBook': 'Blueprints',
    'Material': 'Materials',
    'Consumable': 'Consumables',
    'Capsule': 'Consumables',
    'Vehicle': 'Vehicles',
    'Pet': 'Pets',
    'SkillImplant': 'Skill Implants',
    'Furniture': 'Furnishings',
    'Decoration': 'Furnishings',
    'StorageContainer': 'Furnishings',
    'Sign': 'Furnishings',
    'Strongbox': 'Strongboxes',
}

ALL_CATEGORIES = [
    'Weapons', 'Armor', 'Tools', 'Enhancers', 'Clothes',
    'Blueprints', 'Materials', 'Consumables', 'Vehicles', 'Pets',
    'Skill Implants', 'Furnishings', 'Strongboxes', 'Other',
]

PLANETS = [
    'Calypso', 'Arkadia', 'Cyrene', 'Rocktropia',
    'Next Island', 'Monria', 'Toulan', 'Howling Mine (Space)',
]

# ---------------------------------------------------------------------------
# Item classification helpers
# ---------------------------------------------------------------------------


def _get_type(slim: dict | None) -> str | None:
    """Extract item type from a slim item dict."""
    if slim is None:
        return None
    return slim.get('t') or None


def _get_name(slim: dict | None) -> str:
    """Extract item name from a slim item dict."""
    if slim is None:
        return ''
    return slim.get('n') or ''


def is_limited(name: str) -> bool:
    """Check if an item name has the (L) tag (matches JS regex /\\(.*L.*\\)/)."""
    return bool(_LIMITED_RE.search(name or ''))


def is_blueprint(slim: dict | None) -> bool:
    """Check if slim item is a Blueprint."""
    return _get_type(slim) == 'Blueprint'


def is_blueprint_non_l(slim: dict | None) -> bool:
    """Non-limited blueprint (instance item with QR, absolute markup)."""
    return is_blueprint(slim) and not is_limited(_get_name(slim))


def is_pet(slim: dict | None) -> bool:
    """Check if slim item is a Pet."""
    return _get_type(slim) == 'Pet'


def is_stackable(slim: dict | None) -> bool:
    """Check if an item uses stackable behaviour."""
    t = _get_type(slim)
    if t in STACKABLE_TYPES:
        return True
    if t == 'Blueprint' and is_limited(_get_name(slim)):
        return True
    return False


def _has_condition(slim: dict | None) -> bool:
    """Check if item type has condition (can be damaged)."""
    if is_blueprint(slim) and is_limited(_get_name(slim)):
        return False
    if is_blueprint(slim):
        return True
    t = _get_type(slim)
    return t in CONDITION_TYPES


def is_percent_markup(slim: dict | None) -> bool:
    """Check if item uses percentage markup."""
    if is_stackable(slim):
        sub_type = slim.get('st') if slim else None
        if sub_type and sub_type in ABSOLUTE_MARKUP_MATERIAL_TYPES:
            return False
        return True
    return _has_condition(slim) and is_limited(_get_name(slim))


def is_absolute_markup(slim: dict | None) -> bool:
    """Check if item uses absolute (+PED) markup."""
    return not is_percent_markup(slim)


# ---------------------------------------------------------------------------
# Value calculation
# ---------------------------------------------------------------------------


def get_max_tt(slim: dict | None) -> float | None:
    """Get the maximum TT value for a slim item."""
    if slim is None:
        return None
    # (L) blueprints: always 0.01 PED per unit
    if is_blueprint(slim) and is_limited(_get_name(slim)):
        return 0.01
    v = slim.get('v')
    if v is not None:
        return float(v)
    # Pets: nutrio capacity / 100, fallback to default
    if is_pet(slim):
        nutrio = slim.get('nutrio')
        if nutrio is not None:
            return float(nutrio) / 100
        return PET_DEFAULT_MAX_TT
    return None


def get_unit_tt(slim: dict | None, details: dict | None = None) -> float | None:
    """Get TT value for a single unit, accounting for non-L BPs using QR/100."""
    if is_blueprint_non_l(slim):
        qr = 0
        if details:
            qr = float(details.get('QualityRating', 0) or 0)
        return qr / 100 if qr > 0 else None
    return get_max_tt(slim)


def compute_unit_price(
    slim: dict | None,
    markup: float | None,
    current_tt: float | None = None,
) -> float | None:
    """Compute the unit price for an item given markup.

    For non-L blueprints, uses QR-based TT + absolute markup.
    For absolute markup items, returns TT + markup.
    For percent markup items, returns TT * (markup / 100).
    """
    if markup is None or slim is None:
        return None

    mu = float(markup)

    # Non-L blueprints: TT from QR, absolute markup
    if is_blueprint_non_l(slim):
        # For non-L BPs we need QR-based TT which should be in current_tt
        # when called from enrich_item
        tt = current_tt if current_tt is not None else 0
        return tt + mu if tt > 0 else mu

    max_tt = get_max_tt(slim)
    if max_tt is None:
        return None

    # For non-stackable condition items, prefer CurrentTT if available
    tt = max_tt
    if not is_stackable(slim) and current_tt is not None:
        tt = current_tt

    if is_absolute_markup(slim):
        return tt + mu
    else:
        return tt * (mu / 100)


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------


def get_top_category(item_type: str | None) -> str:
    """Map a raw item type to its top-level inventory category."""
    if not item_type:
        return 'Other'
    return ITEM_TYPE_TOP_CATEGORY.get(item_type, 'Other')


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

_MIN_DECIMALS = 2
_MAX_DECIMALS = 4


def _smart_decimals(val: float, use_precision: bool) -> int:
    """Determine how many decimal places to show.

    Returns -1 if scientific notation should be used.
    """
    abs_val = abs(val)
    if abs_val > 0 and abs_val < 0.01:
        d = _MIN_DECIMALS
        while d < _MAX_DECIMALS and abs_val * (10 ** d) < 1:
            d += 1
        if d >= _MAX_DECIMALS and abs_val * (10 ** _MAX_DECIMALS) < 1:
            return -1
        return d
    if not use_precision:
        return _MIN_DECIMALS
    rounded2 = round(val * 100) / 100
    if abs(val - rounded2) < 1e-9:
        return _MIN_DECIMALS
    rounded3 = round(val * 1000) / 1000
    if abs(val - rounded3) < 1e-9:
        return 3
    return _MAX_DECIMALS


def _format_num(v: float, use_precision: bool) -> str:
    d = _smart_decimals(v, use_precision)
    if d == -1:
        return f"{v:.2e}"
    return f"{v:,.{d}f}"


def format_ped(value) -> str:
    """Format a PED value for display (no suffix)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 'N/A'
    if not math.isfinite(v):
        return 'N/A'
    return _format_num(v, abs(v) < 5)


def format_markup(value, absolute: bool) -> str:
    """Format a markup value for display.

    Absolute: "+X.XX"
    Percent:  "X.XX%"
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 'N/A'
    if not math.isfinite(v):
        return 'N/A'
    if absolute:
        return f"+{_format_num(v, v < 5)}"
    if v >= 10_000_000:
        return f"{v:.2e}%"
    return f"{_format_num(v, v < 105)}%"


# ---------------------------------------------------------------------------
# In-game market price periods (shortest → longest)
# ---------------------------------------------------------------------------

INGAME_PERIODS = [
    ('1d',    'Daily',   'markup_1d'),
    ('7d',    'Weekly',  'markup_7d'),
    ('30d',   'Monthly', 'markup_30d'),
    ('365d',  'Yearly',  'markup_365d'),
    ('3650d', 'Decade',  'markup_3650d'),
]


def build_ingame_lookup(
    raw_rows: list[dict],
    start_period: str = '1d',
) -> dict[str, float]:
    """Build name → markup lookup from raw in-game price snapshot rows.

    Starts from *start_period* and falls back to longer periods when null
    (e.g. start_period='7d' tries 7d → 30d → 365d → 3650d, skipping 1d).
    """
    start_idx = next(
        (i for i, (k, _, _) in enumerate(INGAME_PERIODS) if k == start_period),
        0,
    )
    periods = INGAME_PERIODS[start_idx:]
    lookup: dict[str, float] = {}
    for row in raw_rows:
        name = row.get('item_name')
        if not name:
            continue
        mu = None
        for _, _, col in periods:
            v = row.get(col)
            if v is not None:
                mu = v
                break
        if mu is not None:
            lookup[name] = float(mu)
    return lookup


# ---------------------------------------------------------------------------
# Enrichment
# ---------------------------------------------------------------------------


def enrich_item(
    item: dict,
    slim_lookup: dict[int, dict],
    markup_lookup: dict[int, float],
    ingame_lookup: dict[str, float] | None = None,
) -> dict:
    """Enrich an inventory item with computed values.

    Returns a new dict with all original fields plus:
      _slim, _type, _category, _max_tt, _markup, _market_price,
      _tt_value, _total_value, _value_source, _is_absolute
    """
    item_id = item.get('item_id', 0)
    slim = slim_lookup.get(item_id)
    item_type = _get_type(slim)
    category = get_top_category(item_type)
    max_tt = get_max_tt(slim) if slim else None
    markup = markup_lookup.get(item_id)
    market_price = None
    if slim:
        market_price = slim.get('w') or slim.get('m')
        if market_price is not None:
            market_price = float(market_price)

    quantity = item.get('quantity', 1) or 1

    # Compute TT value
    tt_value = None
    if item.get('value') is not None:
        tt_value = float(item['value'])
    elif max_tt is not None:
        tt_value = max_tt * quantity if is_stackable(slim) else max_tt

    # For non-stackable condition items, use item.value as CurrentTT
    current_tt = None
    if slim and not is_stackable(slim) and item.get('value') is not None:
        current_tt = float(item['value'])

    # For non-L blueprints, derive TT from QR in details
    if is_blueprint_non_l(slim):
        details = item.get('details') or {}
        qr = float(details.get('QualityRating', 0) or 0)
        current_tt = qr / 100 if qr > 0 else None

    # Compute total value: custom markup > in-game > exchange > TT fallback
    total_value = None
    value_source = 'default'

    if markup is not None and slim:
        unit_price = compute_unit_price(slim, markup, current_tt)
        if unit_price is not None:
            total_value = unit_price * quantity if is_stackable(slim) else unit_price
            value_source = 'custom'

    if value_source == 'default' and ingame_lookup is not None and slim:
        item_name = _get_name(slim)
        igm_mu = ingame_lookup.get(item_name) if item_name else None
        if igm_mu is not None:
            unit_price = compute_unit_price(slim, igm_mu, current_tt)
            if unit_price is not None and unit_price > 0:
                total_value = unit_price * quantity if is_stackable(slim) else unit_price
                value_source = 'ingame'

    if value_source == 'default' and market_price is not None and slim:
        unit_price = compute_unit_price(slim, market_price, current_tt)
        if unit_price is not None and unit_price > 0:
            total_value = unit_price * quantity if is_stackable(slim) else unit_price
            value_source = 'exchange'

    if value_source == 'default' and tt_value is not None:
        total_value = tt_value

    return {
        **item,
        'container': item.get('container') or 'Carried',
        '_slim': slim,
        '_type': item_type,
        '_category': category,
        '_max_tt': max_tt,
        '_markup': markup,
        '_market_price': market_price,
        '_tt_value': tt_value,
        '_total_value': total_value,
        '_value_source': value_source,
        '_is_absolute': is_absolute_markup(slim) if slim else True,
    }
