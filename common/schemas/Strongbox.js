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
        }
      },
      "required": [
        "Description"
      ]
    },
    "Loots": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "Rarity": {
            "type": "string",
            "enum": ["Common", "Uncommon", "Rare", "Epic", "Supreme", "Legendary", "Mythical"],
          },
          "AvailableFrom": {
            "type": ["date", "null"],
            "default": null
          },
          "AvailableUntil": {
            "type": ["date", "null"],
            "default": null
          },
          "Item": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
        },
        "required": [
          "Rarity",
          "AvailableFrom",
          "AvailableUntil",
          "Item",
        ]
      }
    }
  },
  "required": [
    "Name",
    "Loots"
  ]
}