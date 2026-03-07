"""Ingestion uploader — buffers globals and trade chat events, sends
compressed batches to the Nexus ingestion API on a periodic timer.

Subscribe to EventBus events as they arrive and drain the buffers every
`upload_interval` seconds (default 30). Only active when authenticated.

Batches are chunked to respect the server's max batch size (500 items)
and rate limits (20 requests per 60 seconds per endpoint). On rate-limit
or transient failure, unsent items are re-queued for the next flush.

Pending items are persisted to SQLite so they survive a crash. On startup,
any items left from a previous session are loaded and sent first.
"""

from __future__ import annotations

import hashlib
import re
import threading
from collections import deque
from datetime import datetime, timedelta

from ..api.nexus_client import RateLimitError, ServerError
from ..chat_parser.models import GlobalEvent
from ..core.constants import EVENT_CATCHUP_COMPLETE, EVENT_GLOBAL, EVENT_HISTORICAL_IMPORT_COMPLETE, EVENT_INGESTION_STATUS, EVENT_MARKET_PRICE_SCAN, EVENT_REPARSE_COMPLETE, EVENT_TRADE_CHAT
from ..core.logger import get_logger

log = get_logger("Ingestion.Upload")

MAX_BATCH_SIZE = 500
INGEST_RATE_LIMIT_MAX_REQUESTS = 20
INGEST_RATE_LIMIT_WINDOW = timedelta(seconds=60)
REALTIME_FLUSH_DELAY = 5  # seconds — flush within this time after new live event

# Must match server-side limits in ingestion.js
MAX_PLAYER_LENGTH = 200
MAX_TARGET_LENGTH = 300
MAX_LOCATION_LENGTH = 200

# Occurrence tracking: identical globals within this window get incrementing occurrence numbers.
# Must match server-side GLOBAL_DEDUP_WINDOW_MS (5 minutes).
OCCURRENCE_WINDOW = timedelta(minutes=5)
MAX_OCCURRENCE = 3

# Trade messages older than this are ignored (server rejects them anyway).
# Must match server-side MAX_EVENT_AGE_MS (24 hours).
MAX_TRADE_AGE = timedelta(days=1)

# Trade keyword pre-filter — must match server-side TRADE_KEYWORDS in ingestion.js
TRADE_KEYWORDS_RE = re.compile(
    r"\b(wts|wtb|wtt|sell|selling|buy|buying|trade|trading|price|pc|offer|obo|lf|looking\s+for)\b",
    re.IGNORECASE,
)
ITEM_LINK_RE = re.compile(r"\[[^\[\]]{2,}\]")


class IngestionUploader:
    """Buffers chat-parsed events and periodically uploads them to the server."""

    def __init__(self, *, event_bus, nexus_client, config, db=None):
        self._event_bus = event_bus
        self._nexus_client = nexus_client
        self._config = config
        self._db = db

        self._global_buffer: deque[dict] = deque()
        self._trade_buffer: deque[dict] = deque()
        self._market_price_buffer: deque[dict] = deque()
        self._market_price_last_seen: dict[str, datetime] = {}  # 1hr dedup
        self._lock = threading.Lock()

        self._stop_event = threading.Event()
        self._flush_requested = threading.Event()
        self._live = False  # True after first catchup complete — enables real-time flush
        self._rate_limit_until: dict[str, datetime] = {}
        self._request_times: dict[str, deque[datetime]] = {
            "global": deque(),
            "trade": deque(),
            "market_price": deque(),
        }
        self._thread: threading.Thread | None = None

        # Occurrence tracking: base_hash -> list of event timestamps (within 5-min window)
        self._recent_hashes: dict[str, list[datetime]] = {}

        # Load any pending items from a previous session (crash recovery)
        if db:
            recovered_globals = db.load_pending_ingestion("global")
            recovered_trades = db.load_pending_ingestion("trade")
            if recovered_globals:
                self._global_buffer.extend(recovered_globals)
                log.info("Recovered %d pending globals from previous session", len(recovered_globals))
            if recovered_trades:
                self._trade_buffer.extend(recovered_trades)
                log.info("Recovered %d pending trades from previous session", len(recovered_trades))
                # Market price ingestion disabled — OCR not ready yet
            # recovered_mp = db.load_pending_ingestion("market_price")
            # if recovered_mp:
            #     self._market_price_buffer.extend(recovered_mp)
            #     log.info("Recovered %d pending market prices from previous session", len(recovered_mp))

        self._event_bus.subscribe(EVENT_GLOBAL, self._on_global)
        self._event_bus.subscribe(EVENT_TRADE_CHAT, self._on_trade)
        # Market price ingestion disabled — OCR not ready yet
        # self._event_bus.subscribe(EVENT_MARKET_PRICE_SCAN, self._on_market_price)
        self._event_bus.subscribe(EVENT_CATCHUP_COMPLETE, self._on_catchup_complete)
        self._event_bus.subscribe(EVENT_REPARSE_COMPLETE, self._on_reparse_complete)
        self._event_bus.subscribe(EVENT_HISTORICAL_IMPORT_COMPLETE, self._on_historical_import_complete)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Start the periodic upload thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="ingestion-upload",
        )
        self._thread.start()
        log.info("Uploader started (interval=%ds)", self._upload_interval)

    def stop(self):
        """Stop the upload thread and flush remaining buffers."""
        self._stop_event.set()
        self._flush_requested.set()  # Wake upload thread immediately
        if self._thread:
            self._thread.join(timeout=5)
        # Final flush
        self._flush()
        # Persist anything still unsent
        self._persist_buffers()
        self._event_bus.unsubscribe(EVENT_GLOBAL, self._on_global)
        self._event_bus.unsubscribe(EVENT_TRADE_CHAT, self._on_trade)
        self._event_bus.unsubscribe(EVENT_MARKET_PRICE_SCAN, self._on_market_price)
        self._event_bus.unsubscribe(EVENT_CATCHUP_COMPLETE, self._on_catchup_complete)
        self._event_bus.unsubscribe(EVENT_REPARSE_COMPLETE, self._on_reparse_complete)
        self._event_bus.unsubscribe(EVENT_HISTORICAL_IMPORT_COMPLETE, self._on_historical_import_complete)
        log.info("Uploader stopped")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_global(self, event):
        # Validate field lengths before buffering (must match server limits)
        if len(event.player_name) > MAX_PLAYER_LENGTH:
            log.warning("Dropping global: player name too long (%d chars)", len(event.player_name))
            return
        if len(event.target_name) > MAX_TARGET_LENGTH:
            log.warning("Dropping global: target name too long (%d chars)", len(event.target_name))
            return
        if event.location and len(event.location) > MAX_LOCATION_LENGTH:
            log.warning("Dropping global: location too long (%d chars), truncating", len(event.location))
            event = GlobalEvent(
                timestamp=event.timestamp,
                global_type=event.global_type,
                player_name=event.player_name,
                target_name=event.target_name,
                value=event.value,
                value_unit=event.value_unit,
                location=event.location[:MAX_LOCATION_LENGTH],
                is_hof=event.is_hof,
                is_ath=event.is_ath,
            )

        event_dict = {
            "timestamp": event.timestamp.isoformat(),
            "type": event.global_type.value,
            "player": event.player_name,
            "target": event.target_name,
            "value": event.value,
            "unit": event.value_unit,
            "location": event.location,
            "hof": event.is_hof,
            "ath": event.is_ath,
        }

        with self._lock:
            occurrence = self._assign_occurrence(event_dict, event.timestamp)
            event_dict["occurrence"] = occurrence
            self._global_buffer.append(event_dict)

        if self._live:
            self._flush_requested.set()
        self._emit_status()

    def _on_trade(self, event):
        # Skip messages without trade keywords or item links (irrelevant chatter)
        if not TRADE_KEYWORDS_RE.search(event.message) and not ITEM_LINK_RE.search(event.message):
            return

        # Skip trade messages older than 1 day (server rejects them anyway)
        if datetime.now() - event.timestamp > MAX_TRADE_AGE:
            return

        with self._lock:
            self._trade_buffer.append({
                "timestamp": event.timestamp.isoformat(),
                "channel": event.channel,
                "username": event.username,
                "message": event.message,
            })

        if self._live:
            self._flush_requested.set()
        self._emit_status()

    def _on_market_price(self, data):
        name = data.get("item_name", "")
        if not name:
            return
        now = datetime.now()
        with self._lock:
            # 1hr dedup: skip if same item was buffered within the last hour
            last = self._market_price_last_seen.get(name)
            if last and (now - last) < timedelta(hours=1):
                return
            self._market_price_last_seen[name] = now
            self._market_price_buffer.append(data)
        if self._live:
            self._flush_requested.set()
        self._emit_status()

    def _on_catchup_complete(self, _data):
        """After initial catchup — re-buffer from DB and enable real-time flush."""
        if self._live:
            return  # Ignore reparse's secondary EVENT_CATCHUP_COMPLETE
        self._live = True
        log.info("Catchup complete, real-time flush enabled (delay=%ds)", REALTIME_FLUSH_DELAY)
        self._rebuffer_from_db()

    def _on_reparse_complete(self, _data):
        """After a manual reparse — re-buffer globals/trades from DB for re-upload."""
        self._rebuffer_from_db()

    def _on_historical_import_complete(self, _data):
        """After historical log import — re-buffer globals/trades from DB for upload."""
        self._rebuffer_from_db()

    def _rebuffer_from_db(self):
        """Re-buffer globals and trades from the local DB for upload.

        During catchup/reparse, EventBus events are suppressed so globals and
        trades are only written to the local DB. This method reads them back
        and queues them for upload. Clears occurrence tracker and buffers
        first to avoid double-counting.
        """
        if not self._db:
            return

        def _rebuffer():
            import time as _time

            with self._lock:
                self._global_buffer.clear()
                self._trade_buffer.clear()
                self._recent_hashes.clear()

            # Stream globals from DB — never hold entire table in RAM.
            # time.sleep(0) yields GIL so UI/keyboard hook stays responsive.
            global_count = 0
            last_yield = _time.monotonic()
            for g in self._db.iter_globals():
                occurrence = self._assign_occurrence(g, datetime.fromisoformat(g["timestamp"]))
                g["occurrence"] = occurrence
                with self._lock:
                    self._global_buffer.append(g)
                global_count += 1
                if _time.monotonic() - last_yield > 0.008:
                    _time.sleep(0)
                    last_yield = _time.monotonic()

            # Stream trades — filter inline, append matches directly.
            trade_count = 0
            now = datetime.now()
            last_yield = _time.monotonic()
            for t in self._db.iter_trades(max_age_hours=24):
                if not (TRADE_KEYWORDS_RE.search(t["message"]) or ITEM_LINK_RE.search(t["message"])):
                    continue
                if now - datetime.fromisoformat(t["timestamp"]) > MAX_TRADE_AGE:
                    continue
                with self._lock:
                    self._trade_buffer.append(t)
                trade_count += 1
                if _time.monotonic() - last_yield > 0.008:
                    _time.sleep(0)
                    last_yield = _time.monotonic()

            log.info("Re-buffered %d globals and %d trades from local DB for upload",
                     global_count, trade_count)
            self._emit_status()
            if global_count or trade_count:
                self._flush_requested.set()

        threading.Thread(target=_rebuffer, daemon=True, name="ingestion-rebuffer").start()

    # ------------------------------------------------------------------
    # Occurrence tracking
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_global_hash(event_dict: dict) -> str:
        """Compute content hash for occurrence tracking (internal consistency)."""
        parts = [
            event_dict.get("type", ""),
            event_dict.get("player", ""),
            event_dict.get("target", ""),
            str(event_dict["value"]) if event_dict.get("value") is not None else "",
            event_dict.get("unit", "") or "PED",
            event_dict.get("location", "") or "",
            "1" if event_dict.get("hof") else "0",
            "1" if event_dict.get("ath") else "0",
        ]
        return hashlib.sha256("|".join(parts).encode()).hexdigest()

    def _assign_occurrence(self, event_dict: dict, event_ts: datetime) -> int:
        """Assign occurrence number based on recent identical events.

        Within a 5-minute window of the event timestamp, counts how many
        prior events have the same content hash. Returns count + 1, capped
        at MAX_OCCURRENCE. Must be called under self._lock.
        """
        h = self._compute_global_hash(event_dict)
        cutoff = event_ts - OCCURRENCE_WINDOW

        # Clean expired entries for this hash
        if h in self._recent_hashes:
            self._recent_hashes[h] = [
                ts for ts in self._recent_hashes[h] if ts > cutoff
            ]
            if not self._recent_hashes[h]:
                del self._recent_hashes[h]

        # Count existing occurrences within window
        count = len(self._recent_hashes.get(h, []))
        occurrence = count + 1

        if occurrence > MAX_OCCURRENCE:
            log.debug(
                "Occurrence overflow (%d > %d) for %s [%s] %s %.2f %s — capping at %d",
                occurrence, MAX_OCCURRENCE,
                event_dict.get("type", "?"), event_dict.get("player", "?"),
                event_dict.get("target", "?"), event_dict.get("value", 0),
                event_dict.get("unit", "PED"), MAX_OCCURRENCE,
            )
            occurrence = MAX_OCCURRENCE

        # Record this event's timestamp
        if h not in self._recent_hashes:
            self._recent_hashes[h] = []
        self._recent_hashes[h].append(event_ts)

        return occurrence

    def _cleanup_occurrence_tracker(self):
        """Remove entries older than the occurrence window."""
        now = datetime.now()
        cutoff = now - OCCURRENCE_WINDOW
        stale = [h for h, timestamps in self._recent_hashes.items()
                 if all(ts < cutoff for ts in timestamps)]
        for h in stale:
            del self._recent_hashes[h]

    def _prune_request_times(self, type_name: str, now: datetime) -> deque[datetime]:
        """Drop request timestamps outside the rolling limit window."""
        times = self._request_times[type_name]
        cutoff = now - INGEST_RATE_LIMIT_WINDOW
        while times and times[0] <= cutoff:
            times.popleft()
        return times

    def _reserve_rate_limit_slot(self, type_name: str) -> tuple[bool, int]:
        """Reserve one request slot for an endpoint if within rate limits."""
        now = datetime.now()
        with self._lock:
            blocked_until = self._rate_limit_until.get(type_name)
            if blocked_until and now < blocked_until:
                wait_s = max(1, int((blocked_until - now).total_seconds()))
                return False, wait_s
            if blocked_until and now >= blocked_until:
                self._rate_limit_until.pop(type_name, None)

            times = self._prune_request_times(type_name, now)
            if len(times) >= INGEST_RATE_LIMIT_MAX_REQUESTS:
                next_allowed = times[0] + INGEST_RATE_LIMIT_WINDOW
                self._rate_limit_until[type_name] = next_allowed
                wait_s = max(1, int((next_allowed - now).total_seconds()))
                return False, wait_s

            times.append(now)

        return True, 0

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    @property
    def _upload_interval(self) -> int:
        return getattr(self._config, "ingestion_upload_interval_seconds", 30)

    def _run(self):
        while not self._stop_event.is_set():
            # Wait for either the regular interval or a real-time flush nudge
            self._flush_requested.wait(timeout=self._upload_interval)
            if self._stop_event.is_set():
                break

            if self._flush_requested.is_set():
                self._flush_requested.clear()
                # Brief delay to batch nearby events (e.g. multiple globals in rapid succession)
                self._stop_event.wait(timeout=REALTIME_FLUSH_DELAY)
                if self._stop_event.is_set():
                    break

            self._flush()

    def _emit_status(self):
        """Publish pending buffer count for UI status display."""
        with self._lock:
            pending = len(self._global_buffer) + len(self._trade_buffer) + len(self._market_price_buffer)
        self._event_bus.publish(EVENT_INGESTION_STATUS, {"pending": pending})

    def _flush(self):
        """Drain buffers and send to server in chunks of MAX_BATCH_SIZE."""
        if not self._nexus_client.is_authenticated():
            return

        # Per-endpoint rate limiting is enforced in _flush_type().
        # Clean stale occurrence tracker entries
        with self._lock:
            self._cleanup_occurrence_tracker()

        g_sent, g_processed = self._flush_type(self._global_buffer, "global", self._nexus_client.ingest_globals)
        t_sent, t_processed = self._flush_type(self._trade_buffer, "trade", self._nexus_client.ingest_trades)
        # Market price ingestion disabled — OCR not ready yet
        mp_sent, mp_processed = 0, []

        # Delete only the specific items confirmed processed by the server.
        # Items still in the buffer (re-queued from rate limiting) stay in the DB
        # so they survive a restart via _rebuffer_from_db().
        changed = g_processed or t_processed
        if self._db and changed:
            try:
                g_del = self._db.delete_ingested_globals(g_processed) if g_processed else 0
                t_del = self._db.delete_ingested_trades(t_processed) if t_processed else 0
                if g_del or t_del:
                    log.debug("Cleaned up %d globals, %d trades from local DB", g_del, t_del)
            except Exception as e:
                log.warning("Failed to clean up ingested data from local DB: %s", e)

        # Only re-persist remaining buffer if something was actually sent/processed.
        # Avoids expensive full-buffer rewrite every cycle when rate-limited.
        if changed:
            self._persist_buffers()
        self._emit_status()

    def _flush_type(self, buffer, type_name, send_fn) -> tuple[int, list[dict]]:
        """Flush a buffer to the server.

        Returns (accepted_count, processed_items) where processed_items are
        the items from chunks that the server successfully handled (accepted,
        duplicate, or invalid — all confirmed processed). Items from chunks
        that hit rate limits or server errors are re-queued and NOT included.
        """
        items = self._drain(buffer)
        if not items:
            return 0, []

        sent = 0
        processed = []
        for chunk_start in range(0, len(items), MAX_BATCH_SIZE):
            chunk = items[chunk_start:chunk_start + MAX_BATCH_SIZE]

            if not self._nexus_client.is_authenticated():
                unsent = items[chunk_start:]
                self._requeue(buffer, unsent)
                return sent, processed

            allowed, wait_s = self._reserve_rate_limit_slot(type_name)
            if not allowed:
                unsent = items[chunk_start:]
                self._requeue(buffer, unsent)
                log.info(
                    "%s pre-emptive throttle, re-queued %d items (retry in %ds)",
                    type_name.capitalize(),
                    len(unsent),
                    wait_s,
                )
                return sent, processed
            try:
                result = send_fn(chunk)
                if result:
                    sent += result.get("accepted", 0)
                    processed.extend(chunk)
                    invalid = result.get("invalid", 0)
                    log.debug(
                        "%s chunk: %d accepted, %d dup, %d conflict, %d invalid",
                        type_name.capitalize(),
                        result.get("accepted", 0),
                        result.get("duplicates", 0),
                        result.get("conflicts", 0),
                        invalid,
                    )
                    if invalid > 0:
                        errors = result.get("errors", [])
                        for err in errors[:5]:  # log first 5 validation errors
                            idx = err.get("index", -1)
                            log.warning("%s validation error at index %d: %s",
                                        type_name.capitalize(), idx, err.get("error", "unknown"))
                            if 0 <= idx < len(chunk):
                                log.warning("  Rejected event: %s", chunk[idx])
                else:
                    # send_fn returned None — API error was already logged by _handle_error.
                    # Log batch summary so we can diagnose the issue.
                    self._log_failed_batch(type_name, chunk)
            except RateLimitError as e:
                self._rate_limit_until[type_name] = (
                    datetime.now() + timedelta(seconds=e.retry_after)
                )
                unsent = items[chunk_start:]
                self._requeue(buffer, unsent)
                log.warning("%s rate-limited, re-queued %d items (retry in %ds)",
                            type_name.capitalize(), len(unsent), e.retry_after)
                return sent, processed
            except ServerError as e:
                unsent = items[chunk_start:]
                self._requeue(buffer, unsent)
                log.warning("%s server error, re-queued %d items: %s",
                            type_name.capitalize(), len(unsent), e)
                return sent, processed
            except Exception as e:
                log.warning("%s upload failed (client error): %s", type_name.capitalize(), e)
                self._log_failed_batch(type_name, chunk)

        if sent:
            log.info("%s flush complete: %d accepted", type_name.capitalize(), sent)

        # Clear persisted pending items after successful flush
        if self._db:
            self._db.clear_pending_ingestion(type_name)

        return sent, processed

    @staticmethod
    def _log_failed_batch(type_name: str, chunk: list[dict]):
        """Log a summary of a failed batch for debugging."""
        if not chunk:
            return
        if type_name == "global":
            # Show first few events: type, player, target, value, occurrence
            for item in chunk[:5]:
                log.warning(
                    "  [%s] %s | %s → %s | %.2f %s | occ=%s | ts=%s",
                    type_name, item.get("type", "?"),
                    item.get("player", "?"), item.get("target", "?"),
                    item.get("value", 0), item.get("unit", "PED"),
                    item.get("occurrence", "?"), item.get("timestamp", "?"),
                )
            if len(chunk) > 5:
                log.warning("  ... and %d more %s events", len(chunk) - 5, type_name)
        elif type_name == "trade":
            for item in chunk[:3]:
                msg = item.get("message", "")
                log.warning(
                    "  [%s] %s in %s: %s | ts=%s",
                    type_name, item.get("username", "?"),
                    item.get("channel", "?"),
                    msg[:80] + ("..." if len(msg) > 80 else ""),
                    item.get("timestamp", "?"),
                )
            if len(chunk) > 3:
                log.warning("  ... and %d more %s messages", len(chunk) - 3, type_name)

    # ------------------------------------------------------------------
    # Buffer helpers
    # ------------------------------------------------------------------

    def _drain(self, buffer: deque) -> list[dict]:
        with self._lock:
            items = list(buffer)
            buffer.clear()
        return items

    def _requeue(self, buffer: deque, items: list[dict]):
        """Prepend unsent items back into the buffer (oldest first)."""
        with self._lock:
            buffer.extendleft(reversed(items))

    def _persist_buffers(self):
        """Save current buffer contents to disk for crash recovery."""
        if not self._db:
            return
        with self._lock:
            globals_list = list(self._global_buffer)
            trades_list = list(self._trade_buffer)
        if globals_list:
            self._db.save_pending_ingestion("global", globals_list)
        else:
            self._db.clear_pending_ingestion("global")
        if trades_list:
            self._db.save_pending_ingestion("trade", trades_list)
        else:
            self._db.clear_pending_ingestion("trade")


def _chunked(items: list, size: int):
    """Yield successive chunks of *size* from *items*."""
    for i in range(0, len(items), size):
        yield items[i:i + size]
