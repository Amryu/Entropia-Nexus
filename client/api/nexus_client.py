"""Authenticated API client for the Entropia Nexus backend."""

import requests

from ..core.constants import EVENT_API_SCOPE_ERROR
from ..core.logger import get_logger

log = get_logger("API")


class NexusClient:
    """Authenticated requests to the Nexus backend (entropianexus.com/api/...)."""

    def __init__(self, config, oauth, event_bus=None):
        self._config = config
        self._oauth = oauth
        self._session = requests.Session()
        self._event_bus = event_bus
        self._scope_error_fired = False

    def close(self):
        """Close the underlying HTTP session, aborting any in-flight requests."""
        self._session.close()

    def _headers(self) -> dict:
        token = self._oauth.get_access_token()
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}

    def _url(self, path: str) -> str:
        return f"{self._config.nexus_base_url}/api{path}"

    def _handle_error(self, e: Exception, context: str):
        """Log error; if 403, publish a one-time scope error event."""
        if (isinstance(e, requests.HTTPError)
                and e.response is not None
                and e.response.status_code == 403
                and not self._scope_error_fired
                and self._event_bus):
            self._scope_error_fired = True
            self._event_bus.publish(EVENT_API_SCOPE_ERROR, {"endpoint": context})
        log.error("Failed to %s: %s", context, e)

    def is_authenticated(self) -> bool:
        return self._oauth.is_authenticated()

    # Skills
    def get_skills(self) -> dict | None:
        """GET /api/tools/skills — returns {skills: {...}, updated_at: ...}."""
        try:
            resp = self._session.get(self._url("/tools/skills"),
                                     headers=self._headers(), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get skills")
            return None

    def upload_skills(self, skills: dict[str, float], track_import: bool = True) -> dict | None:
        """PUT /api/tools/skills — upload scanned skills."""
        try:
            resp = self._session.put(self._url("/tools/skills"),
                                     headers=self._headers(),
                                     json={"skills": skills, "trackImport": track_import},
                                     timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "upload skills")
            return None

    def get_skill_history(self, skill_names: list[str] | None = None,
                         from_date: str | None = None,
                         to_date: str | None = None) -> list[dict] | None:
        """GET /api/tools/skills/history — per-skill value history."""
        try:
            params = {}
            if skill_names:
                params["skill"] = skill_names
            if from_date:
                params["from"] = from_date
            if to_date:
                params["to"] = to_date
            resp = self._session.get(self._url("/tools/skills/history"),
                                     headers=self._headers(),
                                     params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get skill history")
            return None

    # Loadouts
    def get_loadouts(self) -> list[dict] | None:
        """GET /api/tools/loadout — returns list of user loadouts."""
        try:
            resp = self._session.get(self._url("/tools/loadout"),
                                     headers=self._headers(), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get loadouts")
            return None

    def get_loadout(self, loadout_id: str) -> dict | None:
        """GET /api/tools/loadout/:id — returns a single loadout."""
        try:
            resp = self._session.get(self._url(f"/tools/loadout/{loadout_id}"),
                                     headers=self._headers(), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, f"get loadout {loadout_id}")
            return None

    def save_loadout(self, loadout_id: str, data: dict) -> dict | None:
        """PUT /api/tools/loadout/:id — update a loadout."""
        try:
            resp = self._session.put(self._url(f"/tools/loadout/{loadout_id}"),
                                     headers=self._headers(),
                                     json=data, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, f"save loadout {loadout_id}")
            return None

    def create_loadout(self, data: dict) -> dict | None:
        """POST /api/tools/loadout — create a new loadout."""
        try:
            resp = self._session.post(self._url("/tools/loadout"),
                                      headers=self._headers(),
                                      json=data, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "create loadout")
            return None

    def delete_loadout(self, loadout_id: str) -> bool:
        """DELETE /api/tools/loadout/:id — delete a loadout."""
        try:
            resp = self._session.delete(self._url(f"/tools/loadout/{loadout_id}"),
                                        headers=self._headers(), timeout=10)
            resp.raise_for_status()
            return True
        except Exception as e:
            self._handle_error(e, f"delete loadout {loadout_id}")
            return False

    # News (public, no auth)
    def get_news(self, limit: int = 500) -> list[dict]:
        """GET /api/news — returns latest published announcements (no auth)."""
        try:
            resp = self._session.get(self._url(f"/news?limit={limit}"), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.error("Failed to get news: %s", e)
            return []

    def get_news_article(self, article_id: int) -> dict | None:
        """GET /api/news/:id — returns full announcement with content_html."""
        try:
            resp = self._session.get(self._url(f"/news/{article_id}"), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.error("Failed to get news article %s: %s", article_id, e)
            return None

    # Preferences
    def get_preferences(self) -> dict | None:
        """GET /api/users/preferences — returns {key: data} map."""
        try:
            resp = self._session.get(self._url("/users/preferences"),
                                     headers=self._headers(), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get preferences")
            return None

    def save_preference(self, key: str, data) -> bool:
        """PUT /api/users/preferences — save a single preference."""
        try:
            resp = self._session.put(self._url("/users/preferences"),
                                     headers=self._headers(),
                                     json={"key": key, "data": data},
                                     timeout=10)
            resp.raise_for_status()
            return True
        except Exception as e:
            self._handle_error(e, f"save preference '{key}'")
            return False

    # Inventory
    def get_inventory(self) -> list[dict] | None:
        """GET /api/users/inventory — returns list of inventory items."""
        try:
            resp = self._session.get(self._url("/users/inventory"),
                                     headers=self._headers(), timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get inventory")
            return None

    def get_inventory_markups(self) -> list[dict] | None:
        """GET /api/users/inventory/markups — returns [{item_id, markup, updated_at}]."""
        try:
            resp = self._session.get(self._url("/users/inventory/markups"),
                                     headers=self._headers(), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get inventory markups")
            return None

    def save_inventory_markups(self, items: list[dict]) -> bool:
        """PUT /api/users/inventory/markups — bulk upsert [{item_id, markup}]."""
        try:
            resp = self._session.put(self._url("/users/inventory/markups"),
                                     headers=self._headers(),
                                     json={"items": items}, timeout=10)
            resp.raise_for_status()
            return True
        except Exception as e:
            self._handle_error(e, "save inventory markups")
            return False

    def delete_inventory_markup(self, item_id: int) -> bool:
        """DELETE /api/users/inventory/markups/:item_id."""
        try:
            resp = self._session.delete(
                self._url(f"/users/inventory/markups/{item_id}"),
                headers=self._headers(), timeout=10)
            resp.raise_for_status()
            return True
        except Exception as e:
            self._handle_error(e, f"delete inventory markup {item_id}")
            return False

    def import_inventory(self, items: list[dict], sync: bool = True) -> dict | None:
        """PUT /api/users/inventory — Full sync import.

        Returns: {added, updated, removed, unchanged, total} on success.
        """
        try:
            resp = self._session.put(self._url("/users/inventory"),
                                     headers=self._headers(),
                                     json={"items": items, "sync": sync},
                                     timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "import inventory")
            return None

    def get_import_history(self, limit: int = 20, offset: int = 0) -> list[dict] | None:
        """GET /api/users/inventory/imports — Paginated import history."""
        try:
            resp = self._session.get(
                self._url("/users/inventory/imports"),
                headers=self._headers(),
                params={"limit": limit, "offset": offset},
                timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get import history")
            return None

    def get_import_deltas(self, import_id: int) -> list[dict] | None:
        """GET /api/users/inventory/imports/{id}/deltas — Per-item changes."""
        try:
            resp = self._session.get(
                self._url(f"/users/inventory/imports/{import_id}/deltas"),
                headers=self._headers(),
                timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, f"get import deltas {import_id}")
            return None

    def get_value_history(self) -> list[dict] | None:
        """GET /api/users/inventory/imports/value-history — Portfolio value timeline."""
        try:
            resp = self._session.get(
                self._url("/users/inventory/imports/value-history"),
                headers=self._headers(),
                timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get value history")
            return None

    def get_inventory_containers(self) -> list[dict] | None:
        """GET /api/users/inventory/containers — custom container names."""
        try:
            resp = self._session.get(self._url("/users/inventory/containers"),
                                     headers=self._headers(), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get inventory containers")
            return None

    # Exchange (public, no auth)
    def get_exchange_items(self) -> list[dict]:
        """GET /api/market/exchange — returns categorized exchange slim items (no auth).

        Flattens the categorized tree [{name, items: [...]}] into a single
        list of slim item dicts with keys: i, n, t, v, st, w, m, p, b, s, etc.
        """
        try:
            resp = self._session.get(self._url("/market/exchange"), timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.error("Failed to fetch exchange items: %s", e)
            return []

        flat = []
        if isinstance(data, list):
            for category in data:
                if isinstance(category, dict):
                    items = category.get("items", [])
                    if isinstance(items, list):
                        flat.extend(items)
        elif isinstance(data, dict):
            items = data.get("items", [])
            if isinstance(items, list):
                flat.extend(items)
        return flat

    def get_shared_loadout(self, share_code: str) -> dict | None:
        """GET /api/tools/loadout/share/:share_code — fetch a publicly shared loadout."""
        try:
            resp = self._session.get(
                self._url(f"/tools/loadout/share/{share_code}"), timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.error("Failed to get shared loadout %s: %s", share_code, e)
            return None
