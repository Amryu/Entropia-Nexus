"""Hunt tracker — subscribes to EventBus events and drives encounter management."""

import json
import math
import threading
import uuid
from datetime import datetime, timedelta

from ..core.constants import (
    EVENT_CATCHUP_COMPLETE,
    EVENT_COMBAT, EVENT_GLOBAL, EVENT_LOOT_GROUP, EVENT_MOB_TARGET_CHANGED,
    EVENT_ACTIVE_TOOL_CHANGED, EVENT_HUNT_SESSION_STARTED,
    EVENT_HUNT_SESSION_STOPPED, EVENT_HUNT_ENCOUNTER_STARTED,
    EVENT_HUNT_ENCOUNTER_ENDED, EVENT_HUNT_SESSION_UPDATED,
    EVENT_HUNT_STARTED, EVENT_HUNT_ENDED, EVENT_HUNT_SPLIT,
    EVENT_HUNT_END_REQUESTED, EVENT_SESSION_AUTO_TIMEOUT,
    EVENT_LOOT_BLACKLIST_CHANGED,
    EVENT_ACTIVE_LOADOUT_CHANGED, EVENT_SESSION_LOADOUT_UPDATED,
    EVENT_PLAYER_DEATH, EVENT_PLAYER_REVIVED, EVENT_OPEN_ENCOUNTER_UPDATED,
)
from ..core.logger import get_logger
from .encounter_manager import EncounterManager
from .entity_resolver import EntityResolver
from .hunt_detector import HuntDetector
from .loadout_manager import SessionLoadoutManager
from .loot_filter import LootFilter
from .ocr_state import OCRStateTracker
from .running_stats import SessionRunningStats
from .session import (
    EncounterLootItem, Hunt, HuntSession, MobEncounter, SessionLoadoutEntry,
)
from .tool_inference import ToolInferenceEngine

log = get_logger("Hunt")


# ---------------------------------------------------------------------------
# DB row → dataclass helpers (used by session restore)
# ---------------------------------------------------------------------------

def _encounter_from_row(row: dict) -> MobEncounter:
    """Reconstruct a MobEncounter from a DB row dict."""
    merged_from_raw = row.get("merged_from")
    merged_from = json.loads(merged_from_raw) if merged_from_raw else []

    return MobEncounter(
        id=row["id"], session_id=row["session_id"],
        mob_name=row["mob_name"], mob_name_source=row["mob_name_source"],
        start_time=datetime.fromisoformat(row["start_time"]),
        end_time=datetime.fromisoformat(row["end_time"]) if row.get("end_time") else None,
        hunt_id=row.get("hunt_id"),
        damage_dealt=row.get("damage_dealt", 0),
        damage_taken=row.get("damage_taken", 0),
        heals_received=row.get("heals_received", 0),
        loot_total_ped=row.get("loot_total_ped", 0),
        shots_fired=row.get("shots_fired", 0),
        critical_hits=row.get("critical_hits", 0),
        cost=row.get("cost", 0),
        confidence=row.get("confidence", 1.0),
        player_avoids=row.get("player_avoids", 0),
        target_avoids=row.get("target_avoids", 0),
        mob_misses=row.get("mob_misses", 0),
        deflects=row.get("deflects", 0),
        blocks=row.get("blocks", 0),
        outcome=row.get("outcome", "kill"),
        death_count=row.get("death_count", 0),
        killed_by_mob=row.get("killed_by_mob"),
        is_open_ended=bool(row.get("is_open_ended", 0)),
        merged_into=row.get("merged_into"),
        merged_from=merged_from,
    )


def _hunt_from_row(row: dict) -> Hunt:
    """Reconstruct a Hunt from a DB row dict."""
    return Hunt(
        id=row["id"], session_id=row["session_id"],
        start_time=datetime.fromisoformat(row["start_time"]),
        end_time=datetime.fromisoformat(row["end_time"]) if row.get("end_time") else None,
        primary_mob=row.get("primary_mob"),
        location_label=row.get("location_label"),
    )


def _loadout_entry_from_row(row: dict) -> SessionLoadoutEntry:
    """Reconstruct a SessionLoadoutEntry from a DB row dict."""
    return SessionLoadoutEntry(
        id=row["id"], session_id=row["session_id"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        loadout_data=json.loads(row.get("loadout_data", "{}")),
        weapon_name=row.get("weapon_name"),
        cost_per_shot=row.get("cost_per_shot", 0),
        damage_min=row.get("damage_min", 0),
        damage_max=row.get("damage_max", 0),
        crit_damage=row.get("crit_damage", 1.0),
        source=row.get("source", "snapshot"),
    )


class HuntTracker:
    """Subscribes to EventBus events and manages hunt sessions.

    Listens for:
    - Combat events (damage dealt/received, evades, dodges, heals)
    - Loot groups
    - Mob target changes (from OCR)
    - Tool changes (from OCR)
    - Session start/stop commands

    Enhanced features:
    - Automatic hunt detection (splits by mob type changes, not mixed spawns)
    - Tool inference from damage values using loadout weapon signatures
    - Retroactive event enrichment when tool info arrives late
    - Session auto-timeout after configurable inactivity period
    """

    TIMEOUT_CHECK_INTERVAL = 1.0  # seconds

    def __init__(self, config, event_bus, db, data_client=None):
        self._config = config
        self._event_bus = event_bus
        self._db = db
        self._data_client = data_client
        self._session: HuntSession | None = None
        self._manager: EncounterManager | None = None
        self._hunt_detector: HuntDetector | None = None
        self._tool_inference: ToolInferenceEngine = ToolInferenceEngine()
        self._loadout_mgr = SessionLoadoutManager(config, db, data_client, self._tool_inference)
        self._loot_filter: LootFilter = LootFilter(config, data_client)
        self._entity_resolver: EntityResolver = EntityResolver(data_client)
        self._ocr_state: OCRStateTracker = OCRStateTracker(event_bus)
        self._running_stats: SessionRunningStats | None = None
        self._timeout_timer: threading.Timer | None = None
        self._persisted_encounter_ids: set[str] = set()
        self._open_encounters: list[MobEncounter] = []  # Unresolved death/timeout encounters
        self._active = False
        self._live = False  # True after chat log catchup completes
        self._last_activity_time: datetime | None = None
        self._auto_timeout = timedelta(milliseconds=config.session_auto_timeout_ms)

        # Subscribe to events
        event_bus.subscribe(EVENT_CATCHUP_COMPLETE, self._on_catchup_complete)
        event_bus.subscribe(EVENT_HUNT_SESSION_STARTED, self._on_session_start)
        event_bus.subscribe(EVENT_HUNT_SESSION_STOPPED, self._on_session_stop)
        event_bus.subscribe(EVENT_COMBAT, self._on_combat)
        event_bus.subscribe(EVENT_LOOT_GROUP, self._on_loot)
        event_bus.subscribe(EVENT_MOB_TARGET_CHANGED, self._on_mob_changed)
        event_bus.subscribe(EVENT_ACTIVE_TOOL_CHANGED, self._on_tool_changed)
        event_bus.subscribe(EVENT_HUNT_END_REQUESTED, self._on_hunt_end_requested)
        event_bus.subscribe(EVENT_GLOBAL, self._on_global)
        event_bus.subscribe(EVENT_PLAYER_DEATH, self._on_player_death)
        event_bus.subscribe(EVENT_PLAYER_REVIVED, self._on_player_revived)
        event_bus.subscribe(EVENT_LOOT_BLACKLIST_CHANGED, self._on_blacklist_changed)
        event_bus.subscribe(EVENT_ACTIVE_LOADOUT_CHANGED, self._on_active_loadout_changed)

    GLOBAL_CORRELATION_WINDOW = timedelta(seconds=10)

    @property
    def tool_inference(self) -> ToolInferenceEngine:
        """Expose tool inference for external signature loading."""
        return self._tool_inference

    def _on_catchup_complete(self, _data):
        """Chat log watcher finished replaying old lines — safe to track now."""
        if self._live:
            return  # Already live; ignore reparse completions
        self._live = True
        self._try_restore_session()
        # Pre-warm heavy subsystems in background threads so they're
        # ready before the next session starts, without blocking the watcher.
        self._loadout_mgr.warmup()
        self._loot_filter.warmup()
        self._entity_resolver.warmup()
        log.info("Catchup complete, hunt tracking active")

    def _try_restore_session(self):
        """Check DB for an incomplete session and restore it."""
        row = self._db.get_incomplete_session()
        if not row:
            return

        session_id = row["id"]
        log.info("Restoring incomplete session: %s", session_id)

        # 1. Build HuntSession
        session = HuntSession(
            id=session_id,
            start_time=datetime.fromisoformat(row["start_time"]),
            loadout_id=row.get("loadout_id"),
            primary_mob=row.get("primary_mob"),
            notes=row.get("notes"),
        )

        # 2. Load completed encounters (end_time IS NOT NULL)
        enc_rows = self._db.get_session_encounters(session_id)
        for er in enc_rows:
            if not er.get("end_time"):
                # Skip partial encounters (mid-combat on crash)
                self._persisted_encounter_ids.add(er["id"])
                continue
            enc = _encounter_from_row(er)
            # Load loot items for proper effective_loot_ped calculation
            loot_rows = self._db.get_encounter_loot_items(enc.id)
            for lr in loot_rows:
                enc.loot_items.append(EncounterLootItem(
                    item_name=lr["item_name"],
                    quantity=lr["quantity"],
                    value_ped=lr["value_ped"],
                    is_blacklisted=bool(lr.get("is_blacklisted", 0)),
                    is_refining_output=bool(lr.get("is_refining_output", 0)),
                    is_in_loot_table=bool(lr.get("is_in_loot_table", 1)),
                ))
            session.encounters.append(enc)
            self._persisted_encounter_ids.add(enc.id)

        # 3. Load hunts and assign encounters
        hunt_rows = self._db.get_session_hunts(session_id)
        for hr in hunt_rows:
            hunt = _hunt_from_row(hr)
            for enc in session.encounters:
                if enc.hunt_id == hunt.id:
                    hunt.encounters.append(enc)
            session.hunts.append(hunt)

        # 4. Load loadout entries
        loadout_rows = self._db.get_session_loadouts(session_id)
        for lr in loadout_rows:
            session.loadout_entries.append(_loadout_entry_from_row(lr))

        # 5. Set up internal state
        self._session = session
        self._manager = EncounterManager(self._config, self._session)
        self._hunt_detector = HuntDetector(self._config)
        self._running_stats = SessionRunningStats()
        self._tool_inference.reset_timeline()
        self._loot_filter.invalidate_mob_cache()
        self._active = True
        self._last_activity_time = datetime.utcnow()

        # Rebuild running stats from restored encounters
        for enc in session.encounters:
            self._running_stats.on_encounter_finalized(enc)
            # Strip loot items from restored encounters (already in DB)
            enc.loot_items = []

        # 5b. Restore open-ended encounters
        self._open_encounters = [
            enc for enc in session.encounters if enc.is_open_ended
        ]

        # 6. Restore loadout manager + weapon signatures
        self._loadout_mgr.restore_session(session)

        # 7. Seed hunt detector with the last hunt's state
        if session.hunts:
            last_hunt = session.hunts[-1]
            self._hunt_detector._current_hunt = last_hunt
            if last_hunt.primary_mob:
                self._hunt_detector._mob_tracker.set_dominant(last_hunt.primary_mob)
            # Seed recent kills from last hunt's encounters
            recent = last_hunt.encounters[-self._config.hunt_split_mob_threshold:]
            for enc in recent:
                self._hunt_detector._mob_tracker._recent_kills.append(enc.mob_name)

        # 8. Start timeout checker
        self._start_timeout_checker()

        # 9. Publish events so UI rebuilds
        self._event_bus.publish(EVENT_HUNT_SESSION_STARTED, {
            "session_id": session.id,
        })
        for enc in session.encounters:
            self._event_bus.publish(EVENT_HUNT_ENCOUNTER_ENDED, enc.to_dict())
        self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED, session.to_summary())

        log.info("Session restored: %d encounters, %d hunts",
                 len(session.encounters), len(session.hunts))

    def stop(self):
        """Clean shutdown."""
        if self._session:
            self._on_session_stop({"session_id": self._session.id})
        self._cancel_timeout()

    def _init_session(self, session_id: str | None = None,
                      primary_mob: str | None = None,
                      loadout_id: str | None = None):
        """Initialize a new hunt session. No-ops if already active."""
        if self._active:
            return

        session_id = session_id or str(uuid.uuid4())
        now = datetime.utcnow()

        self._session = HuntSession(
            id=session_id,
            start_time=now,
            loadout_id=loadout_id,
            primary_mob=primary_mob,
        )
        self._manager = EncounterManager(self._config, self._session)
        self._hunt_detector = HuntDetector(self._config)
        self._running_stats = SessionRunningStats()
        self._loot_filter.invalidate_mob_cache()
        self._tool_inference.reset_timeline()
        self._active = True  # BEFORE any publish to prevent re-entrance
        self._last_activity_time = now

        # Persist session start
        self._db.insert_hunt_session(
            session_id, now.isoformat(), loadout_id, primary_mob
        )

        # Snapshot active loadout for cost tracking
        self._loadout_mgr.start_session(self._session)

        # Set expected DPP from loadout if available
        if self._running_stats:
            self._running_stats.set_expected_dpp(self._loadout_mgr.expected_dpp)

        self._start_timeout_checker()
        log.info("Session started: %s", session_id)

    def _on_session_start(self, data):
        """Handle external session start request."""
        if not self._live or not isinstance(data, dict) or self._active:
            return
        self._init_session(
            session_id=data.get("session_id"),
            primary_mob=data.get("primary_mob"),
            loadout_id=data.get("loadout_id"),
        )

    def _on_session_stop(self, data):
        if not self._session:
            return

        now = datetime.utcnow()

        # Close any active encounter
        if self._manager:
            ended = self._manager.force_close()
            if ended:
                self._persist_encounter(ended)
                self._event_bus.publish(EVENT_HUNT_ENCOUNTER_ENDED, ended.to_dict())

        # Close current hunt
        if self._hunt_detector:
            hunt = self._hunt_detector.end_current_hunt(now)
            if hunt:
                self._db.end_hunt(hunt.id, now.isoformat(), hunt.total_cost)
                self._event_bus.publish(EVENT_HUNT_ENDED, hunt.to_dict())
            self._hunt_detector.reset()

        self._loadout_mgr.end_session()

        # Auto-abandon remaining open encounters on session end
        for enc in list(self._open_encounters):
            enc.outcome = "abandoned"
            enc.is_open_ended = False
            self._persist_encounter(enc)
        self._open_encounters.clear()

        self._session.end_time = now
        self._db.end_hunt_session(self._session.id, now.isoformat())

        # Publish final summary
        self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED, self._session.to_summary())

        self._cancel_timeout()
        self._active = False
        self._last_activity_time = None
        self._persisted_encounter_ids.clear()
        self._tool_inference.clear()
        log.info("Session ended: %s", self._session.id)
        self._session = None
        self._manager = None
        self._hunt_detector = None
        self._running_stats = None

    def _on_hunt_end_requested(self, data):
        """Manually end the current hunt without ending the session.

        The next encounter will automatically start a new hunt.
        """
        if not self._active or not self._hunt_detector:
            return

        now = datetime.utcnow()

        # Close the active encounter first
        if self._manager:
            ended = self._manager.force_close()
            if ended:
                self._persist_encounter(ended)
                self._event_bus.publish(EVENT_HUNT_ENCOUNTER_ENDED, ended.to_dict())

        # Close the current hunt
        hunt = self._hunt_detector.end_current_hunt(now)
        if hunt:
            self._db.end_hunt(hunt.id, now.isoformat(), hunt.total_cost)
            self._event_bus.publish(EVENT_HUNT_ENDED, hunt.to_dict())
            log.info("Hunt manually ended: %s", hunt.id[:8])

        self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED, self._session.to_summary())

    def _on_combat(self, data):
        if not self._live:
            return

        # Auto-start session on first combat event
        if not self._active:
            self._init_session()
            self._event_bus.publish(EVENT_HUNT_SESSION_STARTED, {
                "session_id": self._session.id,
            })

        if not self._manager:
            return

        raw_type = data.event_type if hasattr(data, 'event_type') else data.get('event_type', '')
        event_type = raw_type.value if hasattr(raw_type, 'value') else str(raw_type)
        amount = data.amount if hasattr(data, 'amount') else data.get('amount', 0)
        timestamp = None
        if hasattr(data, 'timestamp'):
            try:
                timestamp = datetime.fromisoformat(data.timestamp)
            except (ValueError, TypeError):
                pass

        now = timestamp or datetime.utcnow()
        self._last_activity_time = now

        if event_type == "damage_dealt":
            self._handle_damage(amount or 0, False, now)
        elif event_type == "critical_hit":
            self._handle_damage(amount or 0, True, now)
        elif event_type == "damage_received":
            if amount is not None and amount == 0.0:
                self._manager.on_block(timestamp=now)
            else:
                self._manager.on_damage_received(amount or 0, timestamp=now)
        elif event_type == "self_heal":
            self._manager.on_heal(amount or 0, timestamp=now)
        elif event_type in ("player_evade", "player_dodge", "player_jam"):
            self._manager.on_player_avoid(timestamp=now)
        elif event_type in ("target_evade", "target_dodge", "target_jam"):
            self._manager.on_target_avoid(timestamp=now)
        elif event_type == "mob_miss":
            self._manager.on_mob_miss(timestamp=now)
        elif event_type == "deflect":
            self._manager.on_deflect(timestamp=now)

        # Notify loadout manager of combat activity
        self._loadout_mgr.on_combat()

        # Publish session update
        self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED, self._session.to_summary())

    def _ensure_encounter_in_db(self, enc):
        """Insert encounter row into DB if not yet persisted (for FK integrity)."""
        if enc.id not in self._persisted_encounter_ids:
            self._db.insert_mob_encounter(
                enc.id, enc.session_id, enc.mob_name,
                enc.mob_name_source, enc.start_time.isoformat(),
            )
            self._persisted_encounter_ids.add(enc.id)

    def _handle_damage(self, amount: float, is_crit: bool, now: datetime):
        """Handle damage dealt with tool inference and cost tracking."""
        self._manager.on_damage_dealt(amount, is_crit=is_crit, timestamp=now)

        enc = self._manager.current_encounter
        if not enc:
            return

        # Resolve mob ID if not yet set
        if enc.mob_id is None and enc.mob_name != "Unknown":
            enc.mob_id = self._entity_resolver.resolve_mob(enc.mob_name)

        self._ensure_encounter_in_db(enc)

        # Tool inference: try to infer weapon from damage value
        tool_name = self._manager._current_tool
        tool_source = "ocr" if tool_name else None
        cost_per_shot = 0.0

        if not tool_name and self._tool_inference.has_signatures:
            inferred, confidence, cost = self._tool_inference.infer_tool(amount, is_crit=is_crit)
            if inferred:
                tool_name = inferred
                tool_source = "inferred"
                cost_per_shot = cost

        # Get cost from signature if we know the tool
        if tool_name and not cost_per_shot:
            cost_per_shot = self._tool_inference.get_cost_per_shot(tool_name)

        # Accumulate cost on encounter
        if cost_per_shot > 0:
            enc.cost += cost_per_shot

        # Record detailed combat event
        event = self._tool_inference.create_event(
            encounter_id=enc.id,
            timestamp=now,
            event_type="critical_hit" if is_crit else "damage_dealt",
            amount=amount,
            tool_name=tool_name,
            tool_source=tool_source,
            confidence=1.0 if tool_source == "ocr" else 0.0,
        )

        # Buffer for retroactive enrichment (per-encounter, no time trim)
        self._tool_inference.buffer_event(
            enc.id, event.id, now, amount, is_crit, tool_name, tool_source,
        )

        if not tool_name:
            # Track for auto-detection of unknown weapons
            self._loadout_mgr.on_unmatched_damage(amount)

        # Persist combat event detail
        self._db.insert_combat_event_detail(
            event.id, event.encounter_id, event.timestamp.isoformat(),
            event.event_type, event.amount,
            event.tool_name, event.tool_source, event.inferred_confidence,
        )

    def _on_loot(self, data):
        if not self._live or not self._active or not self._manager:
            return

        # Get current mob name for loot table validation
        mob_name = None
        if self._manager.current_encounter:
            mob_name = self._manager.current_encounter.mob_name
        elif self._session and self._session.primary_mob:
            mob_name = self._session.primary_mob

        # Classify each item through the loot filter.
        # All items are stored (for retroactive blacklist changes);
        # raw total is used on the encounter — filtering happens at display time.
        items = data.items if hasattr(data, 'items') else []
        classified = []
        raw_total = 0.0

        for item in items:
            item_name = item.item_name if hasattr(item, 'item_name') else item.get('item_name', '')
            quantity = item.quantity if hasattr(item, 'quantity') else item.get('quantity', 0)
            value_ped = item.value_ped if hasattr(item, 'value_ped') else item.get('value_ped', 0)

            classification = self._loot_filter.classify(item_name, mob_name)

            loot_entry = EncounterLootItem(
                item_name=item_name,
                quantity=quantity,
                value_ped=value_ped,
                item_id=self._entity_resolver.resolve_item(item_name),
                is_blacklisted=classification["is_blacklisted"],
                is_refining_output=classification["is_refining_output"],
                is_in_loot_table=classification["is_in_loot_table"],
            )
            classified.append(loot_entry)
            raw_total += value_ped

        self._last_activity_time = datetime.utcnow()
        self._manager.on_loot_group(raw_total, classified)
        self._loadout_mgr.on_loot()
        self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED, self._session.to_summary())

    def _on_mob_changed(self, data):
        if not self._live or not self._active or not self._manager:
            return

        mob_name = data.get("mob_name", "") if isinstance(data, dict) else str(data)
        confidence = data.get("confidence", 1.0) if isinstance(data, dict) else 1.0
        source = data.get("source", "ocr") if isinstance(data, dict) else "ocr"

        self._last_activity_time = datetime.utcnow()

        ended = self._manager.on_mob_name_detected(mob_name, confidence, source)
        if ended:
            self._persist_encounter(ended)
            self._event_bus.publish(EVENT_HUNT_ENCOUNTER_ENDED, ended.to_dict())

        self._event_bus.publish(EVENT_HUNT_ENCOUNTER_STARTED, {
            "mob_name": mob_name,
            "source": source,
        })

    def _on_tool_changed(self, data):
        if not self._live or not self._active or not self._manager:
            return

        tool_name = data.get("tool_name", "") if isinstance(data, dict) else str(data)
        self._manager.set_current_tool(tool_name)

        # Record on timeline for retroactive attribution
        now = datetime.utcnow()
        self._tool_inference.on_tool_detected(tool_name, now)

        # Retroactive enrichment — re-attribute unattributed events in current encounter
        enc = self._manager.current_encounter
        if enc:
            enriched = self._tool_inference.enrich_encounter(enc.id)
            for event_id, new_tool, new_source, new_confidence in enriched:
                self._db.update_combat_event_tool(
                    event_id, new_tool, new_source, new_confidence
                )
            if enriched:
                self._rebuild_encounter_tool_stats(enc)

    def _on_global(self, data):
        """Correlate global events with recent encounters."""
        if not self._live or not self._active or not self._session:
            return

        # Only correlate kill/team kill globals
        global_type = data.global_type if hasattr(data, 'global_type') else None
        if global_type and global_type.value not in ("kill", "team_kill"):
            return

        target = data.target_name if hasattr(data, 'target_name') else ""
        is_hof = data.is_hof if hasattr(data, 'is_hof') else False
        is_ath = data.is_ath if hasattr(data, 'is_ath') else False
        value = data.value if hasattr(data, 'value') else 0
        timestamp = data.timestamp if hasattr(data, 'timestamp') else datetime.utcnow()

        now = datetime.utcnow()
        match = None

        # Check current encounter (in CLOSING state after loot)
        if self._manager and self._manager.current_encounter:
            enc = self._manager.current_encounter
            if enc.loot_total_ped > 0 and math.floor(enc.loot_total_ped) == value:
                if target.lower() in enc.mob_name.lower() or enc.mob_name.lower() in target.lower():
                    match = enc

        # Check last completed encounter (within time window)
        if not match and self._session.encounters:
            enc = self._session.encounters[-1]
            if enc.end_time and (now - enc.end_time) < self.GLOBAL_CORRELATION_WINDOW:
                if enc.loot_total_ped > 0 and math.floor(enc.loot_total_ped) == value:
                    if target.lower() in enc.mob_name.lower() or enc.mob_name.lower() in target.lower():
                        match = enc

        if match:
            match.is_global = True
            match.is_hof = is_hof or is_ath
            self._db.update_mob_encounter(
                match.id, is_global=1, is_hof=1 if match.is_hof else 0
            )
            self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED, self._session.to_summary())
            log.info("Global correlated with encounter %s (mob: %s, value: %s PED)",
                     match.id[:8], match.mob_name, value)

    def _on_player_death(self, data):
        """Handle player death — close encounter immediately, mark as open-ended."""
        if not self._live or not self._active or not self._manager:
            return

        mob_name = data.mob_name if hasattr(data, 'mob_name') else ""
        timestamp = data.timestamp if hasattr(data, 'timestamp') else None

        ended = self._manager.on_death(mob_name, timestamp=timestamp)
        if ended:
            # Auto-merge: if enabled and previous open encounter is same mob, merge them
            if self._config.auto_merge_deaths and self._open_encounters:
                last_open = self._open_encounters[-1]
                if (last_open.mob_name == ended.mob_name
                        or last_open.mob_name == "Unknown"
                        or ended.mob_name == "Unknown"):
                    self._merge_encounter_into(ended, last_open)
                    log.info("Auto-merged death encounter into open encounter %s",
                             last_open.id[:8])
                    self._persist_encounter(ended)
                    self._event_bus.publish(EVENT_HUNT_ENCOUNTER_ENDED, ended.to_dict())
                    self._persist_encounter(last_open)
                    self._event_bus.publish(EVENT_OPEN_ENCOUNTER_UPDATED,
                                            self._get_open_encounters_data())
                    self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED,
                                            self._session.to_summary())
                    return

            self._open_encounters.append(ended)
            self._persist_encounter(ended)
            self._event_bus.publish(EVENT_HUNT_ENCOUNTER_ENDED, ended.to_dict())
            self._event_bus.publish(EVENT_OPEN_ENCOUNTER_UPDATED,
                                    self._get_open_encounters_data())
            self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED,
                                    self._session.to_summary())
            log.info("Player died to %s — encounter %s is open-ended (cost: %.2f PED)",
                     mob_name, ended.id[:8], ended.cost)

    def _on_player_revived(self, data):
        """Handle player revival — informational only, no state change."""
        if not self._live:
            return
        log.info("Player revived")

    # -- Open encounter management -----------------------------------------

    @property
    def open_encounters(self) -> list[MobEncounter]:
        """Return list of unresolved open-ended encounters."""
        return list(self._open_encounters)

    def _get_open_encounters_data(self) -> list[dict]:
        """Build serializable list of open encounters for UI."""
        return [
            {
                "id": enc.id,
                "mob_name": enc.mob_name,
                "cost": enc.cost,
                "damage_dealt": enc.damage_dealt,
                "death_count": enc.death_count,
                "start_time": enc.start_time.isoformat(),
                "end_time": enc.end_time.isoformat() if enc.end_time else None,
            }
            for enc in self._open_encounters
        ]

    def merge_open_encounter(self, open_encounter_id: str,
                              target_encounter_id: str) -> bool:
        """Merge an open encounter's stats into a target encounter.

        Returns True if the merge succeeded.
        Can merge into completed encounters (kill) or other open encounters.
        """
        open_enc = self._find_open_encounter(open_encounter_id)
        if not open_enc:
            log.warning("Merge failed: open encounter %s not found", open_encounter_id)
            return False

        target_enc = self._find_encounter(target_encounter_id)
        if not target_enc:
            log.warning("Merge failed: target encounter %s not found", target_encounter_id)
            return False

        # Validate merge compatibility (same mob or either is Unknown)
        if not self._can_merge(open_enc, target_enc):
            log.warning("Merge failed: incompatible mobs (%s → %s)",
                        open_enc.mob_name, target_enc.mob_name)
            return False

        self._merge_encounter_into(open_enc, target_enc)

        # Persist changes
        self._persist_encounter(target_enc)
        self._persist_encounter(open_enc)

        self._event_bus.publish(EVENT_HUNT_ENCOUNTER_ENDED, target_enc.to_dict())
        self._event_bus.publish(EVENT_OPEN_ENCOUNTER_UPDATED,
                                self._get_open_encounters_data())
        self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED,
                                self._session.to_summary())

        log.info("Merged open encounter %s into %s", open_enc.id[:8], target_enc.id[:8])
        return True

    def abandon_open_encounter(self, open_encounter_id: str) -> bool:
        """Mark an open encounter as abandoned (standalone loss)."""
        open_enc = self._find_open_encounter(open_encounter_id)
        if not open_enc:
            return False

        open_enc.outcome = "abandoned"
        open_enc.is_open_ended = False
        self._open_encounters.remove(open_enc)

        self._persist_encounter(open_enc)
        self._event_bus.publish(EVENT_HUNT_ENCOUNTER_ENDED, open_enc.to_dict())
        self._event_bus.publish(EVENT_OPEN_ENCOUNTER_UPDATED,
                                self._get_open_encounters_data())
        self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED,
                                self._session.to_summary())

        log.info("Abandoned open encounter %s (cost: %.2f PED)",
                 open_enc.id[:8], open_enc.cost)
        return True

    def reopen_encounter(self, encounter_id: str) -> bool:
        """Re-open an abandoned encounter back to open-ended status."""
        enc = self._find_encounter(encounter_id)
        if not enc or enc.outcome != "abandoned":
            return False

        enc.outcome = "death" if enc.death_count > 0 else "timeout"
        enc.is_open_ended = True
        self._open_encounters.append(enc)

        self._persist_encounter(enc)
        self._event_bus.publish(EVENT_OPEN_ENCOUNTER_UPDATED,
                                self._get_open_encounters_data())
        log.info("Re-opened encounter %s as open-ended", enc.id[:8])
        return True

    def split_merged_encounter(self, target_encounter_id: str,
                                source_encounter_id: str) -> bool:
        """Undo a merge — restore the source encounter and remove its stats from target.

        Returns True if the split succeeded.
        """
        target_enc = self._find_encounter(target_encounter_id)
        if not target_enc or source_encounter_id not in target_enc.merged_from:
            log.warning("Split failed: %s not found in merged_from of %s",
                        source_encounter_id, target_encounter_id)
            return False

        source_enc = self._find_encounter(source_encounter_id)
        if not source_enc:
            log.warning("Split failed: source encounter %s not found", source_encounter_id)
            return False

        # Reverse the merge
        target_enc.damage_dealt -= source_enc.damage_dealt
        target_enc.damage_taken -= source_enc.damage_taken
        target_enc.shots_fired -= source_enc.shots_fired
        target_enc.cost -= source_enc.cost
        target_enc.death_count -= source_enc.death_count
        target_enc.heals_received -= source_enc.heals_received
        target_enc.merged_from.remove(source_encounter_id)

        # Restore source encounter
        source_enc.outcome = "death" if source_enc.death_count > 0 else "timeout"
        source_enc.is_open_ended = True
        source_enc.merged_into = None
        self._open_encounters.append(source_enc)

        # Persist
        self._persist_encounter(target_enc)
        self._persist_encounter(source_enc)

        self._event_bus.publish(EVENT_HUNT_ENCOUNTER_ENDED, target_enc.to_dict())
        self._event_bus.publish(EVENT_OPEN_ENCOUNTER_UPDATED,
                                self._get_open_encounters_data())
        self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED,
                                self._session.to_summary())

        log.info("Split encounter %s out of %s", source_enc.id[:8], target_enc.id[:8])
        return True

    def _merge_encounter_into(self, source: MobEncounter, target: MobEncounter):
        """Merge source encounter stats into target. Mutates both."""
        target.damage_dealt += source.damage_dealt
        target.damage_taken += source.damage_taken
        target.shots_fired += source.shots_fired
        target.cost += source.cost
        target.death_count += source.death_count
        target.heals_received += source.heals_received
        target.merged_from.append(source.id)

        # Merge tool stats
        for tool_name, src_stats in source.tool_stats.items():
            if tool_name in target.tool_stats:
                ts = target.tool_stats[tool_name]
                ts.shots_fired += src_stats.shots_fired
                ts.damage_dealt += src_stats.damage_dealt
                ts.critical_hits += src_stats.critical_hits
            else:
                from .session import EncounterToolStats
                target.tool_stats[tool_name] = EncounterToolStats(
                    tool_name=tool_name,
                    shots_fired=src_stats.shots_fired,
                    damage_dealt=src_stats.damage_dealt,
                    critical_hits=src_stats.critical_hits,
                )

        # If target mob is Unknown but source has a name, adopt it
        if target.mob_name == "Unknown" and source.mob_name != "Unknown":
            target.mob_name = source.mob_name
            target.mob_name_source = source.mob_name_source

        # Mark source as merged
        source.outcome = "merged"
        source.is_open_ended = False
        source.merged_into = target.id
        if source in self._open_encounters:
            self._open_encounters.remove(source)

    def _can_merge(self, source: MobEncounter, target: MobEncounter) -> bool:
        """Check if two encounters can be merged (same mob or either Unknown)."""
        if source.mob_name == "Unknown" or target.mob_name == "Unknown":
            return True
        return source.mob_name == target.mob_name

    def _find_open_encounter(self, encounter_id: str) -> MobEncounter | None:
        """Find an open encounter by ID."""
        for enc in self._open_encounters:
            if enc.id == encounter_id:
                return enc
        return None

    def _find_encounter(self, encounter_id: str) -> MobEncounter | None:
        """Find any encounter in the session by ID."""
        if not self._session:
            return None
        for enc in self._session.encounters:
            if enc.id == encounter_id:
                return enc
        return None

    def _on_blacklist_changed(self, _data):
        """Reclassify all in-memory loot items when blacklist config changes."""
        if not self._active or not self._session:
            return

        # Reclassify loot items on all completed encounters
        for enc in self._session.encounters:
            self._reclassify_encounter_loot(enc)

        # Reclassify current encounter if any
        if self._manager and self._manager.current_encounter:
            self._reclassify_encounter_loot(self._manager.current_encounter)

        # Also reclassify encounters in hunts (they reference the same objects,
        # but be safe in case of future changes)

        self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED, self._session.to_summary())

    def _on_active_loadout_changed(self, data):
        """Handle loadout changes from the loadout page."""
        loadout = data.get("loadout") if isinstance(data, dict) else None
        weapon_name = data.get("weapon_name") if isinstance(data, dict) else None
        stats = data.get("stats") if isinstance(data, dict) else None
        if loadout:
            self._loadout_mgr.on_active_loadout_changed(loadout, weapon_name, stats)
        if self._active and self._session:
            # Update running stats with expected DPP from loadout
            if self._running_stats:
                self._running_stats.set_expected_dpp(self._loadout_mgr.expected_dpp)
            self._event_bus.publish(EVENT_SESSION_LOADOUT_UPDATED, {
                "session_id": self._session.id,
            })

    def _reclassify_encounter_loot(self, encounter):
        """Re-run loot filter on all items in an encounter."""
        mob_name = encounter.mob_name if encounter.mob_name != "Unknown" else None
        for li in encounter.loot_items:
            c = self._loot_filter.classify(li.item_name, mob_name)
            li.is_blacklisted = c["is_blacklisted"]
            li.is_refining_output = c["is_refining_output"]
            li.is_in_loot_table = c["is_in_loot_table"]

    def _rebuild_encounter_tool_stats(self, enc: MobEncounter):
        """Rebuild tool_stats from the tool_inference event buffer."""
        events = self._tool_inference.get_encounter_events(enc.id)
        if not events:
            return
        enc.tool_stats.clear()
        enc.cost = 0.0
        for ev in events:
            _event_id, _timestamp, amount, is_crit, tool_name, _tool_source = ev
            tool = tool_name or "Unknown"
            if tool not in enc.tool_stats:
                from .session import EncounterToolStats
                enc.tool_stats[tool] = EncounterToolStats(tool_name=tool)
            enc.tool_stats[tool].damage_dealt += amount
            enc.tool_stats[tool].shots_fired += 1
            if is_crit:
                enc.tool_stats[tool].critical_hits += 1
            enc.cost += self._tool_inference.get_cost_per_shot(tool)

    def _persist_encounter(self, encounter):
        """Save a completed encounter and check for hunt boundaries."""
        # Capture OCR supporting data before persisting
        if not self._ocr_state.is_stale("target"):
            encounter.is_shared_loot = self._ocr_state.state.target_is_shared

        # Hunt detection — check if this encounter triggers a split
        if self._hunt_detector:
            if not self._hunt_detector.current_hunt:
                # First encounter — start the first hunt
                hunt = self._hunt_detector.start_hunt(
                    self._session.id, encounter, encounter.start_time
                )
                self._session.hunts.append(hunt)
                self._db.insert_hunt(
                    hunt.id, hunt.session_id, hunt.start_time.isoformat(),
                    hunt.primary_mob
                )
                self._event_bus.publish(EVENT_HUNT_STARTED, hunt.to_dict())
            else:
                boundary = self._hunt_detector.on_encounter_ended(encounter)
                if boundary:
                    # Split: close old hunt, start new one
                    now = encounter.start_time
                    old_hunt = self._hunt_detector.end_current_hunt(now)
                    if old_hunt:
                        self._db.end_hunt(old_hunt.id, now.isoformat(), old_hunt.total_cost)
                        self._event_bus.publish(EVENT_HUNT_ENDED, old_hunt.to_dict())

                    # Start new hunt with this encounter
                    new_hunt = self._hunt_detector.start_hunt(
                        self._session.id, encounter, now
                    )
                    self._session.hunts.append(new_hunt)
                    self._db.insert_hunt(
                        new_hunt.id, new_hunt.session_id,
                        new_hunt.start_time.isoformat(), new_hunt.primary_mob
                    )
                    self._event_bus.publish(EVENT_HUNT_SPLIT, {
                        "reason": boundary.split_reason,
                        "old_mob": old_hunt.primary_mob if old_hunt else None,
                        "new_mob": boundary.new_hunt_mob,
                    })
                    self._event_bus.publish(EVENT_HUNT_STARTED, new_hunt.to_dict())

        # Location-based hunt boundary check (if OCR provides coordinates)
        if self._hunt_detector and not self._ocr_state.is_stale("location"):
            ocr = self._ocr_state.state
            if ocr.lon is not None and ocr.lat is not None:
                loc_boundary = self._hunt_detector._location_tracker.observe(
                    ocr.lon, ocr.lat
                )
                if loc_boundary and self._hunt_detector.current_hunt:
                    now = encounter.start_time
                    old_hunt = self._hunt_detector.end_current_hunt(now)
                    if old_hunt:
                        self._db.end_hunt(old_hunt.id, now.isoformat(), old_hunt.total_cost)
                        self._event_bus.publish(EVENT_HUNT_ENDED, old_hunt.to_dict())
                    new_hunt = self._hunt_detector.start_hunt(
                        self._session.id, encounter, now
                    )
                    self._session.hunts.append(new_hunt)
                    self._db.insert_hunt(
                        new_hunt.id, new_hunt.session_id,
                        new_hunt.start_time.isoformat(), new_hunt.primary_mob
                    )
                    self._event_bus.publish(EVENT_HUNT_SPLIT, {
                        "reason": loc_boundary.split_reason,
                        "old_mob": old_hunt.primary_mob if old_hunt else None,
                        "new_mob": loc_boundary.new_hunt_mob,
                    })
                    self._event_bus.publish(EVENT_HUNT_STARTED, new_hunt.to_dict())

        # Persist the encounter (row may already exist from _ensure_encounter_in_db)
        self._ensure_encounter_in_db(encounter)
        self._db.update_mob_encounter(
            encounter.id,
            hunt_id=encounter.hunt_id,
            end_time=encounter.end_time.isoformat() if encounter.end_time else None,
            mob_id=encounter.mob_id,
            damage_dealt=encounter.damage_dealt,
            damage_taken=encounter.damage_taken,
            heals_received=encounter.heals_received,
            loot_total_ped=encounter.loot_total_ped,
            shots_fired=encounter.shots_fired,
            critical_hits=encounter.critical_hits,
            cost=encounter.cost,
            confidence=encounter.confidence,
            player_avoids=encounter.player_avoids,
            target_avoids=encounter.target_avoids,
            mob_misses=encounter.mob_misses,
            deflects=encounter.deflects,
            blocks=encounter.blocks,
            outcome=encounter.outcome,
            death_count=encounter.death_count,
            killed_by_mob=encounter.killed_by_mob,
            is_open_ended=1 if encounter.is_open_ended else 0,
            is_shared_loot=1 if encounter.is_shared_loot else (0 if encounter.is_shared_loot is not None else None),
            merged_into=encounter.merged_into,
            merged_from=json.dumps(encounter.merged_from) if encounter.merged_from else None,
        )
        for stats in encounter.tool_stats.values():
            self._db.upsert_encounter_tool_stat(
                encounter.id, stats.tool_name,
                shots_delta=stats.shots_fired,
                damage_delta=stats.damage_dealt,
                crits_delta=stats.critical_hits,
            )

        # Persist loot items
        if encounter.loot_items:
            self._db.insert_encounter_loot_items(encounter.id, encounter.loot_items)

        # Update running stats and free memory
        if self._running_stats:
            self._running_stats.on_encounter_finalized(encounter)
        self._tool_inference.clear_encounter(encounter.id)
        # Strip loot items — already persisted to DB.
        # Keep tool_stats (small) since merge operations need them.
        encounter.loot_items = []

    def _start_timeout_checker(self):
        """Start periodic timeout checks for encounter closing and session inactivity."""
        self._cancel_timeout()

        def check():
            if not self._active or not self._manager:
                return

            try:
                # Check encounter timeout
                ended = self._manager.check_timeout()
                if ended:
                    # Timeout from ACTIVE state (no loot) → open-ended
                    if ended.outcome == "timeout" and ended.damage_dealt > 0:
                        ended.is_open_ended = True
                        self._open_encounters.append(ended)
                        self._event_bus.publish(EVENT_OPEN_ENCOUNTER_UPDATED,
                                                self._get_open_encounters_data())
                    self._persist_encounter(ended)
                    self._event_bus.publish(EVENT_HUNT_ENCOUNTER_ENDED, ended.to_dict())
                    self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED,
                                            self._session.to_summary())

                # Check session auto-timeout
                if self._last_activity_time:
                    elapsed = datetime.utcnow() - self._last_activity_time
                    if elapsed > self._auto_timeout:
                        log.info("Session auto-timeout after %s inactivity", elapsed)
                        self._event_bus.publish(EVENT_SESSION_AUTO_TIMEOUT, {
                            "session_id": self._session.id,
                            "inactivity_seconds": elapsed.total_seconds(),
                        })
                        self._on_session_stop({"session_id": self._session.id})
                        return  # Don't reschedule — session is over
            except Exception as e:
                log.error("Timeout checker error: %s", e)

            # Reschedule
            if self._active:
                self._timeout_timer = threading.Timer(
                    self.TIMEOUT_CHECK_INTERVAL, check
                )
                self._timeout_timer.daemon = True
                self._timeout_timer.start()

        self._timeout_timer = threading.Timer(self.TIMEOUT_CHECK_INTERVAL, check)
        self._timeout_timer.daemon = True
        self._timeout_timer.start()

    def _cancel_timeout(self):
        if self._timeout_timer:
            self._timeout_timer.cancel()
            self._timeout_timer = None
