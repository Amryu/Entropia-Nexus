export const Clothing = {
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
      "additionalProperties": false,
      "properties": {
        "Weight": {
          "type": ["number", "null"],
          "default": null
        },
        "Type": {
          "type": ["string", "null"],
          "default": null
        },
        "Gender": {
          "type": "string",
          "enum": ["Both", "Male", "Female"]
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
            }
          },
          "required": [
            "MaxTT",
            "MinTT"
          ]
        }
      },
      "required": [
        "Weight",
        "Type",
        "Gender",
        "Economy"
      ]
    },
    "Set": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "Name": {
          "type": ["string", "null"],
          "default": null
        },
        "EffectsOnSetEquip": { "$ref": "https://entropianexus.com/schemas/EffectsOnSetEquip.json" }
      },
      "required": [
        "Name",
        "EffectsOnSetEquip"
      ]
    },
    "EffectsOnEquip": { "$ref": "https://entropianexus.com/schemas/EffectsOnEquip.json" }
  },
  "required": [
    "Name",
    "Properties",
    "Set"
  ]
}