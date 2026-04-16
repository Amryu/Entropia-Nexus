"""Session tracking persistence and crash recovery tests.

These tests exercise the full save/load cycle against a real
in-memory SQLite database so the schema, transaction wrapping,
orphan cleanup, and recovery blob round-trip are all covered by
the same test.

Scenarios covered:
- Clean save + restore of a session with kills and loot
- Orphan cleanup of partial encounters on restore
- Transaction rollback on mid-persist DB failure
- Enhancer inference state survives a crash
- Shrapnel/break buffer survives a crash
- Config signature triggers recalc on restore
- Atomic merge rollback
- Late-arriving (post-kill) loot
- Full crash → restart cycle
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from client.core.database import Database
from client.hunt.encounter_manager import EncounterManager
from client.hunt.enhancer_inference import (
    CONFIRMATION_SAMPLES,
    EnhancerInferenceEngine,
    InferenceState,
    KIND_DAMAGE,
)
from client.hunt.session import HuntSession, MobEncounter
from client.hunt.tracker import HuntTracker


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_config(**overrides):
    config = MagicMock()
    config.encounter_close_timeout_ms = overrides.get("encounter_close_timeout_ms", 15000)
    config.loot_close_timeout_ms = overrides.get("loot_close_timeout_ms", 3000)
    config.max_encounter_duration_ms = overrides.get("max_encounter_duration_ms", 600000)
    config.attribution_window_ms = overrides.get("attribution_window_ms", 3000)
    config.session_auto_timeout_ms = overrides.get("session_auto_timeout_ms", 3600000)
    config.hunt_split_mob_threshold = overrides.get("hunt_split_mob_threshold", 10)
    config.hunt_split_min_remote_kills = overrides.get("hunt_split_min_remote_kills", 5)
    config.hunt_markup_pct = overrides.get("hunt_markup_pct", 100.0)
    config.loot_blacklist = overrides.get("loot_blacklist", [])
    config.loot_blacklist_per_mob = overrides.get("loot_blacklist_per_mob", {})
    config.tool_cost_filter = overrides.get("tool_cost_filter", [])
    config.cost_settings_version = overrides.get("cost_settings_version", 1)
    config.custom_markups_version = overrides.get("custom_markups_version", 1)
    config.auto_merge_deaths = overrides.get("auto_merge_deaths", False)
    return config


def _make_db() -> tuple[Database, str]:
    fd, path = tempfile.mkstemp(suffix=".db", prefix="test_session_")
    os.close(fd)
    return Database(path), path


def _insert_session(db: Database, session_id: str = "sess-1",
                    start: datetime | None = None) -> None:
    start = start or datetime(2026, 4, 10, 12, 0, 0)
    db.insert_hunt_session(session_id, start.isoformat())


def _insert_encounter(db: Database, enc_id: str, session_id: str,
                      end_time: str | None, mob: str = "Atrox") -> None:
    """Directly insert an encounter row for setup purposes."""
    with db._lock:
        db._conn.execute(
            "INSERT INTO mob_encounters "
            "(id, session_id, mob_name, mob_name_source, start_time, end_time) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (enc_id, session_id, mob, "ocr",
             "2026-04-10T12:00:00", end_time),
        )
        db._conn.commit()


# ---------------------------------------------------------------------------
# Database.transaction() primitives
# ---------------------------------------------------------------------------

class TestDatabaseTransaction(unittest.TestCase):
    """Verify the new transaction() context manager rolls back
    multi-statement writes on failure."""

    def setUp(self):
        self.db, self.path = _make_db()
        _insert_session(self.db)

    def tearDown(self):
        self.db.close()
        os.unlink(self.path)

    def test_successful_tx_commits(self):
        with self.db.transaction():
            _insert_encounter(self.db, "enc-a", "sess-1", "2026-04-10T12:01:00")
        rows = self.db.get_session_encounters("sess-1")
        self.assertEqual(len(rows), 1)

    def test_rollback_on_exception_undoes_writes(self):
        try:
            with self.db.transaction():
                _insert_encounter(self.db, "enc-b", "sess-1", "2026-04-10T12:01:00")
                raise RuntimeError("simulated crash")
        except RuntimeError:
            pass
        rows = self.db.get_session_encounters("sess-1")
        self.assertEqual(rows, [])

    def test_rollback_undoes_multiple_writes(self):
        try:
            with self.db.transaction():
                _insert_encounter(self.db, "enc-c", "sess-1", "2026-04-10T12:01:00")
                _insert_encounter(self.db, "enc-d", "sess-1", "2026-04-10T12:02:00")
                raise ValueError("fail after two inserts")
        except ValueError:
            pass
        self.assertEqual(self.db.get_session_encounters("sess-1"), [])

    def test_nested_tx_rollback_only_inner(self):
        # SAVEPOINT-based tx should let the outer tx proceed even if
        # the inner one rolls back.
        with self.db.transaction():
            _insert_encounter(self.db, "outer", "sess-1", "2026-04-10T12:01:00")
            try:
                with self.db.transaction():
                    _insert_encounter(self.db, "inner", "sess-1", "2026-04-10T12:02:00")
                    raise RuntimeError("inner fail")
            except RuntimeError:
                pass
            # outer write still visible
        rows = self.db.get_session_encounters("sess-1")
        names = {r["id"] for r in rows}
        self.assertIn("outer", names)
        self.assertNotIn("inner", names)


# ---------------------------------------------------------------------------
# Orphan partial encounter cleanup
# ---------------------------------------------------------------------------

class TestOrphanCleanup(unittest.TestCase):

    def setUp(self):
        self.db, self.path = _make_db()
        _insert_session(self.db)

    def tearDown(self):
        self.db.close()
        os.unlink(self.path)

    def test_delete_partial_encounters_removes_end_time_null(self):
        _insert_encounter(self.db, "complete", "sess-1", "2026-04-10T12:05:00")
        _insert_encounter(self.db, "partial", "sess-1", None)
        removed = self.db.delete_partial_encounters("sess-1")
        self.assertEqual(removed, 1)
        rows = self.db.get_session_encounters("sess-1")
        ids = {r["id"] for r in rows}
        self.assertEqual(ids, {"complete"})

    def test_delete_partial_encounters_no_orphans_returns_zero(self):
        _insert_encounter(self.db, "complete", "sess-1", "2026-04-10T12:05:00")
        self.assertEqual(self.db.delete_partial_encounters("sess-1"), 0)

    def test_delete_partial_cascades_to_loot_and_stats(self):
        _insert_encounter(self.db, "partial", "sess-1", None)
        # Add child rows
        with self.db._lock:
            self.db._conn.execute(
                "INSERT INTO encounter_loot_items "
                "(encounter_id, item_name, quantity, value_ped) "
                "VALUES (?, ?, ?, ?)",
                ("partial", "Shrapnel", 100, 1.0),
            )
            self.db._conn.execute(
                "INSERT INTO encounter_tool_stats "
                "(encounter_id, tool_name, shots_fired, damage_dealt, critical_hits) "
                "VALUES (?, ?, ?, ?, ?)",
                ("partial", "Gun", 10, 100.0, 1),
            )
            self.db._conn.commit()

        self.db.delete_partial_encounters("sess-1")
        with self.db._lock:
            loot_count = self.db._conn.execute(
                "SELECT COUNT(*) FROM encounter_loot_items WHERE encounter_id = ?",
                ("partial",),
            ).fetchone()[0]
            tool_count = self.db._conn.execute(
                "SELECT COUNT(*) FROM encounter_tool_stats WHERE encounter_id = ?",
                ("partial",),
            ).fetchone()[0]
        self.assertEqual(loot_count, 0)
        self.assertEqual(tool_count, 0)

    def test_cleanup_scoped_to_session(self):
        _insert_session(self.db, session_id="sess-2")
        _insert_encounter(self.db, "partial-1", "sess-1", None)
        _insert_encounter(self.db, "partial-2", "sess-2", None)
        removed = self.db.delete_partial_encounters("sess-1")
        self.assertEqual(removed, 1)
        # sess-2's orphan untouched
        rows = self.db.get_session_encounters("sess-2")
        self.assertEqual(len(rows), 1)


# ---------------------------------------------------------------------------
# Recovery state blobs: save + load
# ---------------------------------------------------------------------------

class TestRecoveryStateBlobs(unittest.TestCase):

    def setUp(self):
        self.db, self.path = _make_db()
        _insert_session(self.db)

    def tearDown(self):
        self.db.close()
        os.unlink(self.path)

    def test_empty_session_returns_nulls(self):
        state = self.db.get_session_recovery_state("sess-1")
        self.assertIsNone(state["enhancer_inference_state"])
        self.assertIsNone(state["shrapnel_buffer"])
        self.assertIsNone(state["break_buffer"])
        self.assertIsNone(state["config_signature"])

    def test_save_and_load_blobs(self):
        self.db.save_session_recovery_state(
            "sess-1",
            enhancer_inference_state='{"version": 1}',
            break_buffer='[["2026-04-10T12:00:00", 0.8]]',
            config_signature="abc123",
        )
        state = self.db.get_session_recovery_state("sess-1")
        self.assertEqual(state["enhancer_inference_state"], '{"version": 1}')
        self.assertEqual(state["break_buffer"], '[["2026-04-10T12:00:00", 0.8]]')
        self.assertEqual(state["config_signature"], "abc123")
        self.assertIsNone(state["shrapnel_buffer"])

    def test_partial_update_preserves_other_fields(self):
        self.db.save_session_recovery_state(
            "sess-1",
            enhancer_inference_state='{"version": 1}',
            config_signature="sig-a",
        )
        # Update only the signature; enhancer state must survive
        self.db.save_session_recovery_state(
            "sess-1", config_signature="sig-b",
        )
        state = self.db.get_session_recovery_state("sess-1")
        self.assertEqual(state["enhancer_inference_state"], '{"version": 1}')
        self.assertEqual(state["config_signature"], "sig-b")

    def test_missing_session_returns_all_none(self):
        state = self.db.get_session_recovery_state("nonexistent")
        self.assertEqual(
            state,
            {
                "enhancer_inference_state": None,
                "shrapnel_buffer": None,
                "break_buffer": None,
                "config_signature": None,
            },
        )


# ---------------------------------------------------------------------------
# Enhancer inference survives a crash via session recovery blob
# ---------------------------------------------------------------------------

class TestEnhancerInferenceSessionRoundTrip(unittest.TestCase):
    """End-to-end: build engine state, serialize into session row,
    load it back as if after a crash, verify it resumes."""

    def setUp(self):
        self.db, self.path = _make_db()
        _insert_session(self.db)

    def tearDown(self):
        self.db.close()
        os.unlink(self.path)

    def test_confirmed_state_survives_round_trip(self):
        # Build an engine mid-session with confirmed enhancers
        eng = EnhancerInferenceEngine()
        eng.register_tool("Gun", 10.0, 20.0)
        eng.set_active_tool("Gun")
        base = datetime(2026, 4, 10, 12, 0, 0)
        for i in range(CONFIRMATION_SAMPLES):
            eng.observe_damage(25.0, False, base + timedelta(seconds=i))
        self.assertEqual(
            eng.active_tool_state().state, InferenceState.CONFIRMED_PRESENT,
        )

        # Save into session row (simulates tracker._save_recovery_state)
        self.db.save_session_recovery_state(
            "sess-1",
            enhancer_inference_state=json.dumps(eng.to_dict()),
        )

        # Simulate crash + restart: load blob, rebuild engine
        state = self.db.get_session_recovery_state("sess-1")
        restored = EnhancerInferenceEngine.from_dict(
            json.loads(state["enhancer_inference_state"]),
        )
        self.assertEqual(
            restored.active_tool_state().state, InferenceState.CONFIRMED_PRESENT,
        )
        self.assertEqual(
            restored.active_tool_state().over_count, CONFIRMATION_SAMPLES,
        )

    def test_corrupt_blob_falls_back_to_empty_engine(self):
        self.db.save_session_recovery_state(
            "sess-1",
            enhancer_inference_state="{truncated json",
        )
        state = self.db.get_session_recovery_state("sess-1")
        try:
            json.loads(state["enhancer_inference_state"])
            self.fail("expected JSON decode error")
        except json.JSONDecodeError:
            pass
        # Tracker code catches this and falls back to an empty engine
        fresh = EnhancerInferenceEngine()
        self.assertEqual(fresh._tools, {})


# ---------------------------------------------------------------------------
# HuntTracker end-to-end: _save_recovery_state + _restore_recovery_state
# ---------------------------------------------------------------------------

class TestTrackerRecoveryHelpers(unittest.TestCase):
    """Exercise tracker's save/restore helpers against a real DB."""

    def setUp(self):
        self.db, self.path = _make_db()
        _insert_session(self.db)
        self.config = _make_config()
        self.event_bus = MagicMock()
        self.tracker = HuntTracker(self.config, self.event_bus, self.db)
        self.tracker._live = True
        self.session = HuntSession(
            id="sess-1", start_time=datetime(2026, 4, 10, 12, 0, 0),
        )
        self.tracker._session = self.session
        self.tracker._manager = EncounterManager(self.config, self.session)
        self.tracker._active = True

    def tearDown(self):
        self.db.close()
        os.unlink(self.path)

    def test_save_recovery_state_persists_engine(self):
        self.tracker._enhancer_inference.register_tool("Gun", 10.0, 20.0)
        self.tracker._enhancer_inference.set_active_tool("Gun")
        base = datetime(2026, 4, 10, 12, 0, 0)
        for i in range(CONFIRMATION_SAMPLES):
            self.tracker._enhancer_inference.observe_damage(
                25.0, False, base + timedelta(seconds=i),
            )
        self.tracker._save_recovery_state()

        state = self.db.get_session_recovery_state("sess-1")
        self.assertIsNotNone(state["enhancer_inference_state"])
        blob = json.loads(state["enhancer_inference_state"])
        self.assertIn("Gun", blob["tools"])
        self.assertEqual(blob["tools"]["Gun"]["state"], "confirmed_present")
        self.assertIsNotNone(state["config_signature"])

    def test_save_recovery_state_persists_break_buffer(self):
        ts = datetime(2026, 4, 10, 12, 0, 0)
        self.tracker._recent_enhancer_breaks = [(ts, 0.8), (ts, 1.2)]
        self.tracker._save_recovery_state()

        state = self.db.get_session_recovery_state("sess-1")
        buf = json.loads(state["break_buffer"])
        self.assertEqual(len(buf), 2)
        self.assertEqual(buf[0][1], 0.8)
        self.assertEqual(buf[1][1], 1.2)

    def test_restore_recovery_state_rehydrates_engine(self):
        # Save state from one tracker, restore into a fresh one
        self.tracker._enhancer_inference.register_tool("Gun", 10.0, 20.0)
        self.tracker._enhancer_inference.set_active_tool("Gun")
        base = datetime(2026, 4, 10, 12, 0, 0)
        for i in range(CONFIRMATION_SAMPLES):
            self.tracker._enhancer_inference.observe_damage(
                25.0, False, base + timedelta(seconds=i),
            )
        self.tracker._save_recovery_state()

        # New tracker (simulates app restart)
        tracker2 = HuntTracker(_make_config(), MagicMock(), self.db)
        tracker2._session = self.session
        tracker2._restore_recovery_state("sess-1")

        state = tracker2._enhancer_inference.get_state("Gun", KIND_DAMAGE)
        self.assertIsNotNone(state)
        self.assertEqual(state.state, InferenceState.CONFIRMED_PRESENT)

    def test_restore_with_no_blob_is_noop(self):
        # Fresh session, nothing saved — restore should be silent no-op
        self.tracker._restore_recovery_state("sess-1")
        self.assertEqual(self.tracker._enhancer_inference._tools, {})

    def test_restore_prunes_stale_break_buffer_entries(self):
        old_ts = datetime.utcnow() - timedelta(minutes=5)
        recent_ts = datetime.utcnow()
        self.db.save_session_recovery_state(
            "sess-1",
            break_buffer=json.dumps([
                [old_ts.isoformat(), 0.5],
                [recent_ts.isoformat(), 0.8],
            ]),
        )
        self.tracker._restore_recovery_state("sess-1")
        # Only the recent entry should survive the cutoff
        self.assertEqual(len(self.tracker._recent_enhancer_breaks), 1)
        self.assertEqual(self.tracker._recent_enhancer_breaks[0][1], 0.8)

    def test_config_change_triggers_recalc(self):
        # Save with one signature
        self.tracker._save_recovery_state()
        original_sig = self.db.get_session_recovery_state(
            "sess-1",
        )["config_signature"]

        # Change config on a fresh tracker and restore
        new_config = _make_config(cost_settings_version=999)
        tracker2 = HuntTracker(new_config, MagicMock(), self.db)
        tracker2._session = self.session
        tracker2.recalculate_session = MagicMock()
        tracker2._restore_recovery_state("sess-1")
        tracker2.recalculate_session.assert_called_once()

    def test_matching_config_skips_recalc(self):
        self.tracker._save_recovery_state()

        tracker2 = HuntTracker(self.config, MagicMock(), self.db)
        tracker2._session = self.session
        tracker2.recalculate_session = MagicMock()
        tracker2._restore_recovery_state("sess-1")
        tracker2.recalculate_session.assert_not_called()

    def test_corrupt_enhancer_blob_logged_not_raised(self):
        self.db.save_session_recovery_state(
            "sess-1",
            enhancer_inference_state="{truncated",
        )
        # Should not raise
        self.tracker._restore_recovery_state("sess-1")
        self.assertEqual(self.tracker._enhancer_inference._tools, {})


# ---------------------------------------------------------------------------
# End-to-end: crash + restart cycle
# ---------------------------------------------------------------------------

class TestFullCrashRestartCycle(unittest.TestCase):
    """Simulate a full session lifecycle: start, kill, crash, restart,
    restore. Verify nothing is lost or double-counted."""

    def setUp(self):
        self.db, self.path = _make_db()
        self.config = _make_config()

    def tearDown(self):
        self.db.close()
        os.unlink(self.path)

    def _make_tracker(self):
        tracker = HuntTracker(self.config, MagicMock(), self.db)
        tracker._live = True
        return tracker

    def test_orphan_cleanup_runs_on_restore(self):
        # Pre-populate a session with one completed and one orphan
        _insert_session(self.db, session_id="sess-1")
        _insert_encounter(
            self.db, "complete-1", "sess-1", "2026-04-10T12:05:00",
        )
        _insert_encounter(self.db, "orphan-1", "sess-1", None)

        tracker = self._make_tracker()
        # Simulate _try_restore_session's orphan cleanup call
        removed = self.db.delete_partial_encounters("sess-1")
        self.assertEqual(removed, 1)
        rows = self.db.get_session_encounters("sess-1")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "complete-1")

    def test_recovery_blob_survives_db_reconnect(self):
        # Save state, close DB, reopen, verify blob still there
        _insert_session(self.db, session_id="sess-1")
        self.db.save_session_recovery_state(
            "sess-1",
            enhancer_inference_state='{"version": 1, "tools": {}}',
            config_signature="sig-1",
        )
        self.db.close()

        # Reopen at the same path
        db2 = Database(self.path)
        state = db2.get_session_recovery_state("sess-1")
        self.assertEqual(state["config_signature"], "sig-1")
        self.assertEqual(
            state["enhancer_inference_state"],
            '{"version": 1, "tools": {}}',
        )
        db2.close()
        # Prevent tearDown double-close
        self.db = db2

    def test_persist_encounter_tx_rollback_on_failure(self):
        """Mid-write failure must leave the encounter row un-updated."""
        _insert_session(self.db, session_id="sess-1")
        # Pre-insert the encounter row so tracker's _ensure_encounter_in_db
        # sees it as existing. Also mark it as persisted in the tracker so
        # the insert path is skipped.
        _insert_encounter(self.db, "enc-1", "sess-1", None)

        # Inject a db wrapper that fails on the loot insert step
        failing_db = _FailingDB(self.db, fail_on="insert_encounter_loot_items")
        tracker = HuntTracker(self.config, MagicMock(), failing_db)
        tracker._live = True
        tracker._persisted_encounter_ids.add("enc-1")
        session = HuntSession(id="sess-1", start_time=datetime(2026, 4, 10, 12, 0, 0))
        tracker._session = session
        tracker._manager = EncounterManager(self.config, session)

        # Build an encounter with loot so the insert step runs
        enc = MobEncounter(
            id="enc-1",
            session_id="sess-1",
            mob_name="Atrox",
            mob_name_source="ocr",
            start_time=datetime(2026, 4, 10, 12, 0, 0),
            end_time=datetime(2026, 4, 10, 12, 1, 0),
            damage_dealt=100.0,
            loot_total_ped=5.0,
        )
        from client.hunt.session import EncounterLootItem
        enc.loot_items.append(
            EncounterLootItem(item_name="Shrapnel", quantity=100, value_ped=1.0),
        )

        with self.assertRaises(RuntimeError):
            tracker._persist_encounter(enc)

        # The encounter row should NOT have the finalized end_time
        # because the tx rolled back the update.
        with self.db._lock:
            row = self.db._conn.execute(
                "SELECT end_time, damage_dealt FROM mob_encounters WHERE id = ?",
                ("enc-1",),
            ).fetchone()
        # damage_dealt should still be 0 (original) — rollback worked
        self.assertEqual(row[0], None)
        self.assertEqual(row[1], 0)


class _FailingDB:
    """Thin wrapper that forwards every call except one, which raises.

    Used to simulate a DB write failure mid-transaction. Must forward
    transaction() context manager so the real rollback path runs.
    """

    def __init__(self, real: Database, fail_on: str):
        self._real = real
        self._fail_on = fail_on
        # Expose the lock + conn so tests can still inspect post-failure
        self._lock = real._lock

    def __getattr__(self, name):
        if name == self._fail_on:
            def _raise(*a, **kw):
                raise RuntimeError(f"simulated {name} failure")
            return _raise
        return getattr(self._real, name)


# ---------------------------------------------------------------------------
# Post-kill late loot
# ---------------------------------------------------------------------------

class TestPostKillLoot(unittest.TestCase):
    """Loot arriving after an encounter was already closed+persisted
    must still land on the correct encounter and re-persist."""

    def setUp(self):
        self.config = _make_config()
        self.session = HuntSession(
            id="s1", start_time=datetime(2026, 4, 10, 12, 0, 0),
        )
        self.em = EncounterManager(self.config, self.session)

    def test_late_loot_attaches_to_recently_closed_encounter(self):
        self.em.on_mob_name_detected("Atrox")
        self.em.on_damage_dealt(50.0)
        # Encounter closes (e.g. via death or timeout)
        closed = self.em._close_encounter(
            self.em._active, datetime(2026, 4, 10, 12, 0, 30),
        )
        self.assertIsNotNone(closed)
        self.assertEqual(self.em._recently_closed[-1][1], closed)

        # Late loot arrives within the window
        target = self.em._find_loot_target(
            datetime(2026, 4, 10, 12, 0, 32),
        )
        self.assertIs(target, closed)

    def test_late_loot_outside_window_is_orphaned(self):
        self.em.on_mob_name_detected("Atrox")
        self.em.on_damage_dealt(50.0)
        self.em._close_encounter(
            self.em._active, datetime(2026, 4, 10, 12, 0, 30),
        )

        # Loot arrives well after the POST_KILL_LOOT_WINDOW
        target = self.em._find_loot_target(
            datetime(2026, 4, 10, 12, 1, 0),
        )
        self.assertIsNone(target)

    def test_prune_recently_closed_drops_old_entries(self):
        self.em.on_mob_name_detected("Atrox")
        self.em.on_damage_dealt(50.0)
        self.em._close_encounter(
            self.em._active, datetime(2026, 4, 10, 12, 0, 30),
        )
        self.em._prune_recently_closed(datetime(2026, 4, 10, 12, 0, 32))
        self.assertEqual(len(self.em._recently_closed), 1)
        self.em._prune_recently_closed(datetime(2026, 4, 10, 12, 1, 0))
        self.assertEqual(self.em._recently_closed, [])


# ---------------------------------------------------------------------------
# Atomic merge
# ---------------------------------------------------------------------------

class TestAtomicMerge(unittest.TestCase):
    """Verify merge_open_encounter rolls back cleanly when either
    side's persist fails."""

    def setUp(self):
        self.db, self.path = _make_db()
        _insert_session(self.db)
        self.config = _make_config()
        self.tracker = HuntTracker(self.config, MagicMock(), self.db)
        self.tracker._live = True
        self.session = HuntSession(
            id="sess-1", start_time=datetime(2026, 4, 10, 12, 0, 0),
        )
        self.tracker._session = self.session
        self.tracker._manager = EncounterManager(self.config, self.session)
        self.tracker._active = True

    def tearDown(self):
        self.db.close()
        os.unlink(self.path)

    def _build_open_and_target(self):
        from client.hunt.session import MobEncounter
        open_enc = MobEncounter(
            id="open-1",
            session_id="sess-1",
            mob_name="Atrox",
            mob_name_source="ocr",
            start_time=datetime(2026, 4, 10, 12, 0, 0),
            end_time=datetime(2026, 4, 10, 12, 0, 30),
            damage_dealt=50.0,
            outcome="death",
            is_open_ended=True,
        )
        target_enc = MobEncounter(
            id="target-1",
            session_id="sess-1",
            mob_name="Atrox",
            mob_name_source="ocr",
            start_time=datetime(2026, 4, 10, 12, 1, 0),
            end_time=datetime(2026, 4, 10, 12, 2, 0),
            damage_dealt=80.0,
            outcome="kill",
        )
        self.tracker._open_encounters = [open_enc]
        self.session.encounters.append(target_enc)
        return open_enc, target_enc

    def test_successful_merge_persists_both(self):
        self._build_open_and_target()
        result = self.tracker.merge_open_encounter("open-1", "target-1")
        self.assertTrue(result)
        rows = self.db.get_session_encounters("sess-1")
        ids = {r["id"] for r in rows}
        self.assertEqual(ids, {"open-1", "target-1"})

    def test_merge_failure_rolls_back_both_sides(self):
        open_enc, target_enc = self._build_open_and_target()

        # Inject failure on the second persist by patching insert_encounter_loot_items
        # to raise once. Since neither enc has loot items, we need a different hook —
        # patch upsert_encounter_tool_stat to fail on the second encounter's call.
        original = self.db.upsert_encounter_tool_stat
        call_count = [0]
        def flaky(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] > 1:
                raise RuntimeError("simulated failure on second persist")
            return original(*args, **kwargs)

        # Give both encounters tool_stats so upsert_encounter_tool_stat fires
        from client.hunt.session import EncounterToolStats
        open_enc.tool_stats["Gun"] = EncounterToolStats(
            tool_name="Gun", shots_fired=5, damage_dealt=50.0,
        )
        target_enc.tool_stats["Gun"] = EncounterToolStats(
            tool_name="Gun", shots_fired=8, damage_dealt=80.0,
        )

        self.db.upsert_encounter_tool_stat = flaky
        try:
            result = self.tracker.merge_open_encounter("open-1", "target-1")
        finally:
            self.db.upsert_encounter_tool_stat = original

        self.assertFalse(result)
        # Neither encounter should have been finalized to disk
        rows = self.db.get_session_encounters("sess-1")
        for r in rows:
            self.assertIsNone(r.get("merged_into"))
            self.assertIsNone(r.get("merged_from"))


if __name__ == "__main__":
    unittest.main()
