export const Vendor = {
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
        "Description": {
          "type": ["string", "null"],
          "default": null
        },
        "Coordinates": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "Longitude": {
              "type": ["integer", "null"],
              "default": null
            },
            "Latitude": {
              "type": ["integer", "null"],
              "default": null
            },
            "Altitude": {
              "type": ["integer", "null"],
              "default": null
            },
          },
          "required": [
            "Longitude",
            "Latitude",
            "Altitude"
          ]
        },
      },
      "required": [
        "Description",
        "Coordinates"
      ]
    },
    "Planet": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
    "Offers": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "IsLimited": {
            "type": ["boolean", "null"],
            "default": null
          },
          "Item": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
          "Prices": {
            "type": "array",
            "items": {
              "type": "object",
              "additionalProperties": false,
              "properties": {
                "Item": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
                "Amount": {
                  "type": ["integer", "null"],
                  "default": null
                }
              },
              "required": [
                "Item",
                "Amount"
              ]
            }
          }
        },
        "required": [
          "Item",
          "Prices"
        ]
      }
    }
  },
  "required": [
    "Name",
    "Planet",
    "Offers"
  ]
}