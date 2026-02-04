export const Location = {
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
              "type": ["number", "null"],
              "default": null
            },
            "Latitude": {
              "type": ["number", "null"],
              "default": null
            },
            "Altitude": {
              "type": ["number", "null"],
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
    "Planet": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" }
  },
  "required": [
    "Name",
    "Properties",
    "Planet"
  ]
};
