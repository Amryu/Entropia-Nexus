"""Tool categorization for the hunt dashboard.

Classifies an item name into offense / defense / utility based on the
item type served by the data API. Mining gear (finders, refiners,
excavators, etc.) is explicitly excluded - hunting is not mining, and
the mining tracker owns those items.
"""

import threading
from typing import Literal

from ..core.logger import get_logger

log = get_logger("ToolCategorizer")

Category = Literal["offense", "defense", "utility"]

# Mapping of data_client getter names to categories. Each getter returns
# a list of items; every item's "Name" ends up in the name -> category
# index under the corresponding category.
_GETTER_CATEGORY: tuple[tuple[str, Category], ...] = (
    ("get_weapons", "offense"),
    ("get_amplifiers", "offense"),
    ("get_scopes_and_sights", "offense"),
    ("get_armors", "defense"),
    ("get_armor_sets", "defense"),
    ("get_armor_platings", "defense"),
    ("get_medical_tools", "defense"),
    ("get_medical_chips", "defense"),
    ("get_stimulants", "defense"),
    ("get_effect_chips", "utility"),
    ("get_teleportation_chips", "utility"),
    ("get_misc_tools", "utility"),
    ("get_absorbers", "utility"),
    ("get_scanners", "utility"),
    ("get_implants", "utility"),
)

# Mining-only getters. Items returned by these are intentionally
# dropped from the hunt dashboard - the mining tracker handles them.
_MINING_GETTERS: tuple[str, ...] = (
    "get_finders",
    "get_finder_amplifiers",
    "get_refiners",
    "get_excavators",
)


class ToolCategorizer:
    """Lazily builds a name -> (category, item_type) index from the data API.

    Thread-safe: the first call to any public method loads the index
    under a lock; subsequent calls are lock-free reads on the finished
    dict.
    """

    def __init__(self, data_client, markup_resolver=None):
        self._data_client = data_client
        # Fallback source used when data_client cannot resolve a name.
        # MarkupResolver exposes `_item_name_to_type` built from the
        # exchange cache and is already populated for most known items.
        self._markup_resolver = markup_resolver

        self._lock = threading.Lock()
        self._loaded = False
        # name_lower -> category
        self._category: dict[str, Category] = {}
        # name_lower -> item type string (for per-view widget selection)
        self._item_type: dict[str, str] = {}
        # Names that belong to mining gear are stored here so we can
        # explicitly return None for them (vs the utility default that
        # unknown items fall into).
        self._mining: set[str] = set()
        # Remember names we warned about so log stays quiet.
        self._warned_unknown: set[str] = set()

    # -- Public API --------------------------------------------------

    def category_for(self, name: str | None) -> Category | None:
        """Return the dashboard category for *name*, or None to skip.

        None means 'do not show this tool in the hunt dashboard', used
        for mining gear. Unknown non-mining names default to ``utility``.
        """
        if not name:
            return None
        self._ensure_loaded()
        key = name.lower()
        if key in self._mining:
            return None
        category = self._category.get(key)
        if category is not None:
            return category
        # Fallback via markup resolver's exchange-cache type index.
        category = self._category_from_markup_resolver(key)
        if category is not None:
            self._category[key] = category
            return category
        # Last-resort default: bucket unknown items into utility so they
        # stay visible instead of vanishing from the dashboard.
        if key not in self._warned_unknown:
            log.debug("Unknown tool category for %r - defaulting to utility", name)
            self._warned_unknown.add(key)
        return "utility"

    def item_type_for(self, name: str | None) -> str | None:
        if not name:
            return None
        self._ensure_loaded()
        return self._item_type.get(name.lower())

    def is_in_loadout(self, name: str | None, loadout: dict | None) -> bool:
        """Return True if *name* matches any active-tool slot in *loadout*.

        Loadouts are nested dicts with a ``Gear`` dict keyed by slot,
        each slot holding a dict with a ``Name``. Only the active-tool
        slots are inspected, matching the tracker's definition.
        """
        if not name or not loadout:
            return False
        key = name.lower()
        gear = (loadout.get("Gear") or {}) if isinstance(loadout, dict) else {}
        for slot in ("Weapon", "Healing", "Consumables", "Armor"):
            slot_value = gear.get(slot)
            if isinstance(slot_value, dict):
                slot_name = (slot_value.get("Name") or "").strip()
                if slot_name.lower() == key:
                    return True
        return False

    # -- Loading -----------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._load()
            self._loaded = True

    def _load(self) -> None:
        if self._data_client is None:
            log.warning("ToolCategorizer: no data_client available, using fallback only")
            return

        for getter_name, category in _GETTER_CATEGORY:
            self._ingest_getter(getter_name, category)
        for getter_name in _MINING_GETTERS:
            self._ingest_mining(getter_name)

        log.info("ToolCategorizer: indexed %d items (%d mining excluded)",
                 len(self._category), len(self._mining))

    def _ingest_getter(self, getter_name: str, category: Category) -> None:
        getter = getattr(self._data_client, getter_name, None)
        if getter is None:
            return
        try:
            items = getter() or []
        except Exception as e:
            log.warning("ToolCategorizer: %s failed: %s", getter_name, e)
            return
        for item in items:
            name = (item.get("Name") or "").strip()
            if not name:
                continue
            key = name.lower()
            # Do not overwrite an existing entry: earlier getters in the
            # table take precedence. Weapons win over amps if there is
            # ever an accidental overlap.
            if key not in self._category:
                self._category[key] = category
            item_type = item.get("Type") or item.get("type")
            if item_type and key not in self._item_type:
                self._item_type[key] = str(item_type)

    def _ingest_mining(self, getter_name: str) -> None:
        getter = getattr(self._data_client, getter_name, None)
        if getter is None:
            return
        try:
            items = getter() or []
        except Exception as e:
            log.warning("ToolCategorizer: %s failed: %s", getter_name, e)
            return
        for item in items:
            name = (item.get("Name") or "").strip()
            if name:
                self._mining.add(name.lower())

    def _category_from_markup_resolver(self, key: str) -> Category | None:
        if self._markup_resolver is None:
            return None
        type_map = getattr(self._markup_resolver, "_item_name_to_type", None)
        if not type_map:
            return None
        item_type = type_map.get(key)
        if not item_type:
            return None
        lower_type = item_type.lower()
        if any(w in lower_type for w in ("weapon", "amplifier", "scope", "sight")):
            return "offense"
        if any(w in lower_type for w in ("armor", "plating", "medical", "stimulant", "fap")):
            return "defense"
        if any(w in lower_type for w in ("finder", "excavator", "refiner")):
            return None  # mining
        return "utility"
