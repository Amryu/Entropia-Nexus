export const Mob = {
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
        "AggressionTimer": {
          "type": ["string", "null"],
          "enum": ["Very Long", "Long", "Medium", "Short", "Very Short", "Instant", null],
          "default": null
        },
        "AttacksPerMinute": {
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
          "NameMode": {
            "type": ["string", "null"],
            "enum": ["Suffix", "Prefix", "Verbatim", "Empty", null],
            "default": null
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
              "Boss": {
                "type": ["boolean", "null"],
                "default": false
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
                "type": ["object", "null"],
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
                "type": ["object", "null"],
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
                    "type": ["number", "null"],
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
                "TotalDamage": {
                  "type": ["number", "null"],
                  "default": null
                },
                "Damage": {
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
                "IsAoE": {
                  "type": "boolean",
                  "default": false
                }
              },
              "required": [
                "Name",
                "TotalDamage",
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
    "Spawns": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "Properties": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "Density": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5
              },
              "IsShared": { "type": "boolean" },
              "IsEvent": { "type": "boolean" },
              "Shape": { 
                "type": "string",
                "enum": ["Point", "Circle", "Rectangle", "Polygon"]
              },
              "Data": {
                "anyOf": [
                  { "type": "null" },
                  {
                    "type": "object",
                    "additionalProperties": false,
                    "properties": {
                      "x": { "type": "number" },
                      "y": { "type": "number" },
                      "width": { "type": "number" },
                      "height": { "type": "number" },
                      "radius": { "type": "number" },
                      "vertices": {
                        "type": "array",
                        "items": { "type": "number" },
                        "minItems": 6
                      }
                    }
                  }
                ]
              },
              "Coordinates": {
                "type": "object",
                "properties": {
                  "Altitude": { "type": ["number", "null"] }
                },
                "required": ["Altitude"]
              }
            },
            "required": ["Density", "IsShared", "IsEvent", "Shape", "Data", "Coordinates"]
          },
          "Maturities": {
            "type": "array",
            "items": {
              "type": "object",
              "additionalProperties": false,
              "properties": {
                "IsRare": { "type": "boolean" },
                "Maturity": {
                  "type": "object",
                  "properties": {
                    "Name": { "type": ["string", "null"] },
                    "Mob": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" }
                  },
                  "required": ["Name", "Mob"]
                }
              },
              "required": ["IsRare", "Maturity"]
            }
          }
        },
        "required": ["Properties", "Maturities"]
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
            "enum": ["Always", "Very often", "Often", "Common", "Uncommon", "Rare", "Very rare", "Extremely rare", "Discontinued"]
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
    "Type": { "type": ["string", "null"], "enum": ["Animal", "Mutant", "Robot", "Asteroid", null] },
    "Planet": { "$ref": "https://entropianexus.com/schemas/NamedEntity.json" },
    "Species": {
      "type": ["object", "null"],
      "additionalProperties": true,
      "properties": {
        "Name": { "type": ["string", "null"] },
        "Properties": {
          "type": "object",
          "additionalProperties": true,
          "properties": {
            "CodexType": { "type": ["string", "null"], "enum": ["Mob", "MobLooter", "Asteroid", null] },
            "CodexBaseCost": { "type": ["number", "null"] }
          }
        },
        "Links": { "type": "object", "additionalProperties": true }
      }
    }
  },
  "required": [
    "Name",
    "Properties"
  ]
}