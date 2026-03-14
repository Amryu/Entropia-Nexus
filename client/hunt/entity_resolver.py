"""Entity resolver — maps string names to database IDs from the API.

Builds name->ID lookup tables lazily from DataClient.
Thread-safe: lookup dicts are built once in a background thread
and atomically swapped via dict assignment.
Returns None for unknown entities (never blocks).
"""

import threading

from ..core.logger import get_logger

log = get_logger("EntityResolver")


class EntityResolver:
    """Lazy-loaded name-to-ID resolver backed by DataClient."""

    def __init__(self, data_client=None):
        self._data_client = data_client
        self._ready = threading.Event()

        # Lookup tables (built once, atomically swapped)
        self._mob_name_to_id: dict[str, int] = {}
        self._item_name_to_id: dict[str, int] = {}
        self._weapon_name_to_id: dict[str, int] = {}

        # Reverse lookups
        self._mob_id_to_name: dict[int, str] = {}
        self._item_id_to_name: dict[int, str] = {}

    @property
    def is_ready(self) -> bool:
        return self._ready.is_set()

    def warmup(self):
        """Load all lookup tables in a background thread."""
        if not self._data_client:
            self._ready.set()
            return

        def _load():
            try:
                self._load_mobs()
                self._load_items()
                self._load_weapons()
                log.info("Entity resolver ready: %d mobs, %d items, %d weapons",
                         len(self._mob_name_to_id),
                         len(self._item_name_to_id),
                         len(self._weapon_name_to_id))
            except Exception as e:
                log.error("Entity resolver warmup failed: %s", e)
            finally:
                self._ready.set()

        threading.Thread(target=_load, daemon=True,
                         name="entity-resolver-warmup").start()

    def _load_mobs(self):
        mobs = self._data_client.get_mobs()
        name_to_id = {}
        id_to_name = {}
        for mob in mobs:
            mob_id = mob.get("Id")
            name = mob.get("Name")
            if mob_id is not None and name:
                name_to_id[name.lower()] = mob_id
                id_to_name[mob_id] = name
        # Atomic swap
        self._mob_name_to_id = name_to_id
        self._mob_id_to_name = id_to_name

    def _load_items(self):
        name_to_id = {}
        id_to_name = {}

        for getter in ("get_items", "get_materials"):
            try:
                entities = getattr(self._data_client, getter)()
                for entity in entities:
                    eid = entity.get("Id")
                    name = entity.get("Name")
                    if eid is not None and name:
                        key = name.lower()
                        if key not in name_to_id:
                            name_to_id[key] = eid
                            id_to_name[eid] = name
            except Exception as e:
                log.warning("Failed to load %s: %s", getter, e)

        self._item_name_to_id = name_to_id
        self._item_id_to_name = id_to_name

    def _load_weapons(self):
        name_to_id = {}
        try:
            weapons = self._data_client.get_weapons()
            for weapon in weapons:
                wid = weapon.get("Id")
                name = weapon.get("Name")
                if wid is not None and name:
                    name_to_id[name.lower()] = wid
        except Exception as e:
            log.warning("Failed to load weapons: %s", e)
        self._weapon_name_to_id = name_to_id

    def resolve_mob(self, name: str) -> int | None:
        """Resolve a mob name to its database ID. Returns None if unknown."""
        if not name or name == "Unknown":
            return None
        return self._mob_name_to_id.get(name.lower())

    def resolve_item(self, name: str) -> int | None:
        """Resolve an item name to its database ID. Returns None if unknown."""
        if not name:
            return None
        return self._item_name_to_id.get(name.lower())

    def resolve_weapon(self, name: str) -> int | None:
        """Resolve a weapon name to its database ID. Returns None if unknown."""
        if not name:
            return None
        return self._weapon_name_to_id.get(name.lower())

    def get_mob_name(self, mob_id: int) -> str | None:
        """Reverse lookup: get mob name from ID."""
        return self._mob_id_to_name.get(mob_id)

    def get_item_name(self, item_id: int) -> str | None:
        """Reverse lookup: get item name from ID."""
        return self._item_id_to_name.get(item_id)
