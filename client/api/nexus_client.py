"""Authenticated API client for the Entropia Nexus backend."""

import gzip
import json
import sys
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def _get_client_version() -> str:
    """Read version from manifest.json next to the executable/script."""
    for base in [Path(sys.executable).parent, Path(__file__).resolve().parent.parent]:
        manifest = base / "manifest.json"
        if manifest.exists():
            try:
                with open(manifest) as f:
                    return json.load(f).get("version", "0.0.0")
            except Exception:
                pass
    return "0.0.0"

from ..core.constants import EVENT_API_SCOPE_ERROR
from ..core.logger import get_logger

log = get_logger("API")


class RateLimitError(Exception):
    """Raised when the server responds with 429 Too Many Requests."""

    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limited, retry after {retry_after}s")


class ServerError(Exception):
    """Raised on 5xx or network errors — caller should retry."""
    pass


class NexusClient:
    """Authenticated requests to the Nexus backend (entropianexus.com/api/...)."""

    def __init__(self, config, oauth, event_bus=None):
        self._config = config
        self._oauth = oauth
        self._session = requests.Session()
        self._session.headers["User-Agent"] = f"NexusClient/{_get_client_version()}"
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)
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

    def _auth_headers(self, context: str) -> dict | None:
        """Return auth headers or None when unauthenticated.

        This avoids hitting auth-protected endpoints when the user is logged out.
        """
        if not self._oauth.is_authenticated():
            log.debug("Skipping %s: unauthenticated", context)
            return None
        token = self._oauth.get_access_token()
        if not token:
            log.debug("Skipping %s: missing access token", context)
            return None
        return {"Authorization": f"Bearer {token}"}

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
        if isinstance(e, requests.HTTPError) and e.response is not None:
            try:
                body = e.response.json()
                log.error("Failed to %s: %s — %s", context, e, body.get("error", ""))
            except Exception:
                log.error("Failed to %s: %s", context, e)
        else:
            log.error("Failed to %s: %s", context, e)

    def is_authenticated(self) -> bool:
        return self._oauth.is_authenticated()

    # Skills
    def get_skills(self) -> dict | None:
        """GET /api/tools/skills — returns {skills: {...}, updated_at: ...}."""
        try:
            headers = self._auth_headers("get skills")
            if headers is None:
                return None
            resp = self._session.get(self._url("/tools/skills"),
                                     headers=headers, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get skills")
            return None

    def upload_skills(self, skills: dict[str, float], track_import: bool = True) -> dict | None:
        """PUT /api/tools/skills — upload scanned skills."""
        try:
            headers = self._auth_headers("upload skills")
            if headers is None:
                return None
            resp = self._session.put(self._url("/tools/skills"),
                                     headers=headers,
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
            headers = self._auth_headers("get skill history")
            if headers is None:
                return None
            params = {}
            if skill_names:
                params["skill"] = skill_names
            if from_date:
                params["from"] = from_date
            if to_date:
                params["to"] = to_date
            resp = self._session.get(self._url("/tools/skills/history"),
                                     headers=headers,
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
            headers = self._auth_headers("get loadouts")
            if headers is None:
                return None
            resp = self._session.get(self._url("/tools/loadout"),
                                     headers=headers, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get loadouts")
            return None

    def get_loadout(self, loadout_id: str) -> dict | None:
        """GET /api/tools/loadout/:id — returns a single loadout."""
        try:
            headers = self._auth_headers(f"get loadout {loadout_id}")
            if headers is None:
                return None
            resp = self._session.get(self._url(f"/tools/loadout/{loadout_id}"),
                                     headers=headers, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, f"get loadout {loadout_id}")
            return None

    def save_loadout(self, loadout_id: str, data: dict) -> dict | None:
        """PUT /api/tools/loadout/:id — update a loadout."""
        try:
            headers = self._auth_headers(f"save loadout {loadout_id}")
            if headers is None:
                return None
            resp = self._session.put(self._url(f"/tools/loadout/{loadout_id}"),
                                     headers=headers,
                                     json=data, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, f"save loadout {loadout_id}")
            return None

    def create_loadout(self, data: dict) -> dict | None:
        """POST /api/tools/loadout — create a new loadout."""
        try:
            headers = self._auth_headers("create loadout")
            if headers is None:
                return None
            resp = self._session.post(self._url("/tools/loadout"),
                                      headers=headers,
                                      json=data, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "create loadout")
            return None

    def delete_loadout(self, loadout_id: str) -> bool:
        """DELETE /api/tools/loadout/:id — delete a loadout."""
        try:
            headers = self._auth_headers(f"delete loadout {loadout_id}")
            if headers is None:
                return False
            resp = self._session.delete(self._url(f"/tools/loadout/{loadout_id}"),
                                        headers=headers, timeout=10)
            resp.raise_for_status()
            return True
        except Exception as e:
            self._handle_error(e, f"delete loadout {loadout_id}")
            return False

    # Globals (public, no auth)
    def get_globals(self, since: str | None = None, limit: int = 200) -> dict | None:
        """GET /api/globals — public confirmed globals feed."""
        try:
            params: dict = {"limit": limit}
            if since:
                params["since"] = since
            resp = self._session.get(
                self._url("/globals"), params=params, timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get globals")
            return None

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
            headers = self._auth_headers("get preferences")
            if headers is None:
                return None
            resp = self._session.get(self._url("/users/preferences"),
                                     headers=headers, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get preferences")
            return None

    def save_preference(self, key: str, data) -> bool:
        """PUT /api/users/preferences — save a single preference."""
        try:
            headers = self._auth_headers(f"save preference '{key}'")
            if headers is None:
                return False
            resp = self._session.put(self._url("/users/preferences"),
                                     headers=headers,
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
            headers = self._auth_headers("get inventory")
            if headers is None:
                return None
            resp = self._session.get(self._url("/users/inventory"),
                                     headers=headers, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get inventory")
            return None

    def get_inventory_markups(self) -> list[dict] | None:
        """GET /api/users/inventory/markups — returns [{item_id, markup, updated_at}]."""
        try:
            headers = self._auth_headers("get inventory markups")
            if headers is None:
                return None
            resp = self._session.get(self._url("/users/inventory/markups"),
                                     headers=headers, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get inventory markups")
            return None

    def save_inventory_markups(self, items: list[dict]) -> bool:
        """PUT /api/users/inventory/markups — bulk upsert [{item_id, markup}]."""
        try:
            headers = self._auth_headers("save inventory markups")
            if headers is None:
                return False
            resp = self._session.put(self._url("/users/inventory/markups"),
                                     headers=headers,
                                     json={"items": items}, timeout=10)
            resp.raise_for_status()
            return True
        except Exception as e:
            self._handle_error(e, "save inventory markups")
            return False

    def delete_inventory_markup(self, item_id: int) -> bool:
        """DELETE /api/users/inventory/markups/:item_id."""
        try:
            headers = self._auth_headers(f"delete inventory markup {item_id}")
            if headers is None:
                return False
            resp = self._session.delete(
                self._url(f"/users/inventory/markups/{item_id}"),
                headers=headers, timeout=10)
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
            headers = self._auth_headers("import inventory")
            if headers is None:
                return None
            resp = self._session.put(self._url("/users/inventory"),
                                     headers=headers,
                                     json={"items": items, "sync": sync},
                                     timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "import inventory")
            return None

    def get_import_history(self, limit: int = 20, offset: int = 0,
                           since: str | None = None) -> list[dict] | None:
        """GET /api/users/inventory/imports — Paginated import history."""
        try:
            headers = self._auth_headers("get import history")
            if headers is None:
                return None
            params: dict = {"limit": limit, "offset": offset}
            if since:
                params["since"] = since
            resp = self._session.get(
                self._url("/users/inventory/imports"),
                headers=headers,
                params=params,
                timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get import history")
            return None

    def get_import_deltas(self, import_id: int) -> list[dict] | None:
        """GET /api/users/inventory/imports/{id}/deltas — Per-item changes."""
        try:
            headers = self._auth_headers(f"get import deltas {import_id}")
            if headers is None:
                return None
            resp = self._session.get(
                self._url(f"/users/inventory/imports/{import_id}/deltas"),
                headers=headers,
                timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, f"get import deltas {import_id}")
            return None

    def get_value_history(self, since: str | None = None) -> list[dict] | None:
        """GET /api/users/inventory/imports/value-history — Portfolio value timeline."""
        try:
            headers = self._auth_headers("get value history")
            if headers is None:
                return None
            params: dict = {}
            if since:
                params["since"] = since
            resp = self._session.get(
                self._url("/users/inventory/imports/value-history"),
                headers=headers,
                params=params,
                timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get value history")
            return None

    def get_inventory_containers(self) -> list[dict] | None:
        """GET /api/users/inventory/containers — custom container names."""
        try:
            headers = self._auth_headers("get inventory containers")
            if headers is None:
                return None
            resp = self._session.get(self._url("/users/inventory/containers"),
                                     headers=headers, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get inventory containers")
            return None

    # Exchange (public, no auth)
    def get_exchange_items(self) -> list[dict]:
        """GET /api/market/exchange — returns categorized exchange slim items (no auth).

        The API returns a deeply nested dict of categories (e.g.
        ``{"weapons": {"melee": {"sword": [...items]}}, ...}``).  We recursively
        traverse it and collect every leaf array into a single flat list of slim
        item dicts with keys: i, n, t, v, st, w, m, p, b, s, etc.
        """
        try:
            # Explicitly request gzip — server serves brotli first, but the
            # brotli Python package is not installed so requests can't decode it.
            resp = self._session.get(
                self._url("/market/exchange"),
                headers={"Accept-Encoding": "gzip, deflate"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.error("Failed to fetch exchange items: %s", e)
            return []

        flat: list[dict] = []

        def _traverse(node):
            if isinstance(node, list):
                flat.extend(node)
            elif isinstance(node, dict):
                for v in node.values():
                    _traverse(v)

        _traverse(data)
        return flat

    # Exchange — Orders

    def get_my_orders(self) -> list[dict] | None:
        """GET /api/market/exchange/orders — current user's exchange orders."""
        try:
            headers = self._auth_headers("get my orders")
            if headers is None:
                return None
            resp = self._session.get(self._url("/market/exchange/orders"),
                                     headers=headers, timeout=15)
            if resp.status_code == 429:
                raise RateLimitError(resp.json().get("retryAfter", 60))
            resp.raise_for_status()
            return resp.json()
        except (RateLimitError, ServerError):
            raise
        except Exception as e:
            self._handle_error(e, "get my orders")
            return None

    def get_item_orders(self, item_id: int) -> dict | None:
        """GET /api/market/exchange/orders/item/{id} — order book for an item (public)."""
        try:
            resp = self._session.get(
                self._url(f"/market/exchange/orders/item/{item_id}"), timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, f"get item orders {item_id}")
            return None

    def get_user_orders(self, user_id: int) -> list[dict] | None:
        """GET /api/market/exchange/orders/user/{id} — all active orders by user (public)."""
        try:
            resp = self._session.get(
                self._url(f"/market/exchange/orders/user/{user_id}"), timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, f"get user orders {user_id}")
            return None

    def create_order(self, data: dict) -> dict | None:
        """POST /api/market/exchange/orders — create a new exchange order.

        Returns the created order dict, or raises on error.
        Raises RateLimitError on 429.
        """
        try:
            headers = self._auth_headers("create order")
            if headers is None:
                return None
            resp = self._session.post(self._url("/market/exchange/orders"),
                                      headers=headers,
                                      json=data, timeout=15)
            if resp.status_code == 429:
                raise RateLimitError(resp.json().get("retryAfter", 60))
            resp.raise_for_status()
            return resp.json()
        except (RateLimitError, ServerError):
            raise
        except requests.HTTPError as e:
            self._handle_error(e, "create order")
            raise
        except Exception as e:
            self._handle_error(e, "create order")
            return None

    def edit_order(self, order_id: int, data: dict) -> dict | None:
        """PUT /api/market/exchange/orders/{id} — edit an exchange order.

        Returns the updated order dict, or raises on error.
        Raises RateLimitError on 429.
        """
        try:
            headers = self._auth_headers(f"edit order {order_id}")
            if headers is None:
                return None
            resp = self._session.put(
                self._url(f"/market/exchange/orders/{order_id}"),
                headers=headers, json=data, timeout=15)
            if resp.status_code == 429:
                raise RateLimitError(resp.json().get("retryAfter", 60))
            resp.raise_for_status()
            return resp.json()
        except (RateLimitError, ServerError):
            raise
        except requests.HTTPError as e:
            self._handle_error(e, f"edit order {order_id}")
            raise
        except Exception as e:
            self._handle_error(e, f"edit order {order_id}")
            return None

    def close_order(self, order_id: int) -> bool:
        """DELETE /api/market/exchange/orders/{id} — close an exchange order."""
        try:
            headers = self._auth_headers(f"close order {order_id}")
            if headers is None:
                return False
            resp = self._session.delete(
                self._url(f"/market/exchange/orders/{order_id}"),
                headers=headers, timeout=15)
            if resp.status_code == 429:
                raise RateLimitError(resp.json().get("retryAfter", 60))
            resp.raise_for_status()
            return True
        except (RateLimitError, ServerError):
            raise
        except Exception as e:
            self._handle_error(e, f"close order {order_id}")
            return False

    def bump_all_orders(self) -> dict | None:
        """POST /api/market/exchange/orders/bump-all — reset bumped_at on all eligible orders."""
        try:
            headers = self._auth_headers("bump all orders")
            if headers is None:
                return None
            resp = self._session.post(
                self._url("/market/exchange/orders/bump-all"),
                headers=headers, timeout=15)
            if resp.status_code == 429:
                raise RateLimitError(resp.json().get("retryAfter", 60))
            resp.raise_for_status()
            return resp.json()
        except (RateLimitError, ServerError):
            raise
        except Exception as e:
            self._handle_error(e, "bump all orders")
            return None

    # Exchange — Trade Requests

    def get_trade_requests(self) -> list[dict] | None:
        """GET /api/market/trade-requests — current user's trade requests."""
        try:
            headers = self._auth_headers("get trade requests")
            if headers is None:
                return None
            resp = self._session.get(self._url("/market/trade-requests"),
                                     headers=headers, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get trade requests")
            return None

    def create_trade_request(self, target_id: int, planet: str | None,
                              items: list[dict]) -> dict | None:
        """POST /api/market/trade-requests — create or add to a trade request.

        Returns {id, isNew} or None.
        """
        try:
            headers = self._auth_headers("create trade request")
            if headers is None:
                return None
            resp = self._session.post(
                self._url("/market/trade-requests"),
                headers=headers,
                json={
                    "target_id": str(target_id),
                    "planet": planet,
                    "items": items,
                },
                timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as e:
            self._handle_error(e, "create trade request")
            raise
        except Exception as e:
            self._handle_error(e, "create trade request")
            return None

    def cancel_trade_request(self, request_id: int) -> bool:
        """POST /api/market/trade-requests/{id}/cancel."""
        try:
            headers = self._auth_headers(f"cancel trade request {request_id}")
            if headers is None:
                return False
            resp = self._session.post(
                self._url(f"/market/trade-requests/{request_id}/cancel"),
                headers=headers, timeout=10)
            resp.raise_for_status()
            return True
        except Exception as e:
            self._handle_error(e, f"cancel trade request {request_id}")
            return False

    # Exchange — Prices

    def get_exchange_prices(self, item_id: int, **kwargs) -> dict | None:
        """GET /api/market/prices/exchange/{id} — exchange price data.

        Optional kwargs: period, history, gender.
        """
        try:
            params = {k: v for k, v in kwargs.items() if v is not None}
            resp = self._session.get(
                self._url(f"/market/prices/exchange/{item_id}"),
                params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, f"get exchange prices {item_id}")
            return None

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

    # Notifications

    def get_notifications(self, page: int = 1, page_size: int = 20) -> dict | None:
        """GET /api/notifications — {rows, total, unread, page, pageSize}."""
        try:
            headers = self._auth_headers("get notifications")
            if headers is None:
                return None
            resp = self._session.get(
                self._url("/notifications"),
                headers=headers,
                params={"page": page, "pageSize": page_size},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get notifications")
            return None

    def mark_notification_read(self, notification_id: int) -> bool:
        """PATCH /api/notifications/:id — mark single notification as read."""
        try:
            headers = self._auth_headers(f"mark notification {notification_id} read")
            if headers is None:
                return False
            resp = self._session.patch(
                self._url(f"/notifications/{notification_id}"),
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            self._handle_error(e, f"mark notification {notification_id} read")
            return False

    def mark_all_notifications_read(self) -> bool:
        """POST /api/notifications/read-all."""
        try:
            headers = self._auth_headers("mark all notifications read")
            if headers is None:
                return False
            resp = self._session.post(
                self._url("/notifications/read-all"),
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            self._handle_error(e, "mark all notifications read")
            return False

    # Ingestion

    def ingest_globals(self, batch: list[dict]) -> dict | None:
        """POST /api/ingestion/globals — submit a gzip-compressed batch of global events.

        Raises RateLimitError on 429, ServerError on 5xx/network errors.
        Returns None on 4xx client errors (data is bad, no point retrying).
        """
        payload = gzip.compress(json.dumps({"globals": batch}).encode())
        headers = self._auth_headers("ingest globals")
        if headers is None:
            return None
        headers["Content-Encoding"] = "gzip"
        headers["Content-Type"] = "application/json"
        try:
            resp = self._session.post(
                self._url("/ingestion/globals"),
                headers=headers,
                data=payload,
                timeout=15,
            )
            if resp.status_code == 429:
                retry_after = resp.json().get("retryAfter", 60)
                raise RateLimitError(retry_after)
            if resp.status_code >= 500:
                raise ServerError(f"{resp.status_code} {resp.reason}")
            resp.raise_for_status()
            return resp.json()
        except (RateLimitError, ServerError):
            raise
        except requests.ConnectionError as e:
            raise ServerError(str(e)) from e
        except requests.Timeout as e:
            raise ServerError(str(e)) from e
        except Exception as e:
            self._handle_error(e, "ingest globals")
            return None

    def ingest_trades(self, batch: list[dict]) -> dict | None:
        """POST /api/ingestion/trade — submit a gzip-compressed batch of trade messages.

        Raises RateLimitError on 429, ServerError on 5xx/network errors.
        Returns None on 4xx client errors (data is bad, no point retrying).
        """
        payload = gzip.compress(json.dumps({"trades": batch}).encode())
        headers = self._auth_headers("ingest trades")
        if headers is None:
            return None
        headers["Content-Encoding"] = "gzip"
        headers["Content-Type"] = "application/json"
        try:
            resp = self._session.post(
                self._url("/ingestion/trade"),
                headers=headers,
                data=payload,
                timeout=15,
            )
            if resp.status_code == 429:
                retry_after = resp.json().get("retryAfter", 60)
                raise RateLimitError(retry_after)
            if resp.status_code >= 500:
                raise ServerError(f"{resp.status_code} {resp.reason}")
            resp.raise_for_status()
            return resp.json()
        except (RateLimitError, ServerError):
            raise
        except requests.ConnectionError as e:
            raise ServerError(str(e)) from e
        except requests.Timeout as e:
            raise ServerError(str(e)) from e
        except Exception as e:
            self._handle_error(e, "ingest trades")
            return None

    def ingest_market_prices(self, batch: list[dict]) -> dict | None:
        """POST /api/ingestion/market-prices — submit market price observations.

        Raises RateLimitError on 429, ServerError on 5xx/network errors.
        Returns None on 4xx client errors (data is bad, no point retrying).
        """
        payload = gzip.compress(json.dumps({"prices": batch}).encode())
        headers = self._auth_headers("ingest market prices")
        if headers is None:
            return None
        headers["Content-Encoding"] = "gzip"
        headers["Content-Type"] = "application/json"
        try:
            resp = self._session.post(
                self._url("/ingestion/market-prices"),
                headers=headers,
                data=payload,
                timeout=15,
            )
            if resp.status_code == 429:
                retry_after = resp.json().get("retryAfter", 60)
                raise RateLimitError(retry_after)
            if resp.status_code >= 500:
                raise ServerError(f"{resp.status_code} {resp.reason}")
            resp.raise_for_status()
            return resp.json()
        except (RateLimitError, ServerError):
            raise
        except requests.ConnectionError as e:
            raise ServerError(str(e)) from e
        except requests.Timeout as e:
            raise ServerError(str(e)) from e
        except Exception as e:
            self._handle_error(e, "ingest market prices")
            return None

    def get_ingame_prices(self) -> list[dict] | None:
        """GET /api/market/prices/snapshots/latest?all=true — fetch latest market price snapshots."""
        try:
            resp = self._session.get(
                self._url("/market/prices/snapshots/latest"),
                headers=self._headers(),
                params={"all": "true"},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get ingame prices")
            return None

    def get_item_market_prices(self, item_id: int, tier: int | None = None) -> list[dict] | None:
        """GET /api/market/prices/snapshots/latest?itemIds={item_id} — latest snapshot for one item."""
        try:
            params: dict = {"itemIds": str(item_id)}
            if tier is not None:
                params["tier"] = str(tier)
            resp = self._session.get(
                self._url("/market/prices/snapshots/latest"),
                headers=self._headers(),
                params=params,
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get item market prices")
            return None

    def get_item_market_prices_by_name(self, name: str, tier: int | None = None) -> list[dict] | None:
        """GET /api/market/prices/snapshots/latest?name={name} — latest snapshot by item name."""
        try:
            params: dict = {"name": name}
            if tier is not None:
                params["tier"] = str(tier)
            resp = self._session.get(
                self._url("/market/prices/snapshots/latest"),
                headers=self._headers(),
                params=params,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            # API returns a single object for name lookup; normalize to list
            return [data] if isinstance(data, dict) else data
        except Exception as e:
            self._handle_error(e, "get item market prices by name")
            return None

    def get_item_market_price_history(self, item_id: int, days: int = 30) -> list[dict] | None:
        """GET /api/market/prices/snapshots/{item_id} — price history for one item."""
        try:
            from datetime import datetime, timedelta, timezone
            from_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            resp = self._session.get(
                self._url(f"/market/prices/snapshots/{item_id}"),
                headers=self._headers(),
                params={"from": from_date, "limit": "750"},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get item market price history")
            return None

    def get_ingested_globals(self, since: str, limit: int = 200) -> dict | None:
        """GET /api/ingestion/globals — fetch globals since a timestamp."""
        try:
            headers = self._auth_headers("get ingested globals")
            if headers is None:
                return None
            resp = self._session.get(
                self._url("/ingestion/globals"),
                headers=headers,
                params={"since": since, "limit": limit},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get ingested globals")
            return None

    def get_ingested_trades(self, since: str, limit: int = 200) -> dict | None:
        """GET /api/ingestion/trade — fetch trades since a timestamp."""
        try:
            headers = self._auth_headers("get ingested trades")
            if headers is None:
                return None
            resp = self._session.get(
                self._url("/ingestion/trade"),
                headers=headers,
                params={"since": since, "limit": limit},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get ingested trades")
            return None

    # Profiles

    def get_profile(self, identifier: str) -> dict | None:
        """GET /api/users/profiles/{identifier} — public user profile."""
        try:
            encoded = identifier.replace(" ", "~")
            resp = self._session.get(
                self._url(f"/users/profiles/{encoded}"),
                headers=self._headers(), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, f"get profile '{identifier}'")
            return None

    def update_profile(self, identifier: str, data: dict) -> dict | None:
        """PATCH /api/users/profiles/{identifier} — update biography, default tab, showcase."""
        try:
            headers = self._auth_headers(f"update profile '{identifier}'")
            if headers is None:
                return None
            encoded = identifier.replace(" ", "~")
            resp = self._session.patch(
                self._url(f"/users/profiles/{encoded}"),
                headers=headers, json=data, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, f"update profile '{identifier}'")
            return None

    def upload_profile_image(self, user_id: int, image_data: bytes,
                             content_type: str = "image/png") -> dict | None:
        """POST /api/image/user/{userId} — upload profile image (max 3MB)."""
        try:
            headers = self._auth_headers(f"upload profile image {user_id}")
            if headers is None:
                return None
            resp = self._session.post(
                self._url(f"/image/user/{user_id}"),
                headers=headers,
                files={"image": ("profile", image_data, content_type)},
                timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, f"upload profile image {user_id}")
            return None

    def delete_profile_image(self, user_id: int) -> bool:
        """DELETE /api/image/user/{userId} — remove custom profile image."""
        try:
            headers = self._auth_headers(f"delete profile image {user_id}")
            if headers is None:
                return False
            resp = self._session.delete(
                self._url(f"/image/user/{user_id}"),
                headers=headers, timeout=10)
            resp.raise_for_status()
            return True
        except Exception as e:
            self._handle_error(e, f"delete profile image {user_id}")
            return False

    # Global media

    def submit_global_video(self, global_id: int, video_url: str) -> dict | None:
        """POST /api/globals/{id}/media — submit a video link for a global."""
        try:
            headers = self._auth_headers(f"submit video for global {global_id}")
            if headers is None:
                return None
            headers["Content-Type"] = "application/json"
            resp = self._session.post(
                self._url(f"/globals/{global_id}/media"),
                headers=headers,
                json={"video_url": video_url},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, f"submit video for global {global_id}")
            return None

    # Societies

    def get_society(self, identifier: str) -> dict | None:
        """GET /api/societies/{identifier} — society details + members."""
        try:
            encoded = identifier.replace(" ", "~")
            resp = self._session.get(
                self._url(f"/societies/{encoded}"),
                headers=self._headers(), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, f"get society '{identifier}'")
            return None

    def update_society(self, identifier: str, data: dict) -> dict | None:
        """PATCH /api/societies/{identifier} — update description, discord, discordPublic."""
        try:
            headers = self._auth_headers(f"update society '{identifier}'")
            if headers is None:
                return None
            encoded = identifier.replace(" ", "~")
            resp = self._session.patch(
                self._url(f"/societies/{encoded}"),
                headers=headers, json=data, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, f"update society '{identifier}'")
            return None

    def handle_join_request(self, request_id: int, action: str) -> dict | None:
        """PATCH /api/societies/requests/{request_id} — approve or reject."""
        try:
            headers = self._auth_headers(f"{action} join request {request_id}")
            if headers is None:
                return None
            resp = self._session.patch(
                self._url(f"/societies/requests/{request_id}"),
                headers=headers,
                json={"action": action},
                timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, f"{action} join request {request_id}")
            return None

    # Globals

    def get_player_globals(self, eu_name: str) -> dict | None:
        """GET /api/globals/player/{name} — player global event statistics."""
        try:
            encoded = eu_name.replace(" ", "~")
            resp = self._session.get(
                self._url(f"/globals/player/{encoded}"),
                timeout=15,
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, f"fetch globals for {eu_name}")
            return None

    # Globals Media

    def get_upload_budget(self) -> dict | None:
        """GET /api/globals/media/budget — monthly media upload budget."""
        try:
            headers = self._auth_headers("get upload budget")
            if headers is None:
                return None
            resp = self._session.get(
                self._url("/globals/media/budget"),
                headers=headers, timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self._handle_error(e, "get upload budget")
            return None

    def upload_global_media(self, server_global_id: int, file_path: str) -> dict | None:
        """POST /api/globals/{id}/media — upload screenshot to a global."""
        try:
            headers = self._auth_headers("upload global media")
            if headers is None:
                return None
            with open(file_path, "rb") as f:
                files = {"image": (file_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1], f, "image/png")}
                resp = self._session.post(
                    self._url(f"/globals/{server_global_id}/media"),
                    headers=headers,
                    files=files,
                    timeout=30,
                )
            if resp.status_code == 429:
                raise RateLimitError(int(resp.headers.get("Retry-After", 60)))
            resp.raise_for_status()
            return resp.json()
        except RateLimitError:
            raise
        except Exception as e:
            self._handle_error(e, f"upload global media {server_global_id}")
            return None

    def link_youtube(self, server_global_id: int, youtube_url: str) -> dict | None:
        """Backward-compatible alias for submit_global_video."""
        return self.submit_global_video(server_global_id, youtube_url)

    # Streams

    def get_streams(self) -> list[dict] | None:
        """GET /api/streams — returns list of creators with live status."""
        try:
            resp = self._session.get(
                self._url("/streams"),
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("creators", [])
        except Exception as e:
            log.debug("Failed to get streams: %s", e)
            return None
