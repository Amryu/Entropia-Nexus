"""Tests for local-first skill sync behavior."""

import tempfile
import unittest
from pathlib import Path

from client.core.database import Database
from client.skills.sync import SkillDataManager


class _FakeDataClient:
    def get_skills(self):
        return []

    def get_professions(self):
        return []

    def get_skill_ranks(self):
        return []


class _FakeNexusClient:
    def __init__(self, remote_skills: dict[str, float] | None = None, *, upload_ok: bool = True):
        self.remote_skills = dict(remote_skills or {})
        self.upload_ok = upload_ok
        self.upload_calls: list[tuple[dict[str, float], bool]] = []

    def get_skills(self):
        return {"skills": dict(self.remote_skills)}

    def upload_skills(self, skills: dict[str, float], track_import: bool = True):
        self.upload_calls.append((dict(skills), track_import))
        if not self.upload_ok:
            return None
        self.remote_skills = dict(skills)
        return {"ok": True}

    def get_skill_history(self, skill_names=None, from_date=None, to_date=None):
        return None


class TestLocalSkillSync(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.db = Database(self._tmp.name)

    def tearDown(self):
        self.db.close()
        Path(self._tmp.name).unlink(missing_ok=True)

    def _manager(self, nexus_client=None):
        return SkillDataManager(_FakeDataClient(), nexus_client, db=self.db)

    def test_apply_correction_persists_local_dirty(self):
        mgr = self._manager()

        ok = mgr.apply_correction("Evade", 123.45)

        self.assertTrue(ok)
        self.assertAlmostEqual(self.db.get_local_skill_values()["Evade"], 123.45)
        self.assertAlmostEqual(self.db.get_dirty_local_skill_values()["Evade"], 123.45)

    def test_sync_from_nexus_pulls_and_caches_locally(self):
        nexus = _FakeNexusClient({"Aim": 50.0, "Evade": 10.5})
        mgr = self._manager(nexus)

        ok = mgr.sync_from_nexus()

        self.assertTrue(ok)
        self.assertAlmostEqual(mgr.get_skill_value("Aim"), 50.0)
        self.assertAlmostEqual(mgr.get_skill_value("Evade"), 10.5)
        self.assertEqual(self.db.get_dirty_local_skill_values(), {})
        self.assertAlmostEqual(self.db.get_local_skill_values()["Aim"], 50.0)

    def test_sync_from_nexus_pushes_pending_local_changes(self):
        # Create pending local change while offline.
        offline_mgr = self._manager()
        offline_mgr.apply_correction("Evade", 99.0)

        nexus = _FakeNexusClient({"Aim": 5.0, "Evade": 10.0})
        online_mgr = self._manager(nexus)

        ok = online_mgr.sync_from_nexus()

        self.assertTrue(ok)
        self.assertEqual(len(nexus.upload_calls), 1)
        uploaded_values, track_import = nexus.upload_calls[0]
        self.assertTrue(track_import)
        self.assertAlmostEqual(uploaded_values["Aim"], 5.0)
        self.assertAlmostEqual(uploaded_values["Evade"], 99.0)
        self.assertEqual(self.db.get_dirty_local_skill_values(), {})
        self.assertAlmostEqual(self.db.get_local_skill_values()["Evade"], 99.0)

    def test_import_remote_failure_keeps_local_dirty(self):
        nexus = _FakeNexusClient({"Aim": 10.0}, upload_ok=False)
        mgr = self._manager(nexus)

        ok = mgr.apply_imported_values({"Aim": 25.0})

        self.assertFalse(ok)
        self.assertAlmostEqual(self.db.get_local_skill_values()["Aim"], 25.0)
        self.assertAlmostEqual(self.db.get_dirty_local_skill_values()["Aim"], 25.0)
        history = self.db.get_local_skill_history(skill_names=["Aim"])
        self.assertGreaterEqual(len(history), 1)


if __name__ == "__main__":
    unittest.main()
