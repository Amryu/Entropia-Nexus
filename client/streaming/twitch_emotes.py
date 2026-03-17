"""Twitch emote fetching, caching, and resolution.

Supports Twitch native, BTTV, FFZ, and 7TV emotes.
All network I/O runs on background threads — never call from the main thread.
"""

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING

import requests

from ..core.logger import get_logger

if TYPE_CHECKING:
    pass

log = get_logger("TwitchEmotes")

# CDN URLs — use 2x scale for decent quality at 22-28px display size
_TWITCH_CDN = "https://static-cdn.jtvnw.net/emoticons/v2/{id}/default/dark/2.0"
_BTTV_CDN = "https://cdn.betterttv.net/emote/{id}/2x.png"
_FFZ_CDN = "https://cdn.frankerfacez.com/emote/{id}/2"
_7TV_CDN = "https://cdn.7tv.app/emote/{id}/2x.webp"

# API endpoints
_BTTV_GLOBAL_URL = "https://api.betterttv.net/3/cached/emotes/global"
_BTTV_CHANNEL_URL = "https://api.betterttv.net/3/cached/users/twitch/{channel_id}"
_FFZ_CHANNEL_URL = "https://api.frankerfacez.com/v1/room/{channel}"
_7TV_GLOBAL_URL = "https://7tv.io/v3/emote-sets/global"
_7TV_CHANNEL_URL = "https://7tv.io/v3/users/twitch/{channel_id}"

_REQUEST_TIMEOUT = 10


class EmoteManager:
    """Fetches, caches, and resolves emotes from multiple providers."""

    def __init__(self, cache_dir: str):
        self._cache_dir = cache_dir
        self._lock = threading.Lock()
        # {emote_code: local_file_path}
        self._global_emotes: dict[str, str] = {}
        self._channel_emotes: dict[str, str] = {}
        self._globals_loaded = False

        # Ensure cache directories exist
        for provider in ("twitch", "bttv", "ffz", "7tv"):
            os.makedirs(os.path.join(cache_dir, provider), exist_ok=True)

    # ------------------------------------------------------------------
    # Public API (call from background threads)
    # ------------------------------------------------------------------

    def load_global_emotes(self) -> dict[str, str]:
        """Fetch global emotes from BTTV, FFZ, 7TV. Returns the emote map.

        Safe to call from a background thread. Call once on startup.
        """
        if self._globals_loaded:
            return self._global_emotes

        emotes: dict[str, str] = {}

        # BTTV global
        try:
            resp = requests.get(_BTTV_GLOBAL_URL, timeout=_REQUEST_TIMEOUT)
            if resp.ok:
                for e in resp.json():
                    code = e.get("code", "")
                    eid = e.get("id", "")
                    if code and eid:
                        path = self._ensure_cached("bttv", eid, _BTTV_CDN.format(id=eid))
                        if path:
                            emotes[code] = path
        except Exception as exc:
            log.debug("BTTV global fetch failed: %s", exc)

        # 7TV global
        try:
            resp = requests.get(_7TV_GLOBAL_URL, timeout=_REQUEST_TIMEOUT)
            if resp.ok:
                data = resp.json()
                for e in data.get("emotes", []):
                    code = e.get("name", "")
                    eid = e.get("id", "")
                    if code and eid:
                        path = self._ensure_cached("7tv", eid, _7TV_CDN.format(id=eid))
                        if path:
                            emotes[code] = path
        except Exception as exc:
            log.debug("7TV global fetch failed: %s", exc)

        with self._lock:
            self._global_emotes.update(emotes)
            self._globals_loaded = True

        log.debug("Loaded %d global emotes", len(emotes))
        return self._global_emotes

    def load_channel_emotes(self, channel: str, channel_id: str) -> dict[str, str]:
        """Fetch channel-specific emotes. Returns the combined emote map.

        Safe to call from a background thread. Call when joining a channel.
        """
        emotes: dict[str, str] = {}

        # BTTV channel
        try:
            url = _BTTV_CHANNEL_URL.format(channel_id=channel_id)
            resp = requests.get(url, timeout=_REQUEST_TIMEOUT)
            if resp.ok:
                data = resp.json()
                for e in data.get("channelEmotes", []) + data.get("sharedEmotes", []):
                    code = e.get("code", "")
                    eid = e.get("id", "")
                    if code and eid:
                        path = self._ensure_cached("bttv", eid, _BTTV_CDN.format(id=eid))
                        if path:
                            emotes[code] = path
        except Exception as exc:
            log.debug("BTTV channel fetch failed for %s: %s", channel, exc)

        # FFZ channel
        try:
            url = _FFZ_CHANNEL_URL.format(channel=channel)
            resp = requests.get(url, timeout=_REQUEST_TIMEOUT)
            if resp.ok:
                data = resp.json()
                for eset in data.get("sets", {}).values():
                    for e in eset.get("emoticons", []):
                        code = e.get("name", "")
                        eid = e.get("id", "")
                        if code and eid:
                            path = self._ensure_cached(
                                "ffz", str(eid), _FFZ_CDN.format(id=eid),
                            )
                            if path:
                                emotes[code] = path
        except Exception as exc:
            log.debug("FFZ channel fetch failed for %s: %s", channel, exc)

        # 7TV channel
        try:
            url = _7TV_CHANNEL_URL.format(channel_id=channel_id)
            resp = requests.get(url, timeout=_REQUEST_TIMEOUT)
            if resp.ok:
                data = resp.json()
                emote_set = data.get("emote_set", {})
                for e in emote_set.get("emotes", []):
                    code = e.get("name", "")
                    eid = e.get("id", "")
                    if code and eid:
                        path = self._ensure_cached("7tv", eid, _7TV_CDN.format(id=eid))
                        if path:
                            emotes[code] = path
        except Exception as exc:
            log.debug("7TV channel fetch failed for %s: %s", channel, exc)

        with self._lock:
            self._channel_emotes = emotes

        log.debug("Loaded %d channel emotes for %s", len(emotes), channel)
        return emotes

    def clear_channel_emotes(self):
        """Clear channel-specific emotes (called when leaving a channel)."""
        with self._lock:
            self._channel_emotes.clear()

    def get_twitch_emote_path(self, emote_id: str) -> str | None:
        """Return cached path for a Twitch native emote, or None.

        Does NOT download — call ``queue_twitch_emotes`` to fetch missing
        emotes in the background.  This is safe to call from the main thread.
        """
        path = os.path.join(self._cache_dir, "twitch", f"{emote_id}.png")
        return path if os.path.isfile(path) else None

    def queue_twitch_emotes(self, emote_ids: set[str]) -> None:
        """Download missing Twitch emotes in the background.

        Call from the main thread; spawns a daemon thread.
        """
        missing = []
        for eid in emote_ids:
            path = os.path.join(self._cache_dir, "twitch", f"{eid}.png")
            if not os.path.isfile(path):
                missing.append(eid)

        if not missing:
            return

        threading.Thread(
            target=self._download_twitch_emotes,
            args=(missing,),
            daemon=True,
            name="twitch-emotes",
        ).start()

    def _download_twitch_emotes(self, emote_ids: list[str]) -> None:
        """Background thread: download a batch of Twitch emotes."""
        for eid in emote_ids:
            self._ensure_cached("twitch", eid, _TWITCH_CDN.format(id=eid))

    def resolve_third_party(self, word: str) -> str | None:
        """Look up a word in BTTV/FFZ/7TV emote maps. Returns cached file path or None."""
        with self._lock:
            path = self._channel_emotes.get(word)
            if path is not None:
                return path
            return self._global_emotes.get(word)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_cached(self, provider: str, emote_id: str, url: str) -> str | None:
        """Return local file path, downloading if necessary.

        Call from background threads only (does network I/O).
        """
        path = os.path.join(self._cache_dir, provider, f"{emote_id}.png")
        if os.path.isfile(path):
            return path

        try:
            resp = requests.get(url, timeout=_REQUEST_TIMEOUT)
            if resp.ok:
                with open(path, "wb") as f:
                    f.write(resp.content)
                return path
        except Exception as exc:
            log.debug("Emote download failed %s/%s: %s", provider, emote_id, exc)

        return None
