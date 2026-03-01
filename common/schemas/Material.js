export const Material = {
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
        "Type": {
          "type": ["string", "null"],
          "default": null
        },
        "Description": {
          "type": ["string", "null"],
          "default": null
        },
        "Weight": {
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
        "Type",
        "Description",
        "Weight",
        "Economy"
      ]
    },
    "RefiningRecipes": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "Amount": {
            "type": "number"
          },
          "Ingredients": {
            "type": "array",
            "items": {
              "type": "object",
              "additionalProperties": false,
              "properties": {
                "Item": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
                "Amount": {
                  "type": "number"
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
          "Amount",
          "Ingredients"
        ]
      }
    }
  },
  "required": [
    "Name",
    "Properties"
  ]
}