export const FishingRod = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "Id": { "type": ["integer", "null"] },
    "ClassId": { "type": ["string", "null"], "default": null },
    "Name": { "type": "string" },
    "Properties": {
      "type": "object",
      "properties": {
        "Description": { "type": ["string", "null"], "default": null },
        "IsUntradeable": { "type": ["boolean", "null"], "default": null },
        "IsRare": { "type": ["boolean", "null"], "default": null },
        "Weight": { "type": ["number", "null"], "default": null },
        "RodType": {
          "type": "string",
          "enum": ["Casting", "Angling", "Fly Fishing", "Deep Ocean Fishing", "Baitfishing"]
        },
        "Strength": { "type": ["number", "null"], "default": null },
        "Flexibility": { "type": ["number", "null"], "default": null },
        "Economy": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "MaxTT": { "type": ["number", "null"], "default": null },
            "MinTT": { "type": ["number", "null"], "default": null },
            "Decay": { "type": ["number", "null"], "default": null }
          },
          "required": ["MaxTT", "MinTT", "Decay"]
        },
        "Skill": {
          "type": "object",
          "properties": {
            "LearningIntervalStart": { "type": ["number", "null"], "default": null },
            "LearningIntervalEnd": { "type": ["number", "null"], "default": null },
            "IsSiB": { "type": ["boolean", "null"], "default": null }
          },
          "required": ["LearningIntervalStart", "LearningIntervalEnd", "IsSiB"]
        }
      },
      "required": ["Description", "Weight", "RodType", "Economy", "Skill"]
    },
    "Profession": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" }
  },
  "required": ["Name", "Properties"]
}
