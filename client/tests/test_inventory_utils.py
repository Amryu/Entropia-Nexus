"""Tests for client.core.inventory_utils — value calculation and item classification."""

import math
import pytest

from client.core.inventory_utils import (
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
    enrich_item,
    PET_DEFAULT_MAX_TT,
    ALL_CATEGORIES,
    PLANETS,
)


# ---------------------------------------------------------------------------
# Helpers — slim item factories
# ---------------------------------------------------------------------------

def _slim(t: str, *, v: float | None = None, n: str = '', st: str | None = None,
          w: float | None = None, m: float | None = None, nutrio: int | None = None) -> dict:
    """Create a minimal slim-item dict."""
    d: dict = {'t': t, 'n': n, 'i': 1}
    if v is not None:
        d['v'] = v
    if st is not None:
        d['st'] = st
    if w is not None:
        d['w'] = w
    if m is not None:
        d['m'] = m
    if nutrio is not None:
        d['nutrio'] = nutrio
    return d


# ===================================================================
# is_limited
# ===================================================================

class TestIsLimited:
    def test_standard_l_tag(self):
        assert is_limited("Arsonistic Chip 5 (L)") is True

    def test_another_l_tag(self):
        assert is_limited("ArMatrix LR-35 (L)") is True

    def test_no_l_tag(self):
        assert is_limited("Opalo") is False

    def test_empty_string(self):
        assert is_limited("") is False

    def test_l_in_parens_with_other_text(self):
        # JS regex /\(.*L.*\)/ matches any L inside parentheses
        assert is_limited("Some (Large) Item") is True

    def test_l_outside_parens(self):
        assert is_limited("Large Weapon") is False

    def test_none_treated_as_empty(self):
        assert is_limited(None) is False


# ===================================================================
# is_blueprint
# ===================================================================

class TestIsBlueprint:
    def test_blueprint_type(self):
        assert is_blueprint(_slim('Blueprint')) is True

    def test_weapon_type(self):
        assert is_blueprint(_slim('Weapon')) is False

    def test_none_input(self):
        assert is_blueprint(None) is False


# ===================================================================
# is_stackable
# ===================================================================

class TestIsStackable:
    def test_material(self):
        assert is_stackable(_slim('Material')) is True

    def test_consumable(self):
        assert is_stackable(_slim('Consumable')) is True

    def test_enhancer(self):
        assert is_stackable(_slim('Enhancer')) is True

    def test_capsule(self):
        assert is_stackable(_slim('Capsule')) is True

    def test_strongbox(self):
        assert is_stackable(_slim('Strongbox')) is True

    def test_weapon_not_stackable(self):
        assert is_stackable(_slim('Weapon')) is False

    def test_armor_not_stackable(self):
        assert is_stackable(_slim('Armor')) is False

    def test_limited_blueprint_stackable(self):
        """(L) blueprints are stackable."""
        assert is_stackable(_slim('Blueprint', n='Some BP (L)')) is True

    def test_non_l_blueprint_not_stackable(self):
        assert is_stackable(_slim('Blueprint', n='Some BP')) is False

    def test_deed_material_is_stackable(self):
        """Deed materials are stackable (markup type differs, not stackability)."""
        assert is_stackable(_slim('Material', st='Deed')) is True


# ===================================================================
# is_absolute_markup / is_percent_markup
# ===================================================================

class TestMarkupType:
    def test_weapon_absolute(self):
        slim = _slim('Weapon', v=50)
        assert is_absolute_markup(slim) is True
        assert is_percent_markup(slim) is False

    def test_material_percent(self):
        slim = _slim('Material', v=0.10)
        assert is_percent_markup(slim) is True
        assert is_absolute_markup(slim) is False

    def test_deed_material_absolute(self):
        """Deed materials use absolute markup despite being stackable."""
        slim = _slim('Material', v=100, st='Deed')
        assert is_absolute_markup(slim) is True
        assert is_percent_markup(slim) is False

    def test_token_material_absolute(self):
        slim = _slim('Material', v=50, st='Token')
        assert is_absolute_markup(slim) is True

    def test_share_material_absolute(self):
        slim = _slim('Material', v=50, st='Share')
        assert is_absolute_markup(slim) is True

    def test_non_l_blueprint_absolute(self):
        """Non-L blueprints use absolute markup."""
        slim = _slim('Blueprint', n='Weapon Blueprint', v=1.0)
        assert is_absolute_markup(slim) is True

    def test_l_blueprint_percent(self):
        """(L) blueprints are stackable → percent markup."""
        slim = _slim('Blueprint', n='BP (L)', v=0.01)
        assert is_percent_markup(slim) is True

    def test_l_armor_percent(self):
        """(L) armor has condition + limited → percent markup."""
        slim = _slim('Armor', n='Adjusted Pixie (L)', v=10.0)
        assert is_percent_markup(slim) is True

    def test_non_l_armor_absolute(self):
        """Non-L armor → absolute markup (condition, not limited)."""
        slim = _slim('Armor', n='Ghost Armor Gloves', v=15.0)
        assert is_absolute_markup(slim) is True

    def test_consumable_percent(self):
        slim = _slim('Consumable', v=0.50)
        assert is_percent_markup(slim) is True

    def test_enhancer_percent(self):
        slim = _slim('Enhancer', v=1.0)
        assert is_percent_markup(slim) is True


# ===================================================================
# get_max_tt
# ===================================================================

class TestGetMaxTT:
    def test_regular_item(self):
        assert get_max_tt(_slim('Weapon', v=15.5)) == 15.5

    def test_l_blueprint_always_001(self):
        """(L) blueprints always return 0.01 regardless of stored value."""
        assert get_max_tt(_slim('Blueprint', n='BP (L)', v=1.0)) == 0.01

    def test_pet_with_nutrio(self):
        """Pet MaxTT = nutrio capacity / 100."""
        assert get_max_tt(_slim('Pet', nutrio=5000)) == 50.0

    def test_pet_without_nutrio(self):
        """Pet without nutrio falls back to PET_DEFAULT_MAX_TT."""
        assert get_max_tt(_slim('Pet')) == PET_DEFAULT_MAX_TT

    def test_no_value(self):
        assert get_max_tt(_slim('Weapon')) is None

    def test_none_input(self):
        assert get_max_tt(None) is None


# ===================================================================
# get_unit_tt
# ===================================================================

class TestGetUnitTT:
    def test_non_l_blueprint_with_qr(self):
        """Non-L blueprint TT = QR/100."""
        slim = _slim('Blueprint', n='Weapon BP', v=1.0)
        assert get_unit_tt(slim, {'QualityRating': 56}) == pytest.approx(0.56)

    def test_non_l_blueprint_qr_zero(self):
        """Non-L blueprint with QR=0 returns None."""
        slim = _slim('Blueprint', n='Weapon BP', v=1.0)
        assert get_unit_tt(slim, {'QualityRating': 0}) is None

    def test_non_l_blueprint_no_details(self):
        slim = _slim('Blueprint', n='Weapon BP', v=1.0)
        assert get_unit_tt(slim, None) is None

    def test_regular_item_delegates_to_max_tt(self):
        slim = _slim('Weapon', v=25.0)
        assert get_unit_tt(slim) == 25.0

    def test_l_blueprint_delegates_to_max_tt(self):
        slim = _slim('Blueprint', n='BP (L)', v=1.0)
        assert get_unit_tt(slim) == 0.01


# ===================================================================
# compute_unit_price
# ===================================================================

class TestComputeUnitPrice:
    def test_absolute_weapon(self):
        """Weapon: absolute markup → TT + markup."""
        slim = _slim('Weapon', v=50.0)
        assert compute_unit_price(slim, 10.0) == pytest.approx(60.0)

    def test_absolute_weapon_with_current_tt(self):
        """Non-stackable with CurrentTT: uses CurrentTT instead of MaxTT."""
        slim = _slim('Weapon', v=50.0)
        assert compute_unit_price(slim, 10.0, current_tt=30.0) == pytest.approx(40.0)

    def test_percent_material(self):
        """Material: percent markup → TT * (markup/100)."""
        slim = _slim('Material', v=0.10)
        assert compute_unit_price(slim, 150.0) == pytest.approx(0.15)

    def test_percent_material_100(self):
        """100% markup = TT (no markup above TT)."""
        slim = _slim('Material', v=0.10)
        assert compute_unit_price(slim, 100.0) == pytest.approx(0.10)

    def test_non_l_blueprint(self):
        """Non-L BP: TT from QR, absolute markup → QR/100 + markup."""
        slim = _slim('Blueprint', n='Weapon BP', v=1.0)
        # current_tt should be set from QR/100 by enrich_item
        assert compute_unit_price(slim, 5.0, current_tt=0.45) == pytest.approx(5.45)

    def test_deed_material_absolute(self):
        """Deed material: absolute markup despite being stackable."""
        slim = _slim('Material', v=100.0, st='Deed')
        assert compute_unit_price(slim, 50.0) == pytest.approx(150.0)

    def test_none_markup_returns_none(self):
        slim = _slim('Weapon', v=50.0)
        assert compute_unit_price(slim, None) is None

    def test_none_slim_returns_none(self):
        assert compute_unit_price(None, 10.0) is None

    def test_no_value_returns_none(self):
        slim = _slim('Weapon')  # no v
        assert compute_unit_price(slim, 10.0) is None


# ===================================================================
# get_top_category
# ===================================================================

class TestGetTopCategory:
    def test_weapon(self):
        assert get_top_category('Weapon') == 'Weapons'

    def test_armor_set(self):
        assert get_top_category('ArmorSet') == 'Armor'

    def test_medical_tool(self):
        assert get_top_category('MedicalTool') == 'Tools'

    def test_enhancer(self):
        assert get_top_category('Enhancer') == 'Enhancers'

    def test_furniture(self):
        assert get_top_category('Furniture') == 'Furnishings'

    def test_strongbox(self):
        assert get_top_category('Strongbox') == 'Strongboxes'

    def test_none(self):
        assert get_top_category(None) == 'Other'

    def test_unknown(self):
        assert get_top_category('UnknownType') == 'Other'

    def test_empty(self):
        assert get_top_category('') == 'Other'

    def test_all_mapped_types_covered(self):
        """Every type in the map returns a category that's in ALL_CATEGORIES."""
        from client.core.inventory_utils import ITEM_TYPE_TOP_CATEGORY
        for t, cat in ITEM_TYPE_TOP_CATEGORY.items():
            assert cat in ALL_CATEGORIES, f"{t} maps to {cat} which isn't in ALL_CATEGORIES"


# ===================================================================
# format_ped
# ===================================================================

class TestFormatPed:
    def test_normal_value(self):
        assert format_ped(1234.56) == "1,234.56"

    def test_zero(self):
        assert format_ped(0) == "0.00"

    def test_small_value_extended_decimals(self):
        """Small values get extra decimal places."""
        result = format_ped(0.005)
        assert '0.005' in result or '0.01' in result  # Depending on rounding

    def test_very_small_value(self):
        """Very small values may use scientific notation."""
        result = format_ped(0.00001)
        assert result != 'N/A'
        # Should either show extended decimals or scientific notation
        assert 'e' in result or '0.000' in result

    def test_none(self):
        assert format_ped(None) == "N/A"

    def test_nan(self):
        assert format_ped(float('nan')) == "N/A"

    def test_inf(self):
        assert format_ped(float('inf')) == "N/A"

    def test_large_value(self):
        result = format_ped(999999.99)
        assert '999' in result
        assert '.' in result


# ===================================================================
# format_markup
# ===================================================================

class TestFormatMarkup:
    def test_absolute_positive(self):
        result = format_markup(12.5, absolute=True)
        assert result.startswith('+')
        assert '12.50' in result

    def test_absolute_zero(self):
        result = format_markup(0.0, absolute=True)
        assert result == "+0.00"

    def test_percent_normal(self):
        result = format_markup(150.0, absolute=False)
        assert result.endswith('%')
        assert '150.00' in result

    def test_percent_with_precision(self):
        result = format_markup(100.5, absolute=False)
        assert '100.50%' in result

    def test_none_absolute(self):
        assert format_markup(None, absolute=True) == "N/A"

    def test_none_percent(self):
        assert format_markup(None, absolute=False) == "N/A"

    def test_nan(self):
        assert format_markup(float('nan'), absolute=True) == "N/A"

    def test_very_large_percent(self):
        """Very large percent values use scientific notation."""
        result = format_markup(10_000_001.0, absolute=False)
        assert 'e' in result.lower()
        assert '%' in result


# ===================================================================
# enrich_item
# ===================================================================

class TestEnrichItem:
    def _make_item(self, *, item_id=1, item_name='Test', quantity=1,
                   value=None, container=None, container_path=None,
                   details=None):
        d = {
            'item_id': item_id,
            'item_name': item_name,
            'quantity': quantity,
        }
        if value is not None:
            d['value'] = value
        if container is not None:
            d['container'] = container
        if container_path is not None:
            d['container_path'] = container_path
        if details is not None:
            d['details'] = details
        return d

    def test_custom_markup_takes_priority(self):
        """Items with custom markup → value_source='custom'."""
        slim_lookup = {100: _slim('Weapon', v=50.0, w=55.0)}
        markup_lookup = {100: 10.0}
        item = self._make_item(item_id=100, quantity=1)

        result = enrich_item(item, slim_lookup, markup_lookup)
        assert result['_value_source'] == 'custom'
        assert result['_total_value'] == pytest.approx(60.0)  # 50 + 10
        assert result['_markup'] == 10.0

    def test_market_price_fallback(self):
        """No custom markup but market WAP → value_source='exchange'."""
        slim_lookup = {200: _slim('Weapon', v=50.0, w=12.0)}
        markup_lookup = {}
        item = self._make_item(item_id=200, quantity=1)

        result = enrich_item(item, slim_lookup, markup_lookup)
        assert result['_value_source'] == 'exchange'
        # WAP=12 → absolute → 50 + 12 = 62
        assert result['_total_value'] == pytest.approx(62.0)

    def test_market_median_fallback(self):
        """No WAP but has median → uses median."""
        slim_lookup = {300: _slim('Material', v=0.10, m=150.0)}
        markup_lookup = {}
        item = self._make_item(item_id=300, quantity=100)

        result = enrich_item(item, slim_lookup, markup_lookup)
        assert result['_value_source'] == 'exchange'
        # 0.10 * (150/100) * 100 = 15.0
        assert result['_total_value'] == pytest.approx(15.0)

    def test_tt_fallback(self):
        """No markup, no market → value_source='default', uses TT."""
        slim_lookup = {400: _slim('Weapon', v=30.0)}
        markup_lookup = {}
        item = self._make_item(item_id=400, quantity=1)

        result = enrich_item(item, slim_lookup, markup_lookup)
        assert result['_value_source'] == 'default'
        assert result['_total_value'] == pytest.approx(30.0)

    def test_unknown_item_no_slim(self):
        """Item with no slim → category='Other', uses item.value as TT."""
        slim_lookup = {}
        markup_lookup = {}
        item = self._make_item(item_id=0, quantity=1, value=5.0)

        result = enrich_item(item, slim_lookup, markup_lookup)
        assert result['_category'] == 'Other'
        assert result['_type'] is None
        assert result['_tt_value'] == pytest.approx(5.0)
        assert result['_value_source'] == 'default'
        assert result['_total_value'] == pytest.approx(5.0)

    def test_stackable_multiplies_by_quantity(self):
        """Stackable items: total = unit_price × quantity."""
        slim_lookup = {500: _slim('Material', v=0.10)}
        markup_lookup = {500: 200.0}  # 200%
        item = self._make_item(item_id=500, quantity=1000)

        result = enrich_item(item, slim_lookup, markup_lookup)
        assert result['_value_source'] == 'custom'
        # unit_price = 0.10 * (200/100) = 0.20 → total = 0.20 * 1000 = 200.0
        assert result['_total_value'] == pytest.approx(200.0)

    def test_non_stackable_no_quantity_multiply(self):
        """Non-stackable items: total = unit_price (not multiplied by qty)."""
        slim_lookup = {600: _slim('Weapon', v=50.0)}
        markup_lookup = {600: 10.0}
        item = self._make_item(item_id=600, quantity=1)

        result = enrich_item(item, slim_lookup, markup_lookup)
        assert result['_total_value'] == pytest.approx(60.0)

    def test_non_stackable_with_current_tt(self):
        """Non-stackable with item.value → uses as CurrentTT."""
        slim_lookup = {700: _slim('Weapon', v=50.0)}
        markup_lookup = {700: 10.0}
        item = self._make_item(item_id=700, quantity=1, value=30.0)

        result = enrich_item(item, slim_lookup, markup_lookup)
        assert result['_value_source'] == 'custom'
        # CurrentTT=30, markup=10 → 30 + 10 = 40
        assert result['_total_value'] == pytest.approx(40.0)

    def test_container_defaults_to_carried(self):
        """Items with no container get 'Carried'."""
        result = enrich_item(
            self._make_item(item_id=1),
            {}, {},
        )
        assert result['container'] == 'Carried'

    def test_container_preserved(self):
        result = enrich_item(
            self._make_item(item_id=1, container='Calypso'),
            {}, {},
        )
        assert result['container'] == 'Calypso'

    def test_is_absolute_flag(self):
        slim_lookup = {800: _slim('Material', v=0.10)}
        result = enrich_item(self._make_item(item_id=800), slim_lookup, {})
        assert result['_is_absolute'] is False  # Material → percent

    def test_is_absolute_flag_weapon(self):
        slim_lookup = {900: _slim('Weapon', v=50.0)}
        result = enrich_item(self._make_item(item_id=900), slim_lookup, {})
        assert result['_is_absolute'] is True

    def test_is_absolute_flag_no_slim(self):
        """Unknown items default to absolute markup."""
        result = enrich_item(self._make_item(item_id=0), {}, {})
        assert result['_is_absolute'] is True

    def test_non_l_blueprint_uses_qr(self):
        """Non-L blueprint enrichment uses QR from details for TT calculation."""
        slim_lookup = {1000: _slim('Blueprint', n='Weapon BP', v=1.0)}
        markup_lookup = {1000: 5.0}
        item = self._make_item(
            item_id=1000, quantity=1,
            details={'QualityRating': 45},
        )

        result = enrich_item(item, slim_lookup, markup_lookup)
        assert result['_value_source'] == 'custom'
        # QR=45 → TT=0.45, absolute → 0.45 + 5 = 5.45
        assert result['_total_value'] == pytest.approx(5.45)

    def test_stackable_tt_uses_max_tt_times_qty(self):
        """Stackable items: TT = maxTT * quantity."""
        slim_lookup = {1100: _slim('Material', v=0.05)}
        item = self._make_item(item_id=1100, quantity=500)

        result = enrich_item(item, slim_lookup, {})
        assert result['_tt_value'] == pytest.approx(25.0)  # 0.05 * 500

    def test_item_value_overrides_computed_tt(self):
        """When item.value is present, it's used as TT directly."""
        slim_lookup = {1200: _slim('Weapon', v=50.0)}
        item = self._make_item(item_id=1200, quantity=1, value=35.0)

        result = enrich_item(item, slim_lookup, {})
        assert result['_tt_value'] == pytest.approx(35.0)


# ===================================================================
# Constants
# ===================================================================

class TestConstants:
    def test_all_categories_has_other(self):
        assert 'Other' in ALL_CATEGORIES

    def test_planets_has_calypso(self):
        assert 'Calypso' in PLANETS

    def test_all_categories_no_duplicates(self):
        assert len(ALL_CATEGORIES) == len(set(ALL_CATEGORIES))
