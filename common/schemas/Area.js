export const Area = {
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
        "AreaType": {
          "type": ["string", "null"],
          "default": null
        },
        "Shape": {
          "type": ["string", "null"],
          "default": null
        },
        "Data": {
          "type": ["object", "null"],
          "default": null,
          "additionalProperties": true
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
        },
        "Density": {
          "type": ["integer", "null"],
          "default": null
        },
        "MobData": {
          "type": ["array", "null"],
          "default": null,
          "items": { "type": "object", "additionalProperties": true }
        },
        "TaxRateHunting": {
          "type": ["number", "null"],
          "default": null
        },
        "TaxRateMining": {
          "type": ["number", "null"],
          "default": null
        },
        "TaxRateShops": {
          "type": ["number", "null"],
          "default": null
        },
        "LandAreaOwnerName": {
          "type": ["string", "null"],
          "default": null
        }
      },
      "required": [
        "Description",
        "Type",
        "Shape",
        "Data",
        "Coordinates"
      ]
    },
    "Planet": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
    "ParentLocation": {
      "anyOf": [
        { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
        { "type": "null" }
      ]
    }
  },
  "required": [
    "Name",
    "Properties",
    "Planet"
  ]
};
