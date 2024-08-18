export const MindforceImplant = {
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
        "MaxProfessionLevel": {
          "type": ["integer", "null"],
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
            "Absorption": {
              "type": ["number", "null"],
              "default": null
            }
          },
          "required": [
            "MaxTT",
            "MinTT",
            "Absorption"
          ]
        }
      },
      "required": [
        "Weight",
        "MaxProfessionLevel",
        "Economy"
      ]
    }
  },
  "required": [
    "Name",
    "Properties"
  ]
}