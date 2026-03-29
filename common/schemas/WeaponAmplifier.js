export const WeaponAmplifier = {
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
        "Type": {
          "type": "string",
          "enum": ["Energy", "BLP", "Explosive", "Mining", "Melee", "Matrix", "Mindforce"]
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
            },
            "AmmoBurn": {
              "type": ["integer", "null"],
              "default": null
            },
            "Absorption": {
              "type": ["number", "null"],
              "minimum": 0,
              "maximum": 1,
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
        }
      },
      "required": [
        "Description",
        "Weight",
        "Type",
        "Economy",
        "Damage"
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