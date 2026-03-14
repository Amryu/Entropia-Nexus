import unittest
from datetime import datetime

from client.hunt.running_stats import RunningAggregate, MobRunningStats, SessionRunningStats
from client.hunt.session import MobEncounter


def _make_encounter(mob_name="Atrox", outcome="kill", damage=100.0,
                    cost=5.0, loot=8.0, shots=10, crits=2,
                    target_avoids=1, death_count=0):
    enc = MobEncounter(
        id="enc-1", session_id="s1",
        mob_name=mob_name, mob_name_source="ocr",
        start_time=datetime(2026, 1, 1),
        end_time=datetime(2026, 1, 1, 0, 1),
        damage_dealt=damage, cost=cost,
        shots_fired=shots, critical_hits=crits,
        target_avoids=target_avoids,
        loot_total_ped=loot, outcome=outcome,
        death_count=death_count,
    )
    return enc


class TestRunningAggregate(unittest.TestCase):

    def test_empty(self):
        ra = RunningAggregate()
        self.assertEqual(ra.count, 0)
        self.assertEqual(ra.avg, 0.0)
        d = ra.to_dict()
        self.assertEqual(d["count"], 0)

    def test_single_value(self):
        ra = RunningAggregate()
        ra.update(10.0)
        self.assertEqual(ra.count, 1)
        self.assertAlmostEqual(ra.avg, 10.0)
        self.assertAlmostEqual(ra.min_val, 10.0)
        self.assertAlmostEqual(ra.max_val, 10.0)
        self.assertAlmostEqual(ra.total, 10.0)

    def test_multiple_values(self):
        ra = RunningAggregate()
        for v in [10, 20, 30]:
            ra.update(v)
        self.assertEqual(ra.count, 3)
        self.assertAlmostEqual(ra.avg, 20.0)
        self.assertAlmostEqual(ra.min_val, 10.0)
        self.assertAlmostEqual(ra.max_val, 30.0)
        self.assertAlmostEqual(ra.total, 60.0)

    def test_variance(self):
        ra = RunningAggregate()
        for v in [10, 20, 30]:
            ra.update(v)
        # Sample variance of [10,20,30] = 100
        self.assertAlmostEqual(ra.variance, 100.0)
        self.assertAlmostEqual(ra.std_dev, 10.0)

    def test_variance_single_value(self):
        ra = RunningAggregate()
        ra.update(5.0)
        self.assertAlmostEqual(ra.variance, 0.0)


class TestMobRunningStats(unittest.TestCase):

    def test_kill_encounter_updates_stats(self):
        stats = MobRunningStats(mob_name="Atrox")
        enc = _make_encounter(damage=100, cost=5, loot=8, shots=10, crits=2)
        stats.on_encounter_finalized(enc)

        self.assertEqual(stats.kill_count, 1)
        self.assertAlmostEqual(stats.total_damage, 100.0)
        self.assertAlmostEqual(stats.total_cost, 5.0)
        self.assertAlmostEqual(stats.total_loot, 8.0)
        self.assertEqual(stats.total_shots, 10)
        self.assertEqual(stats.total_crits, 2)
        self.assertAlmostEqual(stats.damage_per_kill.avg, 100.0)

    def test_death_encounter_tracks_deaths_not_kills(self):
        stats = MobRunningStats(mob_name="Atrox")
        enc = _make_encounter(outcome="death", death_count=1, damage=50, loot=0)
        stats.on_encounter_finalized(enc)

        self.assertEqual(stats.kill_count, 0)
        self.assertEqual(stats.death_count, 1)
        # damage_per_kill should NOT be updated for non-kill outcomes
        self.assertEqual(stats.damage_per_kill.count, 0)
        # But total_damage should still accumulate
        self.assertAlmostEqual(stats.total_damage, 50.0)

    def test_efficiency_metrics_no_data(self):
        stats = MobRunningStats(mob_name="Atrox")
        self.assertEqual(stats.efficiency_metrics(), {})

    def test_efficiency_metrics_with_dpp(self):
        stats = MobRunningStats(mob_name="Atrox", expected_dpp=2.0)
        # 100 damage, 5 PED cost = 100/(5*100) = 0.2 actual DPP
        # Wait, that's DPP in damage/pec.  1 PED = 100 PEC
        # actual_dpp = 100 / (5*100) = 0.2
        enc = _make_encounter(damage=100, cost=5)
        stats.on_encounter_finalized(enc)

        m = stats.efficiency_metrics()
        self.assertAlmostEqual(m["expected_dpp"], 2.0)
        self.assertAlmostEqual(m["actual_dpp_avg"], 0.2)
        # ratio = 0.2 / 2.0 = 0.1 (mob is 10x more expensive)
        self.assertAlmostEqual(m["efficiency_ratio"], 0.1)

    def test_multiple_encounters(self):
        stats = MobRunningStats(mob_name="Atrox")
        for i in range(5):
            enc = _make_encounter(damage=100 + i * 10, cost=5, loot=8)
            enc.id = f"enc-{i}"
            stats.on_encounter_finalized(enc)

        self.assertEqual(stats.kill_count, 5)
        self.assertAlmostEqual(stats.damage_per_kill.min_val, 100.0)
        self.assertAlmostEqual(stats.damage_per_kill.max_val, 140.0)
        self.assertAlmostEqual(stats.damage_per_kill.avg, 120.0)


class TestSessionRunningStats(unittest.TestCase):

    def test_per_mob_tracking(self):
        srs = SessionRunningStats()
        srs.on_encounter_finalized(_make_encounter("Atrox", damage=100))
        srs.on_encounter_finalized(_make_encounter("Foul", damage=50))
        srs.on_encounter_finalized(_make_encounter("Atrox", damage=120))

        atrox = srs.get_mob_stats("Atrox")
        self.assertIsNotNone(atrox)
        self.assertEqual(atrox.kill_count, 2)

        foul = srs.get_mob_stats("Foul")
        self.assertIsNotNone(foul)
        self.assertEqual(foul.kill_count, 1)

    def test_expected_dpp_propagates(self):
        srs = SessionRunningStats(expected_dpp=2.0)
        srs.on_encounter_finalized(_make_encounter("Atrox", damage=100, cost=5))

        atrox = srs.get_mob_stats("Atrox")
        self.assertAlmostEqual(atrox.expected_dpp, 2.0)

    def test_set_expected_dpp_updates_existing(self):
        srs = SessionRunningStats()
        srs.on_encounter_finalized(_make_encounter("Atrox"))
        srs.set_expected_dpp(3.0)

        atrox = srs.get_mob_stats("Atrox")
        self.assertAlmostEqual(atrox.expected_dpp, 3.0)

    def test_to_dict(self):
        srs = SessionRunningStats()
        srs.on_encounter_finalized(_make_encounter("Atrox"))
        d = srs.to_dict()
        self.assertIn("Atrox", d)
        self.assertEqual(d["Atrox"]["kill_count"], 1)


if __name__ == "__main__":
    unittest.main()
