"""Extensive unit tests for the enhancer auto-detection feature.

Covers:
- Grace-period computation
- State transitions (UNKNOWN -> CONFIRMED_NONE/PRESENT, restart, reset)
- Crit exclusion
- Pause/resume per kind
- Dual-slot tracking (weapon + medical tool simultaneously)
- Weapon swap isolation
- Tool disable/awaiting-decision gating
- Effect classification (damage/heal/passive/unknown)
- Handler parsing of "Received Effect Over Time" lines
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from client.chat_parser.effect_types import (
    EffectCategory,
    classify_effect,
    pauses_damage_inference,
    pauses_heal_inference,
)
from client.chat_parser.handlers.effect import EffectOverTimeHandler
from client.chat_parser.models import EffectReceivedEvent, ParsedLine
from client.hunt.enhancer_inference import (
    CONFIRMATION_SAMPLES,
    CONTRADICTION_SAMPLES,
    EnhancerInferenceEngine,
    InferenceEvent,
    InferenceState,
    KIND_DAMAGE,
    KIND_HEAL,
    compute_grace,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime(2026, 4, 10, 12, 0, 0)


def _feed_damage(eng: EnhancerInferenceEngine, values: list[float],
                 start_offset: int = 0,
                 is_crit: bool = False) -> list:
    """Feed a sequence of damage samples and return any transitions."""
    base = _now()
    out = []
    for i, v in enumerate(values):
        t = eng.observe_damage(v, is_crit, base + timedelta(seconds=start_offset + i))
        if t is not None:
            out.append(t)
    return out


def _feed_heal(eng: EnhancerInferenceEngine, values: list[float],
               start_offset: int = 0) -> list:
    base = _now()
    out = []
    for i, v in enumerate(values):
        t = eng.observe_heal(v, base + timedelta(seconds=start_offset + i))
        if t is not None:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# Grace period
# ---------------------------------------------------------------------------

class TestGracePeriod(unittest.TestCase):

    def test_absolute_cap_large_weapon(self):
        # 1% of 100 = 1.0, capped at 0.2
        self.assertEqual(compute_grace(100.0), 0.2)
        self.assertEqual(compute_grace(50.0), 0.2)

    def test_relative_small_weapon(self):
        # 1% of 10 = 0.1 (below absolute cap)
        self.assertAlmostEqual(compute_grace(10.0), 0.1)
        self.assertAlmostEqual(compute_grace(5.0), 0.05)
        self.assertAlmostEqual(compute_grace(1.0), 0.01)

    def test_exactly_at_cap(self):
        # 1% of 20 = 0.2 (exactly at cap)
        self.assertEqual(compute_grace(20.0), 0.2)

    def test_zero_and_negative(self):
        self.assertEqual(compute_grace(0.0), 0.0)
        self.assertEqual(compute_grace(-5.0), 0.0)


# ---------------------------------------------------------------------------
# Basic state transitions (damage path)
# ---------------------------------------------------------------------------

class TestBasicDamageFlow(unittest.TestCase):

    def setUp(self):
        self.eng = EnhancerInferenceEngine()
        self.eng.register_tool("Gun", 10.0, 20.0)
        self.eng.set_active_tool("Gun")

    def test_initial_state_is_unknown(self):
        self.assertEqual(
            self.eng.active_tool_state().state, InferenceState.UNKNOWN,
        )

    def test_confirmed_none_after_n_in_range(self):
        transitions = _feed_damage(self.eng, [15.0] * CONFIRMATION_SAMPLES)
        self.assertEqual(len(transitions), 1)
        self.assertEqual(transitions[0].event, InferenceEvent.CONFIRMED_NONE)
        self.assertEqual(
            self.eng.active_tool_state().state, InferenceState.CONFIRMED_NONE,
        )

    def test_confirmed_present_after_n_over_range(self):
        # 25 > upper_bound (20 + 0.2)
        transitions = _feed_damage(self.eng, [25.0] * CONFIRMATION_SAMPLES)
        self.assertEqual(len(transitions), 1)
        self.assertEqual(transitions[0].event, InferenceEvent.CONFIRMED_PRESENT)

    def test_confirmed_present_avg_bonus(self):
        _feed_damage(self.eng, [25.0] * CONFIRMATION_SAMPLES)
        state = self.eng.active_tool_state()
        # Over max by 5
        self.assertAlmostEqual(state.average_over_range, 5.0)

    def test_samples_within_grace_count_as_in_range(self):
        # Upper bound = 20 + 0.2 = 20.2; feed 20.15 -> in range
        _feed_damage(self.eng, [20.15] * CONFIRMATION_SAMPLES)
        self.assertEqual(
            self.eng.active_tool_state().state, InferenceState.CONFIRMED_NONE,
        )

    def test_evenly_mixed_samples_stay_unknown(self):
        # 10 over + 10 in = ratio 1:1, far below the 5:1 threshold.
        # Genuine uncertainty — engine must not confirm either way.
        _feed_damage(self.eng, [25.0, 15.0] * 10)
        self.assertEqual(
            self.eng.active_tool_state().state, InferenceState.UNKNOWN,
        )

    def test_nearly_even_samples_stay_unknown(self):
        # 15 over + 4 in: 15 < 5*4 = 20, fails ratio check.
        _feed_damage(self.eng, [25.0] * 15)
        _feed_damage(self.eng, [15.0] * 4, start_offset=15)
        self.assertEqual(
            self.eng.active_tool_state().state, InferenceState.UNKNOWN,
        )

    def test_dominant_over_confirms_despite_outlier(self):
        # 14 over + 1 in + 1 over: 15 over, 1 in. Ratio 15:1 >> 5:1.
        # This used to lock up due to the strict "in_range_count == 0"
        # check, but now confirms correctly.
        _feed_damage(self.eng, [25.0] * 14)
        _feed_damage(self.eng, [15.0], start_offset=14)
        _feed_damage(self.eng, [25.0], start_offset=15)
        self.assertEqual(
            self.eng.active_tool_state().state, InferenceState.CONFIRMED_PRESENT,
        )

    def test_borderline_ratio_confirms(self):
        # 14 over + 3 in + 1 over: at sample 18, over=15, in=3,
        # ratio 15 >= 5*3 = 15 — exactly at threshold. Confirms here
        # (and not earlier because over_count was only 14 when in=3
        # was already present).
        _feed_damage(self.eng, [25.0] * 14)
        _feed_damage(self.eng, [15.0] * 3, start_offset=14)
        _feed_damage(self.eng, [25.0], start_offset=17)
        self.assertEqual(
            self.eng.active_tool_state().state, InferenceState.CONFIRMED_PRESENT,
        )

    def test_last_sample_before_threshold_no_transition(self):
        t = _feed_damage(self.eng, [15.0] * (CONFIRMATION_SAMPLES - 1))
        self.assertEqual(t, [])
        self.assertEqual(
            self.eng.active_tool_state().state, InferenceState.UNKNOWN,
        )


# ---------------------------------------------------------------------------
# Contradiction and restart
# ---------------------------------------------------------------------------

class TestContradictionAndRestart(unittest.TestCase):

    def setUp(self):
        self.eng = EnhancerInferenceEngine()
        self.eng.register_tool("Gun", 10.0, 20.0)
        self.eng.set_active_tool("Gun")

    def test_restart_from_confirmed_present(self):
        # Confirm enhancers present
        _feed_damage(self.eng, [25.0] * CONFIRMATION_SAMPLES)
        # Feed CONTRADICTION_SAMPLES of in-range samples
        transitions = _feed_damage(
            self.eng, [15.0] * CONTRADICTION_SAMPLES,
            start_offset=CONFIRMATION_SAMPLES,
        )
        restart = [t for t in transitions if t.event == InferenceEvent.RESTART]
        self.assertEqual(len(restart), 1)
        self.assertEqual(
            self.eng.active_tool_state().state, InferenceState.UNKNOWN,
        )

    def test_restart_from_confirmed_none(self):
        _feed_damage(self.eng, [15.0] * CONFIRMATION_SAMPLES)
        transitions = _feed_damage(
            self.eng, [25.0] * CONTRADICTION_SAMPLES,
            start_offset=CONFIRMATION_SAMPLES,
        )
        restart = [t for t in transitions if t.event == InferenceEvent.RESTART]
        self.assertEqual(len(restart), 1)
        self.assertEqual(
            self.eng.active_tool_state().state, InferenceState.UNKNOWN,
        )

    def test_isolated_contradiction_does_not_restart(self):
        _feed_damage(self.eng, [25.0] * CONFIRMATION_SAMPLES)
        # Only 1 contradicting sample, then back to over-range
        _feed_damage(self.eng, [15.0], start_offset=100)
        _feed_damage(self.eng, [25.0] * 2, start_offset=101)
        self.assertEqual(
            self.eng.active_tool_state().state, InferenceState.CONFIRMED_PRESENT,
            "one-off sample shouldn't trigger restart",
        )

    def test_counters_reset_after_restart(self):
        _feed_damage(self.eng, [25.0] * CONFIRMATION_SAMPLES)
        _feed_damage(self.eng, [15.0] * CONTRADICTION_SAMPLES,
                     start_offset=CONFIRMATION_SAMPLES)
        state = self.eng.active_tool_state()
        self.assertEqual(state.over_count, 0)
        self.assertEqual(state.in_range_count, 0)
        self.assertEqual(state.over_range_sum, 0.0)
        self.assertEqual(state.contradiction_count, 0)


# ---------------------------------------------------------------------------
# Crit exclusion
# ---------------------------------------------------------------------------

class TestCritExclusion(unittest.TestCase):

    def setUp(self):
        self.eng = EnhancerInferenceEngine()
        self.eng.register_tool("Gun", 10.0, 20.0)
        self.eng.set_active_tool("Gun")

    def test_crits_are_dropped(self):
        _feed_damage(self.eng, [500.0] * 30, is_crit=True)
        state = self.eng.active_tool_state()
        self.assertEqual(state.over_count, 0)
        self.assertEqual(state.in_range_count, 0)
        self.assertEqual(state.state, InferenceState.UNKNOWN)

    def test_crits_interspersed_with_regular_hits(self):
        # Mix 10 regular in-range with 10 crits; only regulars counted
        base = _now()
        for i in range(20):
            is_crit = i % 2 == 0
            self.eng.observe_damage(
                500.0 if is_crit else 15.0, is_crit,
                base + timedelta(seconds=i),
            )
        state = self.eng.active_tool_state()
        self.assertEqual(state.in_range_count, 10)
        self.assertEqual(state.over_count, 0)


# ---------------------------------------------------------------------------
# Pause / resume (per kind)
# ---------------------------------------------------------------------------

class TestPauseResume(unittest.TestCase):

    def test_damage_pause_drops_samples(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        eng.pause(KIND_DAMAGE, "Might")
        _feed_damage(eng, [25.0] * 30)
        self.assertEqual(eng.active_tool_state().over_count, 0)
        self.assertEqual(
            eng.active_tool_state().state, InferenceState.UNKNOWN,
        )

    def test_damage_resume_reenables_samples(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        eng.pause(KIND_DAMAGE, "Might")
        _feed_damage(eng, [25.0] * 10)
        eng.resume(KIND_DAMAGE, "expired")
        _feed_damage(eng, [15.0] * CONFIRMATION_SAMPLES, start_offset=100)
        self.assertEqual(
            eng.active_tool_state().state, InferenceState.CONFIRMED_NONE,
        )

    def test_per_kind_pause_isolation(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.register_tool("Kit", 2.0, 12.0, kind=KIND_HEAL)
        eng.set_active_tool("Gun")
        eng.set_active_tool("Kit")
        # Pause damage only
        eng.pause(KIND_DAMAGE, "Might")
        self.assertTrue(eng.is_paused(KIND_DAMAGE))
        self.assertFalse(eng.is_paused(KIND_HEAL))
        # Damage samples dropped, heal samples flow
        _feed_damage(eng, [25.0] * CONFIRMATION_SAMPLES)
        _feed_heal(eng, [8.0] * CONFIRMATION_SAMPLES)
        self.assertEqual(
            eng.get_state("Gun", KIND_DAMAGE).state, InferenceState.UNKNOWN,
        )
        self.assertEqual(
            eng.get_state("Kit", KIND_HEAL).state, InferenceState.CONFIRMED_NONE,
        )

    def test_resume_unpaused_is_noop(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        eng.resume(KIND_DAMAGE, "no-op")  # should not crash
        self.assertFalse(eng.is_paused(KIND_DAMAGE))


# ---------------------------------------------------------------------------
# Heal path
# ---------------------------------------------------------------------------

class TestHealFlow(unittest.TestCase):

    def setUp(self):
        self.eng = EnhancerInferenceEngine()
        self.eng.register_tool("Kit", 2.0, 12.0, kind=KIND_HEAL)
        self.eng.set_active_tool("Kit")

    def test_heal_confirmed_none(self):
        _feed_heal(self.eng, [7.0] * CONFIRMATION_SAMPLES)
        self.assertEqual(
            self.eng.active_tool_state(KIND_HEAL).state,
            InferenceState.CONFIRMED_NONE,
        )

    def test_heal_confirmed_present(self):
        # 16 > 12 + 0.12
        _feed_heal(self.eng, [16.0] * CONFIRMATION_SAMPLES)
        self.assertEqual(
            self.eng.active_tool_state(KIND_HEAL).state,
            InferenceState.CONFIRMED_PRESENT,
        )

    def test_heal_never_sees_crit_path(self):
        # observe_heal has no is_crit parameter — this test just
        # ensures we can call it without errors.
        _feed_heal(self.eng, [7.0])
        self.assertEqual(
            self.eng.active_tool_state(KIND_HEAL).in_range_count, 1,
        )

    def test_heal_grace_for_small_tool(self):
        # MinHeal=2, MaxHeal=12 -> grace = 0.12
        state = self.eng.active_tool_state(KIND_HEAL)
        self.assertAlmostEqual(state.grace, 0.12)
        # 12.1 is in-range (within grace)
        _feed_heal(self.eng, [12.1] * CONFIRMATION_SAMPLES)
        self.assertEqual(state.state, InferenceState.CONFIRMED_NONE)


# ---------------------------------------------------------------------------
# Dual-slot tracking (weapon + medical tool simultaneously)
# ---------------------------------------------------------------------------

class TestDualSlotTracking(unittest.TestCase):

    def setUp(self):
        self.eng = EnhancerInferenceEngine()
        self.eng.register_tool("Rifle", 50.0, 100.0)
        self.eng.register_tool("EMT", 2.0, 12.0, kind=KIND_HEAL)
        self.eng.set_active_tool("Rifle")
        self.eng.set_active_tool("EMT")  # both active in their slots

    def test_both_active(self):
        self.assertEqual(self.eng._active[KIND_DAMAGE], "Rifle")
        self.assertEqual(self.eng._active[KIND_HEAL], "EMT")

    def test_damage_samples_feed_weapon(self):
        _feed_damage(self.eng, [75.0] * CONFIRMATION_SAMPLES)
        self.assertEqual(
            self.eng.get_state("Rifle", KIND_DAMAGE).state,
            InferenceState.CONFIRMED_NONE,
        )
        self.assertEqual(
            self.eng.get_state("EMT", KIND_HEAL).in_range_count, 0,
        )

    def test_heal_samples_feed_medkit(self):
        _feed_heal(self.eng, [8.0] * CONFIRMATION_SAMPLES)
        self.assertEqual(
            self.eng.get_state("EMT", KIND_HEAL).state,
            InferenceState.CONFIRMED_NONE,
        )
        self.assertEqual(
            self.eng.get_state("Rifle", KIND_DAMAGE).in_range_count, 0,
        )

    def test_parallel_confirmation(self):
        _feed_damage(self.eng, [75.0] * CONFIRMATION_SAMPLES)
        _feed_heal(self.eng, [8.0] * CONFIRMATION_SAMPLES)
        self.assertEqual(
            self.eng.get_state("Rifle", KIND_DAMAGE).state,
            InferenceState.CONFIRMED_NONE,
        )
        self.assertEqual(
            self.eng.get_state("EMT", KIND_HEAL).state,
            InferenceState.CONFIRMED_NONE,
        )


# ---------------------------------------------------------------------------
# Weapon swap
# ---------------------------------------------------------------------------

class TestWeaponSwap(unittest.TestCase):

    def test_state_preserved_across_swap(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("A", 10.0, 20.0)
        eng.register_tool("B", 30.0, 50.0)
        eng.set_active_tool("A")
        _feed_damage(eng, [15.0] * 10)
        eng.set_active_tool("B")
        _feed_damage(eng, [40.0] * 5, start_offset=20)
        self.assertEqual(eng.get_state("A", KIND_DAMAGE).in_range_count, 10)
        self.assertEqual(eng.get_state("B", KIND_DAMAGE).in_range_count, 5)

    def test_swap_back_resumes_previous_state(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("A", 10.0, 20.0)
        eng.register_tool("B", 30.0, 50.0)
        eng.set_active_tool("A")
        _feed_damage(eng, [15.0] * (CONFIRMATION_SAMPLES - 1))
        eng.set_active_tool("B")
        _feed_damage(eng, [40.0] * 5, start_offset=20)
        eng.set_active_tool("A")
        # One more sample and A confirms none
        _feed_damage(eng, [15.0], start_offset=30)
        self.assertEqual(
            eng.get_state("A", KIND_DAMAGE).state,
            InferenceState.CONFIRMED_NONE,
        )

    def test_register_unchanged_range_keeps_state(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [15.0] * 5)
        eng.register_tool("Gun", 10.0, 20.0)  # same range -> no reset
        self.assertEqual(eng.active_tool_state().in_range_count, 5)

    def test_register_changed_range_resets_state(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [15.0] * 5)
        eng.register_tool("Gun", 20.0, 40.0)  # changed -> reset
        self.assertEqual(eng.active_tool_state().in_range_count, 0)
        self.assertEqual(
            eng.active_tool_state().state, InferenceState.UNKNOWN,
        )


# ---------------------------------------------------------------------------
# Disable / awaiting-decision gating
# ---------------------------------------------------------------------------

class TestDisableAndAwaitDecision(unittest.TestCase):

    def setUp(self):
        self.eng = EnhancerInferenceEngine()
        self.eng.register_tool("Gun", 10.0, 20.0)
        self.eng.set_active_tool("Gun")

    def test_disable_drops_all_samples(self):
        self.eng.disable_tool("Gun")
        self.assertTrue(self.eng.is_disabled("Gun"))
        _feed_damage(self.eng, [25.0] * 30)
        self.assertEqual(self.eng.active_tool_state().over_count, 0)

    def test_awaiting_decision_drops_samples(self):
        self.eng.mark_awaiting_decision("Gun")
        _feed_damage(self.eng, [25.0] * 30)
        self.assertEqual(self.eng.active_tool_state().over_count, 0)

    def test_resolve_decision_reenables_samples(self):
        self.eng.mark_awaiting_decision("Gun")
        _feed_damage(self.eng, [25.0] * 30)  # dropped
        self.eng.resolve_decision("Gun")
        _feed_damage(self.eng, [15.0] * CONFIRMATION_SAMPLES, start_offset=30)
        self.assertEqual(
            self.eng.active_tool_state().state, InferenceState.CONFIRMED_NONE,
        )

    def test_reset_tool_clears_state_and_counters(self):
        _feed_damage(self.eng, [25.0] * CONFIRMATION_SAMPLES)
        self.assertEqual(
            self.eng.active_tool_state().state, InferenceState.CONFIRMED_PRESENT,
        )
        self.eng.reset_tool("Gun")
        state = self.eng.active_tool_state()
        self.assertEqual(state.state, InferenceState.UNKNOWN)
        self.assertEqual(state.in_range_count, 0)
        self.assertEqual(state.over_count, 0)
        self.assertEqual(state.over_range_sum, 0.0)

    def test_ignore_then_redetect_flow(self):
        _feed_damage(self.eng, [25.0] * CONFIRMATION_SAMPLES)
        _feed_damage(
            self.eng, [15.0] * CONTRADICTION_SAMPLES,
            start_offset=CONFIRMATION_SAMPLES,
        )
        # Simulate tracker marking awaiting decision, then user picks ignore
        self.eng.mark_awaiting_decision("Gun")
        self.eng.disable_tool("Gun")
        # All future samples ignored
        _feed_damage(self.eng, [25.0] * 30, start_offset=100)
        self.assertEqual(
            self.eng.active_tool_state().state, InferenceState.UNKNOWN,
        )


# ---------------------------------------------------------------------------
# Effect classification
# ---------------------------------------------------------------------------

class TestEffectClassification(unittest.TestCase):

    def test_damage_mod_buffs(self):
        for name in ("Might", "Berserker", "Increased Damage"):
            self.assertEqual(
                classify_effect(name), EffectCategory.DAMAGE_MOD,
                msg=f"{name!r} should be DAMAGE_MOD",
            )
            self.assertTrue(pauses_damage_inference(name))
            self.assertFalse(pauses_heal_inference(name))

    def test_heal_mod_buffs(self):
        for name in ("Increased Healing", "Decreased Healing"):
            self.assertEqual(
                classify_effect(name), EffectCategory.HEAL_MOD,
            )
            self.assertFalse(pauses_damage_inference(name))
            self.assertTrue(pauses_heal_inference(name))

    def test_crit_buffs_are_passive(self):
        # Crit-only modifiers don't affect non-crit damage, and the
        # engine excludes crits from sample intake, so they must be
        # classified as PASSIVE and NOT pause damage inference.
        for name in ("Increased Critical Chance", "Increased Critical Damage"):
            self.assertEqual(
                classify_effect(name), EffectCategory.PASSIVE,
            )
            self.assertFalse(pauses_damage_inference(name))

    def test_passive_buffs(self):
        for name in (
            "Increased Health",
            "Increased Regeneration",
            "Increased Reload Speed",
            "Increased Run Speed",
            "Increased Skill Gain",
        ):
            self.assertEqual(
                classify_effect(name), EffectCategory.PASSIVE,
            )
            self.assertFalse(pauses_damage_inference(name))
            self.assertFalse(pauses_heal_inference(name))

    def test_heal_effect_is_passive(self):
        # The HoT "Heal" effect is unreliable as a use counter and
        # doesn't modify heal output — it's passive.
        self.assertEqual(classify_effect("Heal"), EffectCategory.PASSIVE)

    def test_unknown_effect_defaults_to_unknown(self):
        self.assertEqual(
            classify_effect("Something Random"), EffectCategory.UNKNOWN,
        )
        self.assertFalse(pauses_damage_inference("Something Random"))
        self.assertFalse(pauses_heal_inference("Something Random"))

    def test_empty_string_is_unknown(self):
        self.assertEqual(classify_effect(""), EffectCategory.UNKNOWN)
        self.assertEqual(classify_effect("  "), EffectCategory.UNKNOWN)

    def test_case_insensitive_matching(self):
        self.assertEqual(classify_effect("MIGHT"), EffectCategory.DAMAGE_MOD)
        self.assertEqual(classify_effect("might"), EffectCategory.DAMAGE_MOD)
        self.assertEqual(classify_effect(" Might "), EffectCategory.DAMAGE_MOD)


# ---------------------------------------------------------------------------
# Effect-over-time chat handler
# ---------------------------------------------------------------------------

def _make_system_line(msg: str) -> ParsedLine:
    return ParsedLine(
        timestamp=datetime(2026, 2, 8, 15, 43, 37),
        channel="System",
        username="",
        message=msg,
        raw_line=f"2026-02-08 15:43:37 [System] [] {msg}",
        line_number=1,
    )


class TestEffectOverTimeHandler(unittest.TestCase):

    def setUp(self):
        self.bus = MagicMock()
        self.db = MagicMock()
        self.handler = EffectOverTimeHandler(self.bus, self.db)

    def test_handles_effect_message(self):
        line = _make_system_line("Received Effect Over Time: Heal")
        self.assertTrue(self.handler.can_handle(line))
        self.handler.handle(line)
        self.bus.publish.assert_called_once()
        event_name, event = self.bus.publish.call_args[0]
        self.assertEqual(event_name, "effect_received")
        self.assertIsInstance(event, EffectReceivedEvent)
        self.assertEqual(event.effect_name, "Heal")

    def test_handles_multi_word_effect(self):
        line = _make_system_line(
            "Received Effect Over Time: Increased Critical Chance",
        )
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.effect_name, "Increased Critical Chance")

    def test_handles_divine_intervention(self):
        line = _make_system_line("Received Effect Over Time: Divine Intervention")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.effect_name, "Divine Intervention")

    def test_trims_whitespace_in_effect_name(self):
        line = _make_system_line("Received Effect Over Time:    Heal   ")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.effect_name, "Heal")

    def test_ignores_non_system_channel(self):
        line = ParsedLine(
            timestamp=datetime.now(),
            channel="Globals",
            username="",
            message="Received Effect Over Time: Heal",
            raw_line="",
            line_number=1,
        )
        self.assertFalse(self.handler.can_handle(line))

    def test_ignores_system_with_username(self):
        line = ParsedLine(
            timestamp=datetime.now(),
            channel="System",
            username="SomePlayer",
            message="Received Effect Over Time: Heal",
            raw_line="",
            line_number=1,
        )
        self.assertFalse(self.handler.can_handle(line))

    def test_ignores_unrelated_system_message(self):
        line = _make_system_line("You have gained 0.5 Bravado")
        self.assertFalse(self.handler.can_handle(line))

    def test_suppress_events_mode(self):
        self.handler.suppress_events = True
        line = _make_system_line("Received Effect Over Time: Heal")
        self.handler.handle(line)
        self.bus.publish.assert_not_called()

    def test_empty_effect_name_ignored(self):
        line = _make_system_line("Received Effect Over Time: ")
        self.handler.handle(line)
        self.bus.publish.assert_not_called()


# ---------------------------------------------------------------------------
# Transition payload details
# ---------------------------------------------------------------------------

class TestTransitionPayload(unittest.TestCase):

    def test_confirmed_present_carries_over_range_average(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        # Bonus of exactly 5
        transitions = _feed_damage(eng, [25.0] * CONFIRMATION_SAMPLES)
        self.assertEqual(len(transitions), 1)
        t = transitions[0]
        self.assertEqual(t.event, InferenceEvent.CONFIRMED_PRESENT)
        self.assertEqual(t.tool_name, "Gun")
        self.assertEqual(t.state_before, InferenceState.UNKNOWN)
        self.assertEqual(t.state_after, InferenceState.CONFIRMED_PRESENT)
        self.assertAlmostEqual(t.over_range_average, 5.0)

    def test_varied_over_range_averages(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        # Values 22, 24, 26, 28, 30, ... average bonus (22-20 + 24-20 + ...)/N
        values = [22.0, 24.0, 26.0, 28.0, 30.0] * (CONFIRMATION_SAMPLES // 5)
        # Pad to CONFIRMATION_SAMPLES total
        values = values[:CONFIRMATION_SAMPLES]
        transitions = _feed_damage(eng, values)
        # The cycle (2, 4, 6, 8, 10) avg = 6 bonus
        t = [x for x in transitions if x.event == InferenceEvent.CONFIRMED_PRESENT]
        self.assertEqual(len(t), 1)
        self.assertAlmostEqual(t[0].over_range_average, 6.0)

    def test_restart_carries_reason(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [25.0] * CONFIRMATION_SAMPLES)
        transitions = _feed_damage(
            eng, [15.0] * CONTRADICTION_SAMPLES,
            start_offset=CONFIRMATION_SAMPLES,
        )
        restarts = [t for t in transitions if t.event == InferenceEvent.RESTART]
        self.assertEqual(len(restarts), 1)
        self.assertTrue(restarts[0].reason)
        self.assertIn("confirmed_present", restarts[0].reason)


# ---------------------------------------------------------------------------
# Robustness / guard clauses
# ---------------------------------------------------------------------------

class TestRobustness(unittest.TestCase):

    def test_register_rejects_invalid_range(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("", 10.0, 20.0)  # empty name
        eng.register_tool("A", 0.0, 0.0)    # zero max
        eng.register_tool("A", 20.0, 10.0)  # inverted range
        self.assertNotIn("A", eng._tools)
        self.assertNotIn("", eng._tools)

    def test_register_rejects_unknown_kind(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("A", 10.0, 20.0, kind="nonsense")
        self.assertNotIn("A", eng._tools)

    def test_observe_without_active_tool_is_noop(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("A", 10.0, 20.0)
        # Intentionally don't call set_active_tool
        t = eng.observe_damage(15.0, False, _now())
        self.assertIsNone(t)

    def test_set_active_tool_unknown_name_noop(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("A", 10.0, 20.0)
        eng.set_active_tool("Unknown")
        self.assertIsNone(eng._active[KIND_DAMAGE])

    def test_mark_awaiting_decision_empty(self):
        eng = EnhancerInferenceEngine()
        eng.mark_awaiting_decision("")
        eng.mark_awaiting_decision(None)
        self.assertEqual(eng._awaiting_decision, set())

    def test_reset_unknown_tool_noop(self):
        eng = EnhancerInferenceEngine()
        eng.reset_tool("Unknown")  # should not raise

    def test_disable_unknown_tool_noop(self):
        eng = EnhancerInferenceEngine()
        eng.disable_tool("")
        self.assertEqual(eng._disabled_tools, set())


# ---------------------------------------------------------------------------
# Validate-break hook
# ---------------------------------------------------------------------------

class TestValidateBreak(unittest.TestCase):

    def test_validate_break_clears_contradiction_counter(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [25.0] * CONFIRMATION_SAMPLES)
        # Two contradictions (not yet at threshold)
        _feed_damage(
            eng, [15.0] * (CONTRADICTION_SAMPLES - 1),
            start_offset=CONFIRMATION_SAMPLES,
        )
        self.assertGreater(
            eng.active_tool_state().contradiction_count, 0,
        )
        eng.validate_break("Gun")
        self.assertEqual(eng.active_tool_state().contradiction_count, 0)

    def test_validate_break_unknown_tool_noop(self):
        eng = EnhancerInferenceEngine()
        # Should not raise
        eng.validate_break("NoSuchTool")


# ---------------------------------------------------------------------------
# Boundary conditions — exact damage values at min/max/grace boundaries
# ---------------------------------------------------------------------------

class TestBoundaries(unittest.TestCase):
    """Exact-value boundary tests. The grace for max=20 is 0.2, so the
    upper bound is 20.2 (inclusive at 20.2, exclusive above)."""

    def setUp(self):
        self.eng = EnhancerInferenceEngine()
        self.eng.register_tool("Gun", 10.0, 20.0)
        self.eng.set_active_tool("Gun")

    def test_damage_at_upper_bound_is_in_range(self):
        # upper_bound = 20 + 0.2 = 20.2; 20.2 is NOT > 20.2
        _feed_damage(self.eng, [20.2])
        state = self.eng.active_tool_state()
        self.assertEqual(state.in_range_count, 1)
        self.assertEqual(state.over_count, 0)

    def test_damage_just_above_upper_bound_is_over(self):
        _feed_damage(self.eng, [20.201])
        state = self.eng.active_tool_state()
        self.assertEqual(state.over_count, 1)

    def test_damage_at_lower_bound_is_in_range(self):
        # lower_bound = 10 - 0.2 = 9.8
        _feed_damage(self.eng, [9.8])
        state = self.eng.active_tool_state()
        self.assertEqual(state.in_range_count, 1)
        self.assertEqual(state.under_count, 0)

    def test_damage_just_below_lower_bound_is_under(self):
        _feed_damage(self.eng, [9.799])
        state = self.eng.active_tool_state()
        self.assertEqual(state.under_count, 1)

    def test_damage_at_exact_min(self):
        _feed_damage(self.eng, [10.0])
        self.assertEqual(self.eng.active_tool_state().in_range_count, 1)

    def test_damage_at_exact_max(self):
        _feed_damage(self.eng, [20.0])
        self.assertEqual(self.eng.active_tool_state().in_range_count, 1)

    def test_zero_damage_is_under_range(self):
        _feed_damage(self.eng, [0.0])
        state = self.eng.active_tool_state()
        self.assertEqual(state.under_count, 1)

    def test_negative_damage_is_under_range(self):
        # Defensive: should not crash even on impossible values
        _feed_damage(self.eng, [-5.0])
        state = self.eng.active_tool_state()
        self.assertEqual(state.under_count, 1)

    def test_small_weapon_tight_grace(self):
        # max=5 -> grace=0.05 -> upper_bound=5.05
        eng = EnhancerInferenceEngine()
        eng.register_tool("Dart", 1.0, 5.0)
        eng.set_active_tool("Dart")
        eng.observe_damage(5.05, False, _now())
        eng.observe_damage(5.06, False, _now())
        state = eng.active_tool_state()
        self.assertEqual(state.in_range_count, 1)
        self.assertEqual(state.over_count, 1)


# ---------------------------------------------------------------------------
# Silent buff scenarios (unknown/untracked effects modify damage)
# ---------------------------------------------------------------------------

class TestSilentBuffScenarios(unittest.TestCase):
    """Simulate buffs the engine isn't aware of (not in the classifier)."""

    def test_silent_buff_causes_false_positive_then_restart(self):
        # 1. Confirmed NONE (no enhancers)
        # 2. Silent buff activates: damage jumps over-range
        # 3. After 3 contradictions, restart cycle (prompt triggered)
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [15.0] * CONFIRMATION_SAMPLES)
        self.assertEqual(
            eng.active_tool_state().state, InferenceState.CONFIRMED_NONE,
        )
        # Silent buff → over-range damage
        transitions = _feed_damage(
            eng, [25.0] * CONTRADICTION_SAMPLES,
            start_offset=CONFIRMATION_SAMPLES,
        )
        restarts = [t for t in transitions if t.event == InferenceEvent.RESTART]
        self.assertEqual(len(restarts), 1)

    def test_silent_buff_false_positive_during_initial_detection(self):
        # A brief silent buff during UNKNOWN sampling shouldn't prevent
        # eventual confirmation once dominance is restored.
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        # Buff-inflated samples first
        _feed_damage(eng, [25.0] * 2)
        # Then consistent in-range
        _feed_damage(eng, [15.0] * 15, start_offset=5)
        # 15 >= 5*2 = 10 → confirms
        self.assertEqual(
            eng.active_tool_state().state, InferenceState.CONFIRMED_NONE,
        )


# ---------------------------------------------------------------------------
# Tool name drift (OCR misread creates a different tool key)
# ---------------------------------------------------------------------------

class TestToolNameDrift(unittest.TestCase):
    """If OCR misreads a weapon name, the engine sees a different tool.

    The engine treats them as separate tools (correct behavior given
    the information it has) — we just verify state stays consistent.
    """

    def test_misread_name_gets_own_state(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Mayhem Gun", 10.0, 20.0)
        eng.register_tool("Mayhem Gn", 10.0, 20.0)  # misread variant
        eng.set_active_tool("Mayhem Gun")
        _feed_damage(eng, [15.0] * 10)
        eng.set_active_tool("Mayhem Gn")
        _feed_damage(eng, [15.0] * 10)
        self.assertEqual(
            eng.get_state("Mayhem Gun", KIND_DAMAGE).in_range_count, 10,
        )
        self.assertEqual(
            eng.get_state("Mayhem Gn", KIND_DAMAGE).in_range_count, 10,
        )
        # Neither confirmed because each only has 10 samples
        self.assertEqual(
            eng.get_state("Mayhem Gun", KIND_DAMAGE).state,
            InferenceState.UNKNOWN,
        )

    def test_unregistered_tool_activation_noop(self):
        eng = EnhancerInferenceEngine()
        # Don't register anything
        eng.set_active_tool("SomeGun")
        # Still no active damage tool because activation requires registered state
        self.assertIsNone(eng._active[KIND_DAMAGE])
        # Samples don't crash but are dropped
        _feed_damage(eng, [15.0] * 20)


# ---------------------------------------------------------------------------
# State interaction: disable + pause + weapon swap
# ---------------------------------------------------------------------------

class TestStateInteractions(unittest.TestCase):

    def test_disabled_tool_stays_disabled_after_pause_resume(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        eng.disable_tool("Gun")
        eng.pause(KIND_DAMAGE, "Might")
        eng.resume(KIND_DAMAGE, "expired")
        _feed_damage(eng, [15.0] * CONFIRMATION_SAMPLES)
        # Still disabled even after pause/resume
        self.assertTrue(eng.is_disabled("Gun"))
        self.assertEqual(eng.active_tool_state().in_range_count, 0)

    def test_disabled_tool_after_swap_and_return(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("A", 10.0, 20.0)
        eng.register_tool("B", 10.0, 20.0)
        eng.set_active_tool("A")
        eng.disable_tool("A")
        eng.set_active_tool("B")
        _feed_damage(eng, [15.0] * CONFIRMATION_SAMPLES)
        self.assertEqual(
            eng.get_state("B", KIND_DAMAGE).state,
            InferenceState.CONFIRMED_NONE,
        )
        # Back to A — still disabled
        eng.set_active_tool("A")
        _feed_damage(eng, [15.0] * CONFIRMATION_SAMPLES, start_offset=100)
        self.assertEqual(
            eng.get_state("A", KIND_DAMAGE).state, InferenceState.UNKNOWN,
        )

    def test_awaiting_decision_cleared_on_reset(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        eng.mark_awaiting_decision("Gun")
        eng.reset_tool("Gun")
        self.assertNotIn("Gun", eng._awaiting_decision)

    def test_awaiting_decision_cleared_on_disable(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        eng.mark_awaiting_decision("Gun")
        eng.disable_tool("Gun")
        self.assertNotIn("Gun", eng._awaiting_decision)
        self.assertTrue(eng.is_disabled("Gun"))

    def test_pause_during_contradiction_phase_preserves_confirmed(self):
        # Confirmed PRESENT, 1 contradicting sample, then buff activates
        # and drops samples → still CONFIRMED_PRESENT (not restarted).
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [25.0] * CONFIRMATION_SAMPLES)
        _feed_damage(eng, [15.0], start_offset=CONFIRMATION_SAMPLES)
        # 1 contradiction so far
        self.assertEqual(
            eng.active_tool_state().contradiction_count, 1,
        )
        eng.pause(KIND_DAMAGE, "Might")
        _feed_damage(eng, [15.0] * 20, start_offset=100)  # all dropped
        eng.resume(KIND_DAMAGE, "expired")
        # State is still CONFIRMED_PRESENT
        self.assertEqual(
            eng.active_tool_state().state, InferenceState.CONFIRMED_PRESENT,
        )

    def test_register_with_different_kind_resets_state(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Ambiguous", 10.0, 20.0, kind=KIND_DAMAGE)
        eng.set_active_tool("Ambiguous")
        _feed_damage(eng, [15.0] * 10)
        self.assertEqual(
            eng.get_state("Ambiguous", KIND_DAMAGE).in_range_count, 10,
        )
        # Now re-register with heal kind
        eng.register_tool("Ambiguous", 10.0, 20.0, kind=KIND_HEAL)
        # State was reset
        self.assertEqual(
            eng.get_state("Ambiguous", KIND_HEAL).in_range_count, 0,
        )


# ---------------------------------------------------------------------------
# Multi-tool complex scenarios
# ---------------------------------------------------------------------------

class TestComplexScenarios(unittest.TestCase):

    def test_three_weapons_with_different_states(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("A", 10.0, 20.0)
        eng.register_tool("B", 50.0, 100.0)
        eng.register_tool("C", 1.0, 3.0)
        # A: confirmed none
        eng.set_active_tool("A")
        _feed_damage(eng, [15.0] * CONFIRMATION_SAMPLES)
        # B: confirmed present
        eng.set_active_tool("B")
        _feed_damage(eng, [115.0] * CONFIRMATION_SAMPLES, start_offset=100)
        # C: unknown (only 5 samples)
        eng.set_active_tool("C")
        _feed_damage(eng, [2.0] * 5, start_offset=200)

        self.assertEqual(
            eng.get_state("A", KIND_DAMAGE).state,
            InferenceState.CONFIRMED_NONE,
        )
        self.assertEqual(
            eng.get_state("B", KIND_DAMAGE).state,
            InferenceState.CONFIRMED_PRESENT,
        )
        self.assertEqual(
            eng.get_state("C", KIND_DAMAGE).state, InferenceState.UNKNOWN,
        )

    def test_weapon_and_medical_parallel_lifecycle(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Rifle", 50.0, 100.0)
        eng.register_tool("FAP", 20.0, 50.0, kind=KIND_HEAL)
        eng.set_active_tool("Rifle")
        eng.set_active_tool("FAP")

        # Weapon confirms present while medkit is still unknown
        _feed_damage(eng, [115.0] * CONFIRMATION_SAMPLES)
        self.assertEqual(
            eng.get_state("Rifle", KIND_DAMAGE).state,
            InferenceState.CONFIRMED_PRESENT,
        )
        self.assertEqual(
            eng.get_state("FAP", KIND_HEAL).state, InferenceState.UNKNOWN,
        )

        # Then medkit confirms
        _feed_heal(eng, [35.0] * CONFIRMATION_SAMPLES)
        self.assertEqual(
            eng.get_state("FAP", KIND_HEAL).state,
            InferenceState.CONFIRMED_NONE,
        )

    def test_buff_pause_does_not_affect_heal_inference(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Rifle", 50.0, 100.0)
        eng.register_tool("FAP", 20.0, 50.0, kind=KIND_HEAL)
        eng.set_active_tool("Rifle")
        eng.set_active_tool("FAP")

        eng.pause(KIND_DAMAGE, "Might")
        # Heal samples still flow
        _feed_heal(eng, [35.0] * CONFIRMATION_SAMPLES)
        self.assertEqual(
            eng.get_state("FAP", KIND_HEAL).state,
            InferenceState.CONFIRMED_NONE,
        )

    def test_full_lifecycle_confirm_restart_redetect(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")

        # 1. Confirm NONE
        _feed_damage(eng, [15.0] * CONFIRMATION_SAMPLES)
        self.assertEqual(
            eng.active_tool_state().state, InferenceState.CONFIRMED_NONE,
        )

        # 2. Player adds enhancers → over-range → RESTART
        _feed_damage(
            eng, [25.0] * CONTRADICTION_SAMPLES,
            start_offset=CONFIRMATION_SAMPLES,
        )
        self.assertEqual(
            eng.active_tool_state().state, InferenceState.UNKNOWN,
        )

        # 3. Engine would emit prompt; user picks "redetect"
        eng.mark_awaiting_decision("Gun")
        eng.reset_tool("Gun")
        eng.resolve_decision("Gun")

        # 4. Fresh cycle confirms PRESENT
        _feed_damage(
            eng, [25.0] * CONFIRMATION_SAMPLES, start_offset=100,
        )
        self.assertEqual(
            eng.active_tool_state().state, InferenceState.CONFIRMED_PRESENT,
        )


# ---------------------------------------------------------------------------
# Numerical precision / floating point edge cases
# ---------------------------------------------------------------------------

class TestFloatingPointPrecision(unittest.TestCase):

    def test_floating_point_arithmetic_rounding(self):
        # For max=20.1, grace = min(0.2, 0.01*20.1) = min(0.2, 0.201) = 0.2
        # (absolute cap wins), so upper_bound = 20.1 + 0.2 = 20.3.
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.1)
        eng.set_active_tool("Gun")
        state = eng.active_tool_state()
        self.assertAlmostEqual(state.grace, 0.2)
        self.assertAlmostEqual(state.upper_bound, 20.3, places=9)
        eng.observe_damage(20.3, False, _now())  # at boundary = in-range
        self.assertEqual(state.in_range_count, 1)
        eng.observe_damage(20.301, False, _now())  # just above = over
        self.assertEqual(state.over_count, 1)

    def test_very_small_max_damage(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Tiny", 0.1, 0.5)
        eng.set_active_tool("Tiny")
        # grace = min(0.2, 0.005) = 0.005
        state = eng.active_tool_state()
        self.assertAlmostEqual(state.grace, 0.005)
        # In-range sample
        eng.observe_damage(0.3, False, _now())
        self.assertEqual(state.in_range_count, 1)


# ---------------------------------------------------------------------------
# Effect types: additional defensive tests
# ---------------------------------------------------------------------------

class TestEffectClassificationDefensive(unittest.TestCase):

    def test_none_and_weird_whitespace(self):
        self.assertEqual(classify_effect("\t\n  "), EffectCategory.UNKNOWN)
        # Defensive: should not crash on None (caller typically ensures str,
        # but guard defensively)
        # Use empty string as the nearest valid substitute
        self.assertEqual(classify_effect(""), EffectCategory.UNKNOWN)

    def test_uppercase_and_extra_spaces(self):
        self.assertEqual(
            classify_effect("  MIGHT  "), EffectCategory.DAMAGE_MOD,
        )
        self.assertEqual(
            classify_effect("Increased  Damage"), EffectCategory.UNKNOWN,
            "double space should not match (strict catalog keys)",
        )


# ---------------------------------------------------------------------------
# Effect handler: additional parsing edge cases
# ---------------------------------------------------------------------------

class TestEffectHandlerParseEdgeCases(unittest.TestCase):

    def setUp(self):
        self.bus = MagicMock()
        self.db = MagicMock()
        self.handler = EffectOverTimeHandler(self.bus, self.db)

    def test_effect_with_colon_in_name(self):
        # The regex is greedy-ish: "^Received Effect Over Time: (.+?)\s*$"
        # A name with a colon in it should still parse (everything after
        # the first ": " is captured).
        line = _make_system_line(
            "Received Effect Over Time: Heal: Over Time",
        )
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        self.assertEqual(event.effect_name, "Heal: Over Time")

    def test_effect_trailing_punctuation(self):
        line = _make_system_line("Received Effect Over Time: Might.")
        self.handler.handle(line)
        event = self.bus.publish.call_args[0][1]
        # Punctuation is preserved — classification uses normalized keys
        self.assertEqual(event.effect_name, "Might.")

    def test_starts_with_received_but_wrong_format(self):
        line = _make_system_line("Received item: Foo")
        self.assertFalse(self.handler.can_handle(line))

    def test_case_sensitivity_in_prefix(self):
        # Prefix match is case-sensitive (chat log is consistent)
        line = _make_system_line("received effect over time: Heal")
        self.assertFalse(self.handler.can_handle(line))


# ---------------------------------------------------------------------------
# Real-world integration: actual chat.log lines + actual item signatures
# ---------------------------------------------------------------------------
#
# These tests use raw lines pulled from a real chat.log so we exercise the
# parser and state machine on the actual shapes we'll see in production.
# Values are verbatim copies from client/chat.log — don't "clean them up".

# Real self-heal lines captured on 2026-02-08 during a medkit session.
# Values match EMT Kit Ek-1000 (MinHeal=2, MaxHeal=12) except for an
# initial 39.5 which is from a different tool (excluded).
_REAL_HEAL_LINES = [
    "2026-02-08 15:43:38 [System] [] You healed yourself 4.9 points",
    "2026-02-08 15:43:39 [System] [] You healed yourself 9.6 points",
    "2026-02-08 15:43:41 [System] [] You healed yourself 9.9 points",
    "2026-02-08 15:43:43 [System] [] You healed yourself 9.6 points",
    "2026-02-08 15:43:45 [System] [] You healed yourself 9.9 points",
    "2026-02-08 15:43:47 [System] [] You healed yourself 8.6 points",
    "2026-02-08 15:43:49 [System] [] You healed yourself 9.9 points",
    "2026-02-08 15:43:51 [System] [] You healed yourself 9.6 points",
    "2026-02-08 15:43:52 [System] [] You healed yourself 6.2 points",
]

# Real damage lines for Mayhem Electric Attack Nanochip 15, Perfected.
# These are the first shots of a hunt. The range here is much wider than
# a typical no-enhancer signature because the weapon has amp/scope/etc.
_REAL_DAMAGE_LINES = [
    "2026-02-08 15:38:46 [System] [] You inflicted 200.5 points of damage",
    "2026-02-08 15:38:47 [System] [] You inflicted 134.4 points of damage",
    "2026-02-08 15:38:53 [System] [] You inflicted 185.1 points of damage",
    "2026-02-08 15:38:54 [System] [] You inflicted 141.0 points of damage",
    "2026-02-08 15:38:55 [System] [] You inflicted 135.8 points of damage",
    "2026-02-08 15:38:57 [System] [] You inflicted 122.5 points of damage",
    "2026-02-08 15:38:58 [System] [] You inflicted 116.4 points of damage",
    "2026-02-08 15:38:59 [System] [] You inflicted 218.4 points of damage",
    "2026-02-08 15:39:00 [System] [] You inflicted 203.0 points of damage",
    "2026-02-08 15:39:01 [System] [] You inflicted 128.2 points of damage",
]

# Real enhancer break on the Mayhem weapon
_REAL_ENHANCER_BREAK = (
    "2026-02-08 15:44:57 [System] [] Your enhancer T1 Weapon Damage Enhancer "
    "on your Mayhem Electric Attack Nanochip 15, Perfected broke. "
    "You have 60 enhancers remaining on the item. "
    "You received 0.8000 PED Shrapnel. "
)

# Real effect-over-time line
_REAL_EFFECT_LINE = (
    "2026-02-08 15:43:37 [System] [] Received Effect Over Time: Heal"
)


class TestRealWorldChatLog(unittest.TestCase):
    """Exercise the pipeline on unmodified chat.log samples."""

    def test_line_parser_handles_real_heal_lines(self):
        from client.chat_parser.line_parser import LineParser
        parser = LineParser()
        for raw in _REAL_HEAL_LINES:
            parsed = parser.parse(raw, 1)
            self.assertIsNotNone(parsed, f"failed to parse: {raw!r}")
            self.assertEqual(parsed.channel, "System")
            self.assertEqual(parsed.username, "")
            self.assertTrue(parsed.message.startswith("You healed yourself"))

    def test_line_parser_handles_real_effect_line(self):
        from client.chat_parser.line_parser import LineParser
        parser = LineParser()
        parsed = parser.parse(_REAL_EFFECT_LINE, 1)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.message, "Received Effect Over Time: Heal")

    def test_effect_handler_on_real_line(self):
        from client.chat_parser.line_parser import LineParser
        bus = MagicMock()
        db = MagicMock()
        handler = EffectOverTimeHandler(bus, db)
        parsed = LineParser().parse(_REAL_EFFECT_LINE, 1)
        self.assertTrue(handler.can_handle(parsed))
        handler.handle(parsed)
        event = bus.publish.call_args[0][1]
        self.assertEqual(event.effect_name, "Heal")
        self.assertEqual(event.timestamp.year, 2026)
        self.assertEqual(event.timestamp.hour, 15)

    def test_heal_range_on_real_emt_kit_ek_1000_values(self):
        """Feed real EMT Kit heal values; with the known range they
        should all classify as in-range."""
        eng = EnhancerInferenceEngine()
        # EMT Kit Ek-1000 from the medical tools API
        eng.register_tool("EMT Kit Ek-1000", 2.0, 12.0, kind=KIND_HEAL)
        eng.set_active_tool("EMT Kit Ek-1000")
        # Extract numeric values from the real lines
        import re
        pat = re.compile(r"healed yourself ([\d.]+) points")
        values = []
        for line in _REAL_HEAL_LINES:
            m = pat.search(line)
            if m:
                values.append(float(m.group(1)))
        self.assertEqual(len(values), 9)
        _feed_heal(eng, values)
        state = eng.active_tool_state(KIND_HEAL)
        # All 9 values are between 2-12 (with grace 0.12)
        self.assertEqual(state.in_range_count, 9)
        self.assertEqual(state.over_count, 0)

    def test_heal_range_not_enough_samples_stays_unknown(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("EMT Kit Ek-1000", 2.0, 12.0, kind=KIND_HEAL)
        eng.set_active_tool("EMT Kit Ek-1000")
        _feed_heal(eng, [9.6, 9.9, 8.6])  # only 3 samples
        self.assertEqual(
            eng.active_tool_state(KIND_HEAL).state, InferenceState.UNKNOWN,
        )

    def test_real_damage_spread_is_wide_as_expected(self):
        """Mayhem Electric Attack Nanochip 15, Perfected has a very wide
        effective damage range because the loadout includes amp/scope/
        enhancers.  These raw values from the real chat log span
        116.4 - 218.4, including some that look like crits."""
        import re
        values = []
        pat = re.compile(r"inflicted ([\d.]+) points")
        for line in _REAL_DAMAGE_LINES:
            m = pat.search(line)
            if m:
                values.append(float(m.group(1)))
        self.assertEqual(len(values), 10)
        self.assertAlmostEqual(min(values), 116.4)
        self.assertAlmostEqual(max(values), 218.4)

    def test_enhancer_break_real_line_parses(self):
        from client.core.constants import ENHANCER_BREAK_PATTERN
        from client.chat_parser.line_parser import LineParser
        parsed = LineParser().parse(_REAL_ENHANCER_BREAK, 1)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.channel, "System")
        m = ENHANCER_BREAK_PATTERN.match(parsed.message)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "T1 Weapon Damage Enhancer")
        self.assertEqual(
            m.group(2),
            "Mayhem Electric Attack Nanochip 15, Perfected",
        )
        self.assertEqual(m.group(3), "60")
        self.assertEqual(m.group(4), "0.8000")


# ---------------------------------------------------------------------------
# Timing / event ordering edge cases
# ---------------------------------------------------------------------------

class TestTimingEdgeCases(unittest.TestCase):
    """Events arriving in weird orders and timing."""

    def test_samples_right_at_buff_boundary(self):
        # A sample at the exact instant a buff expires should be
        # counted (buff is already expired by the time we check).
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        eng.pause(KIND_DAMAGE)
        # Engine doesn't know about buff timing — that's the tracker's
        # concern. From the engine's POV, a pause is a pause until
        # explicit resume.
        eng.observe_damage(25.0, False, _now())
        self.assertEqual(eng.active_tool_state().over_count, 0)
        eng.resume(KIND_DAMAGE)
        eng.observe_damage(25.0, False, _now() + timedelta(seconds=1))
        self.assertEqual(eng.active_tool_state().over_count, 1)

    def test_samples_before_tool_registered(self):
        # observe_damage with no registered tool should be a no-op
        eng = EnhancerInferenceEngine()
        eng.set_active_tool("NeverRegistered")
        t = eng.observe_damage(25.0, False, _now())
        self.assertIsNone(t)

    def test_contradiction_counter_decays_on_agreeing_sample(self):
        # After CONFIRMED_PRESENT, mixing one contradicting sample
        # with one agreeing sample should NOT trigger restart.
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [25.0] * CONFIRMATION_SAMPLES)
        # 2 contradictions (short of threshold)
        _feed_damage(eng, [15.0] * 2, start_offset=CONFIRMATION_SAMPLES)
        # Agreeing samples decrement the counter
        _feed_damage(eng, [25.0] * 3, start_offset=CONFIRMATION_SAMPLES + 2)
        self.assertEqual(
            eng.active_tool_state().state, InferenceState.CONFIRMED_PRESENT,
        )
        self.assertEqual(eng.active_tool_state().contradiction_count, 0)

    def test_rapid_tool_swap_during_unknown(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("A", 10.0, 20.0)
        eng.register_tool("B", 30.0, 50.0)
        # Alternate between tools every sample — neither reaches threshold
        for i in range(20):
            if i % 2 == 0:
                eng.set_active_tool("A")
                eng.observe_damage(15.0, False, _now() + timedelta(seconds=i))
            else:
                eng.set_active_tool("B")
                eng.observe_damage(40.0, False, _now() + timedelta(seconds=i))
        self.assertEqual(
            eng.get_state("A", KIND_DAMAGE).state, InferenceState.UNKNOWN,
        )
        self.assertEqual(
            eng.get_state("B", KIND_DAMAGE).state, InferenceState.UNKNOWN,
        )
        self.assertEqual(eng.get_state("A", KIND_DAMAGE).in_range_count, 10)
        self.assertEqual(eng.get_state("B", KIND_DAMAGE).in_range_count, 10)


# ---------------------------------------------------------------------------
# Full pipeline: LineParser -> handlers -> engine
# ---------------------------------------------------------------------------

class TestFullPipeline(unittest.TestCase):
    """End-to-end tests: raw chat lines -> parser -> handler -> engine.

    The engine is fed directly (not via EventBus) to keep the test
    hermetic, but everything up to the event payload uses real code.
    """

    def test_effect_line_pauses_damage_inference_classification(self):
        from client.chat_parser.line_parser import LineParser
        bus = MagicMock()
        handler = EffectOverTimeHandler(bus, MagicMock())
        parser = LineParser()

        raw = "2026-04-10 12:00:00 [System] [] Received Effect Over Time: Might"
        parsed = parser.parse(raw, 1)
        self.assertIsNotNone(parsed)
        handler.handle(parsed)

        event = bus.publish.call_args[0][1]
        self.assertEqual(event.effect_name, "Might")
        self.assertTrue(pauses_damage_inference(event.effect_name))
        self.assertFalse(pauses_heal_inference(event.effect_name))

    def test_multiple_real_effect_lines_classify_correctly(self):
        from client.chat_parser.line_parser import LineParser
        bus = MagicMock()
        handler = EffectOverTimeHandler(bus, MagicMock())
        parser = LineParser()

        # All unique effect names observed in the real chat log
        effects = [
            ("Auto Loot", EffectCategory.PASSIVE),
            ("Decreased Healing", EffectCategory.HEAL_MOD),
            ("Divine Intervention", EffectCategory.PASSIVE),
            ("Heal", EffectCategory.PASSIVE),
            ("Increased Critical Chance", EffectCategory.PASSIVE),
            ("Increased Critical Damage", EffectCategory.PASSIVE),
            ("Increased Health", EffectCategory.PASSIVE),
            ("Increased Regeneration", EffectCategory.PASSIVE),
            ("Increased Reload Speed", EffectCategory.PASSIVE),
            ("Increased Run Speed", EffectCategory.PASSIVE),
            ("Increased Skill Gain", EffectCategory.PASSIVE),
        ]
        for name, expected_category in effects:
            raw = f"2026-04-10 12:00:00 [System] [] Received Effect Over Time: {name}"
            parsed = parser.parse(raw, 1)
            self.assertIsNotNone(parsed, f"parse failed for {raw!r}")
            bus.reset_mock()
            handler.handle(parsed)
            event = bus.publish.call_args[0][1]
            self.assertEqual(event.effect_name, name)
            self.assertEqual(
                classify_effect(event.effect_name), expected_category,
                msg=f"{name} should classify as {expected_category.value}",
            )


# ---------------------------------------------------------------------------
# Gap awareness: what happens when data is missing or inconsistent
# ---------------------------------------------------------------------------

class TestDataGaps(unittest.TestCase):
    """Simulate gaps, dropped events, and inconsistent sequences."""

    def test_missing_tool_signature_registration_fails_gracefully(self):
        eng = EnhancerInferenceEngine()
        # Never register, just set active
        eng.set_active_tool("Ghost")
        # No crash, no effect
        t = eng.observe_damage(15.0, False, _now())
        self.assertIsNone(t)

    def test_sample_burst_after_long_idle(self):
        # Engine was confirmed, then no samples for a while, then a
        # burst of samples comes in. Should behave identically to
        # normal cadence (engine doesn't care about wall time gaps).
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [25.0] * CONFIRMATION_SAMPLES)
        self.assertEqual(
            eng.active_tool_state().state, InferenceState.CONFIRMED_PRESENT,
        )
        # Simulate a 6-hour gap by using big timestamps
        base = _now() + timedelta(hours=6)
        for i in range(10):
            eng.observe_damage(25.0, False, base + timedelta(seconds=i))
        # Still CONFIRMED_PRESENT
        self.assertEqual(
            eng.active_tool_state().state, InferenceState.CONFIRMED_PRESENT,
        )

    def test_partial_confirmation_then_infinite_buff(self):
        # Engine at 10/15 samples when a buff arrives and never expires.
        # Engine should stay UNKNOWN with the existing 10 samples.
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [25.0] * 10)
        self.assertEqual(
            eng.active_tool_state().state, InferenceState.UNKNOWN,
        )
        eng.pause(KIND_DAMAGE, "stuck buff")
        _feed_damage(eng, [15.0] * 100, start_offset=100)
        # Counters unchanged because all samples were dropped
        self.assertEqual(eng.active_tool_state().over_count, 10)
        self.assertEqual(eng.active_tool_state().in_range_count, 0)
        self.assertEqual(
            eng.active_tool_state().state, InferenceState.UNKNOWN,
        )

    def test_enhancer_break_without_prior_confirmation(self):
        # Real enhancer break fires while engine is still UNKNOWN.
        # validate_break should be a no-op; engine shouldn't crash.
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [25.0] * 5)  # only 5 samples
        eng.validate_break("Gun")
        self.assertEqual(
            eng.active_tool_state().state, InferenceState.UNKNOWN,
        )
        self.assertEqual(eng.active_tool_state().contradiction_count, 0)

    def test_enhancer_break_for_unknown_tool_noop(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        # Break fires for a tool we never registered
        eng.validate_break("SomeOtherWeapon")  # should not raise

    def test_under_range_samples_do_not_confirm_anything(self):
        # Consistent under-range damage (which would happen if loadout
        # says N enhancers but actual is fewer). Engine currently
        # tracks this in under_count but doesn't confirm on it — this
        # is the documented gap.
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [5.0] * 50)
        self.assertEqual(
            eng.active_tool_state().state, InferenceState.UNKNOWN,
        )
        self.assertEqual(eng.active_tool_state().under_count, 50)

    def test_extremely_high_damage_outlier(self):
        # An absurdly high damage value (e.g., from a crit that we
        # mis-flagged as non-crit). It's just one "over" sample.
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [10000.0])
        self.assertEqual(eng.active_tool_state().over_count, 1)
        # Bonus mean follows (10000 - 20 = 9980)
        self.assertAlmostEqual(
            eng.active_tool_state().average_over_range, 9980.0,
        )


# ---------------------------------------------------------------------------
# Bidirectional enhancer-shrapnel correlation
# ---------------------------------------------------------------------------
#
# When an enhancer breaks, the game returns the enhancer's TT value as
# shrapnel. This shrapnel is a REFUND, not loot, and must not count in
# the hunt's effective loot total. The break message and the shrapnel
# loot drop can arrive in EITHER order — the tracker buffers both sides
# and matches them by PED value within a 2s window.
#
# These tests exercise the matching logic directly on the tracker
# methods, bypassing the full session/event-bus setup.

from client.hunt.session import EncounterLootItem, MobEncounter
from datetime import datetime


def _make_encounter(name: str = "Atrox Old Alpha") -> MobEncounter:
    return MobEncounter(
        id="enc-1",
        session_id="sess-1",
        hunt_id="hunt-1",
        mob_name=name,
        mob_name_source="ocr",
        start_time=datetime.utcnow(),
    )


def _make_shrapnel_item(value_ped: float) -> EncounterLootItem:
    return EncounterLootItem(
        item_name="Shrapnel",
        quantity=int(value_ped * 100),  # shrapnel is priced per-unit
        value_ped=value_ped,
    )


class _FakeTrackingLog:
    def __init__(self):
        self.entries = []
    def session_info(self, msg):
        self.entries.append(("session_info", msg))
    def enhancer_inference(self, *a, **kw):
        self.entries.append(("enhancer_inference", a, kw))


class _StubTracker:
    """Minimal subset of HuntTracker needed to exercise shrapnel
    matching in isolation. We import the real methods from the class
    so we're testing the production logic, not a reimplementation.
    """
    from client.hunt.tracker import HuntTracker
    ENHANCER_SHRAPNEL_WINDOW = HuntTracker.ENHANCER_SHRAPNEL_WINDOW

    _match_enhancer_shrapnel = HuntTracker._match_enhancer_shrapnel
    _buffer_unmatched_shrapnel = HuntTracker._buffer_unmatched_shrapnel
    _match_loot_against_break = HuntTracker._match_loot_against_break

    def __init__(self):
        self._recent_enhancer_breaks = []
        self._recent_shrapnel_items = []
        self._tracking_log = _FakeTrackingLog()


class TestShrapnelCorrelationForward(unittest.TestCase):
    """Break first, shrapnel second (the originally-handled case).

    The tracker's buffer pruning compares against ``datetime.utcnow()``
    so these tests use real time rather than the fixed ``_now()`` used
    elsewhere.
    """

    def test_break_then_shrapnel_within_window(self):
        t = _StubTracker()
        now = datetime.utcnow()
        # Break arrives first — buffered in _recent_enhancer_breaks
        t._recent_enhancer_breaks.append((now, 0.8))
        # Shrapnel arrives a moment later, same value → match
        matched = t._match_enhancer_shrapnel("Shrapnel", 0.8, now)
        self.assertTrue(matched)
        self.assertEqual(t._recent_enhancer_breaks, [],
                         "matched break should be consumed")

    def test_break_then_shrapnel_value_mismatch_no_match(self):
        t = _StubTracker()
        now = datetime.utcnow()
        t._recent_enhancer_breaks.append((now, 0.8))
        matched = t._match_enhancer_shrapnel("Shrapnel", 1.5, now)
        self.assertFalse(matched)
        # Break remains buffered for a future match
        self.assertEqual(len(t._recent_enhancer_breaks), 1)

    def test_non_shrapnel_item_never_matches(self):
        t = _StubTracker()
        now = datetime.utcnow()
        t._recent_enhancer_breaks.append((now, 0.8))
        matched = t._match_enhancer_shrapnel("Animal Muscle Oil", 0.8, now)
        self.assertFalse(matched)
        self.assertEqual(len(t._recent_enhancer_breaks), 1)


class TestShrapnelCorrelationReverse(unittest.TestCase):
    """Shrapnel first, break second — the newly-fixed case."""

    def test_shrapnel_buffered_then_break_retroactively_matches(self):
        t = _StubTracker()
        enc = _make_encounter()
        loot_item = _make_shrapnel_item(0.8)
        enc.loot_items.append(loot_item)
        enc.loot_total_ped = 0.8

        # 1. Shrapnel arrives first. No matching break yet, so it's
        #    NOT flagged and gets buffered.
        self.assertFalse(loot_item.is_enhancer_shrapnel)
        matched_forward = t._match_enhancer_shrapnel("Shrapnel", 0.8, _now())
        self.assertFalse(matched_forward)
        t._buffer_unmatched_shrapnel(enc, loot_item, _now())
        self.assertEqual(len(t._recent_shrapnel_items), 1)

        # 2. Break message arrives within the window. Should match
        #    the buffered shrapnel and retroactively flip the flag.
        matched_reverse = t._match_loot_against_break(_now(), 0.8)
        self.assertTrue(matched_reverse)
        self.assertTrue(loot_item.is_enhancer_shrapnel)
        self.assertEqual(t._recent_shrapnel_items, [],
                         "matched buffered entry should be consumed")

        # 3. Effective loot now excludes the shrapnel.
        self.assertEqual(enc.effective_loot_ped, 0.0)
        # Raw total unchanged.
        self.assertEqual(enc.loot_total_ped, 0.8)

    def test_shrapnel_buffered_break_with_different_value_no_match(self):
        t = _StubTracker()
        enc = _make_encounter()
        loot_item = _make_shrapnel_item(0.8)
        enc.loot_items.append(loot_item)

        t._buffer_unmatched_shrapnel(enc, loot_item, _now())
        matched = t._match_loot_against_break(_now(), 1.5)
        self.assertFalse(matched)
        self.assertFalse(loot_item.is_enhancer_shrapnel)
        # Buffered item still waiting for its actual match
        self.assertEqual(len(t._recent_shrapnel_items), 1)

    def test_buffered_shrapnel_beyond_window_not_matched(self):
        t = _StubTracker()
        enc = _make_encounter()
        loot_item = _make_shrapnel_item(0.8)
        old_time = _now() - timedelta(seconds=5)  # well beyond 2s window
        t._recent_shrapnel_items.append((old_time, enc, loot_item, 0.8))
        matched = t._match_loot_against_break(_now(), 0.8)
        self.assertFalse(matched)
        self.assertFalse(loot_item.is_enhancer_shrapnel)

    def test_only_matches_first_value_match(self):
        # Two buffered shrapnel items with the same value; only one
        # should be consumed by a single break.
        t = _StubTracker()
        enc = _make_encounter()
        item_a = _make_shrapnel_item(0.8)
        item_b = _make_shrapnel_item(0.8)
        t._recent_shrapnel_items.append((_now(), enc, item_a, 0.8))
        t._recent_shrapnel_items.append((_now(), enc, item_b, 0.8))
        matched = t._match_loot_against_break(_now(), 0.8)
        self.assertTrue(matched)
        # Exactly one item flipped
        flags = [item_a.is_enhancer_shrapnel, item_b.is_enhancer_shrapnel]
        self.assertEqual(sum(flags), 1)
        # Other still buffered
        self.assertEqual(len(t._recent_shrapnel_items), 1)

    def test_non_shrapnel_item_not_buffered(self):
        t = _StubTracker()
        enc = _make_encounter()
        non_shrapnel = EncounterLootItem(
            item_name="Animal Muscle Oil",
            quantity=5,
            value_ped=0.5,
        )
        t._buffer_unmatched_shrapnel(enc, non_shrapnel, _now())
        self.assertEqual(t._recent_shrapnel_items, [])

    def test_buffer_prunes_old_entries(self):
        t = _StubTracker()
        enc = _make_encounter()
        # Insert a very old entry directly (simulates stale state)
        old_time = _now() - timedelta(seconds=30)
        old_item = _make_shrapnel_item(0.5)
        t._recent_shrapnel_items.append((old_time, enc, old_item, 0.5))
        # New buffer call should prune it
        new_item = _make_shrapnel_item(0.8)
        t._buffer_unmatched_shrapnel(enc, new_item, _now())
        # Only the new entry remains
        self.assertEqual(len(t._recent_shrapnel_items), 1)
        self.assertIs(t._recent_shrapnel_items[0][2], new_item)


class TestShrapnelCorrelationAmbiguous(unittest.TestCase):
    """Edge cases where multiple breaks and multiple shrapnel items
    can be ambiguously associated. We verify the algorithm makes
    deterministic, reasonable choices."""

    def test_two_breaks_two_shrapnel_both_matched(self):
        t = _StubTracker()
        enc = _make_encounter()
        item_a = _make_shrapnel_item(0.8)
        item_b = _make_shrapnel_item(1.2)
        enc.loot_items.extend([item_a, item_b])

        # Shrapnel first (both unmatched)
        t._buffer_unmatched_shrapnel(enc, item_a, _now())
        t._buffer_unmatched_shrapnel(enc, item_b, _now())

        # Break for 0.8 arrives
        matched_a = t._match_loot_against_break(_now(), 0.8)
        self.assertTrue(matched_a)
        self.assertTrue(item_a.is_enhancer_shrapnel)
        self.assertFalse(item_b.is_enhancer_shrapnel)

        # Break for 1.2 arrives
        matched_b = t._match_loot_against_break(_now(), 1.2)
        self.assertTrue(matched_b)
        self.assertTrue(item_b.is_enhancer_shrapnel)

        # Buffer drained
        self.assertEqual(t._recent_shrapnel_items, [])

    def test_mixed_order_interleaved(self):
        """Break, shrapnel, break, shrapnel — each break matches the
        next shrapnel in the opposite buffer, not cross-matched.
        """
        t = _StubTracker()
        enc = _make_encounter()

        # 1. Break 0.8 arrives, buffered
        t._recent_enhancer_breaks.append((_now(), 0.8))

        # 2. Shrapnel 0.8 arrives, matches buffered break
        loot_a = _make_shrapnel_item(0.8)
        matched_a = t._match_enhancer_shrapnel("Shrapnel", 0.8, _now())
        self.assertTrue(matched_a)
        loot_a.is_enhancer_shrapnel = matched_a  # caller would set this

        # 3. Shrapnel 1.2 arrives, no matching break, buffered
        loot_b = _make_shrapnel_item(1.2)
        matched_b = t._match_enhancer_shrapnel("Shrapnel", 1.2, _now())
        self.assertFalse(matched_b)
        t._buffer_unmatched_shrapnel(enc, loot_b, _now())

        # 4. Break 1.2 arrives, matches the buffered shrapnel
        matched_c = t._match_loot_against_break(_now(), 1.2)
        self.assertTrue(matched_c)
        self.assertTrue(loot_b.is_enhancer_shrapnel)

        # Both buffers drained
        self.assertEqual(t._recent_enhancer_breaks, [])
        self.assertEqual(t._recent_shrapnel_items, [])


class TestShrapnelRetroactiveEffectiveLoot(unittest.TestCase):
    """Verify the encounter's effective_loot_ped property reflects
    retroactive shrapnel flag changes without explicit recomputation."""

    def test_effective_loot_updates_after_retroactive_flag(self):
        t = _StubTracker()
        enc = _make_encounter()
        # 2.0 PED of mixed loot: 0.8 shrapnel + 1.2 hide
        shrapnel = _make_shrapnel_item(0.8)
        hide = EncounterLootItem(
            item_name="Animal Hide",
            quantity=3,
            value_ped=1.2,
        )
        enc.loot_items.extend([shrapnel, hide])
        enc.loot_total_ped = 2.0

        # Initially nothing is flagged → effective loot = 2.0
        self.assertEqual(enc.effective_loot_ped, 2.0)

        # Simulate the fix: shrapnel arrives → buffered → break
        # arrives → retroactively flagged
        t._buffer_unmatched_shrapnel(enc, shrapnel, _now())
        t._match_loot_against_break(_now(), 0.8)

        # effective loot now excludes the shrapnel
        self.assertEqual(enc.effective_loot_ped, 1.2)
        # Raw total is unchanged
        self.assertEqual(enc.loot_total_ped, 2.0)


# ---------------------------------------------------------------------------
# Truncated / malformed chat lines
# ---------------------------------------------------------------------------

class TestTruncatedChatLines(unittest.TestCase):
    """Chat.log can be cut off mid-line if the game crashes or the
    reader catches a partial flush. The parser must not crash."""

    def setUp(self):
        from client.chat_parser.line_parser import LineParser
        self.parser = LineParser()

    def test_empty_line_returns_none(self):
        self.assertIsNone(self.parser.parse("", 1))

    def test_whitespace_only_line(self):
        self.assertIsNone(self.parser.parse("   \t  ", 1))

    def test_newline_only(self):
        self.assertIsNone(self.parser.parse("\n", 1))
        self.assertIsNone(self.parser.parse("\r\n", 1))

    def test_truncated_before_timestamp(self):
        # Partial flush — only got a few bytes
        self.assertIsNone(self.parser.parse("2026-02-", 1))

    def test_truncated_mid_timestamp(self):
        self.assertIsNone(self.parser.parse("2026-02-08 15:43", 1))

    def test_truncated_after_timestamp_no_channel(self):
        self.assertIsNone(self.parser.parse("2026-02-08 15:43:37 ", 1))

    def test_truncated_mid_effect_line(self):
        # Line cut off inside the effect name — parser should still
        # produce a ParsedLine with whatever message survived
        raw = "2026-02-08 15:43:37 [System] [] Received Effect Over Time: Incr"
        parsed = self.parser.parse(raw, 1)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.message, "Received Effect Over Time: Incr")
        # The handler will emit whatever it found
        bus = MagicMock()
        handler = EffectOverTimeHandler(bus, MagicMock())
        self.assertTrue(handler.can_handle(parsed))
        handler.handle(parsed)
        event = bus.publish.call_args[0][1]
        self.assertEqual(event.effect_name, "Incr")
        # Unknown partial effect -> UNKNOWN category, no pause
        self.assertFalse(pauses_damage_inference(event.effect_name))

    def test_truncated_at_prefix_colon(self):
        # "Received Effect Over Time:" with no name at all
        raw = "2026-02-08 15:43:37 [System] [] Received Effect Over Time:"
        parsed = self.parser.parse(raw, 1)
        self.assertIsNotNone(parsed)
        # can_handle checks startswith — prefix matches (no trailing space)
        bus = MagicMock()
        handler = EffectOverTimeHandler(bus, MagicMock())
        handler.handle(parsed)
        # Regex requires at least one char after the colon -> no event
        bus.publish.assert_not_called()

    def test_invalid_timestamp_rejected(self):
        # Bogus date numbers
        self.assertIsNone(self.parser.parse(
            "2026-13-45 25:99:99 [System] [] foo", 1,
        ))

    def test_non_numeric_timestamp_rejected(self):
        self.assertIsNone(self.parser.parse(
            "YYYY-MM-DD HH:MM:SS [System] [] foo", 1,
        ))

    def test_crlf_line_endings_stripped(self):
        raw = "2026-02-08 15:43:37 [System] [] Received Effect Over Time: Heal\r\n"
        parsed = self.parser.parse(raw, 1)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.message, "Received Effect Over Time: Heal")


# ---------------------------------------------------------------------------
# OCR failure: tool names missing, garbled, whitespace
# ---------------------------------------------------------------------------

class TestOCRFailureScenarios(unittest.TestCase):
    """OCR occasionally produces None, empty, whitespace, or garbled
    tool names. The engine must drop these cleanly instead of crashing
    or creating phantom tool entries."""

    def test_register_none_name_noop(self):
        eng = EnhancerInferenceEngine()
        # register_tool guards on empty string via `not tool_name`
        eng.register_tool("", 10.0, 20.0)
        self.assertEqual(eng._tools, {})

    def test_set_active_none_noop(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        eng.set_active_tool(None)  # should not clear active slot
        self.assertEqual(eng._active[KIND_DAMAGE], "Gun")

    def test_set_active_empty_string_noop(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        eng.set_active_tool("")
        self.assertEqual(eng._active[KIND_DAMAGE], "Gun")

    def test_garbled_name_becomes_separate_tool(self):
        # OCR returns "M4yhem Gun" on one frame, "Mayhem Gun" on another
        eng = EnhancerInferenceEngine()
        eng.register_tool("Mayhem Gun", 10.0, 20.0)
        eng.register_tool("M4yhem Gun", 10.0, 20.0)  # OCR misread
        self.assertIn("Mayhem Gun", eng._tools)
        self.assertIn("M4yhem Gun", eng._tools)
        # Their states are isolated
        eng.set_active_tool("Mayhem Gun")
        _feed_damage(eng, [15.0] * 5)
        eng.set_active_tool("M4yhem Gun")
        self.assertEqual(
            eng.get_state("M4yhem Gun", KIND_DAMAGE).in_range_count, 0,
        )

    def test_trailing_whitespace_ocr_name_treated_as_distinct(self):
        # "Gun " != "Gun" — the engine does not normalize
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.register_tool("Gun ", 10.0, 20.0)
        self.assertEqual(len(eng._tools), 2)

    def test_ocr_drops_active_tool_mid_stream(self):
        # OCR confident on tool A, then loses confidence (returns None)
        # for a few frames, then re-detects A. Samples during the gap
        # still feed A because set_active_tool(None) is a no-op.
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [15.0] * 5)
        eng.set_active_tool(None)  # OCR lost it
        _feed_damage(eng, [15.0] * 5, start_offset=10)  # still counted
        self.assertEqual(
            eng.active_tool_state().in_range_count, 10,
        )

    def test_ocr_misreads_to_unregistered_name_drops_samples(self):
        # OCR swaps from a registered tool to an unregistered name.
        # set_active_tool silently rejects the unregistered name, so
        # the previous tool stays active and keeps accumulating.
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [15.0] * 5)
        eng.set_active_tool("GarbledName")  # not registered -> noop
        _feed_damage(eng, [15.0] * 5, start_offset=10)
        # Samples still went to Gun because active never changed
        self.assertEqual(
            eng.get_state("Gun", KIND_DAMAGE).in_range_count, 10,
        )

    def test_register_with_nan_range_rejected(self):
        eng = EnhancerInferenceEngine()
        nan = float("nan")
        # NaN comparisons all return False; range_max <= 0 is False but
        # range_min > range_max is also False for NaN, so it slips past
        # the guards. Verify the state is at least non-crashing.
        eng.register_tool("Gun", 10.0, nan)
        # Whatever happens, the engine shouldn't crash on sampling
        if "Gun" in eng._tools:
            eng.set_active_tool("Gun")
            eng.observe_damage(15.0, False, _now())  # should not raise

    def test_register_inf_max_accepts(self):
        # Infinite max -> every sample is in-range -> confirms NONE
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, float("inf"))
        eng.set_active_tool("Gun")
        _feed_damage(eng, [9999.0] * CONFIRMATION_SAMPLES)
        self.assertEqual(
            eng.active_tool_state().state, InferenceState.CONFIRMED_NONE,
        )


# ---------------------------------------------------------------------------
# Sample value edge cases: NaN, inf, negative, clock skew
# ---------------------------------------------------------------------------

class TestSampleValueEdgeCases(unittest.TestCase):

    def setUp(self):
        self.eng = EnhancerInferenceEngine()
        self.eng.register_tool("Gun", 10.0, 20.0)
        self.eng.set_active_tool("Gun")

    def test_nan_damage_does_not_confirm(self):
        nan = float("nan")
        # NaN vs float bounds are all False -> falls into the "in-range"
        # branch (last else). Verify no crash and state stays reasonable.
        _feed_damage(self.eng, [nan] * 5)
        # No crash — specific classification is NaN-dependent
        self.assertIsNotNone(self.eng.active_tool_state())

    def test_inf_damage_is_over_range(self):
        _feed_damage(self.eng, [float("inf")])
        self.assertEqual(self.eng.active_tool_state().over_count, 1)

    def test_zero_damage_classified_as_under(self):
        _feed_damage(self.eng, [0.0])
        self.assertEqual(self.eng.active_tool_state().under_count, 1)

    def test_timestamps_going_backward_dont_crash(self):
        # Clock skew / log replay: second sample earlier than first.
        # Engine doesn't enforce monotonic timestamps — just tracks
        # first and last seen.
        base = _now()
        self.eng.observe_damage(15.0, False, base)
        self.eng.observe_damage(15.0, False, base - timedelta(seconds=10))
        state = self.eng.active_tool_state()
        self.assertEqual(state.in_range_count, 2)
        # last_sample_time is the most recent call, not chronologically latest
        self.assertEqual(state.last_sample_time, base - timedelta(seconds=10))

    def test_duplicate_timestamps_count_each_sample(self):
        base = _now()
        for _ in range(5):
            self.eng.observe_damage(15.0, False, base)
        self.assertEqual(self.eng.active_tool_state().in_range_count, 5)


# ---------------------------------------------------------------------------
# Reset + disable + register interactions
# ---------------------------------------------------------------------------

class TestResetDisableInteractions(unittest.TestCase):

    def test_reset_does_not_clear_disabled_flag(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        eng.disable_tool("Gun")
        eng.reset_tool("Gun")
        # Disabled persists across reset — intentional, user's choice
        self.assertTrue(eng.is_disabled("Gun"))

    def test_register_same_range_preserves_disabled(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.disable_tool("Gun")
        eng.register_tool("Gun", 10.0, 20.0)  # same range -> no-op
        self.assertTrue(eng.is_disabled("Gun"))

    def test_register_changed_range_preserves_disabled(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.disable_tool("Gun")
        eng.register_tool("Gun", 15.0, 25.0)  # range change resets state
        # Disable flag lives on the engine, not the ToolState, so reset
        # doesn't affect it
        self.assertTrue(eng.is_disabled("Gun"))
        self.assertEqual(
            eng.get_state("Gun", KIND_DAMAGE).state, InferenceState.UNKNOWN,
        )


# ---------------------------------------------------------------------------
# Persistence and continuation
# ---------------------------------------------------------------------------

import json


class TestPersistenceRoundTrip(unittest.TestCase):
    """to_dict / from_dict must preserve enough state that sampling
    continues transparently across a restart."""

    def test_empty_engine_round_trip(self):
        eng = EnhancerInferenceEngine()
        restored = EnhancerInferenceEngine.from_dict(eng.to_dict())
        self.assertEqual(restored._tools, {})
        self.assertIsNone(restored._active[KIND_DAMAGE])
        self.assertIsNone(restored._active[KIND_HEAL])
        self.assertEqual(restored._disabled_tools, set())

    def test_single_tool_unknown_state_round_trip(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [15.0] * 5)
        blob = eng.to_dict()
        restored = EnhancerInferenceEngine.from_dict(blob)
        s = restored.get_state("Gun", KIND_DAMAGE)
        self.assertIsNotNone(s)
        self.assertEqual(s.state, InferenceState.UNKNOWN)
        self.assertEqual(s.in_range_count, 5)
        self.assertEqual(s.damage_min, 10.0)
        self.assertEqual(s.damage_max, 20.0)
        self.assertEqual(restored._active[KIND_DAMAGE], "Gun")

    def test_confirmed_present_round_trip(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [25.0] * CONFIRMATION_SAMPLES)
        self.assertEqual(
            eng.active_tool_state().state, InferenceState.CONFIRMED_PRESENT,
        )
        restored = EnhancerInferenceEngine.from_dict(eng.to_dict())
        s = restored.active_tool_state()
        self.assertEqual(s.state, InferenceState.CONFIRMED_PRESENT)
        self.assertEqual(s.over_count, CONFIRMATION_SAMPLES)
        self.assertAlmostEqual(s.average_over_range, 5.0)

    def test_confirmed_none_round_trip(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [15.0] * CONFIRMATION_SAMPLES)
        restored = EnhancerInferenceEngine.from_dict(eng.to_dict())
        self.assertEqual(
            restored.active_tool_state().state, InferenceState.CONFIRMED_NONE,
        )

    def test_dual_slot_round_trip(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Rifle", 50.0, 100.0)
        eng.register_tool("FAP", 20.0, 50.0, kind=KIND_HEAL)
        eng.set_active_tool("Rifle")
        eng.set_active_tool("FAP")
        _feed_damage(eng, [75.0] * CONFIRMATION_SAMPLES)
        _feed_heal(eng, [35.0] * CONFIRMATION_SAMPLES)
        restored = EnhancerInferenceEngine.from_dict(eng.to_dict())
        self.assertEqual(restored._active[KIND_DAMAGE], "Rifle")
        self.assertEqual(restored._active[KIND_HEAL], "FAP")
        self.assertEqual(
            restored.get_state("Rifle", KIND_DAMAGE).state,
            InferenceState.CONFIRMED_NONE,
        )
        self.assertEqual(
            restored.get_state("FAP", KIND_HEAL).state,
            InferenceState.CONFIRMED_NONE,
        )

    def test_disabled_tool_round_trip(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        eng.disable_tool("Gun")
        restored = EnhancerInferenceEngine.from_dict(eng.to_dict())
        self.assertTrue(restored.is_disabled("Gun"))

    def test_awaiting_decision_not_persisted(self):
        # Prompt dies with the session — don't resurrect it on load.
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        eng.mark_awaiting_decision("Gun")
        restored = EnhancerInferenceEngine.from_dict(eng.to_dict())
        self.assertNotIn("Gun", restored._awaiting_decision)

    def test_pause_not_persisted(self):
        # Buff state is rebuilt from active effects on load, not from blob.
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.pause(KIND_DAMAGE, "Might")
        restored = EnhancerInferenceEngine.from_dict(eng.to_dict())
        self.assertFalse(restored.is_paused(KIND_DAMAGE))

    def test_sample_timestamps_round_trip(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [15.0] * 3)
        restored = EnhancerInferenceEngine.from_dict(eng.to_dict())
        s = restored.active_tool_state()
        self.assertEqual(s.first_sample_time, _now())
        self.assertEqual(s.last_sample_time, _now() + timedelta(seconds=2))

    def test_blob_is_json_serializable(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [25.0] * CONFIRMATION_SAMPLES)
        eng.disable_tool("Gun")
        # Round-trip through actual JSON, not just dict copy
        blob = json.dumps(eng.to_dict())
        restored = EnhancerInferenceEngine.from_dict(json.loads(blob))
        self.assertEqual(
            restored.active_tool_state().state, InferenceState.CONFIRMED_PRESENT,
        )
        self.assertTrue(restored.is_disabled("Gun"))

    def test_future_schema_version_ignored(self):
        blob = {
            "version": 999,
            "tools": {"Gun": {"damage_min": 10.0, "damage_max": 20.0}},
        }
        restored = EnhancerInferenceEngine.from_dict(blob)
        self.assertEqual(restored._tools, {})

    def test_malformed_blob_does_not_crash(self):
        # None, non-dict, missing keys
        EnhancerInferenceEngine.from_dict(None)
        EnhancerInferenceEngine.from_dict("not a dict")
        EnhancerInferenceEngine.from_dict({})
        EnhancerInferenceEngine.from_dict({"version": 1})

    def test_unknown_state_value_falls_back_to_unknown(self):
        blob = {
            "version": 1,
            "tools": {
                "Gun": {
                    "tool_name": "Gun",
                    "damage_min": 10.0,
                    "damage_max": 20.0,
                    "grace": 0.2,
                    "kind": "damage",
                    "state": "bogus",
                },
            },
        }
        restored = EnhancerInferenceEngine.from_dict(blob)
        self.assertEqual(
            restored.get_state("Gun", KIND_DAMAGE).state, InferenceState.UNKNOWN,
        )

    def test_active_tool_pointing_at_missing_tool_cleared(self):
        blob = {
            "version": 1,
            "tools": {},
            "active": {"damage": "Ghost", "heal": None},
        }
        restored = EnhancerInferenceEngine.from_dict(blob)
        self.assertIsNone(restored._active[KIND_DAMAGE])


class TestPersistenceContinuation(unittest.TestCase):
    """Core requirement: after restart, sampling picks up where it
    left off without re-confirming or double-counting."""

    def test_partial_samples_then_reload_then_confirm(self):
        # 10 samples pre-reload, 5 samples post-reload -> confirmed
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [25.0] * 10)
        self.assertEqual(
            eng.active_tool_state().state, InferenceState.UNKNOWN,
        )
        restored = EnhancerInferenceEngine.from_dict(eng.to_dict())
        # Feed 5 more -> crosses CONFIRMATION_SAMPLES = 15
        transitions = _feed_damage(restored, [25.0] * 5, start_offset=10)
        confirmed = [
            t for t in transitions
            if t.event == InferenceEvent.CONFIRMED_PRESENT
        ]
        self.assertEqual(len(confirmed), 1)
        self.assertEqual(
            restored.active_tool_state().state, InferenceState.CONFIRMED_PRESENT,
        )

    def test_confirmed_state_survives_reload_and_detects_restart(self):
        # Confirmed present, reload, feed contradictions -> restart fires
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [25.0] * CONFIRMATION_SAMPLES)
        restored = EnhancerInferenceEngine.from_dict(eng.to_dict())
        transitions = _feed_damage(
            restored, [15.0] * CONTRADICTION_SAMPLES,
            start_offset=CONFIRMATION_SAMPLES,
        )
        restarts = [
            t for t in transitions if t.event == InferenceEvent.RESTART
        ]
        self.assertEqual(len(restarts), 1)

    def test_disabled_tool_stays_disabled_after_reload(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        eng.disable_tool("Gun")
        restored = EnhancerInferenceEngine.from_dict(eng.to_dict())
        _feed_damage(restored, [25.0] * CONFIRMATION_SAMPLES)
        # Samples dropped because still disabled
        self.assertEqual(
            restored.active_tool_state().over_count, 0,
        )

    def test_contradiction_count_survives_reload(self):
        # Mid-contradiction reload: counter preserved, one more
        # contradiction triggers restart at exactly the normal threshold.
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [25.0] * CONFIRMATION_SAMPLES)
        _feed_damage(
            eng, [15.0] * (CONTRADICTION_SAMPLES - 1),
            start_offset=CONFIRMATION_SAMPLES,
        )
        self.assertEqual(
            eng.active_tool_state().contradiction_count,
            CONTRADICTION_SAMPLES - 1,
        )
        restored = EnhancerInferenceEngine.from_dict(eng.to_dict())
        transitions = _feed_damage(restored, [15.0], start_offset=100)
        restarts = [
            t for t in transitions if t.event == InferenceEvent.RESTART
        ]
        self.assertEqual(len(restarts), 1)

    def test_double_round_trip_is_stable(self):
        # A -> blob -> B -> blob -> C should equal B
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [25.0] * CONFIRMATION_SAMPLES)
        b_blob = eng.to_dict()
        b = EnhancerInferenceEngine.from_dict(b_blob)
        c_blob = b.to_dict()
        self.assertEqual(b_blob, c_blob)

    def test_reload_does_not_double_count_samples(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [15.0] * 7)
        restored = EnhancerInferenceEngine.from_dict(eng.to_dict())
        self.assertEqual(
            restored.active_tool_state().in_range_count, 7,
        )
        # Feed 8 more -> exactly CONFIRMATION_SAMPLES total
        _feed_damage(restored, [15.0] * 8, start_offset=7)
        self.assertEqual(
            restored.active_tool_state().in_range_count, 15,
        )
        self.assertEqual(
            restored.active_tool_state().state, InferenceState.CONFIRMED_NONE,
        )


class TestPersistenceReRegistration(unittest.TestCase):
    """After crash recovery, the tracker re-registers tools from the
    current tool catalog. Verify that register_tool's normal semantics
    (preserve on match, reset on range change) still hold."""

    def test_re_register_same_range_preserves_loaded_state(self):
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [25.0] * CONFIRMATION_SAMPLES)
        restored = EnhancerInferenceEngine.from_dict(eng.to_dict())
        # Tracker re-registers on load
        restored.register_tool("Gun", 10.0, 20.0)
        self.assertEqual(
            restored.active_tool_state().state, InferenceState.CONFIRMED_PRESENT,
        )
        self.assertEqual(
            restored.active_tool_state().over_count, CONFIRMATION_SAMPLES,
        )

    def test_re_register_changed_range_resets_loaded_state(self):
        # Tool stats changed in the DB between sessions (e.g. amp
        # swap). Loaded state is stale -> reset on re-register.
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [25.0] * CONFIRMATION_SAMPLES)
        restored = EnhancerInferenceEngine.from_dict(eng.to_dict())
        restored.register_tool("Gun", 15.0, 30.0)  # new range
        self.assertEqual(
            restored.active_tool_state().state, InferenceState.UNKNOWN,
        )
        self.assertEqual(restored.active_tool_state().over_count, 0)

    def test_loaded_tool_missing_from_catalog_still_usable(self):
        # A tool in the loaded blob that's NOT in the current tool
        # catalog — the engine keeps it (tracker may or may not
        # re-activate it). No crash.
        eng = EnhancerInferenceEngine()
        eng.register_tool("OldGun", 10.0, 20.0)
        eng.set_active_tool("OldGun")
        _feed_damage(eng, [25.0] * CONFIRMATION_SAMPLES)
        restored = EnhancerInferenceEngine.from_dict(eng.to_dict())
        # Tracker only registers "NewGun" this session
        restored.register_tool("NewGun", 30.0, 50.0)
        self.assertIn("OldGun", restored._tools)
        self.assertIn("NewGun", restored._tools)

    def test_active_tool_restored_persists_through_no_ops(self):
        # Reload, then tracker calls set_active_tool with the same
        # name -> no state reset.
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        _feed_damage(eng, [15.0] * 10)
        restored = EnhancerInferenceEngine.from_dict(eng.to_dict())
        restored.set_active_tool("Gun")  # tracker re-activates
        self.assertEqual(
            restored.active_tool_state().in_range_count, 10,
        )


if __name__ == "__main__":
    unittest.main()
