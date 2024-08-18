export const Scanner = {
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
        "Weight",
        "UsesPerMinute",
        "Range",
        "Economy"
      ]
    }
  },
  "required": [
    "Name",
    "Properties"
  ]
}