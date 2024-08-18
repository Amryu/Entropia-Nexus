export const WeaponVisionAttachment = {
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
        "Type": {
          "type": "string",
          "enum": ["Scope", "Sight"]
        },
        "Zoom": {
          "type": ["number", "null"],
          "default": null
        },
        "SkillModification": {
          "type": ["number", "null"],
          "default": null
        },
        "SkillBonus": {
          "type": ["number", "null"],
          "default": null
        },
        "Economy": {
          "type": "object",
          "additionalProperties": false,
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
            }
          },
          "required": [
            "Efficiency",
            "MaxTT",
            "MinTT",
            "Decay"
          ]
        }
      },
      "required": [
        "Weight",
        "Type",
        "Zoom",
        "SkillModification",
        "SkillBonus",
        "Economy"
      ]
    },
    "EffectsOnEquip": { "$ref": "https://entropianexus.com/schemas/EffectsOnEquip.json" }
  },
  "required": [
    "Name",
    "Properties",
    "EffectsOnEquip"
  ]
}