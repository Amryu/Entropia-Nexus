"""Loadout data models."""

from dataclasses import dataclass, field


@dataclass
class LoadoutStats:
    """Calculated stats from the loadout evaluator."""
    # Offensive
    total_damage: float = 0
    offensive_totals: dict = field(default_factory=dict)
    active_effects: list = field(default_factory=list)
    offensive_effects: list = field(default_factory=list)
    defensive_effects: list = field(default_factory=list)
    utility_effects: list = field(default_factory=list)
    effective_damage: float = 0
    damage_interval_min: float = 0
    damage_interval_max: float = 0
    hit_ability: float = 0
    crit_ability: float = 0
    crit_chance: float = 0
    crit_damage: float = 1.0
    range: float = 0
    reload: float = 0
    dps: float = 0
    dpp: float = 0

    # Economy
    decay: float = 0
    ammo_burn: float = 0
    cost: float = 0
    efficiency: float = 0
    weapon_cost: float = 0
    lowest_total_uses: int = 0

    # Defense
    armor_defense: float = 0
    plate_defense: float = 0
    total_defense: float = 0
    top_defense_types: str = ""
    total_absorption: float = 0
    block_chance: float = 0

    # Healing
    total_heal: float = 0
    effective_heal: float = 0
    hps: float = 0
    hpp: float = 0
    heal_reload: float = 0
    heal_decay: float = 0
    heal_ammo_burn: float | None = None
    heal_cost: float | None = None
    heal_total_uses: int = 0
    heal_multiplier: float = 1.0
    hot_breakdown: dict | None = None
    lifesteal_percent: float = 0
    lifesteal_hps: float | None = None


def create_empty_loadout() -> dict:
    """Create an empty loadout matching the website's data format."""
    return {
        "Id": None,
        "Name": "New Loadout",
        "Properties": {
            "BonusDamage": 0,
            "BonusCritChance": 0,
            "BonusCritDamage": 0,
            "BonusReload": 0,
        },
        "Gear": {
            "Weapon": {
                "Name": None,
                "Amplifier": {"Name": None},
                "Scope": {"Name": None, "Sight": {"Name": None}},
                "Sight": {"Name": None},
                "Absorber": {"Name": None},
                "Implant": {"Name": None},
                "Matrix": {"Name": None},
                "Enhancers": {
                    "Damage": 0, "Accuracy": 0, "Range": 0,
                    "Economy": 0, "SkillMod": 0
                },
            },
            "Armor": {
                "SetName": None,
                "PlateName": None,
                "ManageIndividual": False,
                "Head": {"Name": None, "Plate": None},
                "Torso": {"Name": None, "Plate": None},
                "Arms": {"Name": None, "Plate": None},
                "Hands": {"Name": None, "Plate": None},
                "Legs": {"Name": None, "Plate": None},
                "Shins": {"Name": None, "Plate": None},
                "Feet": {"Name": None, "Plate": None},
                "Enhancers": {"Defense": 0, "Durability": 0},
            },
            "Healing": {
                "Name": None,
                "Enhancers": {"Heal": 0, "Economy": 0, "SkillMod": 0},
            },
            "Clothing": [],
            "Consumables": [],
            "Pet": {"Name": None, "Effect": None},
        },
        "Sets": {
            "Weapon": [],
            "Armor": [],
            "Healing": [],
            "Accessories": [],
        },
        "Skill": {"Hit": 200, "Dmg": 200, "Heal": 200},
        "Markup": {
            "Weapon": 100, "Ammo": 100, "Amplifier": 100,
            "Absorber": 100, "Scope": 100, "Sight": 100,
            "ScopeSight": 100, "Matrix": 100, "Implant": 100,
            "ArmorSet": 100, "PlateSet": 100,
            "Armors": {
                "Head": 100, "Torso": 100, "Arms": 100,
                "Hands": 100, "Legs": 100, "Shins": 100, "Feet": 100,
            },
            "Plates": {
                "Head": 100, "Torso": 100, "Arms": 100,
                "Hands": 100, "Legs": 100, "Shins": 100, "Feet": 100,
            },
            "HealingTool": 100,
        },
    }
