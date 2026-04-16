"""Encounter manager — attributes combat and loot events to mob encounters.

Supports multiple alive encounters simultaneously. When the player switches
targets (detected via OCR), the old encounter is suspended and the new one
becomes active. Loot is attributed to the most recently fought encounter
that hasn't received loot yet.
"""

import uuid
from datetime import datetime, timedelta
from enum import Enum, auto

from ..core.logger import get_logger
from .session import MobEncounter, EncounterToolStats, HuntSession

log = get_logger("EncounterMgr")


class EncounterState(Enum):
    IDLE = auto()       # No active encounter
    ACTIVE = auto()     # Combat in progress
    CLOSING = auto()    # Loot received, waiting for next shot or timeout


class EncounterManager:
    """Attributes combat/loot events to mob encounters using OCR and timing.

    Multi-encounter model:
    - Multiple encounters can be alive simultaneously (active + suspended)
    - The active encounter receives all combat events
    - Target switching suspends the old encounter and activates/creates the new one
    - Loot is attributed to the best candidate (most recently fought without loot)
    - Suspended encounters auto-close after the configured timeout
    """

    # Loot deduplication: skip identical loot groups arriving within this window
    LOOT_DEDUP_WINDOW = timedelta(seconds=2)

    # How long after an encounter closes we still accept late-arriving loot.
    # Covers lag / OCR death detection racing the loot drop. Loot arriving
    # after this window is truly orphaned and gets dropped.
    POST_KILL_LOOT_WINDOW = timedelta(seconds=5)

    def __init__(self, config, session: HuntSession):
        self._config = config
        self._session = session
        self._current_tool: str | None = None

        # Active encounter — receives combat events
        self._active: MobEncounter | None = None

        # All alive encounters: enc_id → (encounter, state, last_event_time)
        self._alive: dict[str, tuple[MobEncounter, EncounterState, datetime]] = {}

        # HP tracking for same-name mob differentiation
        # enc_id → last known HP fraction (0.0–1.0)
        self._encounter_hp: dict[str, float] = {}

        # Timing constants from config
        self._close_timeout = timedelta(
            milliseconds=config.encounter_close_timeout_ms
        )
        self._loot_close_timeout = timedelta(
            milliseconds=getattr(config, 'loot_close_timeout_ms', 3000)
        )
        self._max_duration = timedelta(
            milliseconds=getattr(config, 'max_encounter_duration_ms', 600000)
        )

        # Loot deduplication state
        self._last_loot_fingerprint: tuple | None = None
        self._last_loot_time: datetime | None = None

        # Recently closed encounters kept as a fallback for late loot.
        # (close_time, encounter) tuples, pruned on access to the
        # POST_KILL_LOOT_WINDOW.
        self._recently_closed: list[tuple[datetime, MobEncounter]] = []

    @property
    def state(self) -> EncounterState:
        """State of the active encounter."""
        if self._active and self._active.id in self._alive:
            return self._alive[self._active.id][1]
        return EncounterState.IDLE

    @property
    def current_encounter(self) -> MobEncounter | None:
        """The active encounter receiving combat events."""
        return self._active

    @property
    def alive_encounters(self) -> list[tuple[MobEncounter, EncounterState]]:
        """All alive encounters with their state, active first."""
        result = []
        for enc, state, _ts in self._alive.values():
            result.append((enc, state))
        # Sort: active first, then by last event time descending
        result.sort(key=lambda x: (0 if x[0] is self._active else 1))
        return result

    def set_current_tool(self, tool_name: str | None):
        """Update the current tool (from OCR or loadout)."""
        self._current_tool = tool_name

    def on_hp_update(self, hp_pct: float | None):
        """Update the HP reading for the active encounter (from OCR)."""
        if self._active and hp_pct is not None:
            self._encounter_hp[self._active.id] = hp_pct

    def _is_likely_new_mob(self, enc: MobEncounter, hp_pct: float | None) -> bool:
        """Heuristic: is this likely a NEW mob of the same name?

        Returns True if HP jumped significantly upward after damage was dealt.
        This indicates the old mob died and a new one with the same name was
        locked. Not 100% reliable (some mobs regenerate HP) but best available.
        """
        if hp_pct is None or enc.damage_dealt == 0:
            return False

        last_hp = self._encounter_hp.get(enc.id)
        if last_hp is None:
            return False

        # HP increased significantly (>30% jump) after we dealt damage
        hp_jump = hp_pct - last_hp
        return hp_jump > 0.30

    def on_mob_name_detected(self, mob_name: str, confidence: float = 1.0,
                              source: str = "ocr",
                              hp_pct: float | None = None) -> None:
        """Handle OCR-detected mob name — switch active encounter.

        Does NOT close encounters. Suspends the current active and
        activates/creates the encounter for mob_name.

        Same-name mob differentiation: if the active encounter has the same
        mob name but the HP bar jumped significantly higher than expected
        (after damage was dealt), it's likely a new mob of the same type.
        """
        now = datetime.utcnow()

        # Placeholder adoption: if the active encounter is an anonymous
        # placeholder (created by combat arriving before any OCR), rename it
        # in place so its early damage/tool_stats aren't orphaned onto a
        # phantom "Unknown" entry. Only adopt interpolated placeholders —
        # user- and OCR-sourced names are authoritative and must still
        # trigger a target switch.
        if (self._active
                and self._active.mob_name_source == "interpolated"
                and mob_name):
            log.info("Adopted placeholder encounter %s → %s",
                     self._active.id[:8], mob_name)
            self._active.mob_name = mob_name
            self._active.mob_name_source = source
            self._active.confidence = max(self._active.confidence, confidence)
            if hp_pct is not None:
                self._encounter_hp[self._active.id] = hp_pct
            self._update_alive(self._active.id, EncounterState.ACTIVE, now)
            return

        # Same mob as active → check if HP suggests a different individual
        if self._active and self._active.mob_name == mob_name:
            if self._is_likely_new_mob(self._active, hp_pct):
                # HP jumped up after we dealt damage → new mob of same name
                log.info("Same-name mob detected: HP jumped, starting new encounter (%s)",
                         mob_name)
                enc = self._create_encounter(mob_name, source, confidence, now)
                self._set_active(enc, now)
                if hp_pct is not None:
                    self._encounter_hp[enc.id] = hp_pct
            else:
                self._active.confidence = max(self._active.confidence, confidence)
                if hp_pct is not None:
                    self._encounter_hp[self._active.id] = hp_pct
            return

        # Check if we already have a suspended encounter for this mob
        existing = self._find_alive_by_mob(mob_name)
        if existing:
            self._set_active(existing, now)
            existing.confidence = max(existing.confidence, confidence)
            if hp_pct is not None:
                self._encounter_hp[existing.id] = hp_pct
            log.info("Resumed encounter %s (%s)", existing.id[:8], mob_name)
        else:
            # New mob — create new encounter, suspend old
            enc = self._create_encounter(mob_name, source, confidence, now)
            self._set_active(enc, now)
            if hp_pct is not None:
                self._encounter_hp[enc.id] = hp_pct
            log.info("Started encounter %s (%s)", enc.id[:8], mob_name)

    def on_damage_dealt(self, amount: float, is_crit: bool = False,
                        timestamp: datetime | None = None) -> MobEncounter | None:
        """Handle player dealing damage — routed to active encounter.

        If the active encounter is in CLOSING state (loot received), it is
        closed as a kill and a new encounter is started for the new mob.
        Returns the closed encounter if one was finalized, else None.
        """
        now = timestamp or datetime.utcnow()

        # If active encounter already received loot, close it and start fresh
        closed = None
        if self._active and self._active.id in self._alive:
            _enc, state, _ts = self._alive[self._active.id]
            if state == EncounterState.CLOSING:
                closed = self._close_encounter(self._active, now, outcome="kill")

        self._ensure_encounter(now)

        enc = self._active
        if not enc:
            return closed

        enc.damage_dealt += amount
        enc.shots_fired += 1
        if is_crit:
            enc.critical_hits += 1

        # Per-tool attribution
        tool = self._current_tool or "Unknown"
        if tool not in enc.tool_stats:
            enc.tool_stats[tool] = EncounterToolStats(tool_name=tool)
        enc.tool_stats[tool].damage_dealt += amount
        enc.tool_stats[tool].shots_fired += 1
        if is_crit:
            enc.tool_stats[tool].critical_hits += 1

        self._update_alive(enc.id, EncounterState.ACTIVE, now)
        return closed

    def on_damage_received(self, amount: float,
                           timestamp: datetime | None = None) -> MobEncounter | None:
        """Handle player receiving damage. Returns closed encounter if any."""
        now = timestamp or datetime.utcnow()

        # Close CLOSING encounter on new combat
        closed = None
        if self._active and self._active.id in self._alive:
            _enc, state, _ts = self._alive[self._active.id]
            if state == EncounterState.CLOSING:
                closed = self._close_encounter(self._active, now, outcome="kill")

        self._ensure_encounter(now)

        if self._active:
            self._active.damage_taken += amount
            self._update_alive(self._active.id, None, now)
        return closed

    def on_heal(self, amount: float, timestamp: datetime | None = None) -> None:
        """Handle healing received."""
        if self._active:
            self._active.heals_received += amount

    def on_player_avoid(self, timestamp: datetime | None = None) -> None:
        """Player evaded/dodged/jammed a mob attack."""
        if self._active:
            self._active.player_avoids += 1

    def on_target_avoid(self, timestamp: datetime | None = None) -> None:
        """Mob evaded/dodged/jammed a player attack."""
        now = timestamp or datetime.utcnow()
        self._ensure_encounter(now)
        if self._active:
            self._active.target_avoids += 1
            self._update_alive(self._active.id, None, now)

    def on_mob_miss(self, timestamp: datetime | None = None) -> None:
        """Mob missed the player (separate from avoid)."""
        if self._active:
            self._active.mob_misses += 1

    def on_deflect(self, timestamp: datetime | None = None) -> None:
        """Player deflected a mob attack."""
        if self._active:
            self._active.deflects += 1

    def on_block(self, timestamp: datetime | None = None) -> None:
        """Player blocked a mob attack (0.0 damage received)."""
        if self._active:
            self._active.blocks += 1

    def on_loot_group(self, total_ped: float, loot_items: list | None = None,
                      timestamp: datetime | None = None) -> MobEncounter | None:
        """Handle loot drop — attribute to the best alive encounter.

        Finds the most recently fought encounter that hasn't received loot.
        Returns the encounter that received the loot (may differ from active).
        """
        now = timestamp or datetime.utcnow()

        # Deduplication
        first_item = (loot_items[0].item_name if loot_items else "")
        fingerprint = (round(total_ped, 4), len(loot_items) if loot_items else 0, first_item)
        if (self._last_loot_fingerprint == fingerprint
                and self._last_loot_time is not None
                and (now - self._last_loot_time) < self.LOOT_DEDUP_WINDOW):
            log.debug("Duplicate loot group skipped: %s", fingerprint)
            return None
        self._last_loot_fingerprint = fingerprint
        self._last_loot_time = now

        # Find best candidate for this loot
        target = self._find_loot_target(now)
        if not target:
            return None

        target.loot_total_ped += total_ped
        if loot_items:
            target.loot_items.extend(loot_items)
        target.outcome = "kill"
        self._update_alive(target.id, EncounterState.CLOSING, now)

        log.info("Loot %.2f PED attributed to encounter %s (%s)",
                 total_ped, target.id[:8], target.mob_name)
        return target

    def on_death(self, mob_name: str, timestamp: datetime | None = None) -> MobEncounter | None:
        """Handle player death — close the active encounter immediately.

        Returns the closed encounter (now open-ended), or None.
        """
        if not self._active:
            return None

        now = timestamp or datetime.utcnow()
        enc = self._active
        enc.outcome = "death"
        enc.death_count += 1
        enc.killed_by_mob = mob_name
        enc.is_open_ended = True

        if enc.mob_name == "Unknown" and mob_name:
            enc.mob_name = mob_name
            enc.mob_name_source = "death_message"

        return self._close_encounter(enc, now)

    def check_timeout(self) -> list[MobEncounter]:
        """Check all alive encounters for timeout.

        Returns list of encounters that were closed.
        """
        if not self._alive:
            return []

        now = datetime.utcnow()
        closed = []

        for enc_id in list(self._alive.keys()):
            enc, state, last_event = self._alive[enc_id]

            # Max duration cap
            duration = now - enc.start_time
            if duration > self._max_duration:
                log.warning("Encounter %s exceeded max duration (%.0fs), force closing",
                            enc.id[:8], duration.total_seconds())
                closed.append(self._close_encounter(enc, now, outcome="timeout"))
                continue

            # CLOSING state: fast timeout (loot received = kill confirmed)
            if state == EncounterState.CLOSING:
                if (now - last_event) > self._loot_close_timeout:
                    closed.append(self._close_encounter(enc, now, outcome="kill"))
                    continue

            # ACTIVE state: standard timeout (combat without loot)
            if state == EncounterState.ACTIVE:
                if (now - last_event) > self._close_timeout:
                    closed.append(self._close_encounter(enc, now, outcome="timeout"))
                    continue

        return closed

    def force_close(self) -> list[MobEncounter]:
        """Force-close all alive encounters (e.g., session stop)."""
        now = datetime.utcnow()
        closed = []
        for enc_id in list(self._alive.keys()):
            enc, _state, _ts = self._alive[enc_id]
            closed.append(self._close_encounter(enc, now, outcome="force_closed"))
        return closed

    # -- Internal helpers -----------------------------------------------------

    def _ensure_encounter(self, now: datetime):
        """Create an encounter if none is active (anonymous mob)."""
        if not self._active:
            mob_name = self._session.primary_mob or "Unknown"
            source = "user" if self._session.primary_mob else "interpolated"
            enc = self._create_encounter(mob_name, source, 0.5, now)
            self._set_active(enc, now)

    def _create_encounter(self, mob_name: str, source: str,
                           confidence: float, now: datetime) -> MobEncounter:
        """Create a new encounter and register it as alive."""
        enc = MobEncounter(
            id=str(uuid.uuid4()),
            session_id=self._session.id,
            mob_name=mob_name,
            mob_name_source=source,
            start_time=now,
            confidence=confidence,
        )
        self._alive[enc.id] = (enc, EncounterState.ACTIVE, now)
        return enc

    def _set_active(self, enc: MobEncounter, now: datetime):
        """Make an encounter the active one (suspend the previous)."""
        self._active = enc
        self._update_alive(enc.id, EncounterState.ACTIVE, now)

    def _update_alive(self, enc_id: str, new_state: EncounterState | None,
                       now: datetime):
        """Update an alive encounter's state and/or last event time."""
        if enc_id not in self._alive:
            return
        enc, state, _ts = self._alive[enc_id]
        self._alive[enc_id] = (enc, new_state or state, now)

    def _find_alive_by_mob(self, mob_name: str) -> MobEncounter | None:
        """Find an alive encounter matching a mob name."""
        for enc, _state, _ts in self._alive.values():
            if enc.mob_name == mob_name:
                return enc
        return None

    def _find_loot_target(self, now: datetime) -> MobEncounter | None:
        """Find the best encounter to receive loot.

        Priority: most recently active encounter that has damage but no loot.
        If multiple candidates, prefer the one with the most recent event time.

        Fallback: if no alive encounter fits, check recently-closed
        encounters within POST_KILL_LOOT_WINDOW. This catches the race
        where a kill finalizes before its loot drop arrives. The
        caller is responsible for re-persisting the encounter if it
        was already flushed to DB.
        """
        candidates = []
        for enc, state, last_event in self._alive.values():
            if enc.damage_dealt > 0 and enc.loot_total_ped == 0:
                candidates.append((enc, last_event))

        if candidates:
            # Sort by last event time descending — most recently fought first
            candidates.sort(key=lambda x: x[1], reverse=True)
            if len(candidates) > 1:
                # Active may be a fresh switch; prefer the recently-fought one
                return candidates[0][0]
            return candidates[0][0]

        # No alive candidates — check recently-closed for late loot.
        self._prune_recently_closed(now)
        if self._recently_closed:
            # Most recent first; prefer ones without loot yet
            for _t, enc in reversed(self._recently_closed):
                if enc.loot_total_ped == 0:
                    return enc
            # Everything already has loot — tack it onto the most recent
            return self._recently_closed[-1][1]

        # Final fallback: active encounter even if it has no damage yet
        return self._active

    def _close_encounter(self, enc: MobEncounter, now: datetime,
                          outcome: str | None = None) -> MobEncounter:
        """Close an encounter and remove it from the alive set."""
        enc.end_time = now
        if outcome:
            enc.outcome = outcome
        self._session.encounters.append(enc)
        self._alive.pop(enc.id, None)
        self._encounter_hp.pop(enc.id, None)
        if self._active is enc:
            self._active = None
        # Keep a short-window reference so late-arriving loot can still
        # attach (see _find_loot_target). Pruning happens on access.
        self._recently_closed.append((now, enc))
        return enc

    def _prune_recently_closed(self, now: datetime) -> None:
        cutoff = now - self.POST_KILL_LOOT_WINDOW
        self._recently_closed = [
            (t, e) for t, e in self._recently_closed if t > cutoff
        ]
