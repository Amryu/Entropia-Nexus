import unittest
from datetime import datetime
from unittest.mock import MagicMock

from client.hunt import stats as S
from client.hunt.session import MobEncounter, EncounterToolStats
from client.hunt.markup_resolver import MarkupResult


def _enc_with_tool(tool_name: str, shots: int) -> MobEncounter:
    e = MobEncounter(
        id=f"e-{id(object())}",
        session_id="s1",
        mob_name="Atrox",
        mob_name_source="ocr",
        start_time=datetime(2026, 1, 1),
        end_time=datetime(2026, 1, 1),
        shots_fired=shots,
    )
    e.tool_stats[tool_name] = EncounterToolStats(
        tool_name=tool_name, shots_fired=shots, damage_dealt=0.0, critical_hits=0,
    )
    return e


class TestMuConsumed(unittest.TestCase):

    def test_returns_none_without_resolver(self):
        self.assertIsNone(S.mu_consumed([_enc_with_tool("Opalo", 10)], None, {}))

    def test_zero_when_no_overrides(self):
        resolver = MagicMock()
        resolver.resolve.return_value = MarkupResult(100.0, "percentage", "default")
        value = S.mu_consumed([_enc_with_tool("Opalo", 10)], resolver, {})
        self.assertEqual(value, 0)

    def test_decay_markup_contribution(self):
        resolver = MagicMock()
        resolver.resolve.return_value = MarkupResult(100.0, "percentage", "default")
        overrides = {
            "opalo": {
                "decay_pec_per_use": 10.0,  # PEC = 0.10 PED per shot
                "custom_markup": 120.0,     # +20%
                "custom_markup_type": "percentage",
            }
        }
        # 10 shots -> 1.0 PED decay -> 20% -> 0.20 MU
        value = S.mu_consumed([_enc_with_tool("Opalo", 10)], resolver, overrides)
        self.assertAlmostEqual(value, 0.20, places=4)

    def test_decay_skipped_when_markup_is_100(self):
        resolver = MagicMock()
        resolver.resolve.return_value = MarkupResult(100.0, "percentage", "default")
        overrides = {
            "opalo": {
                "decay_pec_per_use": 10.0,
                "custom_markup": 100.0,
                "custom_markup_type": "percentage",
            }
        }
        value = S.mu_consumed([_enc_with_tool("Opalo", 10)], resolver, overrides)
        self.assertEqual(value, 0)


if __name__ == "__main__":
    unittest.main()
