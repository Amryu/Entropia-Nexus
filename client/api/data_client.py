"""Read-only data API client for api.entropianexus.com — no auth required."""

import os
import sys
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..core.logger import get_logger
from .cache_db import CacheDB

log = get_logger("DataAPI")

CACHE_TTL_SECONDS = 1800  # 30 minutes

# Retry on transient connection/SSL errors (common in VMs and flaky networks)
_RETRY_STRATEGY = Retry(
    total=3,
    backoff_factor=0.5,           # 0s, 0.5s, 1s between retries
    status_forcelist=[502, 503, 504],
    allowed_methods=["GET"],
)

# In frozen (PyInstaller) builds the _internal/ tree may be read-only,
# so place the disk cache in the user's data directory instead.
if getattr(sys, "frozen", False):
    CACHE_DIR = Path(os.path.expanduser("~")) / ".entropia-nexus" / "cache"
else:
    CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"


_MAX_MEMORY_ENTRIES = 30  # cap for memory-only cache (small per-item lookups)


class DataClient:
    """Fetches entity data (weapons, armor, etc.) from the public Nexus API."""

    def __init__(self, config):
        self._base_url = config.api_base_url
        self._frontend_url = config.nexus_base_url
        self._session = requests.Session()
        adapter = HTTPAdapter(max_retries=_RETRY_STRATEGY)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)
        # Memory-only cache for small per-item lookups (acquisition, usage,
        # events, mob globals).  Disk-backed endpoints (_get_cached) do NOT
        # use this — callers already hold references to the returned data,
        # so duplicating it here just wastes RAM.
        self._memory_cache: dict[str, tuple[float, list | dict]] = {}
        self._cache_db = CacheDB(CACHE_DIR / "cache.db")
        self._migrate_json_cache()

    def close(self):
        """Close the underlying HTTP session and cache database."""
        self._session.close()
        self._cache_db.close()

    def get_weapons(self) -> list[dict]:
        return self._get_cached("/weapons")

    def get_amplifiers(self) -> list[dict]:
        return self._get_cached("/weaponamplifiers")

    def get_scopes_and_sights(self) -> list[dict]:
        return self._get_cached("/weaponvisionattachments")

    def get_absorbers(self) -> list[dict]:
        return self._get_cached("/absorbers")

    def get_implants(self) -> list[dict]:
        return self._get_cached("/mindforceimplants")

    def get_armor_sets(self) -> list[dict]:
        return self._get_cached("/armorsets")

    def get_armors(self) -> list[dict]:
        return self._get_cached("/armors")

    def get_armor_platings(self) -> list[dict]:
        return self._get_cached("/armorplatings")

    def get_enhancers(self) -> list[dict]:
        return self._get_cached("/enhancers")

    def get_clothing(self) -> list[dict]:
        return self._get_cached("/clothings")

    def get_pets(self) -> list[dict]:
        return self._get_cached("/pets")

    def get_medical_tools(self) -> list[dict]:
        return self._get_cached("/medicaltools")

    def get_stimulants(self) -> list[dict]:
        return self._get_cached("/stimulants")

    def get_effects(self) -> list[dict]:
        return self._get_cached("/effects")

    def get_skills(self) -> list[dict]:
        return self._get_cached("/skills")

    def get_skill_ranks(self) -> list[dict]:
        return self._get_cached("/enumerations/Skill%20Ranks")

    def get_refining_recipes(self) -> list[dict]:
        return self._get_cached("/refiningrecipes")

    def get_items(self) -> list[dict]:
        return self._get_cached("/items")

    def get_materials(self) -> list[dict]:
        return self._get_cached("/materials")

    def get_blueprints(self) -> list[dict]:
        return self._get_cached("/blueprints")

    def get_vehicles(self) -> list[dict]:
        return self._get_cached("/vehicles")

    def get_mobs(self) -> list[dict]:
        return self._get_cached("/mobs")

    def get_professions(self) -> list[dict]:
        return self._get_cached("/professions")

    def get_vendors(self) -> list[dict]:
        return self._get_cached("/vendors")

    def get_missions(self) -> list[dict]:
        return self._get_cached("/missions")

    def get_mission_chains(self) -> list[dict]:
        return self._get_cached("/missionchains")

    def get_events(self, limit: int = 20, include_past: bool = False,
                   past_limit: int = 10) -> list[dict] | dict:
        """Fetch events from the frontend API.

        When *include_past* is True the API returns ``{upcoming, past}``
        instead of a flat list.
        """
        endpoint = f"/api/events?limit={limit}"
        if include_past:
            endpoint += f"&include=past&past_limit={past_limit}"

        now = time.time()
        if endpoint in self._memory_cache:
            cached_time, cached_data = self._memory_cache[endpoint]
            if now - cached_time < CACHE_TTL_SECONDS:
                return cached_data

        try:
            resp = self._session.get(f"{self._frontend_url}{endpoint}", timeout=15)
            resp.raise_for_status()
            data = resp.json()
            self._evict_memory_cache()
            self._memory_cache[endpoint] = (now, data)
            return data
        except Exception as e:
            log.warning("Failed to fetch events: %s", e)
            if endpoint in self._memory_cache:
                return self._memory_cache[endpoint][1]
            return {"upcoming": [], "past": []} if include_past else []

    def get_mission_chain_detail(self, name: str) -> dict | None:
        """Fetch a single mission chain with its missions and dependency graph."""
        from urllib.parse import quote
        try:
            resp = self._session.get(
                f"{self._base_url}/missionchains/{quote(name, safe='')}",
                timeout=15,
            )
            if resp.ok:
                return resp.json()
        except Exception as e:
            log.error("Failed to fetch mission chain '%s': %s", name, e)
        return None

    def get_locations(self) -> list[dict]:
        return self._get_cached("/locations")

    # --- Maps ---

    def get_planets(self) -> list[dict]:
        return self._get_cached("/planets")

    def get_locations_for_planet(self, planet: str) -> list[dict]:
        return self._get_cached(f"/locations?Planet={planet}")

    def get_areas_for_planet(self, planet: str) -> list[dict]:
        return self._get_cached(f"/areas?Planet={planet}")

    def get_mobspawns_for_planet(self, planet: str) -> list[dict]:
        return self._get_cached(f"/mobspawns?Planet={planet}")

    def get_finder_amplifiers(self) -> list[dict]:
        return self._get_cached("/finderamplifiers")

    def get_medical_chips(self) -> list[dict]:
        return self._get_cached("/medicalchips")

    def get_refiners(self) -> list[dict]:
        return self._get_cached("/refiners")

    def get_scanners(self) -> list[dict]:
        return self._get_cached("/scanners")

    def get_finders(self) -> list[dict]:
        return self._get_cached("/finders")

    def get_excavators(self) -> list[dict]:
        return self._get_cached("/excavators")

    def get_teleportation_chips(self) -> list[dict]:
        return self._get_cached("/teleportationchips")

    def get_effect_chips(self) -> list[dict]:
        return self._get_cached("/effectchips")

    def get_misc_tools(self) -> list[dict]:
        return self._get_cached("/misctools")

    def get_capsules(self) -> list[dict]:
        return self._get_cached("/capsules")

    def get_furniture(self) -> list[dict]:
        return self._get_cached("/furniture")

    def get_decorations(self) -> list[dict]:
        return self._get_cached("/decorations")

    def get_storage_containers(self) -> list[dict]:
        return self._get_cached("/storagecontainers")

    def get_signs(self) -> list[dict]:
        return self._get_cached("/signs")

    def get_strongboxes(self) -> list[dict]:
        return self._get_cached("/strongboxes")

    def get_mob_loots(self, mob_name: str) -> list[dict]:
        return self._get_cached(f"/mobloots?Mob={mob_name}")

    def get_mob_globals(self, mob_name: str, period: str = "30d",
                        *, force_refresh: bool = False) -> dict:
        """Fetch global loot event stats for a mob from the frontend API."""
        from urllib.parse import quote
        endpoint = f"/api/globals/target/{quote(mob_name, safe='')}?period={period}"

        now = time.time()
        if not force_refresh:
            if endpoint in self._memory_cache:
                cached_time, cached_data = self._memory_cache[endpoint]
                if now - cached_time < CACHE_TTL_SECONDS:
                    return cached_data

        timeout = 25 if period == "all" else 15
        try:
            resp = self._session.get(
                f"{self._frontend_url}{endpoint}", timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            self._evict_memory_cache()
            self._memory_cache[endpoint] = (now, data)
            return data
        except Exception as e:
            log.warning("Failed to fetch mob globals for '%s': %s", mob_name, e)
            if endpoint in self._memory_cache:
                return self._memory_cache[endpoint][1]
            return {}

    def get_acquisition(self, item_name: str) -> dict:
        """Fetch acquisition data for an item (vendors, loot, blueprints, etc.).

        Returns a dict with keys: Blueprints, Loots, VendorOffers,
        RefiningRecipes, ShopListings, BlueprintDrops, MissionRewards.
        """
        result = self._get_memory_cached(f"/acquisition?items={item_name}")
        return result if isinstance(result, dict) else {}

    def get_usage(self, item_name: str) -> dict:
        """Fetch usage data — where an item is used (blueprints, missions, vendors, refining).

        Returns a dict with keys: Blueprints, Missions, VendorOffers, RefiningRecipes.
        """
        result = self._get_memory_cached(f"/usage/{item_name}")
        return result if isinstance(result, dict) else {}

    def get_tiers(self, item_id: int, is_armor_set: bool = False) -> list[dict]:
        """Fetch tier information for an item."""
        flag = 1 if is_armor_set else 0
        return self._get_cached(f"/tiers?ItemId={item_id}&IsArmorSet={flag}")

    def search(self, query: str) -> list[dict]:
        """Search across all entities. No caching — results are ephemeral."""
        try:
            resp = self._session.get(
                f"{self._base_url}/search",
                params={"query": query, "fuzzy": "true"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []
        except Exception as e:
            log.error("Search failed for '%s': %s", query, e)
            return []

    def _get_memory_cached(self, endpoint: str):
        """Fetch data with memory-only caching (no disk persistence).

        Used for small per-item lookups (acquisition, usage) that don't
        warrant disk persistence.  Bounded to _MAX_MEMORY_ENTRIES.
        """
        now = time.time()
        if endpoint in self._memory_cache:
            cached_time, cached_data = self._memory_cache[endpoint]
            if now - cached_time < CACHE_TTL_SECONDS:
                return cached_data
        try:
            resp = self._session.get(f"{self._base_url}{endpoint}", timeout=15)
            resp.raise_for_status()
            data = resp.json()
            self._evict_memory_cache()
            self._memory_cache[endpoint] = (now, data)
            return data
        except Exception as e:
            log.error("Failed to fetch %s: %s", endpoint, e)
            if endpoint in self._memory_cache:
                return self._memory_cache[endpoint][1]
            return []

    def _evict_memory_cache(self) -> None:
        """Evict oldest entries if memory cache exceeds the size limit."""
        if len(self._memory_cache) < _MAX_MEMORY_ENTRIES:
            return
        # Remove oldest half
        by_age = sorted(self._memory_cache.items(), key=lambda kv: kv[1][0])
        for key, _ in by_age[: len(by_age) // 2]:
            del self._memory_cache[key]

    def _get_cached(self, endpoint: str) -> list[dict]:
        """Fetch data with SQLite disk caching.

        Callers hold their own references to the returned data, so keeping a
        second copy in memory just wastes RAM.
        """
        cached = self._cache_db.get(endpoint, CACHE_TTL_SECONDS)
        if cached is not None:
            return cached

        # Fetch from API
        try:
            resp = self._session.get(f"{self._base_url}{endpoint}", timeout=15)
            resp.raise_for_status()
            data = resp.json()

            try:
                self._cache_db.put(endpoint, data if isinstance(data, list) else [data])
            except Exception as write_err:
                log.debug("Could not write cache for %s: %s", endpoint, write_err)
            return data if isinstance(data, list) else [data]

        except Exception as e:
            log.error("Failed to fetch %s: %s", endpoint, e)
            stale = self._cache_db.get_stale(endpoint)
            return stale if stale is not None else []

    def invalidate_cache(self, endpoint: str | None = None) -> None:
        """Clear cache for a specific endpoint or all endpoints."""
        if endpoint:
            self._memory_cache.pop(endpoint, None)
            self._cache_db.delete(endpoint)
        else:
            self._memory_cache.clear()
            self._cache_db.clear()

    def _migrate_json_cache(self) -> None:
        """One-time cleanup: remove old JSON cache files after SQLite migration."""
        old_files = list(CACHE_DIR.glob("*.json"))
        if not old_files:
            return
        removed = 0
        for f in old_files:
            try:
                f.unlink()
                removed += 1
            except (PermissionError, OSError):
                pass
        if removed:
            log.info("Migrated cache: removed %d old JSON file(s)", removed)
