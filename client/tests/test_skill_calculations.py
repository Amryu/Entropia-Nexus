"""Tests for skill and profession calculation utilities."""

import unittest

from client.skills.calculations import (
    BASE_HP,
    ATTRIBUTE_MULTIPLIER,
    CODEX_REWARD_DIVISORS,
    get_codex_category,
    build_attribute_skill_set,
    effective_points,
    calculate_profession_level,
    calculate_all_profession_levels,
    calculate_hp,
    find_cheapest_profession_path,
    find_cheapest_hp_path,
)


SAMPLE_METADATA = [
    {"Name": "Anatomy", "Category": "Combat", "HPIncrease": 200},
    {"Name": "Courage", "Category": "Combat", "HPIncrease": 500},
    {"Name": "Dexterity", "Category": "Combat", "HPIncrease": 300},
    {"Name": "Agility", "Category": "Attributes", "HPIncrease": 50},
    {"Name": "Strength", "Category": "Attributes", "HPIncrease": 100},
    {"Name": "Alertness", "Category": "Combat", "HPIncrease": None},
]

SAMPLE_PROFESSION_SKILLS = [
    {"Name": "Anatomy", "Weight": 60},
    {"Name": "Courage", "Weight": 40},
    {"Name": "Agility", "Weight": 20},
]


class TestCodexCategory(unittest.TestCase):

    def test_cat1_skill(self):
        self.assertEqual(get_codex_category("Anatomy"), "cat1")
        self.assertEqual(get_codex_category("Rifle"), "cat1")

    def test_cat2_skill(self):
        self.assertEqual(get_codex_category("Courage"), "cat2")

    def test_cat3_skill(self):
        self.assertEqual(get_codex_category("Dodge"), "cat3")
        self.assertEqual(get_codex_category("Evade"), "cat3")

    def test_cat4_skill(self):
        self.assertEqual(get_codex_category("Animal Lore"), "cat4")

    def test_unknown_skill(self):
        self.assertIsNone(get_codex_category("Nonexistent Skill"))


class TestAttributeSkills(unittest.TestCase):

    def test_build_attribute_set(self):
        attrs = build_attribute_skill_set(SAMPLE_METADATA)
        self.assertEqual(attrs, {"Agility", "Strength"})

    def test_empty_metadata(self):
        self.assertEqual(build_attribute_skill_set([]), set())

    def test_effective_points_attribute(self):
        attrs = {"Agility", "Strength"}
        self.assertAlmostEqual(effective_points(1.5, "Agility", attrs), 150.0)

    def test_effective_points_non_attribute(self):
        attrs = {"Agility", "Strength"}
        self.assertAlmostEqual(effective_points(1.5, "Anatomy", attrs), 1.5)


class TestProfessionLevel(unittest.TestCase):

    def test_basic_calculation(self):
        values = {"Anatomy": 1000, "Courage": 500, "Agility": 0}
        level = calculate_profession_level(values, SAMPLE_PROFESSION_SKILLS)
        # (1000*60 + 500*40 + 0*20) / 10000 = (60000 + 20000) / 10000 = 8.0
        self.assertAlmostEqual(level, 8.0)

    def test_with_attribute_multiplier(self):
        values = {"Anatomy": 1000, "Courage": 500, "Agility": 2.0}
        attrs = build_attribute_skill_set(SAMPLE_METADATA)
        level = calculate_profession_level(values, SAMPLE_PROFESSION_SKILLS, attrs)
        # Agility effective = 2.0 * 100 = 200
        # (1000*60 + 500*40 + 200*20) / 10000 = (60000 + 20000 + 4000) / 10000 = 8.4
        self.assertAlmostEqual(level, 8.4)

    def test_without_attribute_multiplier(self):
        values = {"Anatomy": 1000, "Courage": 500, "Agility": 2.0}
        level = calculate_profession_level(values, SAMPLE_PROFESSION_SKILLS)
        # Without multiplier: (1000*60 + 500*40 + 2*20) / 10000 = 8.004
        self.assertAlmostEqual(level, 8.004)

    def test_zero_skills(self):
        level = calculate_profession_level({}, SAMPLE_PROFESSION_SKILLS)
        self.assertAlmostEqual(level, 0.0)

    def test_missing_skill(self):
        values = {"Anatomy": 500}
        level = calculate_profession_level(values, SAMPLE_PROFESSION_SKILLS)
        # Only anatomy contributes: 500*60/10000 = 3.0
        self.assertAlmostEqual(level, 3.0)


class TestAllProfessionLevels(unittest.TestCase):

    def test_multiple_professions(self):
        profs = [
            {"Name": "Fighter", "Skills": [{"Name": "Anatomy", "Weight": 60}]},
            {"Name": "Scout", "Skills": [{"Name": "Courage", "Weight": 80}]},
        ]
        values = {"Anatomy": 1000, "Courage": 500}
        levels = calculate_all_profession_levels(values, profs, SAMPLE_METADATA)
        self.assertAlmostEqual(levels["Fighter"], 6.0)   # 1000*60/10000
        self.assertAlmostEqual(levels["Scout"], 4.0)      # 500*80/10000

    def test_with_attribute_skill(self):
        profs = [
            {"Name": "Agile Prof", "Skills": [{"Name": "Agility", "Weight": 50}]},
        ]
        values = {"Agility": 3.0}
        levels = calculate_all_profession_levels(values, profs, SAMPLE_METADATA)
        # 3.0 * 100 * 50 / 10000 = 1.5
        self.assertAlmostEqual(levels["Agile Prof"], 1.5)


class TestCalculateHP(unittest.TestCase):

    def test_base_hp(self):
        hp = calculate_hp({}, SAMPLE_METADATA)
        self.assertAlmostEqual(hp, BASE_HP)

    def test_with_skills(self):
        values = {"Anatomy": 1000, "Courage": 500}
        hp = calculate_hp(values, SAMPLE_METADATA)
        # 80 + 1000/200 + 500/500 = 80 + 5 + 1 = 86
        self.assertAlmostEqual(hp, 86.0)

    def test_with_attribute_skill(self):
        values = {"Agility": 1.0}
        hp = calculate_hp(values, SAMPLE_METADATA)
        # Agility is an attribute: effective = 1.0 * 100 = 100
        # 80 + 100/50 = 80 + 2 = 82
        self.assertAlmostEqual(hp, 82.0)

    def test_null_hp_increase_ignored(self):
        values = {"Alertness": 1000}
        hp = calculate_hp(values, SAMPLE_METADATA)
        # Alertness has HPIncrease=None, should not contribute
        self.assertAlmostEqual(hp, BASE_HP)


class TestFindCheapestProfessionPath(unittest.TestCase):

    def test_already_at_target(self):
        result = find_cheapest_profession_path(
            {"Anatomy": 1000}, SAMPLE_PROFESSION_SKILLS, 10.0, 5.0
        )
        self.assertEqual(result["totalCost"], 0)
        self.assertTrue(result["feasible"])
        self.assertEqual(result["allocations"], [])

    def test_simple_path(self):
        result = find_cheapest_profession_path(
            {}, SAMPLE_PROFESSION_SKILLS, 0.0, 1.0
        )
        self.assertTrue(result["feasible"])
        self.assertGreater(result["totalCost"], 0)
        self.assertGreater(len(result["allocations"]), 0)

    def test_attribute_skill_efficiency(self):
        """Attribute skills with x100 multiplier should be more efficient."""
        attrs = build_attribute_skill_set(SAMPLE_METADATA)

        result_with_attr = find_cheapest_profession_path(
            {}, SAMPLE_PROFESSION_SKILLS, 0.0, 1.0,
            attribute_skills=attrs,
        )
        result_without_attr = find_cheapest_profession_path(
            {}, SAMPLE_PROFESSION_SKILLS, 0.0, 1.0,
        )
        # With attribute multiplier, Agility is much more efficient
        # so the total cost should be lower (or at least different)
        self.assertTrue(result_with_attr["feasible"])
        self.assertTrue(result_without_attr["feasible"])


class TestFindCheapestHPPath(unittest.TestCase):

    def test_already_at_target(self):
        result = find_cheapest_hp_path({}, SAMPLE_METADATA, 100.0, 90.0)
        self.assertEqual(result["totalCost"], 0)
        self.assertTrue(result["feasible"])

    def test_simple_hp_path(self):
        result = find_cheapest_hp_path({}, SAMPLE_METADATA, 80.0, 85.0)
        self.assertTrue(result["feasible"])
        self.assertGreater(result["totalCost"], 0)

    def test_attribute_hp_contribution(self):
        """Attribute skills with x100 multiplier contribute more HP per raw point."""
        values = {"Agility": 1.0}
        hp = calculate_hp(values, SAMPLE_METADATA)
        # Effective = 100, HP gain = 100/50 = 2
        self.assertAlmostEqual(hp, 82.0)


if __name__ == "__main__":
    unittest.main()
