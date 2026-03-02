"""Ingestion receiver — polls the server for newly ingested globals and
trade messages and publishes them on the EventBus for UI consumption.

Tracks a cursor (last timestamp) per data type so only new entries are
fetched on each tick.  Deduplicates against previously seen entries using
server-provided IDs (globals) or content hashes (trades).
"""

from __future__ import annotations

import hashlib
import time
import threading
from datetime import datetime, timezone

from ..core.constants import EVENT_INGESTED_GLOBAL, EVENT_INGESTED_TRADE
from ..core.logger import get_logger

log = get_logger("Ingestion.Receive")

# Max seen IDs/hashes to keep before pruning (prevents unbounded memory growth)
_MAX_SEEN_SIZE = 10_000
_PRUNE_KEEP = 5_000

# How long to keep re-checking unconfirmed globals before dropping them
_PENDING_MAX_AGE = 300  # 5 minutes


def _content_hash_trade(t: dict) -> str:
    parts = [
        t.get("channel", ""),
        t.get("username", ""),
        t.get("message", ""),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


class IngestionReceiver:
    """Polls ingested data from the server and distributes via EventBus."""

    def __init__(self, *, event_bus, nexus_client, config, db=None):
        self._event_bus = event_bus
        self._nexus_client = nexus_client
        self._config = config
        self._db = db  # local SQLite for dedup, optional

        # Cursors start at "now" — we only want future data
        self._global_cursor = datetime.now(timezone.utc).isoformat()
        self._trade_cursor = datetime.now(timezone.utc).isoformat()

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        # Track entries we've already published to avoid re-emitting.
        # Globals use server IDs (handles multiple occurrences with same content hash).
        # Trades use content hashes (no occurrence concept).
        self._seen_global_ids: set[int] = set()
        self._seen_trade_hashes: set[str] = set()

        # Unconfirmed globals awaiting re-check (id → monotonic first_seen time)
        self._pending_globals: dict[int, float] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="ingestion-receive",
        )
        self._thread.start()
        log.info("Receiver started (interval=%ds)", self._poll_interval)

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        log.info("Receiver stopped")

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    @property
    def _poll_interval(self) -> int:
        return getattr(self._config, "ingestion_receive_interval_seconds", 60)

    def _run(self):
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._poll_interval)
            if self._stop_event.is_set():
                break
            self._poll()

    def _poll(self):
        if not self._nexus_client.is_authenticated():
            return

        self._poll_globals()
        self._poll_trades()

    # ------------------------------------------------------------------
    # Globals
    # ------------------------------------------------------------------

    def _poll_globals(self):
        try:
            data = self._nexus_client.get_ingested_globals(self._global_cursor)
            if not data:
                return

            now = time.monotonic()
            fresh = {
                g["id"]: g
                for g in data.get("globals", [])
                if g.get("id") is not None
            }

            # Re-check pending unconfirmed globals against fresh data
            expired = []
            for gid, first_seen in list(self._pending_globals.items()):
                if gid in fresh and fresh[gid].get("confirmed"):
                    # Now confirmed — publish
                    if gid not in self._seen_global_ids:
                        self._seen_global_ids.add(gid)
                        self._event_bus.publish(EVENT_INGESTED_GLOBAL, fresh[gid])
                    expired.append(gid)
                elif now - first_seen > _PENDING_MAX_AGE:
                    expired.append(gid)
            for gid in expired:
                self._pending_globals.pop(gid, None)

            # Process new entries from this poll
            for gid, g in fresh.items():
                if gid in self._seen_global_ids or gid in self._pending_globals:
                    continue
                if g.get("confirmed"):
                    self._seen_global_ids.add(gid)
                    self._event_bus.publish(EVENT_INGESTED_GLOBAL, g)
                else:
                    self._pending_globals[gid] = now

            # Prune seen IDs to prevent unbounded growth
            if len(self._seen_global_ids) > _MAX_SEEN_SIZE:
                sorted_ids = sorted(self._seen_global_ids)
                self._seen_global_ids = set(sorted_ids[_PRUNE_KEEP:])

            # Hold cursor if there are pending unconfirmed entries so they
            # reappear in the next poll; otherwise advance normally.
            if not self._pending_globals:
                cursor = data.get("cursor")
                if cursor:
                    self._global_cursor = cursor

        except Exception as e:
            log.debug("Global poll failed: %s", e)

    # ------------------------------------------------------------------
    # Trades
    # ------------------------------------------------------------------

    def _poll_trades(self):
        try:
            data = self._nexus_client.get_ingested_trades(self._trade_cursor)
            if not data:
                return

            for t in data.get("trades", []):
                h = _content_hash_trade(t)
                if h in self._seen_trade_hashes:
                    continue
                self._seen_trade_hashes.add(h)
                self._event_bus.publish(EVENT_INGESTED_TRADE, t)

            cursor = data.get("cursor")
            if cursor:
                self._trade_cursor = cursor

        except Exception as e:
            log.debug("Trade poll failed: %s", e)
