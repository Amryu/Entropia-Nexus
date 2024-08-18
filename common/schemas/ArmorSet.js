export const ArmorSet = {
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
        "Economy": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "Durability": {
              "type": ["number", "null"],
              "default": null
            }
          },
          "required": [
            "Durability"
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
        "Economy",
        "Defense"
      ]
    },
    "Armors": {
      "type": "array",
      "minItems": 0,
      "maxItems": 7,
      "items": {
        "type": "array",
        "minItems": 1,
        "maxItems": 2,
        "items": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "Name": {
              "type": ["string", "null"],
              "default": null
            },
            "Properties": {
              "type": "object",
              "additionalProperties": false,
              "properties": {
                "Weight": {
                  "type": ["number", "null"],
                  "default": null
                },
                "Gender": {
                  "type": ["string", "null"],
                  "default": null
                },
                "Slot": {
                  "type": ["string", "null"],
                  "default": null
                },
                "Economy": {
                  "type": "object",
                  "properties": {
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
                    "MaxTT",
                    "MinTT"
                  ]
                }
              },
              "required": [
                "Weight",
                "Gender",
                "Slot",
                "Economy"
              ]
            },
            "EffectsOnEquip": {
              "type": "array",
              "items": {
                "type": "object",
                "additionalProperties": false,
                "properties": {
                  "Name": {
                    "type": ["string", "null"],
                    "default": null
                  },
                  "Values": {
                    "type": "object",
                    "properties": {
                      "Strength": {
                        "type": ["number", "null"],
                        "default": null
                      }
                    },
                    "required": [
                      "Strength"
                    ]
                  }
                },
                "required": [
                  "Name",
                  "Values"
                ]
              }
            }
          },
          "required": [
            "Name",
            "Properties",
            "EffectsOnEquip"
          ]
        }
      }
    },
    "EffectsOnSetEquip": { "$ref": "https://entropianexus.com/schemas/EffectsOnSetEquip.json" },
    "Tiers": { "$ref": "https://entropianexus.com/schemas/Tiers.json" }
  },
  "required": [
    "Name",
    "Properties",
    "EffectsOnSetEquip",
    "Armors",
    "Tiers"
  ]
}