"""Loot filtering — classifies loot items as genuine drops or noise.

Classification priority:
1. Blacklisted (default global, user global, or user per-mob) → always excluded
2. Refining outputs NOT in mob loot table → excluded
3. Refining outputs IN mob loot table → included (conflict resolution)
4. Items NOT in mob loot table → flagged as unknown, still counted as loot
5. Normal loot → counted
"""

from ..core.logger import get_logger

log = get_logger("LootFilter")

# Built-in blacklist — always applied globally, never overridden.
DEFAULT_BLACKLIST: set[str] = {"universal ammo"}


class LootFilter:
    """Classifies loot items using blacklists, refining products, and mob loot tables.

    Blacklist tiers (all are hard exclusions, never overridden by loot table):
    - DEFAULT_BLACKLIST: built-in global exclusions (e.g. Universal Ammo)
    - config.loot_blacklist: user-added global exclusions
    - config.loot_blacklist_per_mob: user-added per-mob exclusions

    Refining outputs are excluded unless the mob's loot table confirms the drop.

    Graceful degradation: when API is unreachable or mob is unknown,
    only the blacklist filters apply. No loot is incorrectly discarded.
    """

    def __init__(self, config, data_client=None):
        self._config = config
        self._data_client = data_client
        self._refining_products: set[str] | None = None  # lazy-loaded
        self._mob_loot_cache: dict[str, set[str]] = {}   # mob_name_lower -> set of item names

    @property
    def global_blacklist(self) -> set[str]:
        """Combined default + user global blacklist (case-insensitive)."""
        user = {name.lower() for name in self._config.loot_blacklist}
        return DEFAULT_BLACKLIST | user

    def mob_blacklist(self, mob_name: str | None) -> set[str]:
        """Per-mob blacklist entries for a specific mob (case-insensitive)."""
        if not mob_name:
            return set()
        per_mob = self._config.loot_blacklist_per_mob
        items = per_mob.get(mob_name.lower(), [])
        return {name.lower() for name in items}

    def _load_refining_products(self) -> set[str]:
        """Lazy-load refining product names from API. Returns empty set on failure."""
        if self._refining_products is not None:
            return self._refining_products

        if not self._data_client:
            self._refining_products = set()
            return self._refining_products

        try:
            recipes = self._data_client.get_refining_recipes()
            self._refining_products = set()
            for recipe in recipes:
                product = recipe.get("Product", {})
                name = product.get("Name") if isinstance(product, dict) else None
                if name:
                    self._refining_products.add(name.lower())
            log.info("Loaded %d refining products", len(self._refining_products))
        except Exception as e:
            log.error("Failed to load refining products: %s", e)
            self._refining_products = set()

        return self._refining_products

    def _get_mob_loot_table(self, mob_name: str) -> set[str] | None:
        """Get known loot table for a mob. Returns None if unknown or API fails."""
        if not mob_name or mob_name == "Unknown":
            return None

        lower_mob = mob_name.lower()
        if lower_mob in self._mob_loot_cache:
            return self._mob_loot_cache[lower_mob]

        if not self._data_client:
            return None

        try:
            loots = self._data_client.get_mob_loots(mob_name)
            if not loots:
                return None
            item_names = set()
            for loot in loots:
                item = loot.get("Item", {})
                name = item.get("Name") if isinstance(item, dict) else None
                if name:
                    item_names.add(name.lower())
            self._mob_loot_cache[lower_mob] = item_names
            log.info("Loaded %d loot entries for mob '%s'", len(item_names), mob_name)
            return item_names
        except Exception as e:
            log.error("Failed to load loot table for '%s': %s", mob_name, e)
            return None

    def classify(self, item_name: str, mob_name: str | None = None) -> dict:
        """Classify a single loot item.

        Returns dict with keys:
            is_blacklisted: bool
            is_refining_output: bool
            is_in_loot_table: bool (True if no mob loot table available)
            should_count: bool (True if item counts toward loot total)
        """
        name_lower = item_name.lower()

        # 1. Blacklist check — always excluded, never overridden by loot table
        if name_lower in self.global_blacklist or name_lower in self.mob_blacklist(mob_name):
            return {
                "is_blacklisted": True,
                "is_refining_output": False,
                "is_in_loot_table": True,
                "should_count": False,
            }

        # 2. Refining output check
        refining_products = self._load_refining_products()
        is_refining = name_lower in refining_products

        # 3. Mob loot table check
        mob_loot_table = self._get_mob_loot_table(mob_name) if mob_name else None
        if mob_loot_table is not None:
            in_table = name_lower in mob_loot_table
        else:
            # No mob loot table available — assume item is valid
            in_table = True

        # 4. Conflict resolution: refining output that IS in mob loot table → genuine loot
        if is_refining and in_table and mob_loot_table is not None:
            is_refining = False  # Override — mob actually drops this

        should_count = not is_refining
        return {
            "is_blacklisted": False,
            "is_refining_output": is_refining,
            "is_in_loot_table": in_table,
            "should_count": should_count,
        }

    def invalidate_mob_cache(self, mob_name: str | None = None):
        """Clear cached mob loot table(s)."""
        if mob_name:
            self._mob_loot_cache.pop(mob_name.lower(), None)
        else:
            self._mob_loot_cache.clear()
