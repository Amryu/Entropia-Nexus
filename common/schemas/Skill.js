export const Skill = {
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
    "Category": {
      "anyOf": [
        { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
        { "type": "null" }
      ],
      "default": null
    },
    "Properties": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "Description": {
          "type": ["string", "null"],
          "default": null
        },
        "HpIncrease": {
          "type": ["number", "integer", "null"],
          "default": null
        },
        "IsHidden": {
          "type": ["boolean", "null"],
          "default": null
        },
        "IsExtractable": {
          "type": ["boolean", "null"],
          "default": null
        }
      },
      "required": [
        "Description",
        "HpIncrease",
        "IsHidden",
        "IsExtractable"
      ]
    },
    "Professions": {
      "type": "array",
      "default": [],
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "Profession": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
          "Weight": {
            "type": ["number", "integer", "null"],
            "default": null
          }
        },
        "required": [
          "Profession",
          "Weight"
        ]
      }
    },
    "Unlocks": {
      "type": "array",
      "default": [],
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "Profession": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
          "Level": {
            "type": ["number", "integer", "null"],
            "default": null
          }
        },
        "required": [
          "Profession",
          "Level"
        ]
      }
    }
  },
  "required": [
    "Name",
    "Category",
    "Properties",
    "Professions",
    "Unlocks"
  ]
};
