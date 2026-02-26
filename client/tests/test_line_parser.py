import unittest
from datetime import datetime

from client.chat_parser.line_parser import LineParser


class TestLineParser(unittest.TestCase):
    def setUp(self):
        self.parser = LineParser()

    def test_system_message(self):
        line = '2026-02-07 11:19:38 [System] [] You have gained 0.6347 experience in your Engineering skill'
        result = self.parser.parse(line, 1)
        self.assertIsNotNone(result)
        self.assertEqual(result.timestamp, datetime(2026, 2, 7, 11, 19, 38))
        self.assertEqual(result.channel, "System")
        self.assertEqual(result.username, "")
        self.assertEqual(result.message, "You have gained 0.6347 experience in your Engineering skill")

    def test_globals_message(self):
        line = '2026-02-07 11:19:15 [Globals] [] Anthony Malcom Denton killed a creature (Leviathan Stalker) with a value of 85 PED!'
        result = self.parser.parse(line, 1)
        self.assertIsNotNone(result)
        self.assertEqual(result.channel, "Globals")
        self.assertEqual(result.username, "")

    def test_chat_message_with_username(self):
        line = '2026-02-07 11:19:24 [#arktrade] [Nark Oo Allon] Level 2,3,5,7,8,9,10,12,13'
        result = self.parser.parse(line, 1)
        self.assertIsNotNone(result)
        self.assertEqual(result.channel, "#arktrade")
        self.assertEqual(result.username, "Nark Oo Allon")
        self.assertEqual(result.message, "Level 2,3,5,7,8,9,10,12,13")

    def test_html_entity_decoding(self):
        line = '2026-02-07 11:20:26 [Globals] [] Team &quot;(Shared Loot)&quot; killed a creature (Warrior C1-TF) with a value of 102 PED!'
        result = self.parser.parse(line, 1)
        self.assertIsNotNone(result)
        self.assertIn('"(Shared Loot)"', result.message)

    def test_amp_entity(self):
        line = '2026-02-07 11:21:26 [#calytrade] [MysterSnow MysterSnow MysterSnow] WTB PILLS &amp; Boxes any amount PM'
        result = self.parser.parse(line, 1)
        self.assertIsNotNone(result)
        self.assertIn("PILLS & Boxes", result.message)

    def test_empty_line(self):
        result = self.parser.parse("", 1)
        self.assertIsNone(result)

    def test_malformed_line(self):
        result = self.parser.parse("this is not a valid log line", 1)
        self.assertIsNone(result)

    def test_line_number_preserved(self):
        line = '2026-02-07 11:19:38 [System] [] test'
        result = self.parser.parse(line, 42)
        self.assertEqual(result.line_number, 42)


if __name__ == "__main__":
    unittest.main()
