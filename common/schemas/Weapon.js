export const Weapon = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "Id": {
      "type": ["integer", "null"]
    },
    "ClassId": {
      "type": ["string", "null"],
      "default": null
    },
    "Name": {
      "type": "string"
    },
    "Properties": {
      "type": "object",
      "properties": {
        "Description": {
          "type": ["string", "null"],
          "default": null
        },
        "IsUntradeable": {
          "type": ["boolean", "null"],
          "default": null
        },
        "IsRare": {
          "type": ["boolean", "null"],
          "default": null
        },
        "Weight": {
          "type": ["number", "null"],
          "default": null
        },
        "Type": {
          "type": ["string", "null"],
          "default": null
        },
        "Category": {
          "type": ["string", "null"],
          "default": null
        },
        "Class": {
          "type": "string"
        },
        "UsesPerMinute": {
          "type": ["integer", "null"],
          "default": null
        },
        "Range": {
          "type": ["number", "null"],
          "default": null
        },
        "ImpactRadius": {
          "type": ["number", "null"],
          "default": null
        },
        "Mindforce": {
          "type": ["object", "null"],
          "default": null,
          "properties": {
            "Level": {
              "type": ["integer", "null"],
              "default": null
            },
            "Concentration": {
              "type": ["number", "null"],
              "default": null
            },
            "Cooldown": {
              "type": ["number", "null"],
              "default": null
            },
            "CooldownGroup": {
              "type": ["integer", "null"],
              "default": null
            }
          },
          "required": [
            "Level",
            "Concentration",
            "Cooldown",
            "CooldownGroup"
          ]
        },
        "Economy": {
          "type": "object",
          "properties": {
            "Efficiency": {
              "type": ["number", "null"],
              "default": null
            },
            "MaxTT": {
              "type": ["number", "null"],
              "default": null
            },
            "MinTT": {
              "type": ["number", "null"],
              "default": null
            },
            "Decay": {
              "type": ["number", "null"],
              "default": null
            },
            "AmmoBurn": {
              "type": ["integer", "null"],
              "default": null
            }
          },
          "required": [
            "Efficiency",
            "MaxTT",
            "MinTT",
            "Decay",
            "AmmoBurn"
          ]
        },
        "Damage": {
          "type": "object",
          "properties": {
            "Stab": {
              "type": ["number", "null"],
              "default": null
            },
            "Cut": {
              "type": ["number", "null"],
              "default": null
            },
            "Impact": {
              "type": ["number", "null"],
              "default": null
            },
            "Penetration": {
              "type": ["number", "null"],
              "default": null
            },
            "Shrapnel": {
              "type": ["number", "null"],
              "default": null
            },
            "Burn": {
              "type": ["number", "null"],
              "default": null
            },
            "Cold": {
              "type": ["number", "null"],
              "default": null
            },
            "Acid": {
              "type": ["number", "null"],
              "default": null
            },
            "Electric": {
              "type": ["number", "null"],
              "default": null
            }
          },
          "required": [
            "Stab",
            "Cut",
            "Impact",
            "Penetration",
            "Shrapnel",
            "Burn",
            "Cold",
            "Acid",
            "Electric"
          ]
        },
        "Skill": {
          "type": "object",
          "properties": {
            "Hit": {
              "type": "object",
              "properties": {
                "LearningIntervalStart": {
                  "type": ["number", "null"],
                  "default": null
                },
                "LearningIntervalEnd": {
                  "type": ["number", "null"],
                  "default": null
                }
              },
              "required": [
                "LearningIntervalStart",
                "LearningIntervalEnd"
              ]
            },
            "Dmg": {
              "type": "object",
              "properties": {
                "LearningIntervalStart": {
                  "type": ["number", "null"],
                  "default": null
                },
                "LearningIntervalEnd": {
                  "type": ["number", "null"],
                  "default": null
                }
              },
              "required": [
                "LearningIntervalStart",
                "LearningIntervalEnd"
              ]
            },
            "IsSiB": {
              "type": ["boolean", "null"],
              "default": null
            }
          },
          "required": [
            "Hit",
            "Dmg",
            "IsSiB"
          ]
        }
      },
      "required": [
        "Description",
        "Weight",
        "Type",
        "Category",
        "Class",
        "UsesPerMinute",
        "Range",
        "ImpactRadius",
        "Mindforce",
        "Economy",
        "Damage",
        "Skill"
      ]
    },
    "Ammo": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
    "AttachmentType": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
    "ProfessionHit": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
    "ProfessionDmg": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
    "EffectsOnEquip": { "$ref": "https://entropianexus.com/schemas/EffectsOnEquip.json" },
    "EffectsOnUse": { "$ref": "https://entropianexus.com/schemas/EffectsOnUse.json" },
    "Tiers": { "$ref": "https://entropianexus.com/schemas/Tiers.json" }
  },
  "required": [
    "Name",
    "Properties",
    "Ammo",
    "ProfessionHit",
    "ProfessionDmg",
    "EffectsOnEquip",
    "Tiers"
  ]
}