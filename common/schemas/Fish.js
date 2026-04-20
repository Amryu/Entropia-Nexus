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
            "enum": ["Sea", "River", "Lake", "Deep Ocean"]
          },
          "default": []
        },
        "Difficulty": {
          "type": ["string", "null"],
          "enum": ["Easy", "Medium", "Hard", "Very Hard", null],
          "default": null
        },
        "MinDepth": {
          "type": ["number", "null"],
          "default": null
        },
        "Strength": {
          "type": ["number", "null"],
          "default": null
        },
        "ScrapsToRefine": {
          "type": ["integer", "null"],
          "default": null
        },
        "Weight": {
          "type": ["number", "null"],
          "minimum": 0,
          "maximum": 1,
          "default": null
        },
        "TimeOfDay": {
          "oneOf": [
            { "type": "null" },
            {
              "type": "object",
              "additionalProperties": false,
              "properties": {
                "Start": {
                  "type": "number",
                  "enum": [0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1]
                },
                "End": {
                  "type": "number",
                  "enum": [0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1]
                }
              },
              "required": ["Start", "End"]
            }
          ],
          "default": null
        },
        "RodTypes": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": ["Casting", "Angling", "Fly Fishing", "Deep Ocean Fishing", "Baitfishing"]
          },
          "default": []
        },
        "PreferredLureTypes": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": ["Sinkers", "Lures", "Baits", "Worms", "Jigs", "Flys", "Spinners", "Spoons"]
          },
          "default": []
        }
      },
      "required": [
        "Description",
        "Biomes",
        "Difficulty",
        "MinDepth",
        "Strength",
        "ScrapsToRefine",
        "Weight",
        "TimeOfDay",
        "RodTypes",
        "PreferredLureTypes"
      ]
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
