export const Pet = {
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
        "Rarity": {
          "type": "string",
          "enum": ["Common", "Uncommon", "Rare", "Epic", "Legendary", "Mythic", "Unique"]
        },
        "TrainingDifficulty": {
          "type": "string",
          "enum": ["Easy", "Average", "Hard"]
        },
        "NutrioCapacity": {
          "type": ["integer", "null"],
          "default": null
        },
        "NutrioConsumptionPerHour": {
          "type": ["integer", "null"],
          "default": null
        },
        "ExportableLevel": {
          "type": ["integer", "null"],
          "default": null
        },
        "TamingLevel": {
          "type": ["integer", "null"],
          "default": null
        }
      },
      "required": [
        "Rarity",
        "TrainingDifficulty",
        "NutrioCapacity",
        "NutrioConsumptionPerHour",
        "ExportableLevel",
        "TamingLevel"
      ]
    },
    "Effects": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "Name": {
            "type": "string"
          },
          "Properties": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "Strength": {
                "type": ["number", "null"],
                "default": null
              },
              "NutrioConsumptionPerHour": {
                "type": ["integer", "null"],
                "default": null
              },
              "Unlock": {
                "type": "object",
                "properties": {
                  "Level": {
                    "type": ["integer", "null"],
                    "default": null
                  },
                  "CostPED": {
                    "type": ["number", "null"],
                    "default": null
                  },
                  "CostEssence": {
                    "type": ["integer", "null"],
                    "default": null
                  },
                  "CostRareEssence": {
                    "type": ["integer", "null"],
                    "default": null
                  },
                  "Criteria": {
                    "type": ["string", "null"],
                    "default": null
                  },
                  "CriteriaValue": {
                    "type": ["number", "null"],
                    "default": null
                  }
                },
                "required": [
                  "Level",
                  "CostPED",
                  "CostEssence",
                  "CostRareEssence",
                  "Criteria",
                  "CriteriaValue"
                ]
              }
            },
            "required": [
              "Strength",
              "NutrioConsumptionPerHour",
              "Unlock"
            ]
          }
        },
        "required": [
          "Name",
          "Properties"
        ]
      }
    },
    "Planet": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" }
  },
  "required": [
    "Name",
    "Properties",
    "Effects",
    "Planet"
  ]
}