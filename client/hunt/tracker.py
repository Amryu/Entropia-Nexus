"""Hunt tracker — subscribes to EventBus events and drives encounter management."""

import json
import math
import threading
import uuid
from datetime import datetime, timedelta

from ..core.constants import (
    EVENT_CATCHUP_COMPLETE,
    EVENT_COMBAT, EVENT_GLOBAL, EVENT_LOOT_GROUP, EVENT_MOB_TARGET_CHANGED,
    EVENT_ACTIVE_TOOL_CHANGED, EVENT_ENHANCER_BREAK,
    EVENT_HUNT_SESSION_STARTED,
    EVENT_HUNT_SESSION_STOPPED, EVENT_HUNT_ENCOUNTER_STARTED,
    EVENT_HUNT_ENCOUNTER_ENDED, EVENT_HUNT_SESSION_UPDATED,
    EVENT_HUNT_STARTED, EVENT_HUNT_ENDED, EVENT_HUNT_SPLIT,
    EVENT_HUNT_END_REQUESTED, EVENT_SESSION_AUTO_TIMEOUT,
    EVENT_ENHANCER_TIMELINE_EDITED,
    EVENT_GEAR_OVERRIDE_CHANGED,
    EVENT_LOOT_BLACKLIST_CHANGED, EVENT_SESSION_MARKUP_CHANGED,
    EVENT_TOOL_COST_FILTER_CHANGED,
    EVENT_ACTIVE_LOADOUT_CHANGED, EVENT_SESSION_LOADOUT_UPDATED,
    EVENT_PLAYER_DEATH, EVENT_PLAYER_REVIVED, EVENT_OPEN_ENCOUNTER_UPDATED,
    EVENT_EFFECT_RECEIVED,
    EVENT_ENHANCER_REDETECT_PROMPT, EVENT_ENHANCER_REDETECT_DECISION,
)
from ..core.logger import get_logger
from .combat_action_log import CombatAction, CombatActionLog
from .encounter_manager import EncounterManager
from .enhancer_inference import (
    EnhancerInferenceEngine, InferenceEvent as EnhInfEvent,
)
from .entity_resolver import EntityResolver
from .hunt_detector import HuntDetector
from .loadout_manager import SessionLoadoutManager
from .loot_filter import LootFilter
from .ocr_state import OCRStateTracker
from .reload_correlator import ReloadCorrelator
from .running_stats import SessionRunningStats
from .session import (
    EncounterLootItem, EncounterToolStats,
    Hunt, HuntSession, MobEncounter, SessionLoadoutEntry,
)
from .tool_filter import ToolFilter
from .tool_inference import ToolInferenceEngine
from .tracking_log import TrackingLog

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
        self._tool_filter: ToolFilter = ToolFilter(config)
        self._tracking_log: TrackingLog = TrackingLog(event_bus)
        self._combat_log: CombatActionLog | None = None
        self._reload_correlator: ReloadCorrelator | None = None
        self._running_stats: SessionRunningStats | None = None
        self._timeout_timer: threading.Timer | None = None
        self._persisted_encounter_ids: set[str] = set()
        self._open_encounters: list[MobEncounter] = []  # Unresolved death/timeout encounters
        self._active = False
        self._live = False  # True after chat log catchup completes
        self._last_activity_time: datetime | None = None
        # Timestamp of the most recently closed encounter. Used to scope
        # the "prepend idle tool use to next encounter" reassignment so
        # we don't reach back through a whole session of orphan actions.
        self._last_encounter_end_time: datetime | None = None
        self._auto_timeout = timedelta(milliseconds=config.session_auto_timeout_ms)
        # Bidirectional enhancer-shrapnel correlation. The enhancer break
        # message and the shrapnel loot drop can arrive in EITHER order
        # (varying by a couple of seconds), so we buffer both sides:
        #
        #   _recent_enhancer_breaks : breaks awaiting a matching shrapnel
        #   _recent_shrapnel_items  : shrapnel loot awaiting a matching break
        #
        # When either arrives, it first checks the opposite buffer for
        # a value-matching entry within ENHANCER_SHRAPNEL_WINDOW. If
        # found, the two are merged (shrapnel is marked as enhancer
        # refund retroactively). Otherwise the new event is added to
        # its own buffer to wait for its counterpart.
        self._recent_enhancer_breaks: list[tuple[datetime, float]] = []
        # (timestamp, encounter_ref, loot_item_ref, value_ped)
        self._recent_shrapnel_items: list[
            tuple[datetime, MobEncounter, "EncounterLootItem", float]
        ] = []

        # Enhancer auto-detection: per-tool state machine that watches
        # damage/heal samples and infers enhancer presence from offset
        # vs expected [min, max] range. See enhancer_inference.py.
        self._enhancer_inference = EnhancerInferenceEngine()
        # Active damage- and heal-modifying buffs keyed by lowercased
        # effect name -> expiry time. The engine pauses the matching
        # inference kind while any entry is live.
        self._active_damage_buffs: dict[str, datetime] = {}
        self._active_heal_buffs: dict[str, datetime] = {}
        # Default buff duration assumed when the chat message doesn't
        # carry explicit timing. 5 min is conservative; worst case a
        # stale entry prevents inference for this long after expiry.
        self._buff_default_duration = timedelta(minutes=5)
        # Medical tool heal range cache (name -> (min, max)) populated
        # lazily the first time we see the tool via OCR.
        self._heal_tool_ranges: dict[str, tuple[float, float]] = {}
        # Context from the last enhancer break, used to correlate a
        # subsequent inference RESTART with that break (suggests the
        # break count was inconsistent with observed damage).
        self._last_break_validation: dict | None = None

        # Cached config signature, computed on session start and re-
        # compared on restore. When the hash changes between sessions
        # we re-run recalculate_session() because tool costs, filters,
        # or blacklists may have shifted and the stored stats are stale.
        self._config_signature_cached: str | None = None

        # Register reload drop callback — fires when reload bar drops from >=100 to <100
        self._ocr_state.on_reload_drop(self._on_reload_drop)

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
        event_bus.subscribe(EVENT_ENHANCER_BREAK, self._on_enhancer_break)
        event_bus.subscribe(EVENT_EFFECT_RECEIVED, self._on_effect_received)
        event_bus.subscribe(
            EVENT_ENHANCER_REDETECT_DECISION, self._on_enhancer_redetect_decision,
        )
        event_bus.subscribe(EVENT_LOOT_BLACKLIST_CHANGED, self._on_blacklist_changed)
        event_bus.subscribe(EVENT_TOOL_COST_FILTER_CHANGED, self._on_tool_filter_changed)
        event_bus.subscribe(EVENT_ACTIVE_LOADOUT_CHANGED, self._on_active_loadout_changed)
        event_bus.subscribe(EVENT_GEAR_OVERRIDE_CHANGED, self._on_gear_override_changed)
        event_bus.subscribe(EVENT_SESSION_MARKUP_CHANGED, self._on_session_markup_changed)

        # Expose gear overrides to the inference engine. Called once at
        # construction; the provider pulls fresh values on every cost
        # lookup so later DB edits flow through without re-registration.
        try:
            self._tool_inference.set_override_provider(
                lambda: self._db.get_all_gear_overrides()
            )
        except Exception as e:
            log.warning("Failed to register gear override provider: %s", e)

    GLOBAL_CORRELATION_WINDOW = timedelta(seconds=10)
    # Window within which shrapnel loot is correlated to an enhancer break
    ENHANCER_SHRAPNEL_WINDOW = timedelta(seconds=2)

    @property
    def tool_inference(self) -> ToolInferenceEngine:
        """Expose tool inference for external signature loading."""
        return self._tool_inference

    def _build_summary(self) -> dict:
        """Build session summary including all alive encounters' stats."""
        summary = self._session.to_summary()
        alive_data = []
        if self._manager:
            for enc, state in self._manager.alive_encounters:
                summary["kills"] += 1 if enc.loot_total_ped > 0 else 0
                summary["damage_dealt"] += enc.damage_dealt
                summary["damage_taken"] += enc.damage_taken
                summary["loot_total"] += enc.effective_loot_ped
                summary["total_cost"] += enc.cost
                alive_data.append({
                    "id": enc.id,
                    "mob_name": enc.mob_name,
                    "state": state.name,
                    "damage_dealt": enc.damage_dealt,
                    "cost": enc.cost,
                    "is_active": enc is self._manager.current_encounter,
                })
        summary["alive_encounters"] = alive_data
        return summary

    def _build_summary_with_history(self) -> dict:
        """Build summary including loadout event history (for Hunt Log view)."""
        summary = self._build_summary()
        try:
            summary["loadout_events"] = self._loadout_mgr.get_loadout_events()
        except Exception:
            summary["loadout_events"] = []
        return summary

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
        self._tracking_log.session_info("Chat log catchup complete — hunt tracking active")
        log.info("Catchup complete, hunt tracking active")

    def _try_restore_session(self):
        """Check DB for an incomplete session and restore it."""
        row = self._db.get_incomplete_session()
        if not row:
            return

        session_id = row["id"]
        log.info("Restoring incomplete session: %s", session_id)

        # 0. Drop orphaned partial encounters from the previous crash.
        # These are rows with end_time IS NULL that the restore loop
        # would skip anyway, but keeping them pollutes stats queries.
        removed = self._db.delete_partial_encounters(session_id)
        if removed:
            log.info("Dropped %d orphaned partial encounter(s) from session %s",
                     removed, session_id)

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
                    is_enhancer_shrapnel=bool(lr.get("is_enhancer_shrapnel", 0)),
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
        self._combat_log = CombatActionLog()
        self._reload_correlator = ReloadCorrelator(self._config, self._combat_log, self._db)
        self._tool_inference.reset_timeline()
        self._loot_filter.invalidate_mob_cache()
        self._active = True
        self._last_activity_time = datetime.utcnow()

        # Rebuild combat log from DB
        self._restore_combat_log(session_id)

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

        # 6b. Restore crash-recovery blobs (enhancer inference engine,
        # shrapnel/break buffers, config signature). Must run AFTER
        # loadout restore so any tool ranges the loadout manager
        # registers are already in place — from_dict preserves
        # matching ranges and resets mismatched ones cleanly.
        self._restore_recovery_state(session_id)

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
        self._combat_log = CombatActionLog()
        self._reload_correlator = ReloadCorrelator(self._config, self._combat_log, self._db)
        self._loot_filter.invalidate_mob_cache()
        self._tool_inference.reset_timeline()
        self._active = True  # BEFORE any publish to prevent re-entrance
        self._last_activity_time = now

        # Persist session start
        self._db.insert_hunt_session(
            session_id, now.isoformat(), loadout_id, primary_mob
        )
        self._tracking_log.session_started(session_id)

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

        # Close all alive encounters
        if self._manager:
            for ended in self._manager.force_close():
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
        self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED, self._build_summary())
        self._tracking_log.session_ended(
            self._session.id, self._session.kill_count, self._session.total_cost,
        )

        self._cancel_timeout()
        self._active = False
        self._last_activity_time = None
        self._persisted_encounter_ids.clear()
        self._tool_inference.clear()
        if self._combat_log:
            self._combat_log.clear()
        log.info("Session ended: %s", self._session.id)
        self._session = None
        self._manager = None
        self._hunt_detector = None
        self._running_stats = None
        self._combat_log = None
        self._reload_correlator = None

    def _on_hunt_end_requested(self, data):
        """Manually end the current hunt without ending the session.

        The next encounter will automatically start a new hunt.
        """
        if not self._active or not self._hunt_detector:
            return

        now = datetime.utcnow()

        # Close all alive encounters first
        if self._manager:
            for ended in self._manager.force_close():
                self._persist_encounter(ended)
                self._event_bus.publish(EVENT_HUNT_ENCOUNTER_ENDED, ended.to_dict())

        # Close the current hunt
        hunt = self._hunt_detector.end_current_hunt(now)
        if hunt:
            self._db.end_hunt(hunt.id, now.isoformat(), hunt.total_cost)
            self._event_bus.publish(EVENT_HUNT_ENDED, hunt.to_dict())
            log.info("Hunt manually ended: %s", hunt.id[:8])

        self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED, self._build_summary())

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

        # Visible tracking log
        self._tracking_log.combat_event(event_type, amount or 0, now)

        if event_type == "damage_dealt":
            self._handle_damage(amount or 0, False, now)
        elif event_type == "critical_hit":
            self._handle_damage(amount or 0, True, now)
        elif event_type == "damage_received":
            if amount is not None and amount == 0.0:
                self._manager.on_block(timestamp=now)
                self._log_non_damage_event("block", 0.0, now)
            else:
                self._manager.on_damage_received(amount or 0, timestamp=now)
                self._log_non_damage_event("damage_received", amount or 0, now)
        elif event_type == "self_heal":
            self._manager.on_heal(amount or 0, timestamp=now)
            self._log_non_damage_event("self_heal", amount or 0, now)
            # Feed heal enhancer inference. The engine drops samples
            # if no medical tool is registered/active or if paused.
            self._feed_heal_enhancer_inference(amount or 0, now)
        elif event_type in ("player_evade", "player_dodge", "player_jam"):
            self._manager.on_player_avoid(timestamp=now)
            self._log_non_damage_event(event_type, 0.0, now)
        elif event_type in ("target_evade", "target_dodge", "target_jam"):
            self._manager.on_target_avoid(timestamp=now)
            self._log_non_damage_event(event_type, 0.0, now)
        elif event_type == "mob_miss":
            self._manager.on_mob_miss(timestamp=now)
            self._log_non_damage_event("mob_miss", 0.0, now)
        elif event_type == "deflect":
            self._manager.on_deflect(timestamp=now)
            self._log_non_damage_event("deflect", 0.0, now)

        # Keep encounter HP state updated for same-name mob differentiation
        if not self._ocr_state.is_stale("target"):
            self._manager.on_hp_update(self._ocr_state.state.target_hp_pct)

        # Notify loadout manager of combat activity
        self._loadout_mgr.on_combat()

        # Publish session update
        self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED, self._build_summary())

    def _log_non_damage_event(self, event_type: str, amount: float, now: datetime):
        """Record a non-damage combat event to the combat log and DB."""
        enc = self._manager.current_encounter if self._manager else None
        encounter_id = enc.id if enc else None

        event_id = str(uuid.uuid4())

        # Persist to DB (only if we have an encounter — FK constraint)
        if encounter_id:
            self._ensure_encounter_in_db(enc)
            self._db.insert_combat_event_detail(
                event_id, encounter_id, now.isoformat(),
                event_type, amount, None, None, 0.0,
            )

        # Add to session combat log (always — even without encounter)
        if self._combat_log:
            action = CombatAction(
                id=event_id,
                encounter_id=encounter_id,
                timestamp=now,
                event_type=event_type,
                amount=amount,
            )
            self._combat_log.append(action)

    def _ensure_encounter_in_db(self, enc):
        """Insert encounter row into DB if not yet persisted (for FK integrity)."""
        if enc.id not in self._persisted_encounter_ids:
            self._db.insert_mob_encounter(
                enc.id, enc.session_id, enc.mob_name,
                enc.mob_name_source, enc.start_time.isoformat(),
            )
            self._persisted_encounter_ids.add(enc.id)

    def _handle_damage(self, amount: float, is_crit: bool, now: datetime):
        """Handle damage dealt with tool inference, cost tracking, and combat logging."""
        prev_encounter_id = (self._manager.current_encounter.id
                             if self._manager.current_encounter else None)
        closed = self._manager.on_damage_dealt(amount, is_crit=is_crit, timestamp=now)

        # If a CLOSING encounter was finalized (new shot after loot), persist it
        if closed:
            self._tracking_log.encounter_ended(
                closed.mob_name, closed.outcome, closed.damage_dealt, closed.cost,
            )
            self._persist_encounter(closed)
            self._event_bus.publish(EVENT_HUNT_ENCOUNTER_ENDED, closed.to_dict())

        enc = self._manager.current_encounter
        if not enc:
            return

        # Prepend orphaned tool uses (heals, buffs) since the last
        # encounter ended onto this freshly started encounter.
        if enc.id != prev_encounter_id:
            self._prepend_orphan_actions(enc)

        # Resolve mob ID if not yet set
        if enc.mob_id is None and enc.mob_name != "Unknown":
            enc.mob_id = self._entity_resolver.resolve_mob(enc.mob_name)

        self._ensure_encounter_in_db(enc)

        # Tool attribution cascade:
        # 1. OCR tool current and not stale → "ocr_direct"
        # 2. Damage-range inference → "inferred"
        # 3. Leave unattributed (reload correlator may fix later)
        tool_name = None
        tool_source = None
        confidence = 0.0
        cost_per_shot = 0.0

        # Priority 1: OCR direct (tool is current and not stale)
        if not self._ocr_state.is_stale("tool"):
            ocr_tool = self._ocr_state.state.ocr_tool_name
            if ocr_tool:
                tool_name = ocr_tool
                tool_source = "ocr_direct"
                confidence = 0.9

        # Priority 2: Manager's current tool (set by tool change event)
        if not tool_name and self._manager._current_tool:
            tool_name = self._manager._current_tool
            tool_source = "ocr_direct"
            confidence = 0.9

        # Priority 3: Damage-range inference
        if not tool_name and self._tool_inference.has_signatures:
            inferred, inf_confidence, cost = self._tool_inference.infer_tool(amount, is_crit=is_crit)
            if inferred:
                tool_name = inferred
                tool_source = "inferred"
                confidence = inf_confidence
                cost_per_shot = cost

        # Get cost from signature if we know the tool
        if tool_name and not cost_per_shot:
            cost_per_shot = self._tool_inference.get_cost_per_shot(tool_name)

        # Accumulate cost on encounter (respecting tool filter)
        if cost_per_shot > 0 and self._tool_filter.should_include_cost(tool_name):
            enc.cost += cost_per_shot
            if enc.shots_fired <= 3:  # Log first few shots for diagnostics
                log.info("Shot cost: +%.4f PEC (%s via %s), total=%.2f PEC",
                         cost_per_shot, tool_name, tool_source, enc.cost)

        # Log tool attribution decision
        if tool_name:
            self._tracking_log.tool_attributed(
                "critical_hit" if is_crit else "damage_dealt",
                amount, tool_name, tool_source, confidence,
            )

        if not tool_name:
            # Track for auto-detection of unknown weapons
            self._loadout_mgr.on_unmatched_damage(amount)

        event_id = str(uuid.uuid4())
        event_type = "critical_hit" if is_crit else "damage_dealt"

        # Persist combat event detail
        self._db.insert_combat_event_detail(
            event_id, enc.id, now.isoformat(),
            event_type, amount,
            tool_name, tool_source, confidence,
        )

        # Add to session combat log
        if self._combat_log:
            action = CombatAction(
                id=event_id,
                encounter_id=enc.id,
                timestamp=now,
                event_type=event_type,
                amount=amount,
                tool_name=tool_name,
                tool_source=tool_source,
                confidence=confidence,
            )
            self._combat_log.append(action)

        # Feed the enhancer auto-detection engine. The engine itself
        # skips crits and pauses on damage-modifying buffs, so we can
        # unconditionally call it here. Transitions (CONFIRMED_*,
        # RESTART) are handled on the returned Transition object.
        self._feed_enhancer_inference(amount, is_crit, now)

    def _feed_enhancer_inference(self, amount: float, is_crit: bool,
                                 timestamp: datetime) -> None:
        """Feed a damage sample into the enhancer inference engine."""
        from .enhancer_inference import KIND_DAMAGE
        self._expire_buffs(self._active_damage_buffs, timestamp,
                           KIND_DAMAGE, "damage buffs expired")
        transition = self._enhancer_inference.observe_damage(
            amount, is_crit, timestamp,
        )
        self._handle_inference_transition(transition)

    def _feed_heal_enhancer_inference(self, amount: float,
                                      timestamp: datetime) -> None:
        """Feed a self-heal sample into the enhancer inference engine.

        Registers the currently-equipped medical tool lazily on first
        use (looking up MinHeal/MaxHeal via data_client) so players
        don't need to configure anything.
        """
        from .enhancer_inference import KIND_HEAL
        self._expire_buffs(self._active_heal_buffs, timestamp,
                           KIND_HEAL, "heal buffs expired")

        # Lazy register: if the active OCR tool name is a known medical
        # tool we haven't seen yet, look up its heal range and register.
        ocr_tool = (self._ocr_state.state.ocr_tool_name or "").strip()
        if ocr_tool and ocr_tool not in self._heal_tool_ranges:
            rng = self._lookup_heal_range(ocr_tool)
            if rng is not None:
                self._heal_tool_ranges[ocr_tool] = rng
                self._enhancer_inference.register_tool(
                    ocr_tool, rng[0], rng[1], kind=KIND_HEAL,
                )
                self._enhancer_inference.set_active_tool(ocr_tool)

        transition = self._enhancer_inference.observe_heal(amount, timestamp)
        self._handle_inference_transition(transition)

    def _expire_buffs(self, buffs: dict[str, datetime], timestamp: datetime,
                      kind: str, resume_reason: str) -> None:
        """Drop expired buffs and resume the matching inference kind."""
        expired = [name for name, exp in buffs.items() if exp <= timestamp]
        for name in expired:
            del buffs[name]
        if not buffs and self._enhancer_inference.is_paused(kind):
            self._enhancer_inference.resume(kind, resume_reason)

    def _handle_inference_transition(self, transition) -> None:
        """Route a Transition emitted by the enhancer inference engine.

        CONFIRMED_PRESENT: inject missing enhancer state, re-evaluate
        loadout, and retroactively recalculate session cost.  The
        confirmed-present hook emits its own tracking log entry so
        the message can include the correction reason.

        CONFIRMED_NONE: just log.

        RESTART: log and correlate with any recent break so the user
        can tell a manual change from a missed break.
        """
        if transition is None:
            return
        if transition.event == EnhInfEvent.CONFIRMED_PRESENT:
            self._on_enhancer_inference_confirmed_present(transition)
        elif transition.event == EnhInfEvent.CONFIRMED_NONE:
            self._tracking_log.enhancer_inference(
                "confirmed_none", transition.tool_name,
            )
        elif transition.event == EnhInfEvent.RESTART:
            self._tracking_log.enhancer_inference(
                "restart", transition.tool_name,
                {"reason": transition.reason},
            )
            self._on_enhancer_inference_restart(transition)

    def _lookup_heal_range(self, tool_name: str) -> tuple[float, float] | None:
        """Look up MinHeal/MaxHeal for a medical tool from the data client."""
        if not self._data_client:
            return None
        try:
            tools = self._data_client.get_medical_tools() or []
        except Exception:
            return None
        target = tool_name.strip().lower()
        for t in tools:
            name = (t.get("Name") or "").strip()
            if not name or name.lower() != target:
                continue
            props = t.get("Properties") or {}
            mn = props.get("MinHeal")
            mx = props.get("MaxHeal")
            if isinstance(mn, (int, float)) and isinstance(mx, (int, float)):
                return float(mn), float(mx)
        return None

    def _on_enhancer_inference_confirmed_present(self, transition) -> None:
        """Hook called when the engine confirms enhancers on a tool.

        If the loadout's enhancer state has 0 active slots for the
        corresponding enhancer type (damage-on-weapon or heal-on-heal-
        tool), we've been charging cost at the no-enhancer rate — wrong.
        This method:

        1. Synthetically adds 1 active enhancer slot to the state so
           the loadout re-evaluates with enhancer decay included.
        2. The re-evaluation updates ``tool_inference`` signatures
           with the corrected cost_per_shot.
        3. Calls ``recalculate_session()`` which rebuilds encounter
           cost totals from the combat log using the new signatures,
           retroactively fixing every shot in the session.

        We can only inject 1 slot as a lower bound because the observed
        damage bonus doesn't uniquely determine the count (we'd need
        per-enhancer-tier data).  A break event later will refine the
        count as the normal break flow updates state.
        """
        enc = self._manager.current_encounter if self._manager else None
        if enc is not None:
            setattr(enc, "enhancers_inferred_present", True)
            setattr(enc, "enhancers_inferred_tool", transition.tool_name)
            setattr(enc, "enhancers_inferred_avg_bonus",
                    transition.over_range_average)

        # Determine the category/slot to adjust based on the tool kind.
        from .enhancer_inference import KIND_HEAL
        tool_state = self._enhancer_inference.get_state(
            transition.tool_name, kind="damage",
        ) or self._enhancer_inference.get_state(
            transition.tool_name, kind=KIND_HEAL,
        )
        if tool_state is None:
            return
        if tool_state.kind == "damage":
            category, slot_key = "weapon", "Damage"
        else:
            category, slot_key = "healing", "Heal"

        # Check current state. If already has active slots, the loadout
        # cost is already correct; nothing to fix retroactively.
        state_slot = self._loadout_mgr._enhancer_state.get_slot(
            category, slot_key,
        )
        if state_slot.active_slots > 0:
            log.info(
                "Enhancer inference confirmed on %r but state already "
                "has %d active %s slot(s); no cost correction needed",
                transition.tool_name, state_slot.active_slots, slot_key,
            )
            return

        # Inject a synthetic "1 active slot" so re-evaluation includes
        # enhancer decay. This is a conservative lower bound — the
        # actual count may be higher, but this at least corrects the
        # under-charging of cost.
        #
        # Safety: capture cost before the adjust. If the loadout
        # calculator isn't ready or the evaluation fails silently,
        # tool_inference will still hold the old signature (or none
        # at all). Only proceed with recalculate_session() when the
        # cost has actually increased — otherwise recalculating with
        # an unchanged/missing signature would either be a no-op at
        # best or wipe existing cost data at worst.
        cost_before = self._tool_inference.get_cost_per_shot(
            transition.tool_name,
        )
        log.info(
            "Enhancer inference: injecting 1 %s.%s slot on %r "
            "(avg observed bonus: +%.2f HP, cost before: %.4f PEC)",
            category, slot_key, transition.tool_name,
            transition.over_range_average, cost_before,
        )
        try:
            self._loadout_mgr.on_enhancer_adjust(
                category, slot_key, num_slots=1,
            )
        except Exception as e:
            log.warning("Failed to inject enhancer slot: %s", e)
            return

        cost_after = self._tool_inference.get_cost_per_shot(
            transition.tool_name,
        )
        if cost_after <= cost_before:
            # Either the calculator is unavailable (no stats update),
            # or the weapon happens to have no per-enhancer decay cost.
            # Either way, a recalculate_session() call can't improve
            # things and risks wiping cost data on a zero signature.
            log.warning(
                "Enhancer adjust on %r did not increase cost "
                "(%.4f -> %.4f PEC); skipping retroactive recalc",
                transition.tool_name, cost_before, cost_after,
            )
            self._tracking_log.enhancer_inference(
                "confirmed_present", transition.tool_name,
                {
                    "over_avg": transition.over_range_average,
                    "reason": "slot injected but loadout eval unchanged",
                },
            )
            return

        # Recompute all encounter costs using the updated signatures.
        self.recalculate_session()
        self._tracking_log.enhancer_inference(
            "confirmed_present", transition.tool_name,
            {
                "over_avg": transition.over_range_average,
                "reason": (
                    f"injected 1 {slot_key.lower()} slot, "
                    f"cost {cost_before:.4f}->{cost_after:.4f} PEC, "
                    f"session recalculated"
                ),
            },
        )

    def _on_enhancer_inference_restart(self, transition) -> None:
        """Hook called when the engine restarts its cycle for a tool.

        The RESTART transition fires when unexplained damage (not
        attributable to any tracked buff) contradicts a previously
        CONFIRMED state.  Possible causes:

        1. A missed enhancer break.
        2. A manual add/remove by the player.
        3. An untracked buff we didn't classify.

        Since the engine has already transitioned back to UNKNOWN,
        we prompt the user to choose how to handle it: redetect (let
        the engine re-sample), manually configure the loadout, or
        ignore the tool for the rest of the session.  The tool is
        marked ``awaiting_decision`` so no further prompts fire
        until the user answers.
        """
        enc = self._manager.current_encounter if self._manager else None
        if enc is not None:
            setattr(enc, "enhancers_inferred_present", False)
            setattr(enc, "enhancers_inferred_restart_reason", transition.reason)

        tool_name = transition.tool_name

        # Correlate with a recent break on the same tool — anything
        # within the last 15 s is likely break-related rather than manual.
        mismatched_break = False
        last = self._last_break_validation
        if last and last.get("tool") == tool_name:
            elapsed = datetime.utcnow() - last["timestamp"]
            if elapsed <= timedelta(seconds=15):
                mismatched_break = True
                self._tracking_log.enhancer_inference(
                    "mismatch", tool_name,
                    {
                        "reason": (
                            f"damage stayed {transition.reason} "
                            f"after break of {last.get('enhancer_name')}"
                        ),
                    },
                )
                self._last_break_validation = None

        # Prompt the user. Mark the tool as awaiting a decision so no
        # further restarts can pile up additional prompts for the same
        # tool before the user answers.
        self._enhancer_inference.mark_awaiting_decision(tool_name)
        self._event_bus.publish(EVENT_ENHANCER_REDETECT_PROMPT, {
            "tool_name": tool_name,
            "reason": transition.reason,
            "mismatched_break": mismatched_break,
            "over_range_average": transition.over_range_average,
        })

    def _on_enhancer_redetect_decision(self, data) -> None:
        """Handle the user's response to an enhancer redetect prompt.

        Accepts a dict with ``tool_name`` and ``decision`` keys.
        *decision* is one of:

        - ``"redetect"`` : resume sampling, engine auto-detects again
        - ``"manual"``   : same as redetect (the UI opened the loadout
                           editor so the user can set enhancers
                           explicitly; we still want fresh inference
                           in case they edit incompletely)
        - ``"ignore"``   : permanently disable auto-detection for
                           this tool for the rest of the session
        """
        if not isinstance(data, dict):
            return
        tool_name = (data.get("tool_name") or "").strip()
        if not tool_name:
            return
        decision = (data.get("decision") or "").strip().lower()
        if decision == "ignore":
            self._enhancer_inference.disable_tool(tool_name)
            self._tracking_log.enhancer_inference(
                "restart", tool_name,
                {"reason": "user chose to ignore auto-detection"},
            )
            return
        if decision in ("redetect", "manual"):
            # Reset engine state for this tool and resume sampling.
            # The next 15 in-range or over-range samples will produce
            # a new CONFIRMED_* transition, which may retroactively
            # correct cost again.
            self._enhancer_inference.reset_tool(tool_name)
            self._enhancer_inference.resolve_decision(tool_name)
            self._tracking_log.enhancer_inference(
                "restart", tool_name,
                {"reason": f"user chose {decision}, re-detecting"},
            )
            return
        # Unknown decision — treat as cancel (resume sampling, leave
        # state as-is so progress already made is preserved).
        self._enhancer_inference.resolve_decision(tool_name)

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

        loot_timestamp = data.timestamp if hasattr(data, 'timestamp') else datetime.utcnow()

        for item in items:
            item_name = item.item_name if hasattr(item, 'item_name') else item.get('item_name', '')
            quantity = item.quantity if hasattr(item, 'quantity') else item.get('quantity', 0)
            value_ped = item.value_ped if hasattr(item, 'value_ped') else item.get('value_ped', 0)

            classification = self._loot_filter.classify(item_name, mob_name)

            # Check if this is enhancer shrapnel (refund, not mob loot)
            is_enhancer_shrapnel = self._match_enhancer_shrapnel(
                item_name, value_ped, loot_timestamp,
            )

            loot_entry = EncounterLootItem(
                item_name=item_name,
                quantity=quantity,
                value_ped=value_ped,
                item_id=self._entity_resolver.resolve_item(item_name),
                is_blacklisted=classification["is_blacklisted"],
                is_refining_output=classification["is_refining_output"],
                is_in_loot_table=classification["is_in_loot_table"],
                is_enhancer_shrapnel=is_enhancer_shrapnel,
            )
            classified.append(loot_entry)
            raw_total += value_ped

            if is_enhancer_shrapnel:
                self._tracking_log.session_info(
                    f"Shrapnel {value_ped:.2f} PED identified as enhancer refund"
                )

        self._last_activity_time = datetime.utcnow()
        loot_target = self._manager.on_loot_group(raw_total, classified)
        self._loadout_mgr.on_loot()

        # Late-arriving loot: if the manager matched to an encounter
        # that was already closed+persisted (end_time set), re-persist
        # it so the new loot rows + updated loot_total_ped make it to
        # disk. Without this the new items only live in memory.
        if (loot_target is not None
                and loot_target.end_time is not None):
            log.info("Post-kill loot attached to closed encounter %s (%s)",
                     loot_target.id[:8], loot_target.mob_name)
            self._persist_encounter(loot_target)

        # Buffer any unmatched shrapnel items for retroactive
        # correlation. The enhancer break message may arrive shortly
        # after the loot drop; if so, _on_enhancer_break will flip
        # the is_enhancer_shrapnel flag on the item we just created.
        if loot_target is not None:
            for loot_item in classified:
                if (loot_item.item_name.lower() == "shrapnel"
                        and not loot_item.is_enhancer_shrapnel):
                    self._buffer_unmatched_shrapnel(
                        loot_target, loot_item, loot_timestamp,
                    )

        target_name = loot_target.mob_name if loot_target else mob_name
        self._tracking_log.loot_received(raw_total, len(classified), target_name)
        self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED, self._build_summary())

    def _on_mob_changed(self, data):
        if not self._live or not self._active or not self._manager:
            return

        mob_name = data.get("mob_name", "") if isinstance(data, dict) else str(data)
        confidence = data.get("confidence", 1.0) if isinstance(data, dict) else 1.0
        source = data.get("source", "ocr") if isinstance(data, dict) else "ocr"

        # Pass HP for same-name mob differentiation
        hp_pct = None
        if not self._ocr_state.is_stale("target"):
            hp_pct = self._ocr_state.state.target_hp_pct

        self._last_activity_time = datetime.utcnow()
        self._tracking_log.ocr_mob_detected(mob_name, source)

        prev_encounter_id = (self._manager.current_encounter.id
                             if self._manager.current_encounter else None)
        # Suspends old encounter (if any), activates/creates encounter for mob_name
        self._manager.on_mob_name_detected(mob_name, confidence, source, hp_pct=hp_pct)

        enc = self._manager.current_encounter
        if enc and enc.id != prev_encounter_id:
            self._prepend_orphan_actions(enc)

        self._tracking_log.encounter_started(mob_name, source)
        self._event_bus.publish(EVENT_HUNT_ENCOUNTER_STARTED, {
            "mob_name": mob_name,
            "source": source,
        })

    def _prepend_orphan_actions(self, encounter) -> None:
        """Reassign tool uses that occurred between encounters onto *encounter*.

        Any CombatAction with encounter_id=None whose timestamp is after
        the previous encounter's end (or the session start) gets attached
        to *encounter* and tagged phase="pre_encounter". Lets the UI show
        heals and idle shots inside the next encounter's event log.
        """
        if not self._combat_log:
            return
        since = self._last_encounter_end_time
        if since is None and self._session is not None:
            since = self._session.start_time
        if since is None:
            return
        reassigned = self._combat_log.reassign_unattached(
            encounter.id, since, phase="pre_encounter",
        )
        if reassigned:
            log.debug("Prepended %d orphan action(s) to encounter %s",
                      len(reassigned), encounter.id[:8])

    def _on_tool_changed(self, data):
        if not self._live or not self._active or not self._manager:
            return

        tool_name = data.get("tool_name", "") if isinstance(data, dict) else str(data)
        self._manager.set_current_tool(tool_name)
        self._tracking_log.ocr_tool_detected(tool_name)

        # Record on timeline for retroactive attribution
        now = datetime.utcnow()
        self._tool_inference.on_tool_detected(tool_name, now)

        # Enhancer auto-detection: switch the engine's active tool.
        # If we have a signature for this tool, register its damage
        # range so the engine has a baseline to compare against.
        if tool_name:
            for sig in self._tool_inference._signatures:
                if sig.weapon_name == tool_name:
                    self._enhancer_inference.register_tool(
                        tool_name, sig.damage_min, sig.damage_max,
                    )
                    break
        self._enhancer_inference.set_active_tool(tool_name or None)

        # Retroactive enrichment — re-attribute events in current encounter
        # using the tool timeline via the combat log as source of truth
        enc = self._manager.current_encounter
        if enc and self._combat_log:
            actions = self._combat_log.get_by_encounter(enc.id)
            enriched = self._tool_inference.enrich_actions(actions)
            for event_id, new_tool, new_source, new_confidence in enriched:
                self._db.update_combat_event_tool(
                    event_id, new_tool, new_source, new_confidence
                )
                self._combat_log.update_tool(
                    event_id, new_tool, new_source, new_confidence
                )
            if enriched:
                self._tracking_log.tool_retroactive(
                    len(enriched), tool_name, "ocr_timeline",
                )
                self._recalculate_encounter_stats(enc)

    def _on_reload_drop(self, tool_name: str | None, timestamp: datetime):
        """Handle reload bar drop — retroactively attribute recent damage events."""
        if not self._active or not self._reload_correlator:
            return

        reload_pct = self._ocr_state.state.reload_pct or 0
        self._tracking_log.ocr_reload_drop(tool_name, reload_pct)

        attributed = self._reload_correlator.on_reload_drop(tool_name, timestamp)
        if attributed > 0:
            self._tracking_log.tool_retroactive(attributed, tool_name, "ocr_reload")
            enc = self._manager.current_encounter if self._manager else None
            if enc:
                self._recalculate_encounter_stats(enc)

    # Loadout gear slots that hold tools the player can actively use.
    # Excludes purely cosmetic / passive slots (Pet, Armor, Clothing) so a
    # creature or armor name containing the effect keyword can't false-match.
    _ACTIVE_TOOL_GEAR_SLOTS = ("Weapon", "Healing", "Consumables")

    def _equipped_active_tool_names(self) -> list[str]:
        """All currently-equipped active-tool names from the loadout.

        Covers weapons, medical tools/chips, effect chips, and consumables —
        anything that can be held and used from the player status bar slot.
        """
        names: list[str] = []
        loadout = self._loadout_mgr.active_loadout if self._loadout_mgr else None
        gear = (loadout or {}).get("Gear") or {}
        for slot in self._ACTIVE_TOOL_GEAR_SLOTS:
            slot_value = gear.get(slot)
            if isinstance(slot_value, dict):
                name = (slot_value.get("Name") or "").strip()
                if name:
                    names.append(name)
        return names

    def _apply_inference_buff_pause(self, effect_name: str,
                                    timestamp: datetime) -> None:
        """Pause the enhancer inference engine if *effect_name* modifies
        damage or heal output.

        Effect messages can come from other players too, but we err on
        the side of pausing — a brief unnecessary pause is harmless,
        whereas observing samples under an uncounted buff would skew
        the baseline and produce false CONFIRMED_PRESENT transitions.

        Crit-only buffs are intentionally classified PASSIVE (not
        DAMAGE_MOD) because the engine already excludes crits from its
        sample intake.  Equipped damage-altering items (amplifiers,
        scopes, sights) are already baked into the loadout-evaluated
        range and don't need runtime tracking.
        """
        from ..chat_parser.effect_types import (
            pauses_damage_inference, pauses_heal_inference,
        )
        from .enhancer_inference import KIND_DAMAGE, KIND_HEAL
        key = effect_name.lower().strip()
        expiry = timestamp + self._buff_default_duration
        if pauses_damage_inference(effect_name):
            self._active_damage_buffs[key] = expiry
            if not self._enhancer_inference.is_paused(KIND_DAMAGE):
                self._enhancer_inference.pause(
                    KIND_DAMAGE, f"damage buff active: {effect_name}",
                )
        if pauses_heal_inference(effect_name):
            self._active_heal_buffs[key] = expiry
            if not self._enhancer_inference.is_paused(KIND_HEAL):
                self._enhancer_inference.pause(
                    KIND_HEAL, f"heal buff active: {effect_name}",
                )

    def _on_effect_received(self, event):
        """Handle 'Received Effect Over Time: <name>' system messages.

        Such effects can come from other players too (team healers, buffers),
        so attribution requires a strong signal that *we* triggered it.  The
        active tool slot can hold weapons, medical tools/chips, effect chips,
        or consumables — all are checked.

        Attribution paths:

        1. OCR-detected active tool name contains the effect keyword
           (e.g. effect 'Divine Intervention' + tool 'Divine Intervention Chip').
           Stale OCR is still trusted here because the cached name persists
           until a new tool is OCR'd; staleness just means no recent change.
           -> definitive: charge the cost.

        2. OCR has never seen any tool AND exactly one equipped item from
           the loadout's active-tool slots matches the effect keyword.
           -> probable: charge the cost (best-effort).

        3. OCR shows a different tool, or no/multiple candidates exist.
           -> ignore (likely another player's effect).

        Utility tools like the Divine Intervention Chip don't fire damage
        events, so this is the *only* path that adds their cost to a hunt.
        """
        if not self._live or not self._active or not self._manager:
            return
        effect_name = getattr(event, "effect_name", None)
        if not effect_name:
            return

        effect_lc = effect_name.lower().strip()
        if not effect_lc:
            return

        # Pause enhancer auto-detection if this is a damage- or heal-
        # modifying buff. Harmless if it's someone else's buff — the
        # pause expires after the default duration and the engine
        # resumes automatically.
        ts = getattr(event, "timestamp", None) or datetime.utcnow()
        self._apply_inference_buff_pause(effect_name, ts)

        ocr_tool = (self._ocr_state.state.ocr_tool_name or "").strip()

        chosen_tool: str | None = None
        confidence: float = 0.0
        source: str = ""

        if ocr_tool and effect_lc in ocr_tool.lower():
            # Path 1: OCR confirms a matching tool is equipped right now.
            # Stale OCR is fine — the cached name persists until the tool
            # actually changes, so the last-known name is still current.
            chosen_tool = ocr_tool
            confidence = 0.95
            source = "ocr_effect"
        elif not ocr_tool:
            # Path 2: OCR has never seen any tool. Walk the equipped
            # active-tool slots (weapon, healing, consumables) for a match.
            candidates = [
                n for n in self._equipped_active_tool_names()
                if effect_lc in n.lower()
            ]
            if len(candidates) == 1:
                chosen_tool = candidates[0]
                confidence = 0.65
                source = "effect_inferred"
            else:
                return
        else:
            # OCR shows a different tool — likely another player's effect
            return

        if not self._tool_filter.should_include_cost(chosen_tool):
            return

        # Cost lookup. For weapons this returns the per-shot decay+ammo from
        # the loaded signature. For medical/effect chips that aren't in the
        # inference engine the cost will be 0 — we still record the use as a
        # confirmation signal but don't add to encounter cost.
        cost = self._tool_inference.get_cost_per_shot(chosen_tool)

        enc = self._manager.current_encounter
        if enc is not None and cost > 0:
            enc.cost += cost
        self._tracking_log.tool_attributed(
            "effect", cost, chosen_tool, source, confidence,
        )
        log.info("Effect %r attributed to %s (+%.4f PEC, source=%s)",
                 effect_name, chosen_tool, cost, source)

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
            self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED, self._build_summary())
            self._tracking_log.global_event(target, value, match.is_hof)
            log.info("Global correlated with encounter %s (mob: %s, value: %s PED)",
                     match.id[:8], match.mob_name, value)

    def _on_player_death(self, data):
        """Handle player death — close encounter immediately, mark as open-ended."""
        if not self._live or not self._active or not self._manager:
            return

        mob_name = data.mob_name if hasattr(data, 'mob_name') else ""
        timestamp = data.timestamp if hasattr(data, 'timestamp') else None
        self._tracking_log.death(mob_name)

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
                                            self._build_summary())
                    return

            self._open_encounters.append(ended)
            self._persist_encounter(ended)
            self._event_bus.publish(EVENT_HUNT_ENCOUNTER_ENDED, ended.to_dict())
            self._event_bus.publish(EVENT_OPEN_ENCOUNTER_UPDATED,
                                    self._get_open_encounters_data())
            self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED,
                                    self._build_summary())
            log.info("Player died to %s — encounter %s is open-ended (cost: %.2f PED)",
                     mob_name, ended.id[:8], ended.cost)

    def _on_player_revived(self, data):
        """Handle player revival — informational only, no state change."""
        if not self._live:
            return
        log.info("Player revived")

    def _on_enhancer_break(self, data):
        """Track enhancer break — decrement enhancer state, re-evaluate, correlate shrapnel."""
        if not self._live:
            return
        timestamp = data.timestamp if hasattr(data, 'timestamp') else datetime.utcnow()
        shrapnel_ped = data.shrapnel_ped if hasattr(data, 'shrapnel_ped') else 0
        enhancer_name = data.enhancer_name if hasattr(data, 'enhancer_name') else ""
        item_name = data.item_name if hasattr(data, 'item_name') else ""
        remaining = data.remaining if hasattr(data, 'remaining') else None

        # Bidirectional shrapnel correlation. First check whether a
        # shrapnel loot item already arrived (within the correlation
        # window) that matches this break's PED value. If so, mark it
        # retroactively so it's excluded from effective_loot_ped. If
        # not, remember this break for a future shrapnel drop.
        if shrapnel_ped > 0:
            matched = self._match_loot_against_break(timestamp, shrapnel_ped)
            if not matched:
                self._recent_enhancer_breaks.append((timestamp, shrapnel_ped))
                cutoff = datetime.utcnow() - self.ENHANCER_SHRAPNEL_WINDOW * 5
                self._recent_enhancer_breaks = [
                    b for b in self._recent_enhancer_breaks if b[0] > cutoff
                ]

        # Track on current encounter
        enc = self._manager.current_encounter if self._manager else None
        if enc:
            enc.enhancer_breaks += 1
            enc.enhancer_shrapnel_ped += shrapnel_ped

        # Notify enhancer auto-detect engine: the post-break damage is
        # expected to shift, so clear the contradiction counter. If the
        # shift isn't observed (damage stays over-range), subsequent
        # observe_damage() calls will eventually trigger RESTART — which
        # the _handle_inference_transition() hook logs as a "restart"
        # signal, implicitly flagging the missed break.
        active_tool = (self._ocr_state.state.ocr_tool_name or "").strip()
        if active_tool:
            self._enhancer_inference.validate_break(active_tool)
            # Remember the break-time state so the restart hook can
            # attribute a subsequent cycle restart to this break.
            self._last_break_validation = {
                "tool": active_tool,
                "timestamp": timestamp,
                "enhancer_name": enhancer_name,
            }

        # Decrement enhancer state and re-evaluate loadout
        delta = self._loadout_mgr.on_enhancer_break(
            enhancer_name, item_name, remaining, shrapnel_ped,
        )

        if delta:
            total_info = f"{delta['old_total']}→{delta['new_total']} total"
            slot_info = ""
            if delta.get("slot_changed"):
                slot_info = f", slots {delta['old_active']}→{delta['new_active']}"
            cost_str = ""
            if delta.get("slot_changed") and self._loadout_mgr.active_stats:
                cost_str = f", cost now {self._loadout_mgr.active_stats.cost / 100:.4f} PED/shot"
            self._tracking_log.session_info(
                f"Enhancer broke: {enhancer_name} on {item_name} "
                f"({total_info}{slot_info}{cost_str})"
            )
        else:
            self._tracking_log.session_info(
                f"Enhancer broke: {enhancer_name} on {item_name} "
                f"(+{shrapnel_ped:.2f} PED shrapnel, unmatched slot)"
            )

    def _match_enhancer_shrapnel(self, item_name: str, value_ped: float,
                                  loot_timestamp: datetime) -> bool:
        """Check if a loot item is shrapnel from a recent enhancer break.

        Returns True if the item matched an already-recorded break.
        Non-shrapnel items always return False without side effects.

        The caller is responsible for buffering unmatched shrapnel
        items into ``_recent_shrapnel_items`` after the loot item is
        constructed — see :meth:`_buffer_unmatched_shrapnel`.
        """
        if item_name.lower() != "shrapnel":
            return False
        for i, (break_time, break_ped) in enumerate(self._recent_enhancer_breaks):
            if abs(loot_timestamp - break_time) > self.ENHANCER_SHRAPNEL_WINDOW:
                continue
            # Match by value: enhancer shrapnel value equals the enhancer's TT
            if abs(value_ped - break_ped) < 0.0001:
                # Consume this break so it doesn't match again
                self._recent_enhancer_breaks.pop(i)
                return True
        return False

    def _buffer_unmatched_shrapnel(self, enc: MobEncounter,
                                    loot_item: EncounterLootItem,
                                    timestamp: datetime) -> None:
        """Buffer a shrapnel loot item pending a future enhancer break.

        Called when shrapnel arrives in loot but no recent enhancer
        break explains it. If a break message arrives for the same
        PED value within ENHANCER_SHRAPNEL_WINDOW, the item will be
        retroactively flagged as enhancer shrapnel (and thereby
        excluded from ``effective_loot_ped``).

        Prunes entries older than 5x the window so the buffer can't
        grow unbounded on a long session.
        """
        if loot_item.item_name.lower() != "shrapnel":
            return
        self._recent_shrapnel_items.append(
            (timestamp, enc, loot_item, loot_item.value_ped),
        )
        cutoff = timestamp - self.ENHANCER_SHRAPNEL_WINDOW * 5
        self._recent_shrapnel_items = [
            s for s in self._recent_shrapnel_items if s[0] > cutoff
        ]

    def _match_loot_against_break(self, break_timestamp: datetime,
                                   break_ped: float) -> bool:
        """Check buffered unmatched shrapnel for a value match.

        Called when an enhancer break message arrives. If a recent
        shrapnel loot item matches the break's PED value, it's
        retroactively flagged as enhancer shrapnel (excluded from
        effective loot) and this method returns True. The caller
        should then skip adding the break to ``_recent_enhancer_breaks``.
        """
        for i, (loot_ts, enc, loot_item, value_ped) in enumerate(
            self._recent_shrapnel_items,
        ):
            if abs(break_timestamp - loot_ts) > self.ENHANCER_SHRAPNEL_WINDOW:
                continue
            if abs(value_ped - break_ped) < 0.0001:
                # Retroactive fix: flip the flag on the buffered item.
                # effective_loot_ped is a computed property, so the
                # UI will reflect the change on next render.
                loot_item.is_enhancer_shrapnel = True
                self._recent_shrapnel_items.pop(i)
                log.info(
                    "Retroactive shrapnel correlation: %.4f PED on %s "
                    "(break arrived after loot)",
                    value_ped, enc.mob_name,
                )
                self._tracking_log.session_info(
                    f"Shrapnel {value_ped:.2f} PED identified as enhancer "
                    "refund (retroactive)"
                )
                return True
        return False

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

        # Persist both sides of the merge in one transaction so a
        # crash can't leave target.merged_from pointing at source while
        # source.merged_into is still null (or vice versa). Rollback
        # on any failure puts both back in their pre-merge state on
        # disk. In-memory state is left merged; next restore will
        # rebuild from the (now rolled back) DB rows.
        try:
            with self._db.transaction():
                self._persist_encounter(target_enc)
                self._persist_encounter(open_enc)
        except Exception as e:
            log.error("Merge persistence failed, rolling back: %s", e)
            return False

        self._event_bus.publish(EVENT_HUNT_ENCOUNTER_ENDED, target_enc.to_dict())
        self._event_bus.publish(EVENT_OPEN_ENCOUNTER_UPDATED,
                                self._get_open_encounters_data())
        self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED,
                                self._build_summary())

        log.info("Merged open encounter %s into %s", open_enc.id[:8], target_enc.id[:8])
        return True

    def replay_enhancer_timeline(self, from_encounter_id: str | None = None) -> int:
        """Apply anchored enhancer timeline events to the current session.

        Phase 3 MVP behavior:
            * Loads anchored events from session_loadout_events (rows
              with anchor_kind IS NOT NULL).
            * Publishes EVENT_ENHANCER_TIMELINE_EDITED so UI panels can
              re-read the timeline, then recalculates encounter costs
              via the normal recalculate path so any gear overrides the
              user layered to match the anchored state take effect.
            * Returns the number of anchored events applied.

        Cost adjustments directly from enhancer deltas (e.g. "2 Economy
        enhancers reduce decay by 6.5%") are intentionally left to the
        gear override layer for Phase 3: the user records the state via
        the timeline dialog and adjusts the gear override to reflect
        the resulting decay. This keeps the cost math in a single
        predictable place instead of compounding two sources.

        *from_encounter_id* scopes the recalculation to encounters
        started at or after that encounter's start_time. Past encounters
        are not touched.
        """
        if not self._session:
            return 0
        try:
            events = self._db.get_anchored_loadout_events(self._session.id)
        except Exception as e:
            log.warning("replay_enhancer_timeline: load failed: %s", e)
            events = []

        cutoff = None
        if from_encounter_id:
            anchor_enc = self._find_encounter(from_encounter_id)
            if anchor_enc is not None:
                cutoff = anchor_enc.start_time

        try:
            if cutoff is not None:
                self.recalculate_session(from_timestamp=cutoff)
            else:
                self.recalculate_session()
        except TypeError:
            # Older recalculate_session without kwarg support.
            self.recalculate_session()
        except Exception as e:
            log.warning("replay_enhancer_timeline: recalc failed: %s", e)

        self._event_bus.publish(EVENT_ENHANCER_TIMELINE_EDITED, {
            "session_id": self._session.id,
            "event_count": len(events),
        })
        self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED, self._build_summary())
        return len(events)

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
                                self._build_summary())

        log.info("Abandoned open encounter %s (cost: %.2f PED)",
                 open_enc.id[:8], open_enc.cost)
        return True

    def resolve_open_encounter_as_kill(self, open_encounter_id: str,
                                         loot_ped: float | None = None) -> bool:
        """Mark an open encounter as a kill and optionally set its loot.

        When *loot_ped* is provided the encounter's loot_total_ped is
        overwritten; existing per-item rows are left alone for the loot
        editor to touch up afterward. The encounter is removed from the
        open list, persisted, and ``EVENT_HUNT_ENCOUNTER_ENDED`` plus
        session updates are published.
        """
        open_enc = self._find_open_encounter(open_encounter_id)
        if not open_enc:
            return False

        open_enc.outcome = "kill"
        open_enc.is_open_ended = False
        if loot_ped is not None:
            open_enc.loot_total_ped = float(loot_ped)
        self._open_encounters.remove(open_enc)

        self._persist_encounter(open_enc)
        self._event_bus.publish(EVENT_HUNT_ENCOUNTER_ENDED, open_enc.to_dict())
        self._event_bus.publish(EVENT_OPEN_ENCOUNTER_UPDATED,
                                self._get_open_encounters_data())
        self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED,
                                self._build_summary())

        log.info("Resolved open encounter %s as kill (loot: %.2f PED)",
                 open_enc.id[:8], open_enc.loot_total_ped)
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
                                self._build_summary())

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

    def _on_tool_filter_changed(self, _data):
        """Recalculate costs when tool cost filter settings change."""
        self._tool_filter.on_config_changed()
        if self._active:
            self.recalculate_session()

    def _on_gear_override_changed(self, _data):
        """User edited a gear override - recompute cost for the session.

        The override provider is already hot-loaded from the DB on every
        cost lookup, so we just need to rebuild the accumulated encounter
        costs and push fresh summaries.
        """
        if not self._active or not self._session:
            return
        try:
            self.recalculate_session()
        except Exception as e:
            log.warning("recalculate_session after gear override failed: %s", e)
        self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED, self._build_summary())

    def _on_session_markup_changed(self, _data):
        """Per-session (L) markup blob changed - publish a refresh.

        No cost recomputation is needed: markup only affects loot
        valuation, which MarkupResolver already consults lazily with the
        session_id passed by the dashboard.
        """
        if not self._active:
            return
        self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED, self._build_summary())

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

        self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED, self._build_summary())

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
            # Recalculate costs with new weapon signatures
            self.recalculate_session()
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

    def _recalculate_encounter_stats(self, enc: MobEncounter):
        """Recalculate encounter tool_stats and cost from the combat action log.

        Uses the combat log as source of truth for tool attribution and the
        tool filter for cost inclusion. This allows mid-hunt settings changes
        (gear updates, filter changes) to be reflected immediately.
        """
        if not self._combat_log:
            return

        actions = self._combat_log.get_by_encounter(enc.id)
        damage_actions = [
            a for a in actions
            if a.event_type in ("damage_dealt", "critical_hit")
        ]

        if not damage_actions:
            return

        enc.tool_stats.clear()
        enc.cost = 0.0
        for action in damage_actions:
            tool = action.tool_name or "Unknown"
            if tool not in enc.tool_stats:
                enc.tool_stats[tool] = EncounterToolStats(tool_name=tool)
            enc.tool_stats[tool].damage_dealt += action.amount
            enc.tool_stats[tool].shots_fired += 1
            if action.event_type == "critical_hit":
                enc.tool_stats[tool].critical_hits += 1
            cost = self._tool_inference.get_cost_per_shot(tool)
            if cost > 0 and self._tool_filter.should_include_cost(tool):
                enc.cost += cost

    def _restore_combat_log(self, session_id: str):
        """Reload combat events from DB into the session combat log."""
        if not self._combat_log:
            return

        for enc in self._session.encounters:
            rows = self._db.get_encounter_combat_events(enc.id)
            for row in rows:
                action = CombatAction(
                    id=row["id"],
                    encounter_id=row["encounter_id"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    event_type=row["event_type"],
                    amount=row.get("amount", 0.0),
                    tool_name=row.get("tool_name"),
                    tool_source=row.get("tool_source"),
                    confidence=row.get("inferred_confidence", 0.0),
                )
                self._combat_log.append(action)

        log.info("Restored %d combat actions from DB", len(self._combat_log))

    def recalculate_session(self):
        """Recalculate all encounter stats from the combat action log.

        Call this when settings change mid-session (tool filter, gear update)
        to recompute cost and tool attribution from raw events.
        """
        if not self._active or not self._session:
            return

        for enc in self._session.encounters:
            self._recalculate_encounter_stats(enc)

        # Also recalculate all alive encounters
        if self._manager:
            for enc, _state in self._manager.alive_encounters:
                self._recalculate_encounter_stats(enc)

        total_encounters = len(self._session.encounters)
        if self._manager:
            total_encounters += len(self._manager.alive_encounters)
        self._tracking_log.recalculated(total_encounters)
        self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED, self._build_summary())
        log.info("Session stats recalculated from combat log")

    # -- Crash recovery state ------------------------------------------

    def _compute_config_signature(self) -> str:
        """Hash the config inputs that affect session stats.

        The signature covers: blacklist version, tool filter rules,
        loadout cost-per-shot inputs, and custom markup state. If any
        of these change between sessions the stored encounter cost /
        effective loot values are stale and must be recomputed.
        """
        import hashlib
        parts = [
            str(sorted(getattr(self._config, "loot_blacklist", []) or [])),
            str(sorted(getattr(self._config, "tool_cost_filter", []) or [])),
            str(getattr(self._config, "cost_settings_version", 0)),
            str(getattr(self._config, "custom_markups_version", 0)),
        ]
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

    def _serialize_shrapnel_buffer(self) -> str:
        """Encode (timestamp, value_ped) pairs for the break buffer.

        Encounter/loot_item refs in _recent_shrapnel_items are NOT
        serialized — they'd need to be rehydrated from the encounter
        row on load, and the matching window is only 2 seconds anyway.
        Any buffered shrapnel older than the window is dropped on
        restore. The break buffer is just (timestamp, value) tuples.
        """
        return json.dumps([
            [ts.isoformat(), value]
            for ts, value in self._recent_enhancer_breaks
        ])

    def _save_recovery_state(self) -> None:
        """Persist all crash-recovery blobs for the current session.

        Called at the end of _persist_encounter so the engine state +
        shrapnel buffers + config hash are committed atomically with
        every kill. A crash between kills loses at most one encounter's
        worth of post-kill state — the engine resumes from the last
        finalized kill on restart.
        """
        if not self._session:
            return
        if self._config_signature_cached is None:
            self._config_signature_cached = self._compute_config_signature()
        try:
            enh_blob = json.dumps(self._enhancer_inference.to_dict())
            break_blob = self._serialize_shrapnel_buffer()
            self._db.save_session_recovery_state(
                self._session.id,
                enhancer_inference_state=enh_blob,
                break_buffer=break_blob,
                config_signature=self._config_signature_cached,
            )
        except Exception as e:
            log.warning("Failed to save session recovery state: %s", e)

    def _restore_recovery_state(self, session_id: str) -> None:
        """Hydrate enhancer inference + buffers + config hash from DB.

        Tools are NOT auto-registered here — the tracker re-registers
        them from the current catalog elsewhere in _try_restore_session.
        from_dict on an empty catalog is safe: register_tool() with a
        matching range is a no-op so loaded state survives; a changed
        range triggers a clean reset.
        """
        blobs = self._db.get_session_recovery_state(session_id)

        # Enhancer inference
        enh_blob = blobs.get("enhancer_inference_state")
        if enh_blob:
            try:
                self._enhancer_inference = EnhancerInferenceEngine.from_dict(
                    json.loads(enh_blob),
                )
                log.info("Restored enhancer inference for %d tool(s)",
                         len(self._enhancer_inference._tools))
            except (ValueError, TypeError, json.JSONDecodeError) as e:
                log.warning("Failed to restore enhancer inference: %s", e)

        # Break buffer — drop anything older than 5x window (same
        # cutoff policy used live in _buffer_unmatched_shrapnel).
        break_blob = blobs.get("break_buffer")
        if break_blob:
            try:
                raw = json.loads(break_blob)
                now = datetime.utcnow()
                cutoff = now - self.ENHANCER_SHRAPNEL_WINDOW * 5
                self._recent_enhancer_breaks = [
                    (datetime.fromisoformat(ts), value)
                    for ts, value in raw
                    if datetime.fromisoformat(ts) > cutoff
                ]
            except (ValueError, TypeError, json.JSONDecodeError) as e:
                log.warning("Failed to restore break buffer: %s", e)

        # Config signature — compare to current, trigger recalc on mismatch
        stored_sig = blobs.get("config_signature")
        current_sig = self._compute_config_signature()
        self._config_signature_cached = current_sig
        if stored_sig and stored_sig != current_sig:
            log.info("Config changed since last session (%s -> %s); "
                     "recalculating stats", stored_sig[:8], current_sig[:8])
            try:
                self.recalculate_session()
            except Exception as e:
                log.warning("Session recalc on restore failed: %s", e)

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

        # Persist the encounter (row may already exist from _ensure_encounter_in_db).
        # All encounter-scoped writes run in one transaction so a crash
        # mid-persist cannot leave partial tool_stats or half-written
        # loot rows — either everything lands or nothing does.
        self._ensure_encounter_in_db(encounter)
        with self._db.transaction():
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
            if encounter.loot_items:
                self._db.insert_encounter_loot_items(encounter.id, encounter.loot_items)
            # Crash-recovery blobs piggyback on the same tx so a crash
            # after the encounter commits but before the recovery save
            # can't leave the two out of sync.
            self._save_recovery_state()

        # Update running stats and free memory
        if self._running_stats:
            self._running_stats.on_encounter_finalized(encounter)
        # Strip loot items — already persisted to DB.
        # Keep tool_stats (small) since merge operations need them.
        encounter.loot_items = []

        # Window start for prepend-to-next: tool uses (heals, buffs,
        # idle shots) that happen after this time with no active
        # encounter will be attached to the next encounter that starts.
        if encounter.end_time:
            self._last_encounter_end_time = encounter.end_time

    def _start_timeout_checker(self):
        """Start periodic timeout checks for encounter closing and session inactivity."""
        self._cancel_timeout()

        def check():
            if not self._active or not self._manager:
                return

            try:
                # Check all alive encounters for timeout
                closed_list = self._manager.check_timeout()
                for ended in closed_list:
                    # Timeout from ACTIVE state (no loot) → open-ended
                    if ended.outcome == "timeout" and ended.damage_dealt > 0:
                        ended.is_open_ended = True
                        self._open_encounters.append(ended)
                        self._event_bus.publish(EVENT_OPEN_ENCOUNTER_UPDATED,
                                                self._get_open_encounters_data())
                    self._persist_encounter(ended)
                    self._event_bus.publish(EVENT_HUNT_ENCOUNTER_ENDED, ended.to_dict())
                if closed_list:
                    self._event_bus.publish(EVENT_HUNT_SESSION_UPDATED,
                                            self._build_summary())

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
