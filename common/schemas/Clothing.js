export const Clothing = {
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
      "additionalProperties": false,
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
        "Slot": {
          "type": ["string", "null"],
          "default": null
        },
        "Gender": {
          "type": ["string", "null"],
          "enum": ["Both", "Male", "Female", "Neutral", null],
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
            }
          },
          "required": [
            "MaxTT",
            "MinTT"
          ]
        }
      },
      "required": [
        "Description",
        "Weight",
        "Type",
        "Slot",
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