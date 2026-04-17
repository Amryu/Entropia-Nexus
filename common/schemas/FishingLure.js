export const FishingLure = {
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
        "LureType": {
          "type": ["string", "null"],
          "enum": ["Sinkers", "Lures", "Baits", "Worms", "Jigs", "Flys", "Spinners", "Spoons", null],
          "default": null
        },
        "Depth": { "type": ["number", "null"], "default": null },
        "Quality": { "type": ["number", "null"], "default": null },
        "Economy": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "MaxTT": { "type": ["number", "null"], "default": null },
            "MinTT": { "type": ["number", "null"], "default": null },
            "Decay": { "type": ["number", "null"], "default": null }
          },
          "required": ["MaxTT", "MinTT", "Decay"]
        }
      },
      "required": ["Description", "Weight", "Economy"]
    }
  },
  "required": ["Name", "Properties"]
}
