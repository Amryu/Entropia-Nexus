export const Mob = {
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
        "AttackRange": {
          "type": ["number", "null"],
          "default": null
        },
        "AggressionRange": {
          "type": ["number", "null"],
          "default": null
        },
        "IsSweatable": {
          "type": ["boolean", "null"],
          "default": null
        }
      },
      "required": [
        "Description",
        "AttackRange",
        "AggressionRange",
        "IsSweatable"
      ]
    },
    "Maturities": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
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
              "Health": {
                "type": ["number", "null"],
                "default": null
              },
              "AttacksPerMinute": {
                "type": ["number", "null"],
                "default": null
              },
              "Level": {
                "type": ["integer", "null"],
                "default": null
              },
              "RegenerationInterval": {
                "type": ["number", "null"],
                "default": null
              },
              "RegenerationAmount": {
                "type": ["number", "null"],
                "default": null
              },
              "MissChance": {
                "type": ["number", "null"],
                "default": null
              },
              "Attributes": {
                "type": "object",
                "additionalProperties": false,
                "properties": {
                  "Strength": {
                    "type": ["number", "null"],
                    "default": null
                  },
                  "Agility": {
                    "type": ["number", "null"],
                    "default": null
                  },
                  "Intelligence": {
                    "type": ["number", "null"],
                    "default": null
                  },
                  "Stamina": {
                    "type": ["number", "null"],
                    "default": null
                  },
                  "Psyche": {
                    "type": ["number", "null"],
                    "default": null
                  }
                },
                "required": [
                  "Strength",
                  "Agility",
                  "Intelligence",
                  "Stamina",
                  "Psyche"
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
              },
              "Taming": {
                "type": "object",
                "additionalProperties": false,
                "properties": {
                  "TamingLevel": {
                    "type": ["integer", "null"],
                    "default": null
                  }
                },
                "required": [
                  "TamingLevel"
                ]
              }
            },
            "required": [
              "Description",
              "Health",
              "AttacksPerMinute",
              "Level",
              "RegenerationInterval",
              "RegenerationAmount",
              "MissChance",
              "Attributes",
              "Defense"
            ]
          },
          "Attacks": {
            "type": "array",
            "items": {
              "type": "object",
              "additionalProperties": false,
              "properties": {
                "Name": {
                  "type": "string",
                  "default": "Primary"
                },
                "Damage": {
                  "type": "object",
                  "additionalProperties": false,
                  "properties": {
                    "Damage": {
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
                    "Damage",
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
                },
                "IsAoE": {
                  "type": "boolean",
                  "default": false
                }
              },
              "required": [
                "Name",
                "Damage",
                "IsAoE"
              ]
            }
          }
        },
        "required": [
          "Name",
          "Properties",
          "Attacks"
        ]
      }
    },
    "Loots": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "Frequency": {
            "type": "string",
            "enum": ["Always", "Very often", "Often", "Common", "Uncommon", "Rare", "Very rare", "Extremely rare"] 
          },
          "IsEvent": {
            "type": "boolean",
            "default": false
          },
          "Maturity": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
          "Item": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" }
        },
        "required": [
          "Frequency",
          "IsEvent",
          "Maturity",
          "Item"
        ]
      }
    },
    "DefensiveProfession": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
    "ScanningProfession": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
    "Planet": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
    "Species": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" }
  },
  "required": [
    "Name",
    "Properties"
  ]
}