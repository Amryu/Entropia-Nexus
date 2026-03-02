"""Notification manager — central hub for all notification sources.

Subscribes to EventBus for globals and trade chat, evaluates rules,
manages cooldowns, polls server notifications, and dispatches to UI.
"""

from __future__ import annotations

import re
import uuid
import threading
from collections import deque, OrderedDict
from datetime import datetime, timedelta

from ..core.logger import get_logger
from ..core.constants import EVENT_GLOBAL, EVENT_INGESTED_GLOBAL, EVENT_TRADE_CHAT
from .models import (
    Notification,
    GlobalNotificationRule,
    SOURCE_GLOBAL,
    SOURCE_TRADE_CHAT,
    SOURCE_NEXUS,
    SOURCE_STREAM,
)
from .rules_engine import RulesEngine

log = get_logger("Notifications")

MAX_NOTIFICATIONS = 200
_MAX_GLOBAL_FPS = 500
_BRACKET_RE = re.compile(r"\[([^\[\]]+)\]")


class NotificationManager:
    """Manages notification creation, storage, and dispatch."""

    def __init__(self, *, config, event_bus, nexus_client=None):
        self._config = config
        self._event_bus = event_bus
        self._nexus_client = nexus_client
        self._lock = threading.Lock()

        # In-memory store (most recent first)
        self._notifications: deque[Notification] = deque(maxlen=MAX_NOTIFICATIONS)

        # Rules engine
        self._rules_engine = RulesEngine(self._load_rules())

        # Global dedup: fingerprints of recently seen globals (local + server)
        self._recent_global_fps: OrderedDict[tuple, None] = OrderedDict()

        # Trade chat cooldown: {(username_lower, item_lower): last_time}
        self._trade_cooldowns: dict[tuple[str, str], datetime] = {}
        self._trade_ignore: set[str] = set(
            u.lower() for u in getattr(config, "trade_chat_ignore_list", [])
        )

        # Server notification tracking
        self._seen_server_ids: set[int] = set()
        self._server_notif_initialized = False

        # Stream tracking
        self._known_live: set[int] = set()
        self._streams_initialized = False
        self._stream_exclude: set[str] = set(
            n.lower() for n in getattr(config, "stream_exclude_list", [])
        )

        # Callbacks for new notifications (called from any thread)
        self._on_notification_callbacks: list = []

        # Only process events after catchup
        self._live = False

        # Subscribe
        self._event_bus.subscribe(EVENT_GLOBAL, self._on_global_event)
        self._event_bus.subscribe(EVENT_TRADE_CHAT, self._on_trade_chat)
        self._event_bus.subscribe(EVENT_INGESTED_GLOBAL, self._on_ingested_global)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_live(self, _data=None):
        """Enable notification processing (call after chat-log catchup)."""
        self._live = True

    def get_notifications(self, limit: int = 50) -> list[Notification]:
        with self._lock:
            return list(self._notifications)[:limit]

    def get_unread_count(self) -> int:
        with self._lock:
            return sum(1 for n in self._notifications if not n.read)

    def mark_read(self, notification_id: str):
        with self._lock:
            for n in self._notifications:
                if n.id == notification_id:
                    n.read = True
                    break

    def mark_all_read(self):
        with self._lock:
            for n in self._notifications:
                n.read = True

    def on_notification(self, callback):
        """Register callback(notification) for new notifications."""
        self._on_notification_callbacks.append(callback)

    def update_rules(self, rules: list[GlobalNotificationRule]):
        self._rules_engine.update_rules(rules)

    def update_trade_ignore(self, usernames: list[str]):
        self._trade_ignore = set(u.lower() for u in usernames)

    def update_stream_exclude(self, names: list[str]):
        self._stream_exclude = set(n.lower() for n in names)

    def reload_config(self):
        """Re-read rules and trade settings from config."""
        self._rules_engine.update_rules(self._load_rules())
        self._trade_ignore = set(
            u.lower()
            for u in getattr(self._config, "trade_chat_ignore_list", [])
        )
        self._stream_exclude = set(
            n.lower()
            for n in getattr(self._config, "stream_exclude_list", [])
        )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _global_fp(self, event) -> tuple:
        """Fingerprint for dedup between local and server globals."""
        return (
            event.global_type.value,
            event.player_name.lower(),
            event.target_name.lower(),
            round(event.value, 2),
        )

    def _record_fp(self, fp: tuple) -> None:
        """Record a global fingerprint, pruning if necessary."""
        self._recent_global_fps[fp] = None
        if len(self._recent_global_fps) > _MAX_GLOBAL_FPS:
            self._recent_global_fps.popitem(last=False)

    def _on_global_event(self, event):
        if not self._live:
            return

        # Record fingerprint so the server echo is suppressed
        self._record_fp(self._global_fp(event))

        should_notify, _rule = self._rules_engine.evaluate(event)
        if not should_notify:
            return

        # Build notification
        if event.is_ath:
            title = f"ATH! {event.player_name}"
            prio = "high"
        elif event.is_hof:
            title = f"HoF: {event.player_name}"
            prio = "high"
        else:
            title = f"Global: {event.player_name}"
            prio = "normal"

        body = f"{event.target_name} — {event.value:.2f} {event.value_unit}"

        self._create_notification(
            source=SOURCE_GLOBAL,
            title=title,
            body=body,
            priority=prio,
            metadata={
                "global_type": event.global_type.value,
                "player": event.player_name,
                "target": event.target_name,
                "value": event.value,
            },
        )

    def _on_ingested_global(self, data):
        """Handle a global event received from the ingestion server (dict, not dataclass)."""
        if not self._live:
            return

        # Create a lightweight object for the rules engine
        class _ServerGlobal:
            pass

        event = _ServerGlobal()
        event.global_type = type("GT", (), {"value": data.get("type", "")})()
        event.player_name = data.get("player", "")
        event.target_name = data.get("target", "")
        event.value = float(data.get("value", 0))
        event.value_unit = data.get("unit", "PED")
        event.is_hof = data.get("hof", False)
        event.is_ath = data.get("ath", False)
        event.location = data.get("location")

        # Skip if already seen from local chat log
        fp = self._global_fp(event)
        if fp in self._recent_global_fps:
            return
        self._record_fp(fp)

        should_notify, _rule = self._rules_engine.evaluate(event)
        if not should_notify:
            return

        if event.is_ath:
            title = f"ATH! {event.player_name}"
            prio = "high"
        elif event.is_hof:
            title = f"HoF: {event.player_name}"
            prio = "high"
        else:
            title = f"Global: {event.player_name}"
            prio = "normal"

        body = f"{event.target_name} — {event.value:.2f} {event.value_unit}"

        self._create_notification(
            source=SOURCE_GLOBAL,
            title=title,
            body=body,
            priority=prio,
            metadata={
                "global_type": data.get("type", ""),
                "player": event.player_name,
                "target": event.target_name,
                "value": event.value,
                "from_server": True,
            },
        )

    def _on_trade_chat(self, msg):
        if not self._live:
            return
        if not getattr(self._config, "trade_chat_notifications_enabled", False):
            return
        if msg.username.lower() in self._trade_ignore:
            return

        items = _BRACKET_RE.findall(msg.message)
        if not items:
            return

        cooldown_secs = getattr(
            self._config, "trade_chat_cooldown_seconds", 300
        )
        now = datetime.now()

        for item in items:
            # Skip waypoint patterns
            if "," in item and item.strip().endswith("Waypoint"):
                continue
            key = (msg.username.lower(), item.lower())
            last = self._trade_cooldowns.get(key)
            if last and (now - last).total_seconds() < cooldown_secs:
                continue
            self._trade_cooldowns[key] = now
            self._create_notification(
                source=SOURCE_TRADE_CHAT,
                title=f"Trade: {msg.username}",
                body=f"[{item}] in {msg.channel}",
                priority="low",
                metadata={
                    "username": msg.username,
                    "item": item,
                    "channel": msg.channel,
                },
            )

    # ------------------------------------------------------------------
    # Server notifications
    # ------------------------------------------------------------------

    def poll_server_notifications(self):
        """Fetch new notifications from Nexus API. Call from background thread."""
        if not self._nexus_client:
            return
        try:
            data = self._nexus_client.get_notifications()
            if not data:
                return
            rows = data.get("rows", [])
            if not self._server_notif_initialized:
                # First poll: seed seen IDs without creating notifications
                self._seen_server_ids = {
                    row.get("id") for row in rows if row.get("id") is not None
                }
                self._server_notif_initialized = True
                return
            for row in rows:
                sid = row.get("id")
                if sid in self._seen_server_ids:
                    continue
                self._seen_server_ids.add(sid)
                self._create_notification(
                    source=SOURCE_NEXUS,
                    title=row.get("type", "Notification"),
                    body=row.get("message", ""),
                    priority="normal",
                    metadata={"server_id": sid},
                    server_id=sid,
                )
        except Exception as e:
            log.debug("Server notification poll failed: %s", e)

    # ------------------------------------------------------------------
    # Stream notifications
    # ------------------------------------------------------------------

    def poll_streams(self):
        """Check for newly live streams. Call from background thread."""
        if not getattr(self._config, "stream_notifications_enabled", True):
            return
        if not self._nexus_client:
            return
        try:
            creators = self._nexus_client.get_streams()
            if creators is None:
                return

            now_live: set[int] = set()
            for c in creators:
                if not c.get("is_live"):
                    continue
                cid = c.get("id")
                if cid is not None:
                    now_live.add(cid)

            if not self._streams_initialized:
                # First poll: populate known-live without notifying
                self._known_live = now_live
                self._streams_initialized = True
                return

            # Detect newly live streams
            for c in creators:
                cid = c.get("id")
                if cid is None or not c.get("is_live"):
                    continue
                if cid in self._known_live:
                    continue
                # Check exclude list
                name = c.get("name", "")
                if name.lower() in self._stream_exclude:
                    continue

                platform = c.get("platform", "")
                title = c.get("stream_title") or ""
                game = c.get("game_name") or ""
                body = f"{title} — {game}" if game else title

                self._create_notification(
                    source=SOURCE_STREAM,
                    title=f"{name} is live on {platform}",
                    body=body,
                    priority="normal",
                    metadata={
                        "creator_id": cid,
                        "name": name,
                        "platform": platform,
                        "channel_url": c.get("channel_url", ""),
                        "viewer_count": c.get("viewer_count", 0),
                    },
                )

            # Update known-live set
            self._known_live = now_live

        except Exception as e:
            log.debug("Stream poll failed: %s", e)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _create_notification(
        self, *, source, title, body, priority, metadata=None, server_id=None
    ):
        notif = Notification(
            id=str(uuid.uuid4()),
            source=source,
            title=title,
            body=body,
            timestamp=datetime.now(),
            priority=priority,
            metadata=metadata or {},
            server_id=server_id,
        )
        with self._lock:
            self._notifications.appendleft(notif)

        for cb in self._on_notification_callbacks:
            try:
                cb(notif)
            except Exception as e:
                log.error("Notification callback error: %s", e)

    def _load_rules(self) -> list[GlobalNotificationRule]:
        raw = getattr(self._config, "notification_rules", [])
        rules = []
        for r in raw:
            try:
                rules.append(GlobalNotificationRule.from_dict(r))
            except Exception:
                pass
        return rules

    def cleanup(self):
        """Unsubscribe from EventBus."""
        self._event_bus.unsubscribe(EVENT_GLOBAL, self._on_global_event)
        self._event_bus.unsubscribe(EVENT_TRADE_CHAT, self._on_trade_chat)
        self._event_bus.unsubscribe(EVENT_INGESTED_GLOBAL, self._on_ingested_global)
