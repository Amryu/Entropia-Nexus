"""Session loadout manager — snapshots loadouts per session for cost tracking."""

import json
import threading
from datetime import datetime
from pathlib import Path

from ..core.logger import get_logger
from .enhancer_state import EnhancerState, MAX_STACK_SIZE
from .session import HuntSession, SessionLoadoutEntry
from .tool_inference import ToolInferenceEngine

log = get_logger("LoadoutManager")


class SessionLoadoutManager:
    """Manages loadout snapshots for hunt sessions.

    Responsibilities:
    - Evaluates loadouts using LoadoutCalculator (owns its own JS bridge)
    - Creates snapshots on session start
    - Handles copy-on-write logic (new snapshot on loadout change + combat)
    - Loads weapon signatures into ToolInferenceEngine
    - Tracks auto-detected unknown weapons
    """

    AUTO_DETECT_THRESHOLD = 3  # Unmatched shots before creating placeholder

    def __init__(self, config, db, data_client, tool_inference: ToolInferenceEngine):
        self._config = config
        self._db = db
        self._data_client = data_client
        self._tool_inference = tool_inference
        self._calculator = None          # Lazy-init LoadoutCalculator
        self._entity_data = None         # Lazy-loaded from DataClient
        self._active_loadout = None      # Latest from EVENT or cache
        self._active_stats = None        # LoadoutStats from evaluation
        self._session = None             # Current session reference
        self._combat_since_last_snapshot = False
        self._loot_since_last_snapshot = False
        self._calculator_ready = threading.Event()  # Signalled when init completes
        self._warmup_started = False

        # Enhancer tracking — overlays the loadout's enhancer fields
        self._enhancer_state: EnhancerState = EnhancerState()

        # Auto-detect unknown weapons
        self._unmatched_damage_values: list[float] = []

    @property
    def active_loadout(self):
        return self._active_loadout

    @property
    def active_stats(self):
        return self._active_stats

    @property
    def enhancer_state(self) -> EnhancerState:
        return self._enhancer_state

    def get_loadout_events(self) -> list[dict]:
        """Get loadout history events for the current session."""
        if not self._session:
            return []
        return self._db.get_session_loadout_events(self._session.id)

    def delete_loadout_event(self, event_id: int):
        """Delete a loadout history event by ID."""
        self._db.delete_loadout_event(event_id)

    @property
    def expected_dpp(self) -> float | None:
        """Expected damage per pec from the current loadout evaluation."""
        stats = self._active_stats
        if stats and hasattr(stats, 'total_damage') and hasattr(stats, 'cost'):
            if stats.cost > 0:
                return stats.total_damage / stats.cost  # cost is in PEC
        return None

    def warmup(self):
        """Pre-initialize the calculator and evaluate active loadout.

        Called after catchup completes so V8 + entity data loading
        doesn't block the watcher thread during a hunt session.
        Also evaluates the active loadout from cache so weapon signatures
        are ready before the first combat event.
        """
        if self._warmup_started:
            return
        self._warmup_started = True

        def _init():
            try:
                self._do_init_calculator()
                log.info("Calculator pre-warmed (V8 + %d entity types)",
                         len(self._entity_data) if self._entity_data else 0)
                # Pre-evaluate the active loadout from cache
                if not self._active_loadout:
                    self.load_active_loadout()
                if self._active_stats:
                    log.info("Active loadout evaluated: %s (cost=%.4f PEC/shot, dmg=%.1f-%.1f)",
                             (self._active_loadout or {}).get("Gear", {}).get("Weapon", {}).get("Name", "?"),
                             self._active_stats.cost,
                             self._active_stats.damage_interval_min,
                             self._active_stats.damage_interval_max)
                else:
                    log.warning("No active loadout or evaluation failed — cost tracking disabled")
            except Exception:
                log.exception("Calculator warmup failed")
            finally:
                self._calculator_ready.set()

        threading.Thread(target=_init, daemon=True, name="loadout-warmup").start()

    def _do_init_calculator(self):
        """Initialize V8 calculator + entity data (heavy work)."""
        if self._calculator is None:
            from ..loadout.calculator import LoadoutCalculator
            self._calculator = LoadoutCalculator(self._config.js_utils_path or None)
        if self._entity_data is None:
            self._entity_data = {
                "weapons": self._data_client.get_weapons() or [],
                "amplifiers": self._data_client.get_amplifiers() or [],
                "scopes_sights": self._data_client.get_scopes_and_sights() or [],
                "absorbers": self._data_client.get_absorbers() or [],
                "implants": self._data_client.get_implants() or [],
                "armors": self._data_client.get_armors() or [],
                "armor_platings": self._data_client.get_armor_platings() or [],
                "armor_sets": self._data_client.get_armor_sets() or [],
                "clothing": self._data_client.get_clothing() or [],
                "pets": self._data_client.get_pets() or [],
                "stimulants": self._data_client.get_stimulants() or [],
                "medical_tools": self._data_client.get_medical_tools() or [],
                "effects": self._data_client.get_effects() or [],
            }

    def _ensure_calculator(self):
        """Ensure calculator is ready, waiting for background warmup if needed."""
        if self._calculator is not None and self._entity_data is not None:
            return
        # If warmup is running, wait for it instead of doing double work
        if self._warmup_started:
            self._calculator_ready.wait(timeout=30)
        else:
            self._do_init_calculator()
            self._calculator_ready.set()

    def _evaluate(self, loadout: dict):
        """Evaluate a loadout with current enhancer state applied.

        Returns (weapon_name, stats) or (None, None).
        """
        self._ensure_calculator()
        weapon_name = (loadout.get("Gear", {}).get("Weapon", {}).get("Name") or "").strip()
        if not weapon_name:
            return None, None
        try:
            # Apply enhancer state overrides before evaluation
            effective_loadout = self._enhancer_state.apply_to_loadout(loadout)
            stats = self._calculator.evaluate(effective_loadout, self._entity_data)
            return weapon_name, stats
        except Exception as e:
            log.error("Loadout evaluation failed: %s", e)
            return weapon_name, None

    def load_active_loadout(self):
        """Load and cache active loadout from local file cache (no UI needed)."""
        loadout_id = self._config.active_loadout_id
        if not loadout_id:
            log.info("No active_loadout_id configured — skipping loadout load")
            return
        cache_path = Path(__file__).parent.parent / "data" / "cache" / "loadouts.json"
        if not cache_path.exists():
            log.warning("Loadout cache not found at %s", cache_path)
            return
        try:
            loadouts = json.loads(cache_path.read_text(encoding="utf-8"))
            for lo in loadouts:
                if lo.get("Id") == loadout_id:
                    self._active_loadout = lo
                    weapon_name, stats = self._evaluate(lo)
                    if stats:
                        self._active_stats = stats
                        self._tool_inference.load_from_loadout_stats(weapon_name, stats)
                        log.info("Loaded active loadout: %s", weapon_name)
                    else:
                        log.warning("Loadout found but evaluation returned no stats")
                    return
            log.warning("Loadout ID %s not found in cache (%d loadouts)", loadout_id, len(loadouts))
        except Exception:
            log.exception("Failed to load active loadout")

    def on_active_loadout_changed(self, loadout: dict, weapon_name: str | None, stats):
        """Called when loadout page publishes EVENT_ACTIVE_LOADOUT_CHANGED."""
        self._active_loadout = loadout
        self._active_stats = stats
        if weapon_name and stats:
            self._tool_inference.load_from_loadout_stats(weapon_name, stats)

        if self._session:
            # Reinitialize enhancer state from the new loadout
            self._enhancer_state = EnhancerState.from_loadout(loadout)

            # Create a history event for this loadout change
            enh_count = self._enhancer_state.total_enhancers()
            cost_str = f"{stats.cost:.2f} PEC/shot" if stats and stats.cost else "unknown"
            self._create_loadout_event(
                "edit",
                f"Loadout changed: {weapon_name or '?'} ({cost_str}, {enh_count} enhancers)",
            )
            self._maybe_create_snapshot("external_update")

    def start_session(self, session: HuntSession):
        """Create initial snapshot for a new session."""
        self._session = session
        self._combat_since_last_snapshot = False
        self._loot_since_last_snapshot = False
        self._unmatched_damage_values.clear()
        if not self._active_loadout:
            self.load_active_loadout()  # Try loading from cache
        if self._active_loadout:
            # Initialize enhancer state from the loadout
            self._enhancer_state = EnhancerState.from_loadout(self._active_loadout)
            self._create_snapshot("snapshot")
            # Create initial loadout event
            self._create_loadout_event("initial",
                f"Session started with {self._enhancer_state.total_count()} enhancers")

    def end_session(self):
        """Clear session state."""
        self._session = None
        self._combat_since_last_snapshot = False
        self._loot_since_last_snapshot = False
        self._unmatched_damage_values.clear()

    def on_enhancer_break(self, enhancer_name: str, item_name: str,
                          remaining: int, shrapnel_ped: float) -> dict | None:
        """Handle an enhancer break — decrement state, re-evaluate if slot depleted.

        Returns the delta dict if matched, None otherwise.
        Only re-evaluates the loadout when an active slot count actually changes
        (i.e., a stack was fully depleted), since the evaluator uses slot counts.
        """
        delta = self._enhancer_state.apply_break(enhancer_name, item_name, remaining)
        if not delta:
            return None

        # Only re-evaluate if a slot was depleted (active count changed)
        if delta.get("slot_changed") and self._active_loadout:
            weapon_name, stats = self._evaluate(self._active_loadout)
            if stats:
                self._active_stats = stats
                self._tool_inference.load_from_loadout_stats(weapon_name, stats)
                log.info("Slot depleted — re-evaluated: cost=%.4f PEC/shot, "
                         "%d→%d active slots", stats.cost,
                         delta["old_active"], delta["new_active"])

        # Persist as an incremental event (no full loadout stored)
        if self._session:
            desc = (f"{delta['category']}.{delta['slot']} "
                    f"{delta['old_total']}→{delta['new_total']} total"
                    + (f", slots {delta['old_active']}→{delta['new_active']}"
                       if delta.get("slot_changed") else "")
                    + f" ({enhancer_name} on {item_name})")
            self._db.insert_loadout_event(
                session_id=self._session.id,
                timestamp=datetime.utcnow().isoformat(),
                event_type="enhancer_break",
                description=desc,
                enhancer_delta=json.dumps(delta),
                cost_per_shot=self._active_stats.cost if self._active_stats else None,
            )

        return delta

    def on_enhancer_adjust(self, category: str, slot_key: str,
                           num_slots: int, stack_size: int = MAX_STACK_SIZE) -> dict | None:
        """Handle a manual enhancer adjustment by the user.

        Sets the number of slots and stack size for a specific enhancer type.
        Returns the delta dict.
        """
        from .enhancer_state import EnhancerSlot
        old_slot = self._enhancer_state.get_slot(category, slot_key)
        old_active = old_slot.active_slots
        old_total = old_slot.total_count

        new_slot = EnhancerSlot.from_loadout(num_slots, stack_size)
        self._enhancer_state.set_slot(category, slot_key, new_slot)

        delta = {
            "category": category,
            "slot": slot_key,
            "old_active": old_active,
            "new_active": new_slot.active_slots,
            "old_total": old_total,
            "new_total": new_slot.total_count,
            "slot_changed": old_active != new_slot.active_slots,
        }

        # Re-evaluate
        if self._active_loadout:
            weapon_name, stats = self._evaluate(self._active_loadout)
            if stats:
                self._active_stats = stats
                self._tool_inference.load_from_loadout_stats(weapon_name, stats)

        # Persist as adjustment event
        if self._session:
            desc = f"Manual: {category}.{slot_key} {old_active}→{new_slot.active_slots} slots"
            self._db.insert_loadout_event(
                session_id=self._session.id,
                timestamp=datetime.utcnow().isoformat(),
                event_type="enhancer_adjust",
                description=desc,
                enhancer_delta=json.dumps(delta),
                cost_per_shot=self._active_stats.cost if self._active_stats else None,
            )

        log.info("Enhancer adjusted: %s.%s %d→%d slots", category, slot_key, old_active, new_slot.active_slots)
        return delta

    def on_tool_detected(self, tool_name: str, cost_per_shot: float = 0,
                         damage_min: float = 0, damage_max: float = 0):
        """Register a newly detected tool (from OCR) that wasn't in the loadout.

        Adds a weapon signature and creates a history event.
        """
        if damage_max > 0:
            self._tool_inference.load_signature(
                tool_name, damage_min, damage_max,
                (damage_min + damage_max) / 2,
                cost_per_shot,
            )

        if self._session:
            self._db.insert_loadout_event(
                session_id=self._session.id,
                timestamp=datetime.utcnow().isoformat(),
                event_type="tool_detected",
                description=f"Auto-detected: {tool_name}",
                tool_name=tool_name,
                cost_per_shot=cost_per_shot,
                damage_min=damage_min,
                damage_max=damage_max,
            )
        log.info("Tool detected and registered: %s", tool_name)

    def _create_loadout_event(self, event_type: str, description: str):
        """Create a loadout event with current state."""
        if not self._session:
            return
        self._db.insert_loadout_event(
            session_id=self._session.id,
            timestamp=datetime.utcnow().isoformat(),
            event_type=event_type,
            description=description,
            loadout_data=json.dumps(self._active_loadout) if self._active_loadout else None,
            cost_per_shot=self._active_stats.cost if self._active_stats else None,
            damage_min=self._active_stats.damage_interval_min if self._active_stats else None,
            damage_max=self._active_stats.damage_interval_max if self._active_stats else None,
        )

    def restore_session(self, session: HuntSession):
        """Restore session state from DB data (after restart).

        Reconstructs enhancer state by replaying loadout events, then
        re-evaluates the loadout with the correct enhancer counts.
        """
        self._session = session
        self._combat_since_last_snapshot = False
        self._loot_since_last_snapshot = False
        self._unmatched_damage_values.clear()

        # Load the base loadout from the latest snapshot
        if not self._active_loadout and session.loadout_entries:
            latest = session.loadout_entries[-1]
            if latest.loadout_data:
                self._active_loadout = latest.loadout_data

        if not self._active_loadout:
            log.warning("No loadout to restore — no cost tracking")
            return

        # Initialize enhancer state from the base loadout
        self._enhancer_state = EnhancerState.from_loadout(self._active_loadout)

        # Replay loadout events to reconstruct current enhancer state
        events = self._db.get_session_loadout_events(session.id)
        break_count = 0
        adjust_count = 0
        for evt in events:
            evt_type = evt.get("event_type", "")
            delta_json = evt.get("enhancer_delta")
            if evt_type in ("enhancer_break", "enhancer_adjust") and delta_json:
                try:
                    delta = json.loads(delta_json)
                    cat = delta.get("category", "")
                    slot = delta.get("slot", "")
                    new_count = delta.get("new_count", 0)
                    self._enhancer_state.set_slot(cat, slot, new_count)
                    if evt_type == "enhancer_break":
                        break_count += 1
                    else:
                        adjust_count += 1
                except (json.JSONDecodeError, KeyError):
                    pass
            elif evt_type == "tool_detected":
                # Re-register detected tools
                tool = evt.get("tool_name")
                if tool:
                    self._tool_inference.load_signature(
                        tool,
                        evt.get("damage_min", 0),
                        evt.get("damage_max", 0),
                        (evt.get("damage_min", 0) + evt.get("damage_max", 0)) / 2,
                        evt.get("cost_per_shot", 0),
                    )

        # Evaluate with reconstructed enhancer state
        weapon_name, stats = self._evaluate(self._active_loadout)
        if stats:
            self._active_stats = stats
            self._tool_inference.load_from_loadout_stats(weapon_name, stats)
            log.info("Loadout restored: %s (cost=%.4f PEC/shot, %d breaks replayed, %d adjustments)",
                     weapon_name, stats.cost, break_count, adjust_count)
        else:
            log.warning("Loadout evaluation failed on restore — no cost tracking")
        log.info("Enhancer state: %d total enhancers", self._enhancer_state.total_count())

    def on_combat(self):
        """Mark that combat happened since last snapshot."""
        self._combat_since_last_snapshot = True

    def on_loot(self):
        """Mark that loot was received — seals the current snapshot."""
        self._loot_since_last_snapshot = True

    def on_unmatched_damage(self, damage: float):
        """Track damage values that didn't match any known weapon signature.

        After AUTO_DETECT_THRESHOLD unmatched shots, creates a placeholder
        session loadout entry for the unknown weapon.
        """
        if not self._session or damage <= 0:
            return
        self._unmatched_damage_values.append(damage)
        if len(self._unmatched_damage_values) >= self.AUTO_DETECT_THRESHOLD:
            self._create_auto_detected_entry()

    def _maybe_create_snapshot(self, source: str):
        """Create new snapshot if conditions met (combat or loot since last)."""
        if not self._session or not self._active_loadout:
            return
        if self._combat_since_last_snapshot or self._loot_since_last_snapshot:
            self._create_snapshot(source)

    def _create_snapshot(self, source: str):
        """Create and persist a loadout snapshot."""
        if not self._session:
            return
        weapon_name, stats = self._evaluate(self._active_loadout) if self._active_loadout else (None, None)
        if stats:
            self._tool_inference.load_from_loadout_stats(weapon_name, stats)
        entry = SessionLoadoutEntry(
            session_id=self._session.id,
            loadout_data=self._active_loadout or {},
            weapon_name=weapon_name,
            cost_per_shot=stats.cost if stats and stats.cost else 0,
            damage_min=stats.damage_interval_min if stats else 0,
            damage_max=stats.damage_interval_max if stats else 0,
            crit_damage=stats.crit_damage if stats else 1.0,
            source=source,
        )
        entry.id = self._db.insert_session_loadout(
            self._session.id, entry.timestamp.isoformat(),
            json.dumps(entry.loadout_data), weapon_name,
            entry.cost_per_shot, entry.damage_min, entry.damage_max,
            source, entry.crit_damage,
        )
        self._session.loadout_entries.append(entry)
        self._combat_since_last_snapshot = False
        self._loot_since_last_snapshot = False
        log.info("Loadout snapshot created: weapon=%s cost/shot=%.4f source=%s",
                 weapon_name, entry.cost_per_shot, source)

    def _create_auto_detected_entry(self):
        """Create a placeholder entry for an unknown weapon from observed damage."""
        if not self._session or not self._unmatched_damage_values:
            return
        damage_min = min(self._unmatched_damage_values)
        damage_max = max(self._unmatched_damage_values)
        now = datetime.utcnow()

        entry = SessionLoadoutEntry(
            session_id=self._session.id,
            timestamp=now,
            loadout_data={},
            weapon_name="Unknown weapon",
            cost_per_shot=0.0,
            damage_min=damage_min,
            damage_max=damage_max,
            source="auto_detected",
        )
        entry.id = self._db.insert_session_loadout(
            self._session.id, now.isoformat(),
            "{}", "Unknown weapon",
            0.0, damage_min, damage_max, "auto_detected",
        )
        self._session.loadout_entries.append(entry)
        self._unmatched_damage_values.clear()
        log.info("Auto-detected unknown weapon: damage range %.1f - %.1f",
                 damage_min, damage_max)
