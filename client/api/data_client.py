"""Read-only data API client for api.entropianexus.com — no auth required."""

import json
import os
import sys
import time
from pathlib import Path

import requests

from ..core.logger import get_logger

log = get_logger("DataAPI")

CACHE_TTL_SECONDS = 1800  # 30 minutes

# In frozen (PyInstaller) builds the _internal/ tree may be read-only,
# so place the disk cache in the user's data directory instead.
if getattr(sys, "frozen", False):
    CACHE_DIR = Path(os.path.expanduser("~")) / ".entropia-nexus" / "cache"
else:
    CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"


class DataClient:
    """Fetches entity data (weapons, armor, etc.) from the public Nexus API."""

    def __init__(self, config):
        self._base_url = config.api_base_url
        self._session = requests.Session()
        self._memory_cache: dict[str, tuple[float, list]] = {}
        os.makedirs(CACHE_DIR, exist_ok=True)

    def close(self):
        """Close the underlying HTTP session, aborting any in-flight requests."""
        self._session.close()

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

    def get_acquisition(self, item_name: str) -> dict:
        """Fetch acquisition data for an item (vendors, loot, blueprints, etc.).

        Returns a dict with keys: Blueprints, Loots, VendorOffers,
        RefiningRecipes, ShopListings, BlueprintDrops.
        """
        result = self._get_cached(f"/acquisition?items={item_name}")
        return result if isinstance(result, dict) else {}

    def get_usage(self, item_name: str) -> dict:
        """Fetch usage data — where an item is used (blueprints, missions, vendors, refining).

        Returns a dict with keys: Blueprints, Missions, VendorOffers, RefiningRecipes.
        """
        result = self._get_cached(f"/usage/{item_name}")
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

    def _get_cached(self, endpoint: str) -> list[dict]:
        """Fetch data with memory + disk caching."""
        now = time.time()

        # Check memory cache
        if endpoint in self._memory_cache:
            cached_time, cached_data = self._memory_cache[endpoint]
            if now - cached_time < CACHE_TTL_SECONDS:
                return cached_data

        # Check disk cache
        safe_name = endpoint.strip('/').replace('/', '_').replace('?', '_').replace('=', '_')
        cache_file = CACHE_DIR / f"{safe_name}.json"
        if cache_file.exists():
            file_age = now - cache_file.stat().st_mtime
            if file_age < CACHE_TTL_SECONDS:
                try:
                    with open(cache_file, "r") as f:
                        data = json.load(f)
                    self._memory_cache[endpoint] = (now, data)
                    return data
                except (json.JSONDecodeError, IOError):
                    pass

        # Fetch from API
        try:
            resp = self._session.get(f"{self._base_url}{endpoint}", timeout=15)
            resp.raise_for_status()
            data = resp.json()

            # Persist to disk and memory
            with open(cache_file, "w") as f:
                json.dump(data, f)
            self._memory_cache[endpoint] = (now, data)
            return data

        except Exception as e:
            log.error("Failed to fetch %s: %s", endpoint, e)
            # Return stale cache if available
            if endpoint in self._memory_cache:
                return self._memory_cache[endpoint][1]
            if cache_file.exists():
                try:
                    with open(cache_file, "r") as f:
                        return json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass
            return []

    def invalidate_cache(self, endpoint: str | None = None) -> None:
        """Clear cache for a specific endpoint or all endpoints."""
        if endpoint:
            self._memory_cache.pop(endpoint, None)
            safe_name = endpoint.strip('/').replace('/', '_').replace('?', '_').replace('=', '_')
            cache_file = CACHE_DIR / f"{safe_name}.json"
            if cache_file.exists():
                cache_file.unlink()
        else:
            self._memory_cache.clear()
            for f in CACHE_DIR.glob("*.json"):
                f.unlink()
