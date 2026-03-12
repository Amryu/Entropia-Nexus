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
        "Type": {
          "type": "string",
          "enum": [
            "Teleporter", "Npc", "Interactable",
            "Area", "Estate",
            "Outpost", "Camp", "City",
            "RevivalPoint", "InstanceEntrance",
            "Vendor"
          ]
        },
        "Description": {
          "type": ["string", "null"],
          "default": null
        },
        "Coordinates": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "Longitude": { "type": ["number", "null"], "default": null },
            "Latitude": { "type": ["number", "null"], "default": null },
            "Altitude": { "type": ["number", "null"], "default": null }
          },
          "required": ["Longitude", "Latitude", "Altitude"]
        },
        "TechnicalId": {
          "type": ["string", "null"],
          "default": null
        },
        // Area-specific properties (when Type = 'Area')
        "AreaType": {
          "type": ["string", "null"],
          "enum": ["PvpArea", "PvpLootArea", "MobArea", "LandArea", "ZoneArea", "CityArea", "EstateArea", "EventArea", "WaveEventArea", null],
          "default": null
        },
        "Shape": {
          "type": ["string", "null"],
          "enum": ["Point", "Circle", "Rectangle", "Polygon", null],
          "default": null
        },
        "Data": {
          "type": ["object", "null"],
          "additionalProperties": true,
          "default": null
        },
        // Estate-specific properties (when Type = 'Estate')
        "EstateType": {
          "type": ["string", "null"],
          "enum": ["Shop", "Apartment", null],
          "default": null
        },
        "OwnerId": {
          "type": ["string", "null"],
          "default": null
        },
        "ItemTradeAvailable": {
          "type": ["boolean", "null"],
          "default": null
        },
        "MaxGuests": {
          "type": ["integer", "null"],
          "default": null
        },
        // LandArea-specific properties (when Type = 'Area' and AreaType = 'LandArea')
        // Tax rates are split into 3 components, each 0-5%
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
        "LandAreaOwnerId": {
          "type": ["string", "null"],
          "default": null
        },
        "LandAreaOwnerName": {
          "type": ["string", "null"],
          "default": null
        },
        // MobArea-specific properties (when Type = 'Area' and AreaType = 'MobArea')
        "Density": {
          "type": ["integer", "null"],
          "default": null
        },
        "IsShared": {
          "type": ["boolean", "null"],
          "default": null
        },
        "IsEvent": {
          "type": ["boolean", "null"],
          "default": null
        },
        "Notes": {
          "type": ["string", "null"],
          "default": null
        },
        "MobData": {
          "type": ["array", "null"],
          "default": null,
          "items": { "type": "object", "additionalProperties": true }
        }
      },
      "required": ["Type", "Coordinates"]
    },
    "Planet": {
      "anyOf": [
        { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
        { "type": "null" }
      ]
    },
    "ParentLocation": {
      "anyOf": [
        { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
        { "type": "null" }
      ]
    },
    "Facilities": {
      "type": "array",
      "items": {
        "anyOf": [
          { "type": "string" },
          {
            "type": "object",
            "properties": {
              "Id": { "type": ["integer", "null"] },
              "Name": { "type": "string" }
            },
            "required": ["Name"]
          }
        ]
      },
      "default": []
    },
    // Sections for Estate type
    "Sections": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "Name": { "type": "string" },
          "Description": { "type": ["string", "null"] },
          "ItemPoints": { "type": ["integer", "null"] }
        },
        "required": ["Name"]
      },
      "default": []
    },
    // Maturities for MobArea type
    "Maturities": {
      "type": "array",
      "items": { "type": "object", "additionalProperties": true },
      "default": []
    },
    // Waves for WaveEvent type
    "Waves": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "Id": { "type": ["integer", "null"] },
          "WaveIndex": { "type": "integer" },
          "TimeToComplete": { "type": ["integer", "null"], "description": "Time in minutes" },
          "MobMaturities": {
            "type": "array",
            "items": { "type": "integer" },
            "description": "Array of MobMaturity IDs"
          }
        },
        "required": ["WaveIndex"]
      },
      "default": []
    }
  },
  "required": ["Name", "Properties"]
};
