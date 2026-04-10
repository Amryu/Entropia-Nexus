import unittest
from datetime import datetime, timedelta

from client.hunt.session import HuntSession, Hunt, MobEncounter, EncounterToolStats
from client.hunt import stats as hunt_stats


def _enc(mob="Atrox", cost=10.0, loot=20.0, shots=5, ts=None,
         outcome="kill", is_global=False, is_hof=False):
    return MobEncounter(
        id=f"enc-{id(object())}",
        session_id="session-1",
        mob_name=mob,
        mob_name_source="ocr",
        start_time=ts or datetime(2026, 1, 1),
        end_time=ts or datetime(2026, 1, 1),
        shots_fired=shots,
        loot_total_ped=loot,
        cost=cost,
        outcome=outcome,
        is_global=is_global,
        is_hof=is_hof,
    )


class TestDashboardProviders(unittest.TestCase):

    def test_encounters_economy_basic(self):
        encs = [
            _enc(cost=10, loot=20),
            _enc(cost=5, loot=2),
            _enc(cost=15, loot=15),
        ]
        result = hunt_stats.encounters_economy(encs)
        self.assertEqual(result["total_kills"], 3)
        self.assertAlmostEqual(result["total_cost"], 30.0)
        self.assertAlmostEqual(result["total_loot"], 37.0)
        self.assertEqual(result["return_pct"], round(37/30*100, 2))
        self.assertAlmostEqual(result["profit_loss"], 7.0)

    def test_encounters_economy_empty(self):
        result = hunt_stats.encounters_economy([])
        self.assertEqual(result["total_kills"], 0)
        self.assertEqual(result["return_pct"], 0)
        self.assertEqual(result["cost_per_kill"], 0)

    def test_mu_consumed_phase1_placeholder(self):
        self.assertIsNone(hunt_stats.mu_consumed([], None, None))
        self.assertIsNone(hunt_stats.mu_consumed([_enc()], None, None))

    def test_aggregate_by_tool_accepts_list(self):
        e = _enc()
        e.tool_stats["Opalo"] = EncounterToolStats(
            tool_name="Opalo", shots_fired=4, damage_dealt=40.0, critical_hits=1,
        )
        result = hunt_stats.aggregate_by_tool([e])
        self.assertIn("Opalo", result)
        self.assertEqual(result["Opalo"]["shots_fired"], 4)
        self.assertEqual(result["Opalo"]["encounters_used"], 1)

    def test_aggregate_by_tool_accepts_session(self):
        s = HuntSession(id="s1", start_time=datetime(2026, 1, 1))
        e = _enc()
        e.tool_stats["Opalo"] = EncounterToolStats(
            tool_name="Opalo", shots_fired=2, damage_dealt=10.0, critical_hits=0,
        )
        s.encounters.append(e)
        result = hunt_stats.aggregate_by_tool(s)
        self.assertIn("Opalo", result)

    def test_session_globals_hof_counts(self):
        s = HuntSession(id="s1", start_time=datetime(2026, 1, 1))
        s.encounters = [
            _enc(is_global=True),
            _enc(is_hof=True, is_global=True),
            _enc(),
        ]
        self.assertEqual(s.global_count, 2)
        self.assertEqual(s.hof_count, 1)


if __name__ == "__main__":
    unittest.main()
