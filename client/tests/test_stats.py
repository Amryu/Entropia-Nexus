import unittest
from datetime import datetime

from client.hunt.session import HuntSession, MobEncounter, EncounterToolStats
from client.hunt.stats import aggregate_by_mob, aggregate_by_tool, session_economy


def _make_session():
    return HuntSession(id="session-1", start_time=datetime(2026, 1, 1))


def _make_encounter(mob_name="Atrox", damage_dealt=100.0, damage_taken=20.0,
                    heals=5.0, loot=50.0, shots=10, crits=2, target_avoids=1,
                    cost=5.0):
    enc = MobEncounter(
        id="enc-1",
        session_id="session-1",
        mob_name=mob_name,
        mob_name_source="ocr",
        start_time=datetime(2026, 1, 1),
        end_time=datetime(2026, 1, 1, 0, 1),
        damage_dealt=damage_dealt,
        damage_taken=damage_taken,
        heals_received=heals,
        loot_total_ped=loot,
        shots_fired=shots,
        critical_hits=crits,
        target_avoids=target_avoids,
        cost=cost,
    )
    return enc


class TestAggregateByMob(unittest.TestCase):

    def test_single_mob(self):
        session = _make_session()
        session.encounters = [_make_encounter("Atrox", damage_dealt=100, loot=50, shots=10, crits=2, target_avoids=1)]
        result = aggregate_by_mob(session)
        self.assertIn("Atrox", result)
        stats = result["Atrox"]
        self.assertEqual(stats["kills"], 1)
        self.assertAlmostEqual(stats["damage_dealt"], 100.0)
        self.assertAlmostEqual(stats["loot_total"], 50.0)

    def test_multiple_mobs(self):
        session = _make_session()
        session.encounters = [
            _make_encounter("Atrox", damage_dealt=100, loot=50),
            _make_encounter("Foul", damage_dealt=200, loot=80),
            _make_encounter("Atrox", damage_dealt=150, loot=60),
        ]
        result = aggregate_by_mob(session)
        self.assertIn("Atrox", result)
        self.assertIn("Foul", result)
        self.assertEqual(result["Atrox"]["kills"], 2)
        self.assertEqual(result["Foul"]["kills"], 1)
        self.assertAlmostEqual(result["Atrox"]["damage_dealt"], 250.0)

    def test_empty_session(self):
        session = _make_session()
        result = aggregate_by_mob(session)
        self.assertEqual(result, {})


class TestAggregateByMobAverages(unittest.TestCase):

    def test_avg_damage_per_kill(self):
        session = _make_session()
        session.encounters = [
            _make_encounter("Atrox", damage_dealt=100),
            _make_encounter("Atrox", damage_dealt=200),
        ]
        result = aggregate_by_mob(session)
        self.assertAlmostEqual(result["Atrox"]["avg_damage_per_kill"], 150.0)

    def test_avg_loot_per_kill(self):
        session = _make_session()
        session.encounters = [
            _make_encounter("Atrox", loot=40),
            _make_encounter("Atrox", loot=60),
        ]
        result = aggregate_by_mob(session)
        self.assertAlmostEqual(result["Atrox"]["avg_loot_per_kill"], 50.0)

    def test_crit_rate(self):
        session = _make_session()
        session.encounters = [_make_encounter("Atrox", shots=20, crits=4)]
        result = aggregate_by_mob(session)
        self.assertAlmostEqual(result["Atrox"]["crit_rate"], 0.2)

    def test_hit_rate(self):
        session = _make_session()
        session.encounters = [_make_encounter("Atrox", shots=8, target_avoids=2)]
        result = aggregate_by_mob(session)
        # hit_rate = shots / (shots + target_avoids) = 8/10 = 0.8
        self.assertAlmostEqual(result["Atrox"]["hit_rate"], 0.8)


class TestAggregateByMobZero(unittest.TestCase):

    def test_zero_shots_zero_rates(self):
        session = _make_session()
        enc = _make_encounter("Atrox", shots=0, crits=0, target_avoids=0)
        session.encounters = [enc]
        result = aggregate_by_mob(session)
        self.assertEqual(result["Atrox"]["crit_rate"], 0)
        self.assertEqual(result["Atrox"]["hit_rate"], 0)


class TestAggregateByTool(unittest.TestCase):

    def test_tool_stats_grouped(self):
        session = _make_session()
        enc = _make_encounter("Atrox")
        enc.tool_stats = {
            "Gun A": EncounterToolStats(tool_name="Gun A", shots_fired=10, damage_dealt=500, critical_hits=2),
            "Gun B": EncounterToolStats(tool_name="Gun B", shots_fired=5, damage_dealt=200, critical_hits=1),
        }
        session.encounters = [enc]
        result = aggregate_by_tool(session)
        self.assertIn("Gun A", result)
        self.assertIn("Gun B", result)
        self.assertEqual(result["Gun A"]["shots_fired"], 10)
        self.assertAlmostEqual(result["Gun A"]["damage_dealt"], 500.0)
        self.assertEqual(result["Gun A"]["encounters_used"], 1)

    def test_tool_empty(self):
        session = _make_session()
        session.encounters = [_make_encounter("Atrox")]
        # Default encounter has no tool_stats
        result = aggregate_by_tool(session)
        self.assertEqual(result, {})

    def test_tool_avg_damage_per_shot(self):
        session = _make_session()
        enc = _make_encounter("Atrox")
        enc.tool_stats = {
            "Gun A": EncounterToolStats(tool_name="Gun A", shots_fired=10, damage_dealt=500, critical_hits=2),
        }
        session.encounters = [enc]
        result = aggregate_by_tool(session)
        self.assertAlmostEqual(result["Gun A"]["avg_damage_per_shot"], 50.0)
        self.assertAlmostEqual(result["Gun A"]["crit_rate"], 0.2)


class TestSessionEconomy(unittest.TestCase):

    def test_session_economy(self):
        session = _make_session()
        session.encounters = [
            _make_encounter("Atrox", shots=10, loot=50),
            _make_encounter("Atrox", shots=20, loot=80),
        ]
        result = session_economy(session, cost_per_use=0.5)
        self.assertEqual(result["total_shots"], 30)
        self.assertAlmostEqual(result["total_cost"], 15.0)  # 30 * 0.5
        self.assertAlmostEqual(result["total_loot"], 130.0)
        self.assertAlmostEqual(result["profit_loss"], 115.0)
        self.assertAlmostEqual(result["return_pct"], 130 / 15 * 100)

    def test_session_economy_zero_cost(self):
        session = _make_session()
        session.encounters = [_make_encounter("Atrox", shots=10, loot=50)]
        result = session_economy(session, cost_per_use=0)
        self.assertEqual(result["return_pct"], 0)

    def test_session_economy_zero_kills(self):
        session = _make_session()
        # No encounters
        result = session_economy(session, cost_per_use=0.5)
        self.assertEqual(result["total_shots"], 0)
        self.assertEqual(result["cost_per_kill"], 0)
        self.assertEqual(result["loot_per_kill"], 0)


if __name__ == "__main__":
    unittest.main()
