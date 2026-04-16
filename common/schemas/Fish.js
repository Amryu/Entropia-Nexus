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
        "Biomes": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": ["Sea", "River", "Lake", "Deep Ocean", "Sky"]
          },
          "default": []
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
        "TimesOfDay": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": ["Dawn", "Day", "Sunset", "Night"]
          },
          "default": []
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
          "required": ["MaxTT"]
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
        "Biomes",
        "Difficulty",
        "MinDepth",
        "TimesOfDay",
        "Weight",
        "Economy",
        "RodTypes"
      ]
    },
    "Sizes": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "Name": { "type": "string" },
          "Strength": { "type": ["number", "null"], "default": null },
          "ScrapsToRefine": { "type": ["integer", "null"], "default": null }
        },
        "required": ["Name"]
      },
      "default": []
    },
    "Species": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "Name": { "type": "string" },
        "CodexBaseCost": { "type": ["number", "null"], "default": null }
      },
      "required": ["Name"]
    },
    "FishOil": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
    "PreferredLure": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
    "Planets": {
      "type": "array",
      "items": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
      "default": []
    },
    "Locations": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "PlanetName": { "type": "string" },
          "Width": { "type": ["integer", "null"], "default": null },
          "Height": { "type": ["integer", "null"], "default": null },
          "Sectors": {
            "type": "array",
            "items": {
              "type": "object",
              "additionalProperties": false,
              "properties": {
                "Col": { "type": "integer" },
                "Row": { "type": "integer" },
                "Rarity": {
                  "type": "string",
                  "enum": ["Common", "Uncommon", "Rare", "Very Rare", "Extremely Rare"],
                  "default": "Common"
                },
                "Note": { "type": ["string", "null"], "default": null }
              },
              "required": ["Col", "Row", "Rarity"]
            },
            "default": []
          }
        },
        "required": ["PlanetName", "Sectors"]
      },
      "default": []
    }
  },
  "required": [
    "Name",
    "Properties",
    "Species"
  ]
}
