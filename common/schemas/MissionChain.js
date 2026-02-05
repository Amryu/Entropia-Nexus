export const MissionChain = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "Id": { "type": ["integer", "null"] },
    "Name": { "type": "string" },
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
        "Type": { "type": ["string", "null"], "default": null },
        "Description": { "type": ["string", "null"], "default": null }
      },
      "required": ["Type", "Description"]
    },
    "Missions": {
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
  "required": ["Name", "Properties", "Planet"]
};
