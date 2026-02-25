export const Mission = {
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
    "MissionChain": {
      "description": "Mission chain this mission belongs to. When creating/updating, provide Name to link to existing chain or create new one.",
      "anyOf": [
        {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "Id": { "type": ["integer", "null"], "description": "Chain ID (read-only from API)" },
            "Name": { "type": "string", "description": "Chain name - used to find or create the chain" },
            "Planet": {
              "anyOf": [
                { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
                { "type": "string" },
                { "type": "null" }
              ],
              "description": "Planet the chain is associated with (string or { Name: string })"
            },
            "PlanetId": { "type": ["integer", "null"], "description": "Planet ID (read-only from API)" },
            "Description": { "type": ["string", "null"], "description": "Chain description (API format)" },
            "Properties": {
              "type": "object",
              "additionalProperties": false,
              "properties": {
                "Type": { "type": ["string", "null"], "default": null },
                "Description": { "type": ["string", "null"], "default": null }
              }
            },
            "Links": { "type": "object", "additionalProperties": true }
          },
          "required": ["Name"]
        },
        { "type": "null" }
      ]
    },
    "Planet": {
      "anyOf": [
        { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
        { "type": "null" }
      ]
    },
    "Properties": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "Type": {
          "type": ["string", "null"],
          "enum": ["One-Time", "Repeatable", "Recurring", null],
          "default": "One-Time",
          "description": "Mission repeatability: One-Time (single completion), Repeatable (can repeat immediately), Recurring (can repeat after cooldown)"
        },
        "Description": { "type": ["string", "null"], "default": null },
        "CooldownDuration": {
          "type": ["string", "null"],
          "default": null,
          "description": "PostgreSQL INTERVAL format (e.g., '1 day', '12 hours', '30 minutes'). Range: 1 minute to 30 days. Only applicable when Type = 'Recurring'."
        },
        "CooldownStartsOn": {
          "type": ["string", "null"],
          "enum": ["Accept", "Completion", null],
          "default": null,
          "description": "When cooldown starts: 'Accept' (on mission accept) or 'Completion' (on mission completion). Only applicable when Type = 'Recurring'."
        }
      },
      "required": ["Type", "Description"]
    },
    "Event": {
      "anyOf": [
        { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
        { "type": "null" }
      ]
    },
    "StartLocationId": {
      "type": ["integer", "null"],
      "default": null,
      "description": "Reference to the Location where this mission starts"
    },
    "StartLocation": {
      "anyOf": [
        {
          "type": "object",
          "additionalProperties": true,
          "properties": {
            "Id": { "type": ["integer", "null"] },
            "Name": { "type": ["string", "null"] },
            "Planet": {
              "anyOf": [
                { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
                { "type": "null" }
              ]
            },
            "Coordinates": {
              "type": ["object", "null"],
              "properties": {
                "Longitude": { "type": ["number", "null"] },
                "Latitude": { "type": ["number", "null"] },
                "Altitude": { "type": ["number", "null"] }
              }
            }
          }
        },
        { "type": "null" }
      ],
      "description": "Resolved start location data (read-only from API)"
    },
    "Steps": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "Id": { "type": ["integer", "null"] },
          "Index": { "type": ["integer", "null"] },
          "Title": { "type": ["string", "null"] },
          "Description": { "type": ["string", "null"] },
          "Objectives": {
            "type": "array",
            "items": {
              "type": "object",
              "additionalProperties": false,
              "properties": {
                "Id": { "type": ["integer", "null"] },
                "Type": { "type": ["string", "null"] },
                "Payload": { "type": ["object", "null"], "additionalProperties": true }
              },
              "required": ["Type", "Payload"]
            }
          }
        },
        "required": ["Index", "Objectives"]
      }
    },
    "Rewards": {
      "description": "Mission rewards. Can be a single reward package (object) or an array of choices (player picks one). Detected implicitly: array = choices mode, object = flat mode.",
      "anyOf": [
        {
          "type": "object",
          "description": "Single reward package (no choices)",
          "additionalProperties": false,
          "properties": {
            "Items": {
              "type": "array",
              "items": {
                "type": "object",
                "additionalProperties": false,
                "properties": {
                  "itemId": { "type": ["integer", "null"] },
                  "itemName": { "type": ["string", "null"] },
                  "quantity": { "type": ["integer", "null"] },
                  "minQuantity": { "type": ["integer", "null"] },
                  "maxQuantity": { "type": ["integer", "null"] },
                  "rarity": { "type": ["string", "null"], "enum": ["guaranteed", "uncommon", "rare", "very-rare", null] },
                  "minPedValue": { "type": ["number", "null"] },
                  "pedValue": { "type": ["number", "null"] }
                }
              }
            },
            "Skills": {
              "type": "array",
              "items": {
                "type": "object",
                "additionalProperties": false,
                "properties": {
                  "skillItemId": { "type": ["integer", "null"] },
                  "skillName": { "type": ["string", "null"] },
                  "pedValue": { "type": ["number", "null"] }
                }
              }
            },
            "Unlocks": {
              "type": "array",
              "items": { "type": "string" }
            }
          }
        },
        {
          "type": "array",
          "description": "Array of reward choices - player picks one package. Each element is a complete reward package with Items, Skills, and Unlocks.",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "Items": {
                "type": "array",
                "items": {
                  "type": "object",
                  "additionalProperties": false,
                  "properties": {
                    "itemId": { "type": ["integer", "null"] },
                    "itemName": { "type": ["string", "null"] },
                    "quantity": { "type": ["integer", "null"] },
                    "minQuantity": { "type": ["integer", "null"] },
                    "maxQuantity": { "type": ["integer", "null"] },
                    "rarity": { "type": ["string", "null"], "enum": ["guaranteed", "uncommon", "rare", "very-rare", null] },
                    "minPedValue": { "type": ["number", "null"] },
                    "pedValue": { "type": ["number", "null"] }
                  }
                }
              },
              "Skills": {
                "type": "array",
                "items": {
                  "type": "object",
                  "additionalProperties": false,
                  "properties": {
                    "skillItemId": { "type": ["integer", "null"] },
                    "skillName": { "type": ["string", "null"] },
                    "pedValue": { "type": ["number", "null"] }
                  }
                }
              },
              "Unlocks": {
                "type": "array",
                "items": { "type": "string" }
              }
            }
          }
        },
        { "type": "null" }
      ]
    },
    "Dependencies": {
      "anyOf": [
        {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "Prerequisites": {
              "type": "array",
              "items": {
                "type": "object",
                "additionalProperties": true,
                "properties": {
                  "Id": { "type": ["integer", "null"] },
                  "Name": { "type": ["string", "null"] }
                }
              }
            },
            "Dependents": {
              "type": "array",
              "items": {
                "type": "object",
                "additionalProperties": true,
                "properties": {
                  "Id": { "type": ["integer", "null"] },
                  "Name": { "type": ["string", "null"] }
                }
              }
            }
          },
          "required": ["Prerequisites", "Dependents"]
        },
        { "type": "null" }
      ]
    }
  },
  "required": ["Name", "Properties", "Planet"]
};
