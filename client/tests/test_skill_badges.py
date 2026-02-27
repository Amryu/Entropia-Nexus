"""Tests for skill badge resolution."""

import unittest

from client.skills.badges import get_skill_badges, Badge


SAMPLE_METADATA = [
    {
        "Name": "Anatomy",
        "Category": "Combat",
        "HPIncrease": 200,
        "Professions": [
            {"Name": "Animal Looter", "Weight": 0.9},
            {"Name": "Evader", "Weight": 0.5},
        ],
    },
    {
        "Name": "Courage",
        "Category": "Combat",
        "HPIncrease": 500,
        "Professions": [
            {"Name": "Dodger", "Weight": 0.3},
        ],
    },
    {
        "Name": "Agility",
        "Category": "Attributes",
        "HPIncrease": 50,
        "Professions": [
            {"Name": "Evader", "Weight": 0.8},
        ],
    },
    {
        "Name": "Alertness",
        "Category": "Combat",
        "HPIncrease": None,
        "Professions": [],
    },
    {
        "Name": "Heavy Melee Weapons",
        "Category": "Combat",
        "HPIncrease": 900,
        "Professions": [
            {"Name": "Robot Looter", "Weight": 0.2},
        ],
    },
]


class TestHPBadge(unittest.TestCase):

    def test_high_hp_badge(self):
        badges = get_skill_badges("Courage", SAMPLE_METADATA)
        hp_badges = [b for b in badges if b.badge_type == "hp"]
        self.assertEqual(len(hp_badges), 1)
        self.assertEqual(hp_badges[0].level, "high")
        self.assertEqual(hp_badges[0].label, "HP")

    def test_medium_hp_badge(self):
        badges = get_skill_badges("Anatomy", SAMPLE_METADATA)
        hp_badges = [b for b in badges if b.badge_type == "hp"]
        self.assertEqual(len(hp_badges), 1)
        self.assertEqual(hp_badges[0].level, "medium")

    def test_low_hp_badge(self):
        """Agility has HPIncrease=50 which is < 200 → low."""
        badges = get_skill_badges("Agility", SAMPLE_METADATA)
        hp_badges = [b for b in badges if b.badge_type == "hp"]
        self.assertEqual(len(hp_badges), 1)
        self.assertEqual(hp_badges[0].level, "low")

    def test_ineffective_hp_badge(self):
        """HPIncrease > 800 → ineffective."""
        badges = get_skill_badges("Heavy Melee Weapons", SAMPLE_METADATA)
        hp_badges = [b for b in badges if b.badge_type == "hp"]
        self.assertEqual(len(hp_badges), 1)
        self.assertEqual(hp_badges[0].level, "ineffective")

    def test_no_hp_badge_when_zero(self):
        badges = get_skill_badges("Alertness", SAMPLE_METADATA)
        hp_badges = [b for b in badges if b.badge_type == "hp"]
        self.assertEqual(len(hp_badges), 0)


class TestLootBadge(unittest.TestCase):

    def test_high_loot_badge(self):
        badges = get_skill_badges("Anatomy", SAMPLE_METADATA)
        loot_badges = [b for b in badges if b.badge_type == "loot"]
        self.assertEqual(len(loot_badges), 1)
        self.assertEqual(loot_badges[0].level, "high")
        self.assertAlmostEqual(loot_badges[0].value, 0.9)

    def test_low_loot_badge(self):
        badges = get_skill_badges("Heavy Melee Weapons", SAMPLE_METADATA)
        loot_badges = [b for b in badges if b.badge_type == "loot"]
        self.assertEqual(len(loot_badges), 1)
        self.assertEqual(loot_badges[0].level, "low")

    def test_no_loot_badge(self):
        badges = get_skill_badges("Courage", SAMPLE_METADATA)
        loot_badges = [b for b in badges if b.badge_type == "loot"]
        self.assertEqual(len(loot_badges), 0)

    def test_no_loot_for_alertness(self):
        badges = get_skill_badges("Alertness", SAMPLE_METADATA)
        loot_badges = [b for b in badges if b.badge_type == "loot"]
        self.assertEqual(len(loot_badges), 0)


class TestDefenseBadge(unittest.TestCase):

    def test_defense_badge_evader(self):
        badges = get_skill_badges("Agility", SAMPLE_METADATA)
        def_badges = [b for b in badges if b.badge_type == "defense"]
        self.assertEqual(len(def_badges), 1)
        self.assertEqual(def_badges[0].label, "Eva")
        self.assertEqual(def_badges[0].level, "high")

    def test_defense_badge_medium_evader(self):
        badges = get_skill_badges("Anatomy", SAMPLE_METADATA)
        def_badges = [b for b in badges if b.badge_type == "defense"]
        self.assertEqual(len(def_badges), 1)
        self.assertEqual(def_badges[0].label, "Eva")
        self.assertEqual(def_badges[0].level, "medium")

    def test_defense_badge_dodger(self):
        badges = get_skill_badges("Courage", SAMPLE_METADATA)
        def_badges = [b for b in badges if b.badge_type == "defense"]
        self.assertEqual(len(def_badges), 1)
        self.assertEqual(def_badges[0].label, "Dod")
        self.assertEqual(def_badges[0].level, "low")

    def test_no_defense_badge(self):
        badges = get_skill_badges("Heavy Melee Weapons", SAMPLE_METADATA)
        def_badges = [b for b in badges if b.badge_type == "defense"]
        self.assertEqual(len(def_badges), 0)


class TestUnknownSkill(unittest.TestCase):

    def test_nonexistent_skill(self):
        badges = get_skill_badges("Nonexistent", SAMPLE_METADATA)
        self.assertEqual(badges, [])


class TestAllBadgesCombined(unittest.TestCase):

    def test_anatomy_has_all_three(self):
        """Anatomy has HP, Loot, and Defense badges."""
        badges = get_skill_badges("Anatomy", SAMPLE_METADATA)
        types = {b.badge_type for b in badges}
        self.assertEqual(types, {"hp", "loot", "defense"})

    def test_alertness_has_none(self):
        badges = get_skill_badges("Alertness", SAMPLE_METADATA)
        self.assertEqual(badges, [])


if __name__ == "__main__":
    unittest.main()
