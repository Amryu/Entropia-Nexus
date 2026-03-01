export const Capsule = {
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
      "properties": {
        "Description": {
          "type": ["string", "null"],
          "default": null
        },
        "Weight": {
          "type": ["number", "null"],
          "default": null
        },
        "MinProfessionLevel": {
          "type": ["integer", "null"],
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
        "Description",
        "Weight",
        "MinProfessionLevel",
        "Economy"
      ]
    },
    "Profession": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
    "Mob": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" }
  },
  "required": [
    "Name",
    "Properties",
    "Profession",
    "Mob"
  ]
}