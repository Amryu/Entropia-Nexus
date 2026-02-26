"""Authenticated API client for the Entropia Nexus backend."""

import requests

from ..core.logger import get_logger

log = get_logger("API")


class NexusClient:
    """Authenticated requests to the Nexus backend (entropianexus.com/api/...)."""

    def __init__(self, config, oauth):
        self._config = config
        self._oauth = oauth
        self._session = requests.Session()

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
            log.error("Failed to get skills: %s", e)
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
            log.error("Failed to upload skills: %s", e)
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
            log.error("Failed to get loadouts: %s", e)
            return None

    def get_loadout(self, loadout_id: str) -> dict | None:
        """GET /api/tools/loadout/:id — returns a single loadout."""
        try:
            resp = self._session.get(self._url(f"/tools/loadout/{loadout_id}"),
                                     headers=self._headers(), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.error("Failed to get loadout %s: %s", loadout_id, e)
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
            log.error("Failed to save loadout %s: %s", loadout_id, e)
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
            log.error("Failed to create loadout: %s", e)
            return None

    def delete_loadout(self, loadout_id: str) -> bool:
        """DELETE /api/tools/loadout/:id — delete a loadout."""
        try:
            resp = self._session.delete(self._url(f"/tools/loadout/{loadout_id}"),
                                        headers=self._headers(), timeout=10)
            resp.raise_for_status()
            return True
        except Exception as e:
            log.error("Failed to delete loadout %s: %s", loadout_id, e)
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
            log.error("Failed to get preferences: %s", e)
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
            log.error("Failed to save preference '%s': %s", key, e)
            return False

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
