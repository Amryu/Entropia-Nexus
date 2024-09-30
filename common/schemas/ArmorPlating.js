export const ArmorPlating = {
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
        "Description": {
          "type": ["string", "null"],
          "default": null
        },
        "Weight": {
          "type": ["number", "null"],
          "default": null
        },
        "Economy": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "Durability": {
              "type": ["number", "null"],
              "default": null
            },
            "MaxTT": {
              "type": ["number", "null"],
              "default": null
            },
            "MinTT": {
              "type": ["number", "null"],
              "default": null
            }
          },
          "required": [
            "Durability",
            "MaxTT",
            "MinTT"
          ]
        },
        "Defense": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "Block": {
              "type": ["number", "null"],
              "default": null
            },
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
            "Block",
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
        "Economy",
        "Defense"
      ]
    }
  },
  "required": [
    "Name",
    "Properties"
  ]
}