"""Hunt boundary detection — splits sessions into logical hunts.

Detects when the player has moved to a new hunting spot or changed target mob.
Mixed spawns (multiple mob types interleaving) do NOT trigger splits.
"""

import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime

from ..core.logger import get_logger
from .session import Hunt, MobEncounter

log = get_logger("HuntDetector")


@dataclass
class HuntBoundaryEvent:
    """Emitted when a hunt split is detected."""
    split_reason: str  # 'mob_type_change' or 'location_change'
    new_hunt_mob: str | None = None


class MobTypeTracker:
    """Tracks mob type composition to detect location/target changes.

    Uses a sliding window of recent kills. Only triggers a split when the
    hunt's dominant mob has completely disappeared from recent kills AND a
    single new mob type has taken over. Mixed spawns (multiple mob types
    interleaving) do NOT trigger splits.
    """

    def __init__(self, window_size: int = 10):
        self._window_size = window_size
        self._dominant_mob: str | None = None
        self._recent_kills: deque[str] = deque(maxlen=window_size)

    @property
    def dominant_mob(self) -> str | None:
        return self._dominant_mob

    def set_dominant(self, mob_name: str):
        """Set the dominant mob for the current hunt."""
        self._dominant_mob = mob_name
        self._recent_kills.clear()

    def observe(self, mob_name: str) -> HuntBoundaryEvent | None:
        """Record a kill and check if a hunt split should occur.

        Returns a HuntBoundaryEvent if the dominant mob has disappeared
        from the recent window AND a single new mob has taken over.
        Returns None for mixed spawns or if the dominant mob is still present.
        """
        self._recent_kills.append(mob_name)

        # Need a full window before we can make any decisions
        if len(self._recent_kills) < self._window_size:
            return None

        # If dominant mob is still in the recent window, no split
        if self._dominant_mob and self._dominant_mob in self._recent_kills:
            return None

        # Dominant mob has disappeared — check if a single new mob dominates
        mob_counts: dict[str, int] = {}
        for m in self._recent_kills:
            mob_counts[m] = mob_counts.get(m, 0) + 1

        if len(mob_counts) == 1:
            # Single mob type in the entire window — clear transition
            new_mob = next(iter(mob_counts))
            return HuntBoundaryEvent(
                split_reason="mob_type_change",
                new_hunt_mob=new_mob,
            )

        # Multiple different mobs in window but none is the original dominant.
        # Check if one mob is strongly dominant (>= 60% of window).
        threshold = self._window_size * 0.6
        for mob, count in mob_counts.items():
            if count >= threshold:
                return HuntBoundaryEvent(
                    split_reason="mob_type_change",
                    new_hunt_mob=mob,
                )

        # Mixed spawn or unclear — don't split
        return None

    def reset(self):
        self._dominant_mob = None
        self._recent_kills.clear()


class LocationTracker:
    """Tracks player location to detect significant movement.

    Placeholder — requires location data from an external source.
    Currently a no-op that never triggers splits.
    """

    def __init__(self, distance_threshold: float = 1000.0,
                 min_kills: int = 5):
        self._distance_threshold = distance_threshold
        self._min_kills = min_kills

    def observe(self, x: float, y: float) -> HuntBoundaryEvent | None:
        """Record a position and check for significant movement.

        Returns a HuntBoundaryEvent if the player has moved far enough
        from the hunt centroid and enough kills have occurred there.
        """
        # No-op until location data source is wired in (Phase 6)
        return None

    def reset(self):
        pass


class HuntDetector:
    """Detects hunt boundaries within a session.

    Manages the current hunt and checks each completed encounter for
    boundary conditions (mob type change, location change).
    """

    def __init__(self, config):
        self._config = config
        self._mob_tracker = MobTypeTracker(
            window_size=config.hunt_split_mob_threshold
        )
        self._location_tracker = LocationTracker(
            min_kills=config.hunt_split_min_remote_kills
        )
        self._current_hunt: Hunt | None = None

    @property
    def current_hunt(self) -> Hunt | None:
        return self._current_hunt

    def start_hunt(self, session_id: str, first_encounter: MobEncounter,
                   now: datetime | None = None) -> Hunt:
        """Create and return a new hunt from the first encounter."""
        now = now or datetime.utcnow()
        hunt = Hunt(
            id=str(uuid.uuid4()),
            session_id=session_id,
            start_time=now,
            primary_mob=first_encounter.mob_name,
        )
        hunt.encounters.append(first_encounter)
        first_encounter.hunt_id = hunt.id

        self._current_hunt = hunt
        self._mob_tracker.set_dominant(first_encounter.mob_name)
        self._location_tracker.reset()

        log.info("Hunt started: %s (mob: %s)", hunt.id[:8], hunt.primary_mob)
        return hunt

    def on_encounter_ended(self, encounter: MobEncounter) -> HuntBoundaryEvent | None:
        """Process a completed encounter and check for hunt boundaries.

        If a boundary is detected, the current hunt is ended and a new one
        must be started by the caller (tracker.py). The encounter that
        triggered the split belongs to the NEW hunt.

        Returns a HuntBoundaryEvent if a split should occur, or None.
        """
        if not self._current_hunt:
            return None

        # Check mob type boundary
        boundary = self._mob_tracker.observe(encounter.mob_name)
        if boundary:
            log.info(
                "Hunt split detected: %s → %s (reason: %s)",
                self._current_hunt.primary_mob,
                boundary.new_hunt_mob,
                boundary.split_reason,
            )
            return boundary

        # Check location boundary (currently no-op)
        # boundary = self._location_tracker.observe(x, y)

        # No boundary — encounter belongs to current hunt
        self._current_hunt.encounters.append(encounter)
        encounter.hunt_id = self._current_hunt.id
        return None

    def end_current_hunt(self, now: datetime | None = None) -> Hunt | None:
        """Close the current hunt and return it."""
        if not self._current_hunt:
            return None

        now = now or datetime.utcnow()
        hunt = self._current_hunt
        hunt.end_time = now
        self._current_hunt = None
        self._mob_tracker.reset()
        self._location_tracker.reset()

        log.info("Hunt ended: %s (%d kills)", hunt.id[:8], hunt.kill_count)
        return hunt

    def reset(self):
        """Full reset (e.g., session ended)."""
        self._current_hunt = None
        self._mob_tracker.reset()
        self._location_tracker.reset()
