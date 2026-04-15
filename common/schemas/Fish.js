export const Fish = {
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
        "Biome": {
          "type": ["string", "null"],
          "enum": ["Sea", "River", "Lake", "Deep Ocean", "Sky", null],
          "default": null
        },
        "Size": {
          "type": ["number", "null"],
          "default": null
        },
        "Strength": {
          "type": ["number", "null"],
          "default": null
        },
        "Difficulty": {
          "type": ["string", "null"],
          "enum": ["Easy", "Medium", "Hard", "Very Hard", "Elite", null],
          "default": null
        },
        "MinDepth": {
          "type": ["number", "null"],
          "default": null
        },
        "TimeOfDay": {
          "type": ["string", "null"],
          "enum": ["Day", "Night", null],
          "default": null
        },
        "RodTypes": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": ["Casting", "Angling", "Fly Fishing", "Deep Ocean Fishing", "Baitfishing"]
          },
          "default": []
        }
      },
      "required": [
        "Description",
        "Biome",
        "Size",
        "Strength",
        "Difficulty",
        "MinDepth",
        "TimeOfDay",
        "RodTypes"
      ]
    },
    "Item": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
    "Species": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "Name": { "type": "string" },
        "CodexBaseCost": { "type": ["number", "null"], "default": null }
      },
      "required": ["Name"]
    },
    "PreferredLure": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
    "Planets": {
      "type": "array",
      "items": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
      "default": []
    }
  },
  "required": [
    "Name",
    "Properties",
    "Item",
    "Species"
  ]
}
