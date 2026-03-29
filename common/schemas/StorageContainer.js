export const StorageContainer = {
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
        "ItemCapacity": {
          "type": ["integer", "null"],
          "default": null
        },
        "WeightCapacity": {
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
        "ItemCapacity",
        "WeightCapacity",
        "Economy"
      ]
    }
  },
  "required": [
    "Name",
    "Properties"
  ]
}