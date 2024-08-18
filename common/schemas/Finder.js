export const Finder = {
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
        "UsesPerMinute": {
          "type": ["number", "null"],
          "default": null
        },
        "Depth": {
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
            "Decay",
            "AmmoBurn"
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
        "UsesPerMinute",
        "Depth",
        "Range",
        "Economy",
        "Skill"
      ]
    },
    "EffectsOnEquip": { "$ref": "https://entropianexus.com/schemas/EffectsOnEquip.json" },
    "Tiers": { "$ref": "https://entropianexus.com/schemas/Tiers.json" }
  },
  "required": [
    "Name",
    "Properties",
    "EffectsOnEquip",
    "Tiers"
  ]
}