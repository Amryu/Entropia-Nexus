"""Enhancer auto-detection state machine.

Observes damage (or heal) samples for the currently-equipped tool and
infers whether damage/heal enhancers are present by comparing observed
values against the tool's no-enhancer [min, max] range.

Key design points
-----------------

- **Grace period** around min and max to absorb rounding error:
    ``grace = min(0.2, 0.01 * max)``.
  For small weapons the 1% cap keeps the grace tight; for large weapons
  the absolute 0.2 cap keeps it from swallowing real offsets.

- **Crits are ignored**. The extended crit damage range makes the grace
  calculation unreliable, so only regular hits are fed into the engine.

- **Buff pause**. When a damage- or heal-modifier buff is active the
  engine is paused — samples are dropped on the floor, not counted.
  The tracker calls ``pause()`` / ``resume()`` based on effect messages.

- **Per-tool state**. The state machine resets whenever the active
  tool changes (OCR-detected) to avoid carrying one weapon's baseline
  over to another.

- **State transitions**::

      UNKNOWN --(N clean samples in-range)--> CONFIRMED_NONE
      UNKNOWN --(N clean samples over-range)--> CONFIRMED_PRESENT
      CONFIRMED_*  --(contradiction / break mismatch)--> DIRTY -> UNKNOWN

  "Contradiction" means an invalid damage sample after we were confident,
  which usually implies the player manually added or removed enhancers
  (or swapped a tier) — we start the cycle over for this tool.

- **Retroactive correction** is coordinated by the tracker, which
  consumes events emitted by this engine (``confirmed`` and
  ``restart``) and adjusts the combat log / encounter cost accordingly.

This module is deliberately decoupled from the tracker, event bus and
database so it can be unit-tested in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..core.logger import get_logger

log = get_logger("EnhancerInference")

# --- Thresholds -----------------------------------------------------------

#: Samples needed in the dominant bucket (over-range or in-range) before
#: we transition to CONFIRMED_* from UNKNOWN.
CONFIRMATION_SAMPLES = 15

#: Samples after CONFIRMED_* that contradict the current conclusion before
#: we treat it as a manual change and restart the cycle.
CONTRADICTION_SAMPLES = 3

#: Minimum ratio of majority to minority for confirmation. Requires at
#: least CONFIRMATION_SAMPLES dominant samples AND the minority bucket to
#: be no more than (dominant / NOISE_RATIO). Tolerates up to ~20% noise
#: so a single outlier (OCR misread, untracked transient buff, etc.)
#: doesn't lock the engine in UNKNOWN forever.
NOISE_RATIO = 5

#: Maximum absolute grace around [min, max] (HP).
GRACE_ABS_CAP = 0.2

#: Relative grace: 1% of damage_max (HP). The effective grace is the
#: minimum of this and GRACE_ABS_CAP so small weapons don't get a cap
#: that's larger than their damage variance.
GRACE_REL_FRAC = 0.01


def compute_grace(damage_max: float) -> float:
    """Return the grace band around min/max for a given damage_max.

    ``grace = min(GRACE_ABS_CAP, GRACE_REL_FRAC * damage_max)``.
    """
    if damage_max <= 0:
        return 0.0
    return min(GRACE_ABS_CAP, GRACE_REL_FRAC * damage_max)


class InferenceState(Enum):
    UNKNOWN = "unknown"               # still gathering samples
    CONFIRMED_NONE = "confirmed_none" # sure there are no enhancers
    CONFIRMED_PRESENT = "confirmed_present"  # sure enhancers are present


# Tool kind decides which sample type feeds this ToolState.
KIND_DAMAGE = "damage"   # weapons (and anything firing damage events)
KIND_HEAL = "heal"       # medical tools (SELF_HEAL events)


@dataclass
class ToolState:
    """Per-tool inference state.

    Each tool keeps its own state so a weapon swap doesn't contaminate
    the next tool's baseline.  The ``kind`` field indicates whether
    this tool is fed by damage or heal samples.
    """
    tool_name: str
    damage_min: float   # legacy field name — holds the lower bound
    damage_max: float   # legacy field name — holds the upper bound
    grace: float
    kind: str = KIND_DAMAGE
    state: InferenceState = InferenceState.UNKNOWN

    # Rolling counters. These are reset whenever the state transitions
    # or on an explicit restart (manual change).
    in_range_count: int = 0   # samples inside [min-grace, max+grace]
    over_count: int = 0       # samples above max+grace (suggest enhancers)
    # under_count tracks below-range samples. Currently informational —
    # the loadout signature is evaluated WITH known enhancer state, so
    # consistent under-range damage would mean enhancers broke that we
    # missed (the normal break flow should catch this via chat). Left
    # here for future use / diagnostics.
    under_count: int = 0      # samples below min-grace

    # Contradiction counter used after CONFIRMED_* to decide whether a
    # shift is real (manual change) or just noise/single outlier.
    contradiction_count: int = 0

    # When confirmed present, the observed over-range mean (HP above max)
    # is a rough estimate of the total enhancer bonus. Useful for
    # retroactive cost allocation if cost-per-enhancer becomes known.
    over_range_sum: float = 0.0
    over_range_n: int = 0

    first_sample_time: datetime | None = None
    last_sample_time: datetime | None = None

    @property
    def lower_bound(self) -> float:
        return self.damage_min - self.grace

    @property
    def upper_bound(self) -> float:
        return self.damage_max + self.grace

    @property
    def average_over_range(self) -> float:
        if self.over_range_n == 0:
            return 0.0
        return self.over_range_sum / self.over_range_n

    def reset_counters(self) -> None:
        self.in_range_count = 0
        self.over_count = 0
        self.under_count = 0
        self.contradiction_count = 0
        self.over_range_sum = 0.0
        self.over_range_n = 0


# Transition events emitted by the engine. The tracker consumes these to
# trigger retroactive correction, log entries, etc.
class InferenceEvent(Enum):
    CONFIRMED_NONE = "confirmed_none"
    CONFIRMED_PRESENT = "confirmed_present"
    RESTART = "restart"     # manual change suspected — cycle starts over
    MISMATCH = "mismatch"   # a real enhancer break doesn't match expectations


@dataclass
class Transition:
    event: InferenceEvent
    tool_name: str
    state_before: InferenceState
    state_after: InferenceState
    # For CONFIRMED_PRESENT this holds the observed mean HP of the
    # over-range damage — a rough estimate of the total enhancer bonus.
    over_range_average: float = 0.0
    # Optional human-readable context for logs.
    reason: str = ""


class EnhancerInferenceEngine:
    """Per-player, per-tool enhancer auto-detection state machine.

    The engine maintains one :class:`ToolState` per tool name it has
    observed. Damage samples feed into the *current* tool's state.
    Call :meth:`set_active_tool` on weapon swaps to switch state;
    call :meth:`pause` and :meth:`resume` based on buff messages.

    All API methods return :class:`Transition` objects (or ``None``)
    so the caller can react without polling state.
    """

    def __init__(self):
        self._tools: dict[str, ToolState] = {}
        # One active tool per kind — a player can carry a weapon and a
        # medical tool and swap between them without losing either's state.
        self._active: dict[str, str | None] = {
            KIND_DAMAGE: None,
            KIND_HEAL: None,
        }
        # Separate pause flags per kind so a damage-modifier buff
        # doesn't freeze heal inference (and vice versa).
        self._paused: dict[str, bool] = {
            KIND_DAMAGE: False,
            KIND_HEAL: False,
        }
        # Tools the user has explicitly opted out of auto-detection for
        # (via the "ignore" response to a redetect prompt).  Samples for
        # these tools are dropped without classification.
        self._disabled_tools: set[str] = set()
        # Tools currently awaiting a user decision after a RESTART.
        # While present, samples are dropped so the engine can't emit
        # another prompt before the user responds to this one.
        self._awaiting_decision: set[str] = set()
        self._total_samples_dropped_paused: int = 0

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def register_tool(self, tool_name: str, range_min: float,
                      range_max: float, kind: str = KIND_DAMAGE) -> None:
        """Register (or refresh) a tool's no-enhancer [min, max] range.

        *kind* picks which sample stream feeds this tool — ``"damage"``
        for weapons, ``"heal"`` for medical tools.  If the tool is
        already known, its range is updated in place; counters are
        reset only when the range actually changes.
        """
        if not tool_name or range_max <= 0 or range_min > range_max:
            return
        if kind not in (KIND_DAMAGE, KIND_HEAL):
            log.warning("Unknown tool kind %r for %r", kind, tool_name)
            return
        grace = compute_grace(range_max)
        existing = self._tools.get(tool_name)
        if existing is not None:
            if (existing.damage_min == range_min
                    and existing.damage_max == range_max
                    and existing.kind == kind):
                return
            log.info("Tool %r range changed %.1f-%.1f -> %.1f-%.1f, resetting",
                     tool_name, existing.damage_min, existing.damage_max,
                     range_min, range_max)
            existing.damage_min = range_min
            existing.damage_max = range_max
            existing.grace = grace
            existing.kind = kind
            existing.state = InferenceState.UNKNOWN
            existing.reset_counters()
            return
        self._tools[tool_name] = ToolState(
            tool_name=tool_name,
            damage_min=range_min,
            damage_max=range_max,
            grace=grace,
            kind=kind,
        )
        log.info("Registered %s tool %r: %.1f-%.1f, grace=%.3f",
                 kind, tool_name, range_min, range_max, grace)

    def set_active_tool(self, tool_name: str | None) -> None:
        """Mark *tool_name* as the active tool for its kind.

        The kind is read from the registered :class:`ToolState`, so
        a weapon and a medical tool can both be active in their
        respective slots simultaneously.  Passing ``None`` or an
        unregistered name is a no-op (we don't clear slots on swap —
        the previous tool's state is preserved in case the player
        swaps back).
        """
        if not tool_name:
            return
        state = self._tools.get(tool_name)
        if state is None:
            return
        kind = state.kind
        if self._active.get(kind) == tool_name:
            return
        log.info("Active %s tool: %r -> %r",
                 kind, self._active.get(kind), tool_name)
        self._active[kind] = tool_name

    # ------------------------------------------------------------------
    # Buff pause (per kind)
    # ------------------------------------------------------------------

    def pause(self, kind: str = KIND_DAMAGE, reason: str = "") -> None:
        """Pause sample intake for *kind* while a modifier buff is active."""
        if kind not in self._paused or self._paused[kind]:
            return
        self._paused[kind] = True
        log.info("Paused %s inference: %s", kind, reason or "(no reason)")

    def resume(self, kind: str = KIND_DAMAGE, reason: str = "") -> None:
        """Resume sample intake for *kind* after all modifier buffs expire."""
        if kind not in self._paused or not self._paused[kind]:
            return
        self._paused[kind] = False
        log.info("Resumed %s inference: %s", kind, reason or "(no reason)")

    def is_paused(self, kind: str = KIND_DAMAGE) -> bool:
        return self._paused.get(kind, False)

    @property
    def paused(self) -> bool:
        """Legacy alias: True if damage inference is paused."""
        return self._paused[KIND_DAMAGE]

    # ------------------------------------------------------------------
    # Disable / user decisions
    # ------------------------------------------------------------------

    def disable_tool(self, tool_name: str) -> None:
        """Permanently ignore a tool for the rest of the session.

        Used when the user responds "ignore" to a redetect prompt —
        the engine stops sampling this tool so no further prompts fire.
        """
        if not tool_name:
            return
        self._disabled_tools.add(tool_name)
        self._awaiting_decision.discard(tool_name)
        log.info("Auto-detection disabled for %r", tool_name)

    def is_disabled(self, tool_name: str) -> bool:
        return tool_name in self._disabled_tools

    def mark_awaiting_decision(self, tool_name: str) -> None:
        """Pause sample intake for a tool until the user responds.

        Called after a RESTART when we've emitted a prompt. While in
        this state, ``observe_*`` drops samples for the tool without
        classifying them, so a second prompt can't fire before the
        user has answered the first.
        """
        if tool_name:
            self._awaiting_decision.add(tool_name)

    def resolve_decision(self, tool_name: str) -> None:
        """Clear the awaiting-decision flag; engine resumes sampling."""
        self._awaiting_decision.discard(tool_name)

    def reset_tool(self, tool_name: str) -> None:
        """Reset a single tool's state to UNKNOWN and clear counters."""
        state = self._tools.get(tool_name)
        if state is None:
            return
        state.state = InferenceState.UNKNOWN
        state.reset_counters()
        state.first_sample_time = None
        state.last_sample_time = None
        self._awaiting_decision.discard(tool_name)

    # ------------------------------------------------------------------
    # Sample intake
    # ------------------------------------------------------------------

    def observe_damage(self, damage: float, is_crit: bool,
                       timestamp: datetime) -> Transition | None:
        """Feed a damage sample (weapon) into the engine.

        Crits are ignored (their extended range makes the grace-period
        calculation unreliable).  Samples while paused or with no
        active weapon are dropped.
        """
        if is_crit:
            return None
        return self._observe(damage, timestamp, KIND_DAMAGE)

    def observe_heal(self, amount: float,
                     timestamp: datetime) -> Transition | None:
        """Feed a self-heal sample (medical tool) into the engine.

        Fed from SELF_HEAL combat events.  Samples while paused or with
        no active medical tool are dropped.  There is no crit concept
        for heals so no ``is_crit`` parameter.
        """
        return self._observe(amount, timestamp, KIND_HEAL)

    def _observe(self, amount: float, timestamp: datetime,
                 kind: str) -> Transition | None:
        """Shared sample-intake path for damage and heal."""
        if self._paused.get(kind, False):
            self._total_samples_dropped_paused += 1
            return None
        active = self._active.get(kind)
        if not active:
            return None
        if active in self._disabled_tools or active in self._awaiting_decision:
            return None
        state = self._tools.get(active)
        if state is None or state.kind != kind:
            return None

        if state.first_sample_time is None:
            state.first_sample_time = timestamp
        state.last_sample_time = timestamp

        if amount > state.upper_bound:
            state.over_count += 1
            state.over_range_sum += amount - state.damage_max
            state.over_range_n += 1
            classification = "over"
        elif amount < state.lower_bound:
            state.under_count += 1
            classification = "under"
        else:
            state.in_range_count += 1
            classification = "in"

        return self._maybe_transition(state, classification)

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def _maybe_transition(self, state: ToolState,
                          classification: str) -> Transition | None:
        """Check if the latest sample triggers a state change."""
        if state.state == InferenceState.UNKNOWN:
            # Dominance-based confirmation: require
            #   majority >= CONFIRMATION_SAMPLES AND
            #   majority >= NOISE_RATIO * minority.
            # This tolerates transient outliers (single OCR misread or
            # silent buff blip) without locking the engine out of
            # ever confirming.
            if (classification == "over"
                    and state.over_count >= CONFIRMATION_SAMPLES
                    and state.over_count >= NOISE_RATIO * state.in_range_count):
                return self._enter_confirmed_present(state)
            if (classification == "in"
                    and state.in_range_count >= CONFIRMATION_SAMPLES
                    and state.in_range_count >= NOISE_RATIO * state.over_count):
                return self._enter_confirmed_none(state)
            return None

        # After CONFIRMED_*, watch for contradictions.
        if state.state == InferenceState.CONFIRMED_NONE:
            if classification == "over":
                state.contradiction_count += 1
                if state.contradiction_count >= CONTRADICTION_SAMPLES:
                    return self._restart_cycle(
                        state, "over-range samples after confirmed_none",
                    )
            else:
                # Any in-range sample clears transient contradictions.
                state.contradiction_count = max(0, state.contradiction_count - 1)
            return None

        if state.state == InferenceState.CONFIRMED_PRESENT:
            if classification == "in":
                state.contradiction_count += 1
                if state.contradiction_count >= CONTRADICTION_SAMPLES:
                    return self._restart_cycle(
                        state, "in-range samples after confirmed_present",
                    )
            else:
                state.contradiction_count = max(0, state.contradiction_count - 1)
            return None

        return None

    def _enter_confirmed_present(self, state: ToolState) -> Transition:
        before = state.state
        state.state = InferenceState.CONFIRMED_PRESENT
        t = Transition(
            event=InferenceEvent.CONFIRMED_PRESENT,
            tool_name=state.tool_name,
            state_before=before,
            state_after=state.state,
            over_range_average=state.average_over_range,
            reason=f"{state.over_count} over-range samples",
        )
        log.info("CONFIRMED enhancers present on %r (avg bonus +%.2f HP over %d samples)",
                 state.tool_name, state.average_over_range, state.over_count)
        return t

    def _enter_confirmed_none(self, state: ToolState) -> Transition:
        before = state.state
        state.state = InferenceState.CONFIRMED_NONE
        t = Transition(
            event=InferenceEvent.CONFIRMED_NONE,
            tool_name=state.tool_name,
            state_before=before,
            state_after=state.state,
            reason=f"{state.in_range_count} in-range samples",
        )
        log.info("CONFIRMED no enhancers on %r (%d in-range samples)",
                 state.tool_name, state.in_range_count)
        return t

    def _restart_cycle(self, state: ToolState, reason: str) -> Transition:
        before = state.state
        log.info("RESTART cycle on %r: %s", state.tool_name, reason)
        state.state = InferenceState.UNKNOWN
        state.reset_counters()
        return Transition(
            event=InferenceEvent.RESTART,
            tool_name=state.tool_name,
            state_before=before,
            state_after=state.state,
            reason=reason,
        )

    # ------------------------------------------------------------------
    # Enhancer-break validation
    # ------------------------------------------------------------------

    def validate_break(self, tool_name: str) -> Transition | None:
        """Called when an enhancer on *tool_name* breaks.

        If we're in CONFIRMED_PRESENT, we expect damage to shift down
        (fewer bonuses per shot).  The actual damage shift is verified
        by subsequent :meth:`observe_damage` calls — if those samples
        come back in-range, great; if they're still over-range we'll
        stay in CONFIRMED_PRESENT which is still correct.

        This method just resets the contradiction counter so a
        legitimate post-break shift doesn't spuriously restart the
        cycle, and returns None.

        The *real* mismatch detection fires when the damage shift
        reveals we missed a break earlier (handled by the tracker via
        :meth:`observe_damage` triggering a RESTART).
        """
        state = self._tools.get(tool_name)
        if state is None:
            return None
        state.contradiction_count = 0
        return None

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def get_state(self, tool_name: str | None = None,
                  kind: str = KIND_DAMAGE) -> ToolState | None:
        """Return the current state for *tool_name* (or the active tool of *kind*)."""
        name = tool_name or self._active.get(kind)
        if not name:
            return None
        return self._tools.get(name)

    def active_tool_state(self, kind: str = KIND_DAMAGE) -> ToolState | None:
        return self.get_state(kind=kind)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    #
    # Confirmed per-tool state is expensive to rebuild (15 clean samples
    # per tool) so we expose JSON-friendly round-trip helpers. The
    # tracker is responsible for choosing where to store the blob.
    # Transient fields are NOT persisted:
    #   - _paused (buff state — rebuilt from active effects on load)
    #   - _awaiting_decision (tied to a UI prompt that died with session)
    # Persisted:
    #   - tool registrations, per-tool counters + state
    #   - active tool slots (damage + heal)
    #   - disabled tool set (user's opt-out is durable)

    SCHEMA_VERSION = 1

    def to_dict(self) -> dict:
        return {
            "version": self.SCHEMA_VERSION,
            "tools": {
                name: {
                    "tool_name": s.tool_name,
                    "damage_min": s.damage_min,
                    "damage_max": s.damage_max,
                    "grace": s.grace,
                    "kind": s.kind,
                    "state": s.state.value,
                    "in_range_count": s.in_range_count,
                    "over_count": s.over_count,
                    "under_count": s.under_count,
                    "contradiction_count": s.contradiction_count,
                    "over_range_sum": s.over_range_sum,
                    "over_range_n": s.over_range_n,
                    "first_sample_time": (
                        s.first_sample_time.isoformat()
                        if s.first_sample_time else None
                    ),
                    "last_sample_time": (
                        s.last_sample_time.isoformat()
                        if s.last_sample_time else None
                    ),
                }
                for name, s in self._tools.items()
            },
            "active": dict(self._active),
            "disabled_tools": sorted(self._disabled_tools),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EnhancerInferenceEngine":
        eng = cls()
        if not isinstance(data, dict):
            return eng
        version = data.get("version", 0)
        if version != cls.SCHEMA_VERSION:
            log.warning("Enhancer inference schema mismatch (%s vs %s), ignoring",
                        version, cls.SCHEMA_VERSION)
            return eng
        for name, raw in (data.get("tools") or {}).items():
            try:
                state_enum = InferenceState(raw.get("state", "unknown"))
            except ValueError:
                state_enum = InferenceState.UNKNOWN
            first_t = raw.get("first_sample_time")
            last_t = raw.get("last_sample_time")
            tool = ToolState(
                tool_name=raw.get("tool_name", name),
                damage_min=float(raw.get("damage_min", 0.0)),
                damage_max=float(raw.get("damage_max", 0.0)),
                grace=float(raw.get("grace", 0.0)),
                kind=raw.get("kind", KIND_DAMAGE),
                state=state_enum,
                in_range_count=int(raw.get("in_range_count", 0)),
                over_count=int(raw.get("over_count", 0)),
                under_count=int(raw.get("under_count", 0)),
                contradiction_count=int(raw.get("contradiction_count", 0)),
                over_range_sum=float(raw.get("over_range_sum", 0.0)),
                over_range_n=int(raw.get("over_range_n", 0)),
                first_sample_time=(
                    datetime.fromisoformat(first_t) if first_t else None
                ),
                last_sample_time=(
                    datetime.fromisoformat(last_t) if last_t else None
                ),
            )
            eng._tools[name] = tool
        active = data.get("active") or {}
        for kind in (KIND_DAMAGE, KIND_HEAL):
            name = active.get(kind)
            if name and name in eng._tools:
                eng._active[kind] = name
        for name in data.get("disabled_tools") or []:
            eng._disabled_tools.add(name)
        return eng
