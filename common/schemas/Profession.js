export const Profession = {
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
    "Description": {
      "type": ["string", "null"],
      "default": null
    },
    "Category": {
      "anyOf": [
        { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
        { "type": "null" }
      ],
      "default": null
    },
    "Skills": {
      "type": "array",
      "default": [],
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "Skill": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
          "Weight": {
            "type": ["number", "integer", "null"],
            "default": null
          }
        },
        "required": [
          "Skill",
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
          "Skill": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
          "Level": {
            "type": ["number", "integer", "null"],
            "default": null
          }
        },
        "required": [
          "Skill",
          "Level"
        ]
      }
    }
  },
  "required": [
    "Name",
    "Description",
    "Category",
    "Skills",
    "Unlocks"
  ]
};
