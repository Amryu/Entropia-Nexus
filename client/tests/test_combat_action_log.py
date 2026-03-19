import unittest
from datetime import datetime, timedelta

from client.hunt.combat_action_log import CombatAction, CombatActionLog


class TestCombatActionLog(unittest.TestCase):
    def setUp(self):
        self.log = CombatActionLog()
        self.t0 = datetime(2026, 3, 19, 12, 0, 0)

    def _action(self, event_type="damage_dealt", amount=100.0, enc_id="enc1",
                tool_name=None, tool_source=None, offset_ms=0):
        return CombatAction(
            id=f"ev-{offset_ms}",
            encounter_id=enc_id,
            timestamp=self.t0 + timedelta(milliseconds=offset_ms),
            event_type=event_type,
            amount=amount,
            tool_name=tool_name,
            tool_source=tool_source,
        )

    def test_append_and_len(self):
        self.assertEqual(len(self.log), 0)
        self.log.append(self._action())
        self.assertEqual(len(self.log), 1)

    def test_get_all(self):
        a1 = self._action(offset_ms=0)
        a2 = self._action(offset_ms=100)
        self.log.append(a1)
        self.log.append(a2)
        all_actions = self.log.get_all()
        self.assertEqual(len(all_actions), 2)
        self.assertEqual(all_actions[0].id, "ev-0")

    def test_get_by_encounter(self):
        self.log.append(self._action(enc_id="enc1", offset_ms=0))
        self.log.append(self._action(enc_id="enc2", offset_ms=100))
        self.log.append(self._action(enc_id="enc1", offset_ms=200))
        self.assertEqual(len(self.log.get_by_encounter("enc1")), 2)
        self.assertEqual(len(self.log.get_by_encounter("enc2")), 1)
        self.assertEqual(len(self.log.get_by_encounter("enc3")), 0)

    def test_get_by_id(self):
        a = self._action()
        self.log.append(a)
        self.assertIs(self.log.get_by_id("ev-0"), a)
        self.assertIsNone(self.log.get_by_id("nonexistent"))

    def test_get_unattributed_since(self):
        # Attributed event
        self.log.append(self._action(tool_name="Gun", tool_source="ocr_direct", offset_ms=0))
        # Unattributed events
        self.log.append(self._action(offset_ms=100))
        self.log.append(self._action(offset_ms=200))
        # Non-damage event (should be excluded)
        self.log.append(self._action(event_type="player_evade", offset_ms=250))

        since = self.t0 + timedelta(milliseconds=50)
        unattributed = self.log.get_unattributed_since(since)
        self.assertEqual(len(unattributed), 2)
        self.assertEqual(unattributed[0].id, "ev-100")
        self.assertEqual(unattributed[1].id, "ev-200")

    def test_get_unattributed_since_respects_timestamp(self):
        self.log.append(self._action(offset_ms=0))
        self.log.append(self._action(offset_ms=500))

        since = self.t0 + timedelta(milliseconds=200)
        unattributed = self.log.get_unattributed_since(since)
        self.assertEqual(len(unattributed), 1)
        self.assertEqual(unattributed[0].id, "ev-500")

    def test_update_tool_basic(self):
        a = self._action()
        self.log.append(a)
        result = self.log.update_tool("ev-0", "Gun", "ocr_direct", 0.9)
        self.assertTrue(result)
        self.assertEqual(a.tool_name, "Gun")
        self.assertEqual(a.tool_source, "ocr_direct")

    def test_update_tool_respects_priority(self):
        a = self._action(tool_name="Gun", tool_source="ocr_reload")
        a.confidence = 0.95
        self.log.append(a)

        # Try to downgrade from ocr_reload to inferred — should fail
        result = self.log.update_tool("ev-0", "Other", "inferred", 0.7)
        self.assertFalse(result)
        self.assertEqual(a.tool_name, "Gun")

    def test_update_tool_allows_upgrade(self):
        a = self._action(tool_name="Gun", tool_source="inferred")
        self.log.append(a)

        # Upgrade from inferred to ocr_reload — should succeed
        result = self.log.update_tool("ev-0", "Better", "ocr_reload", 0.95)
        self.assertTrue(result)
        self.assertEqual(a.tool_name, "Better")

    def test_update_encounter_id(self):
        a = self._action(enc_id="enc1")
        self.log.append(a)

        self.log.update_encounter_id("ev-0", "enc2")
        self.assertEqual(a.encounter_id, "enc2")
        self.assertEqual(len(self.log.get_by_encounter("enc1")), 0)
        self.assertEqual(len(self.log.get_by_encounter("enc2")), 1)

    def test_clear(self):
        self.log.append(self._action())
        self.log.append(self._action(offset_ms=100))
        self.log.clear()
        self.assertEqual(len(self.log), 0)
        self.assertEqual(len(self.log.get_all()), 0)


if __name__ == "__main__":
    unittest.main()
