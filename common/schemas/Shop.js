export const Shop = {
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "Id": {
      "type": ["integer", "null"],
      "default": null
    },
    "Name": {
      "type": "string"
    },
    "Description": {
      "type": ["string", "null"],
      "default": null
    },
    "Planet": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
    "Coordinates": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "Longitude": { "type": ["integer", "null"], "default": null },
        "Latitude": { "type": ["integer", "null"], "default": null },
        "Altitude": { "type": ["integer", "null"], "default": null }
      },
      "required": ["Longitude", "Latitude", "Altitude"]
    },
    "MaxGuests": {
      "type": ["integer", "null"],
      "default": null
    },
    "Owner": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
    "OwnerId": {
      "type": ["string", "null"],
      "default": null
    },
    "HasAdditionalArea": {
      "type": ["boolean", "null"],
      "default": null
    },
    "Sections": {
      "type": "array",
      "default": [],
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "Name": { "type": "string", "enum": ["Indoor", "Display", "Additional"] },
          "Description": { "type": ["string", "null"], "default": null },
          "ItemPoints": { "type": ["integer", "null"], "default": null },
          "MaxItemPoints": { "type": ["integer", "null"], "default": null }
        },
        "required": ["Name"]
      }
    }
  },
  "required": [
    "Name",
    "Planet",
    "Coordinates",
    "Sections"
  ]
}
