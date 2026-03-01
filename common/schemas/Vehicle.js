export const Vehicle = {
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
        "Type": {
          "type": ["string", "null"],
          "enum": ["Land", "Air", "Water", "Amphibious", "Space", null],
          "default": null
        },
        "SpawnedWeight": {
          "type": ["number", "null"],
          "default": null
        },
        "PassengerCount": {
          "type": ["integer", "null"],
          "default": null
        },
        "ItemCapacity": {
          "type": ["integer", "null"],
          "default": null
        },
        "WeightCapacity": {
          "type": ["number", "null"],
          "default": null
        },
        "WheelGrip": {
          "type": ["number", "null"],
          "default": null
        },
        "EnginePower": {
          "type": ["number", "null"],
          "default": null
        },
        "MaxSpeed": {
          "type": ["number", "null"],
          "default": null
        },
        "MaxStructuralIntegrity": {
          "type": ["number", "null"],
          "default": null
        },
        "Economy": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "Durability": {
              "type": ["integer", "null"],
              "default": null
            },
            "MaxTT": {
              "type": ["number", "null"],
              "default": null
            },
            "MinTT": {
              "type": ["number", "null"],
              "default": null
            },
            "FuelConsumptionActive": {
              "type": ["number", "null"],
              "default": null
            },
            "FuelConsumptionPassive": {
              "type": ["number", "null"],
              "default": null
            },
            "Decay": {
              "type": ["number", "null"],
              "default": null
            }
          },
          "required": [
            "Durability",
            "MaxTT",
            "MinTT",
            "FuelConsumptionActive",
            "FuelConsumptionPassive",
            "Decay"
          ]
        },
        "Defense": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "Stab": {
              "type": ["number", "null"],
              "default": null
            },
            "Cut": {
              "type": ["number", "null"],
              "default": null
            },
            "Impact": {
              "type": ["number", "null"],
              "default": null
            },
            "Penetration": {
              "type": ["number", "null"],
              "default": null
            },
            "Shrapnel": {
              "type": ["number", "null"],
              "default": null
            },
            "Burn": {
              "type": ["number", "null"],
              "default": null
            },
            "Cold": {
              "type": ["number", "null"],
              "default": null
            },
            "Acid": {
              "type": ["number", "null"],
              "default": null
            },
            "Electric": {
              "type": ["number", "null"],
              "default": null
            }
          },
          "required": [
            "Stab",
            "Cut",
            "Impact",
            "Penetration",
            "Shrapnel",
            "Burn",
            "Cold",
            "Acid",
            "Electric"
          ]
        }
      },
      "required": [
        "Description",
        "Weight",
        "SpawnedWeight",
        "PassengerCount",
        "ItemCapacity",
        "WeightCapacity",
        "WheelGrip",
        "EnginePower",
        "MaxSpeed",
        "MaxStructuralIntegrity",
        "Economy",
        "Defense"
      ]
    },
    "Fuel": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
    "AttachmentSlots": {
      "type": "array",
      "uniqueItems": true,
      "items": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" }
    }
  },
  "required": [
    "Name",
    "Properties",
    "Fuel",
    "AttachmentSlots"
  ]
}