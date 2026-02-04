export const Apartment = {
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
        "Description": {
          "type": ["string", "null"],
          "default": null
        },
        "Type": {
          "type": ["string", "null"],
          "default": null
        },
        "Coordinates": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "Longitude": {
              "type": ["number", "integer", "null"],
              "default": null
            },
            "Latitude": {
              "type": ["number", "integer", "null"],
              "default": null
            },
            "Altitude": {
              "type": ["number", "integer", "null"],
              "default": null
            }
          },
          "required": [
            "Longitude",
            "Latitude",
            "Altitude"
          ]
        }
      },
      "required": [
        "Description",
        "Type",
        "Coordinates"
      ]
    },
    "Planet": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
    "OwnerId": {
      "type": ["integer", "null"],
      "default": null
    },
    "MaxGuests": {
      "type": ["integer", "null"],
      "default": null
    },
    "Sections": {
      "type": "array",
      "default": [],
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "Name": { "type": "string" },
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
    "Properties",
    "Planet",
    "Sections"
  ]
};
