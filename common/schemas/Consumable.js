export const Consumable = {
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
        "Type": {
          "type": "string",
          "enum": ["Chip", "Nanobots", "Pill"]
        },
        "Economy": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "MaxTT": {
              "type": ["number", "null"],
              "default": null
            }
          },
          "required": [
            "MaxTT"
          ]
        }
      },
      "required": [
        "Description",
        "Weight",
        "Type",
        "Economy"
      ]
    },
    "EffectsOnConsume": { "$ref": "https://entropianexus.com/schemas/EffectsOnUse.json" }
  },
  "required": [
    "Name",
    "Properties",
    "EffectsOnConsume"
  ]
}