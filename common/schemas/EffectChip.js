export const EffectChip = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "additionalProperties": false,
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
        "Weight": {
          "type": ["number", "null"],
          "default": null
        },
        "UsesPerMinute": {
          "type": ["number", "null"],
          "default": null
        },
        "Range": {
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
            },
            "AmmoBurn": {
              "type": ["integer", "null"],
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
          "additionalProperties": false,
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
        },
        "Mindforce": {
          "type": "object",
          "additionalProperties": false,
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
        }
      },
      "required": [
        "Description",
        "Weight",
        "UsesPerMinute",
        "Range",
        "Economy",
        "Skill",
        "Mindforce"
      ]
    },
    "Ammo": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
    "Profession": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
    "EffectsOnUse": { "$ref": "https://entropianexus.com/schemas/EffectsOnUse.json" }
  },
  "required": [
    "Name",
    "Properties",
    "EffectsOnUse"
  ]
}