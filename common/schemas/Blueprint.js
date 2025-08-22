export const Blueprint = {
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
        "Description": {
          "type": ["string", "null"],
          "default": null
        },
        "Type": {
          "type": "string",
          "enum": ["Weapon", "Textile", "Vehicle", "Enhancer", "Furniture", "Tool", "Armor", "Attachment", "Metal Component", "Electrical Component", "Mechanical Component"]
        },
        "Level": {
          "type": ["integer", "null"],
          "default": null
        },
        "IsBoosted": {
          "type": ["boolean", "null"],
          "default": null
        },
        "MinimumCraftAmount": {
          "type": ["integer", "null"],
          "default": null
        },
        "MaximumCraftAmount": {
          "type": ["integer", "null"],
          "default": null
        },
        "Skill": {
          "type": "object",
          "additionalItems": false,
          "properties": {
            "IsSiB": {
              "type": ["boolean", "null"],
              "default": null
            },
            "LearningIntervalStart": {
              "type": ["number", "null"],
              "default": null
            },
            "LearningIntervalEnd": {
              "type": ["number", "null"],
              "default": null
            }
          },
          "required": [
            "IsSiB",
            "LearningIntervalStart",
            "LearningIntervalEnd"
          ]
        }
      },
      "required": [
        "Description",
        "Type",
        "Level",
        "IsBoosted",
        "MinimumCraftAmount",
        "MaximumCraftAmount",
        "Skill"
      ]
    },
    "Materials": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "Amount": {
            "type": "integer"
          },
          "Item": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "Name": {
                "type": "string"
              }
            },
            "required": [
              "Name"
            ]
          }
        },
        "required": [
          "Amount",
          "Item"
        ]
      }
    },
    "Drops": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "Name": { "type": "string" }
        },
        "required": ["Name"]
      },
      "default": []
    },
    "Book": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
    "Product": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
    "Profession": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" }
  },
  "required": [
    "Name",
    "Properties",
    "Materials",
    "Book",
    "Product",
    "Profession"
  ]
}