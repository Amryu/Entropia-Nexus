export const MedicalTool = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "Id": {
      "type": ["integer", "null"]
    },
    "Name": {
      "type": "string"
    },
    "Properties": {
      "type": "object",
      "properties": {
        "Weight": {
          "type": ["number", "null"],
          "default": null
        },
        "MaxHeal": {
          "type": ["number", "null"],
          "default": null
        },
        "MinHeal": {
          "type": ["number", "null"],
          "default": null
        },
        "UsesPerMinute": {
          "type": ["number", "null"],
          "default": null
        },
        "Economy": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
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
            }
          },
          "required": [
            "MaxTT",
            "MinTT",
            "Decay"
          ]
        },
        "Skill": {
          "type": "object",
          "properties": {
            "LearningIntervalStart": {
              "type": ["number", "null"],
              "default": null
            },
            "LearningIntervalEnd": {
              "type": ["number", "null"],
              "default": null
            },
            "IsSiB": {
              "type": ["boolean", "null"],
              "default": null
            }
          },
          "required": [
            "LearningIntervalStart",
            "LearningIntervalEnd",
            "IsSiB"
          ]
        }
      },
      "required": [
        "Weight",
        "MaxHeal",
        "MinHeal",
        "UsesPerMinute",
        "Economy",
        "Skill"
      ]
    },
    "EffectsOnUse": { "$ref": "https://entropianexus.com/schemas/EffectsOnUse.json" },
    "EffectsOnEquip": { "$ref": "https://entropianexus.com/schemas/EffectsOnEquip.json" },
    "Tiers": { "$ref": "https://entropianexus.com/schemas/Tiers.json" }
  },
  "required": [
    "Name",
    "Properties",
    "EffectsOnUse",
    "EffectsOnEquip",
    "Tiers"
  ]
}