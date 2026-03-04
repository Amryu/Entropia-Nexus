"""Per-item markup resolution with priority chain.

Priority: Custom (local DB) > Player Inventory Markup (website API)
         > In-Game (market_price_snapshots) > Exchange (WAP API)
         > Default (100% / +0 PED).
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..core.logger import get_logger

log = get_logger("MarkupResolver")

# Path to the shared item types JS utility
_ITEM_TYPES_JS = Path(__file__).parent.parent.parent / "common" / "itemTypes.js"


@dataclass
class MarkupResult:
    """Resolved markup for a single item."""
    markup_value: float   # e.g. 115.0 (pct) or 5.0 (+PED)
    markup_type: str      # "percentage" or "absolute"
    source: str           # "custom", "inventory", "ingame", "exchange", "default"

    def compute(self, tt_value: float) -> float:
        """Apply markup to a TT value and return estimated market value."""
        if self.markup_type == "percentage":
            return tt_value * (self.markup_value / 100)
        return tt_value + self.markup_value


@dataclass
class ExchangeItemData:
    """Cached exchange data for a single item."""
    item_id: int
    name: str
    item_type: str
    sub_type: str | None  # Material sub-type (e.g. 'Deed', 'Token')
    value: float          # MaxTT / per-unit value
    wap: float | None     # Weighted average price markup
    median: float | None
    p10: float | None


def _load_item_type_checker():
    """Load common/itemTypes.js into a V8 context for markup type checks.

    Returns a callable (type, name, subType) -> bool (True = percentage).
    Falls back to a Python heuristic if py_mini_racer is not available.
    """
    try:
        from py_mini_racer import MiniRacer
    except ImportError:
        log.warning("py-mini-racer not available; using Python fallback for markup types")
        return None

    if not _ITEM_TYPES_JS.exists():
        log.warning("itemTypes.js not found at %s; using Python fallback", _ITEM_TYPES_JS)
        return None

    try:
        from ..loadout.js_bridge import _strip_esm
        source = _ITEM_TYPES_JS.read_text(encoding="utf-8")
        source = _strip_esm(source)

        ctx = MiniRacer()
        ctx.eval(source)
        log.info("Loaded itemTypes.js for markup type resolution")

        def check(item_type: str, item_name: str, sub_type: str | None = None) -> bool:
            """Returns True if the item uses percentage markup."""
            if sub_type:
                return ctx.eval(f"isPercentMarkupType({_js_str(item_type)}, {_js_str(item_name)}, {_js_str(sub_type)})")
            return ctx.eval(f"isPercentMarkupType({_js_str(item_type)}, {_js_str(item_name)})")

        return check
    except Exception as e:
        log.error("Failed to load itemTypes.js: %s", e)
        return None


def _js_str(value: str) -> str:
    """Escape a Python string for inline JS."""
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


class MarkupResolver:
    """Resolves per-item markup from a priority chain of sources.

    Sources checked in order:
    1. Custom (local SQLite) — user-set overrides
    2. Player Inventory Markup — from website API (if authenticated)
    3. In-Game (market_price_snapshots) — OCR'd game market data
    4. Exchange — public exchange WAP data
    5. Default — 100% for percentage items, +0 PED for absolute items
    """

    def __init__(self, db, nexus_client=None, data_client=None):
        self._db = db
        self._nexus_client = nexus_client
        self._data_client = data_client

        # JS-based markup type checker (loaded lazily)
        self._js_checker = None
        self._js_checker_loaded = False

        # Caches (populated lazily via refresh methods)
        self._exchange_cache: dict[str, ExchangeItemData] | None = None
        self._inventory_markups: dict[str, float] | None = None  # name → markup
        self._ingame_cache: dict[str, float] | None = None  # name_lower → markup%
        self._item_id_to_name: dict[int, str] | None = None
        self._item_name_to_type: dict[str, str] | None = None
        self._item_name_to_sub_type: dict[str, str | None] | None = None

    def resolve(self, item_name: str) -> MarkupResult:
        """Resolve markup for an item using the priority chain."""
        name_lower = item_name.lower()

        # 1. Custom (local DB)
        custom = self._db.get_custom_markup(item_name)
        if custom:
            return MarkupResult(
                markup_value=custom["markup_value"],
                markup_type=custom["markup_type"],
                source="custom",
            )

        # 2. Player Inventory Markup (website)
        if self._inventory_markups is not None:
            inv_markup = self._inventory_markups.get(name_lower)
            if inv_markup is not None:
                markup_type = self._get_markup_type(item_name)
                return MarkupResult(
                    markup_value=inv_markup,
                    markup_type=markup_type,
                    source="inventory",
                )

        # 3. In-Game (market_price_snapshots)
        if self._ingame_cache is not None:
            igm_markup = self._ingame_cache.get(name_lower)
            if igm_markup is not None:
                markup_type = self._get_markup_type(item_name)
                return MarkupResult(
                    markup_value=igm_markup,
                    markup_type=markup_type,
                    source="ingame",
                )

        # 4. Exchange (WAP)
        if self._exchange_cache is not None:
            exchange_data = self._exchange_cache.get(name_lower)
            if exchange_data and exchange_data.wap is not None:
                markup_type = self._get_markup_type_for_exchange(exchange_data)
                return MarkupResult(
                    markup_value=exchange_data.wap,
                    markup_type=markup_type,
                    source="exchange",
                )

        # 5. Default
        markup_type = self._get_markup_type(item_name)
        if markup_type == "percentage":
            return MarkupResult(100.0, "percentage", "default")
        return MarkupResult(0.0, "absolute", "default")

    def compute_mu_value(self, item_name: str, tt_value: float) -> tuple[float, str]:
        """Compute markup-adjusted value for display.

        Returns: (mu_value, source_label)
        """
        result = self.resolve(item_name)
        return result.compute(tt_value), result.source

    def refresh_exchange_cache(self) -> bool:
        """Fetch exchange data and build name→markup lookup.

        Returns True on success, False on failure.
        """
        if not self._nexus_client:
            return False

        try:
            data = self._nexus_client.get_exchange_items()
            if not data:
                return False

            cache: dict[str, ExchangeItemData] = {}
            name_to_type: dict[str, str] = {}
            name_to_sub_type: dict[str, str | None] = {}
            id_to_name: dict[int, str] = {}

            for item in data:
                name = item.get("n", "")
                item_id = item.get("i", 0)
                item_type = item.get("t", "")
                sub_type = item.get("st")  # Material sub-type (Deed, Token, etc.)
                value = item.get("v", 0)
                wap = item.get("w")
                median = item.get("m")
                p10 = item.get("p")

                if not name:
                    continue

                entry = ExchangeItemData(
                    item_id=item_id,
                    name=name,
                    item_type=item_type,
                    sub_type=sub_type,
                    value=value,
                    wap=wap,
                    median=median,
                    p10=p10,
                )
                cache[name.lower()] = entry
                name_to_type[name.lower()] = item_type
                name_to_sub_type[name.lower()] = sub_type
                id_to_name[item_id] = name

            self._exchange_cache = cache
            self._item_name_to_type = name_to_type
            self._item_name_to_sub_type = name_to_sub_type
            self._item_id_to_name = id_to_name
            log.info("Exchange cache refreshed: %d items", len(cache))
            return True

        except Exception as e:
            log.error("Failed to refresh exchange cache: %s", e)
            return False

    def refresh_inventory_markups(self) -> bool:
        """Fetch inventory markups from the website API (if authenticated).

        Returns True on success, False on failure.
        """
        if not self._nexus_client or not self._nexus_client.is_authenticated():
            return False

        try:
            markups_list = self._nexus_client.get_inventory_markups()
            if markups_list is None:
                return False

            # Build item_id → markup map
            id_to_markup: dict[int, float] = {}
            for entry in markups_list:
                item_id = entry.get("item_id")
                markup = entry.get("markup")
                if item_id is not None and markup is not None:
                    id_to_markup[item_id] = markup

            # Resolve item_id → item_name using exchange cache
            if self._item_id_to_name is None:
                self.refresh_exchange_cache()

            name_markups: dict[str, float] = {}
            if self._item_id_to_name:
                for item_id, markup in id_to_markup.items():
                    name = self._item_id_to_name.get(item_id)
                    if name:
                        name_markups[name.lower()] = markup

            self._inventory_markups = name_markups
            log.info("Inventory markups refreshed: %d items", len(name_markups))
            return True

        except Exception as e:
            log.error("Failed to refresh inventory markups: %s", e)
            return False

    def refresh_ingame_cache(self) -> bool:
        """Fetch in-game market price data from the website API.

        Returns True on success, False on failure.
        """
        if not self._nexus_client:
            return False

        try:
            data = self._nexus_client.get_ingame_prices()
            if data is None:
                return False

            cache: dict[str, float] = {}
            for row in data:
                name = row.get("item_name")
                if not name:
                    continue
                # Use first non-null markup: 1d → 7d → 30d → 90d → 365d
                mu = (row.get("markup_1d") or row.get("markup_7d")
                      or row.get("markup_30d") or row.get("markup_90d")
                      or row.get("markup_365d"))
                if mu is not None:
                    cache[name.lower()] = float(mu)

            self._ingame_cache = cache
            log.info("In-game price cache refreshed: %d items", len(cache))
            return True

        except Exception as e:
            log.error("Failed to refresh in-game price cache: %s", e)
            return False

    def set_custom_markup(self, item_name: str, markup_value: float,
                          markup_type: str = "percentage") -> None:
        """Save a custom per-item markup to local DB.

        Validates minimums: 100 for percentage, 0 for absolute.
        """
        if markup_type == "percentage":
            markup_value = max(100.0, markup_value)
        else:
            markup_value = max(0.0, markup_value)

        self._db.set_custom_markup(
            item_name, markup_value, markup_type,
            datetime.now(timezone.utc).isoformat(),
        )

    def remove_custom_markup(self, item_name: str) -> None:
        """Remove a custom per-item markup from local DB."""
        self._db.remove_custom_markup(item_name)

    def get_all_custom_markups(self) -> list[dict]:
        """Get all custom markups from local DB."""
        return self._db.get_all_custom_markups()

    def _get_js_checker(self):
        """Lazily load the JS-based markup type checker."""
        if not self._js_checker_loaded:
            self._js_checker = _load_item_type_checker()
            self._js_checker_loaded = True
        return self._js_checker

    def _get_markup_type(self, item_name: str) -> str:
        """Determine if an item uses percentage or absolute markup."""
        name_lower = item_name.lower()

        # Look up item type from exchange cache
        item_type = ""
        sub_type = None
        if self._item_name_to_type:
            item_type = self._item_name_to_type.get(name_lower, "")
        if self._item_name_to_sub_type:
            sub_type = self._item_name_to_sub_type.get(name_lower)

        if item_type:
            # Use JS checker (authoritative source) if available
            checker = self._get_js_checker()
            if checker:
                try:
                    is_pct = checker(item_type, item_name, sub_type)
                    return "percentage" if is_pct else "absolute"
                except Exception:
                    pass

        # Default: assume percentage (most loot items are stackable materials)
        return "percentage"

    def _get_markup_type_for_exchange(self, exchange_data: ExchangeItemData) -> str:
        """Determine markup type for an exchange item."""
        checker = self._get_js_checker()
        if checker:
            try:
                is_pct = checker(exchange_data.item_type, exchange_data.name, exchange_data.sub_type)
                return "percentage" if is_pct else "absolute"
            except Exception:
                pass

        # Default: assume percentage
        return "percentage"
