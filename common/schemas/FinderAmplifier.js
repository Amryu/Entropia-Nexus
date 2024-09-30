export const FinderAmplifier = {
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
        "Description": {
          "type": ["string", "null"],
          "default": null
        },
        "Weight": {
          "type": ["number", "null"],
          "default": null
        },
        "Efficiency": {
          "type": ["number", "null"],
          "default": null
        },
        "MinProfessionLevel": {
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
        }
      },
      "required": [
        "Description",
        "Weight",
        "Efficiency",
        "MinProfessionLevel",
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