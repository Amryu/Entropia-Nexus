"""Encounter manager — attributes combat and loot events to mob encounters."""

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

    State machine:
    - IDLE: waiting for combat event or mob name OCR
    - ACTIVE: attributing events to current encounter
    - CLOSING: loot received, waiting for next shot or encounter_close_timeout

    Multi-mob handling:
    - OCR mob name change closes current encounter, opens new one
    - Events within attribution_window of a name change go to the new encounter
    """

    # Loot deduplication: skip identical loot groups arriving within this window
    LOOT_DEDUP_WINDOW = timedelta(seconds=2)

    def __init__(self, config, session: HuntSession):
        self._config = config
        self._session = session
        self._state = EncounterState.IDLE
        self._current_encounter: MobEncounter | None = None
        self._current_tool: str | None = None
        self._last_event_time: datetime | None = None

        # Timing constants from config (converted to timedelta)
        self._close_timeout = timedelta(
            milliseconds=config.encounter_close_timeout_ms
        )
        self._loot_close_timeout = timedelta(
            milliseconds=getattr(config, 'loot_close_timeout_ms', 3000)
        )
        self._max_duration = timedelta(
            milliseconds=getattr(config, 'max_encounter_duration_ms', 600000)
        )
        self._attribution_window = timedelta(
            milliseconds=config.attribution_window_ms
        )

        # Loot deduplication state
        self._last_loot_fingerprint: tuple | None = None
        self._last_loot_time: datetime | None = None

    @property
    def state(self) -> EncounterState:
        return self._state

    @property
    def current_encounter(self) -> MobEncounter | None:
        return self._current_encounter

    def set_current_tool(self, tool_name: str | None):
        """Update the current tool (from OCR or loadout)."""
        self._current_tool = tool_name

    def on_mob_name_detected(self, mob_name: str, confidence: float = 1.0,
                              source: str = "ocr") -> MobEncounter | None:
        """Handle OCR-detected mob name. Returns ended encounter if target changed."""
        ended = None
        now = datetime.utcnow()

        if self._current_encounter:
            if self._current_encounter.mob_name != mob_name:
                # Target changed — close current, start new
                outcome = "kill" if self._current_encounter.loot_total_ped > 0 else "timeout"
                ended = self._close_encounter(now, outcome=outcome)
                self._start_encounter(mob_name, source, confidence, now)
            else:
                # Same mob — update confidence
                self._current_encounter.confidence = max(
                    self._current_encounter.confidence, confidence
                )
        elif self._state == EncounterState.IDLE:
            # First mob detected
            self._start_encounter(mob_name, source, confidence, now)

        return ended

    def on_damage_dealt(self, amount: float, is_crit: bool = False,
                        timestamp: datetime | None = None) -> None:
        """Handle player dealing damage."""
        now = timestamp or datetime.utcnow()
        self._ensure_encounter(now)

        enc = self._current_encounter
        if not enc:
            return

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

        self._state = EncounterState.ACTIVE
        self._last_event_time = now

    def on_damage_received(self, amount: float, timestamp: datetime | None = None) -> None:
        """Handle player receiving damage."""
        now = timestamp or datetime.utcnow()
        self._ensure_encounter(now)

        if self._current_encounter:
            self._current_encounter.damage_taken += amount
            self._last_event_time = now

    def on_heal(self, amount: float, timestamp: datetime | None = None) -> None:
        """Handle healing received."""
        if self._current_encounter:
            self._current_encounter.heals_received += amount

    def on_player_avoid(self, timestamp: datetime | None = None) -> None:
        """Player evaded/dodged/jammed a mob attack."""
        if self._current_encounter:
            self._current_encounter.player_avoids += 1

    def on_target_avoid(self, timestamp: datetime | None = None) -> None:
        """Mob evaded/dodged/jammed a player attack."""
        now = timestamp or datetime.utcnow()
        self._ensure_encounter(now)
        if self._current_encounter:
            self._current_encounter.target_avoids += 1
            self._last_event_time = now

    def on_mob_miss(self, timestamp: datetime | None = None) -> None:
        """Mob missed the player (separate from avoid)."""
        if self._current_encounter:
            self._current_encounter.mob_misses += 1

    def on_deflect(self, timestamp: datetime | None = None) -> None:
        """Player deflected a mob attack."""
        if self._current_encounter:
            self._current_encounter.deflects += 1

    def on_block(self, timestamp: datetime | None = None) -> None:
        """Player blocked a mob attack (0.0 damage received)."""
        if self._current_encounter:
            self._current_encounter.blocks += 1

    def on_loot_group(self, total_ped: float, loot_items: list | None = None,
                      timestamp: datetime | None = None) -> None:
        """Handle loot drop — attribute to current/most recent encounter."""
        if not self._current_encounter:
            return

        now = timestamp or datetime.utcnow()

        # Deduplication: skip if identical loot group arrives within window
        first_item = (loot_items[0].item_name if loot_items else "")
        fingerprint = (round(total_ped, 4), len(loot_items) if loot_items else 0, first_item)
        if (self._last_loot_fingerprint == fingerprint
                and self._last_loot_time is not None
                and (now - self._last_loot_time) < self.LOOT_DEDUP_WINDOW):
            log.debug("Duplicate loot group skipped: %s", fingerprint)
            return
        self._last_loot_fingerprint = fingerprint
        self._last_loot_time = now

        self._current_encounter.loot_total_ped += total_ped
        if loot_items:
            self._current_encounter.loot_items.extend(loot_items)
        self._current_encounter.outcome = "kill"
        self._state = EncounterState.CLOSING
        self._last_event_time = now

    def on_death(self, mob_name: str, timestamp: datetime | None = None) -> MobEncounter | None:
        """Handle player death — close encounter immediately.

        Returns the closed encounter (now open-ended), or None if no encounter was active.
        The mob_name comes from the death message (adjective already stripped).
        """
        if not self._current_encounter:
            return None

        now = timestamp or datetime.utcnow()
        enc = self._current_encounter
        enc.outcome = "death"
        enc.death_count += 1
        enc.killed_by_mob = mob_name
        enc.is_open_ended = True

        # Use death mob name if encounter had no OCR detection
        if enc.mob_name == "Unknown" and mob_name:
            enc.mob_name = mob_name
            enc.mob_name_source = "death_message"

        return self._close_encounter(now)

    def check_timeout(self) -> MobEncounter | None:
        """Check if the current encounter should be closed due to timeout.
        Call this periodically (e.g., every second).
        Returns the ended encounter if closed, or None.
        """
        if not self._current_encounter:
            return None

        now = datetime.utcnow()

        # Max duration cap: prevent encounters from running forever
        duration = now - self._current_encounter.start_time
        if duration > self._max_duration:
            log.warning("Encounter %s exceeded max duration (%.0fs), force closing",
                        self._current_encounter.id[:8], duration.total_seconds())
            return self._close_encounter(now, outcome="timeout")

        # CLOSING state: use faster loot_close_timeout (loot received = kill confirmed)
        if self._state == EncounterState.CLOSING and self._last_event_time:
            if now - self._last_event_time > self._loot_close_timeout:
                return self._close_encounter(now, outcome="kill")

        # ACTIVE state: use standard close_timeout (combat without loot)
        if self._state == EncounterState.ACTIVE and self._last_event_time:
            if now - self._last_event_time > self._close_timeout:
                return self._close_encounter(now, outcome="timeout")

        return None

    def force_close(self) -> MobEncounter | None:
        """Force-close the current encounter (e.g., session stop)."""
        if self._current_encounter:
            return self._close_encounter(datetime.utcnow(), outcome="force_closed")
        return None

    def _ensure_encounter(self, now: datetime):
        """Create an encounter if none exists (anonymous mob)."""
        if not self._current_encounter:
            mob_name = self._session.primary_mob or "Unknown"
            source = "user" if self._session.primary_mob else "interpolated"
            self._start_encounter(mob_name, source, 0.5, now)

    def _start_encounter(self, mob_name: str, source: str,
                          confidence: float, now: datetime):
        self._current_encounter = MobEncounter(
            id=str(uuid.uuid4()),
            session_id=self._session.id,
            mob_name=mob_name,
            mob_name_source=source,
            start_time=now,
            confidence=confidence,
        )
        self._state = EncounterState.ACTIVE
        self._last_event_time = now

    def _close_encounter(self, now: datetime, outcome: str | None = None) -> MobEncounter:
        enc = self._current_encounter
        enc.end_time = now
        if outcome:
            enc.outcome = outcome
        self._session.encounters.append(enc)
        self._current_encounter = None
        self._state = EncounterState.IDLE
        return enc
