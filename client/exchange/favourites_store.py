"""Exchange favourites persistence — local JSON + server preferences sync."""

from __future__ import annotations

import json
import os
import threading
import uuid
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal

from ..core.logger import get_logger

if TYPE_CHECKING:
    from ..api.nexus_client import NexusClient

log = get_logger("FavouritesStore")

_PREF_KEY = "exchange.favourites"
_EMPTY: dict = {"folders": [], "items": []}


class FavouritesStore(QObject):
    """Manages exchange item favourites with dual persistence (local + server)."""

    changed = pyqtSignal()

    def __init__(self, nexus_client: NexusClient | None = None,
                 local_path: str | None = None):
        super().__init__()
        self._client = nexus_client
        self._local_path = local_path or self._default_local_path()
        self._data: dict = {"folders": [], "items": []}
        self._loaded = False
        self._load_local()

    @staticmethod
    def _default_local_path() -> str:
        app_data = os.path.join(os.path.expanduser("~"), ".entropia-nexus")
        os.makedirs(app_data, exist_ok=True)
        return os.path.join(app_data, "exchange_favourites.json")

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_local(self):
        """Load from local JSON file (instant, no network)."""
        try:
            if os.path.exists(self._local_path):
                with open(self._local_path, 'r') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._data = {
                        "folders": data.get("folders", []),
                        "items": data.get("items", []),
                    }
        except Exception as e:
            log.warning("Failed to load local favourites: %s", e)

    def load_from_server(self):
        """Fetch from server preferences (call in background thread).

        Server value is authoritative. If server is empty but local has data,
        migrate local up to server.
        """
        if not self._client or not self._client.is_authenticated():
            self._loaded = True
            return

        def _do():
            try:
                prefs = self._client.get_preferences()
                if prefs is None:
                    self._loaded = True
                    return
                server_data = prefs.get(_PREF_KEY)
                if server_data and isinstance(server_data, dict):
                    self._data = {
                        "folders": server_data.get("folders", []),
                        "items": server_data.get("items", []),
                    }
                    self._save_local()
                    self.changed.emit()
                elif self._data.get("items") or self._data.get("folders"):
                    # Local has data but server doesn't — migrate up
                    self._sync_to_server()
                self._loaded = True
            except Exception as e:
                log.warning("Failed to load favourites from server: %s", e)
                self._loaded = True

        threading.Thread(target=_do, daemon=True, name="fav-load").start()

    @property
    def loaded(self) -> bool:
        return self._loaded

    # ------------------------------------------------------------------
    # Item operations
    # ------------------------------------------------------------------

    def add_favourite(self, item_id: int, folder_id: str | None = None):
        """Add item to root or a specific folder. No-op if already favourited."""
        if self.is_favourite(item_id):
            return
        if folder_id:
            for folder in self._data["folders"]:
                if folder["id"] == folder_id:
                    folder["items"].append(item_id)
                    break
            else:
                # Folder not found, add to root
                self._data["items"].append(item_id)
        else:
            self._data["items"].append(item_id)
        self._persist()

    def remove_favourite(self, item_id: int):
        """Remove item from all locations (root + all folders)."""
        self._data["items"] = [i for i in self._data["items"] if i != item_id]
        for folder in self._data["folders"]:
            folder["items"] = [i for i in folder["items"] if i != item_id]
        self._persist()

    def toggle_favourite(self, item_id: int) -> bool:
        """Toggle favourite status. Returns True if now favourited."""
        if self.is_favourite(item_id):
            self.remove_favourite(item_id)
            return False
        else:
            self.add_favourite(item_id)
            return True

    def is_favourite(self, item_id: int) -> bool:
        """Check if item exists in any folder or root."""
        if item_id in self._data["items"]:
            return True
        return any(item_id in f["items"] for f in self._data["folders"])

    # ------------------------------------------------------------------
    # Folder operations
    # ------------------------------------------------------------------

    def create_folder(self, name: str) -> str:
        """Create a new folder. Returns folder ID."""
        folder_id = str(uuid.uuid4())
        order = len(self._data["folders"])
        self._data["folders"].append({
            "id": folder_id,
            "name": name,
            "items": [],
            "order": order,
        })
        self._persist()
        return folder_id

    def rename_folder(self, folder_id: str, name: str):
        """Rename an existing folder."""
        for folder in self._data["folders"]:
            if folder["id"] == folder_id:
                folder["name"] = name
                self._persist()
                return

    def delete_folder(self, folder_id: str, keep_items: bool = True):
        """Delete a folder. If keep_items=True, move items to root."""
        for folder in self._data["folders"]:
            if folder["id"] == folder_id:
                if keep_items:
                    for item_id in folder["items"]:
                        if item_id not in self._data["items"]:
                            self._data["items"].append(item_id)
                self._data["folders"] = [
                    f for f in self._data["folders"] if f["id"] != folder_id
                ]
                self._persist()
                return

    def move_to_folder(self, item_id: int, folder_id: str | None):
        """Move item to a folder (or None for root). Removes from current location first."""
        # Remove from everywhere
        self._data["items"] = [i for i in self._data["items"] if i != item_id]
        for folder in self._data["folders"]:
            folder["items"] = [i for i in folder["items"] if i != item_id]

        # Add to target
        if folder_id:
            for folder in self._data["folders"]:
                if folder["id"] == folder_id:
                    folder["items"].append(item_id)
                    break
        else:
            self._data["items"].append(item_id)
        self._persist()

    def reorder_folders(self, ordered_ids: list[str]):
        """Reorder folders by passing folder IDs in desired order."""
        id_to_folder = {f["id"]: f for f in self._data["folders"]}
        reordered = []
        for i, fid in enumerate(ordered_ids):
            if fid in id_to_folder:
                folder = id_to_folder[fid]
                folder["order"] = i
                reordered.append(folder)
        # Add any folders not in ordered_ids at the end
        for folder in self._data["folders"]:
            if folder["id"] not in {f["id"] for f in reordered}:
                folder["order"] = len(reordered)
                reordered.append(folder)
        self._data["folders"] = reordered
        self._persist()

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_all_item_ids(self) -> set[int]:
        """Get all favourited item IDs (root + all folders)."""
        ids = set(self._data["items"])
        for folder in self._data["folders"]:
            ids.update(folder["items"])
        return ids

    def get_folder_item_ids(self, folder_id: str) -> list[int]:
        """Get item IDs in a specific folder."""
        for folder in self._data["folders"]:
            if folder["id"] == folder_id:
                return list(folder["items"])
        return []

    def get_root_item_ids(self) -> list[int]:
        """Get root/unfiled item IDs."""
        return list(self._data["items"])

    def get_folders(self) -> list[dict]:
        """Get folders sorted by order."""
        return sorted(self._data["folders"], key=lambda f: f.get("order", 0))

    def get_data(self) -> dict:
        """Get the raw favourites data."""
        return {
            "folders": list(self._data["folders"]),
            "items": list(self._data["items"]),
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist(self):
        """Save locally + emit signal + schedule server sync."""
        self._save_local()
        self.changed.emit()
        self._sync_to_server()

    def _save_local(self):
        """Write to local JSON file."""
        try:
            os.makedirs(os.path.dirname(self._local_path), exist_ok=True)
            with open(self._local_path, 'w') as f:
                json.dump(self._data, f)
        except Exception as e:
            log.warning("Failed to save local favourites: %s", e)

    def _sync_to_server(self):
        """Fire-and-forget sync to server preferences."""
        if not self._client or not self._client.is_authenticated():
            return
        data = self.get_data()

        def _do():
            try:
                self._client.save_preference(_PREF_KEY, data)
            except Exception as e:
                log.debug("Failed to sync favourites to server: %s", e)

        threading.Thread(target=_do, daemon=True, name="fav-sync").start()
