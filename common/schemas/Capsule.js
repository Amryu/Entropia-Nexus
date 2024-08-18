export const Capsule = {
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