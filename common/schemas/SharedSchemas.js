export const EffectsOnEquip = {
  "$id": "https://entropianexus.com/schemas/EffectsOnEquip.json",
  "$schema": "http://json-schema.org/draft-07/schema#",
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
        "additionalProperties": false,
        "properties": {
          "Strength": {
            "type": ["number", "null"],
            "default": null
          }
        },
        "required": [
          "Strength"
        ]
      },
      "_newEffect": {
        "type": "object",
        "properties": {
          "CanonicalName": { "type": ["string", "null"] },
          "Unit": { "type": ["string", "null"] },
          "IsPositive": { "type": ["boolean", "null"] },
          "Description": { "type": ["string", "null"] }
        }
      }
    },
    "required": [
      "Name",
      "Values"
    ]
  }
}

export const EffectsOnSetEquip = {
  "$id": "https://entropianexus.com/schemas/EffectsOnSetEquip.json",
  "$schema": "http://json-schema.org/draft-07/schema#",
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
        "additionalProperties": false,
        "properties": {
          "Strength": {
            "type": ["number", "null"],
            "default": null
          },
          "MinSetPieces": {
            "type": ["integer", "null"],
            "default": null
          }
        },
        "required": [
          "Strength",
          "MinSetPieces"
        ]
      },
      "_newEffect": {
        "type": "object",
        "properties": {
          "CanonicalName": { "type": ["string", "null"] },
          "Unit": { "type": ["string", "null"] },
          "IsPositive": { "type": ["boolean", "null"] },
          "Description": { "type": ["string", "null"] }
        }
      }
    },
    "required": [
      "Name",
      "Values"
    ]
  }
}

export const EffectsOnUse = {
  "$id": "https://entropianexus.com/schemas/EffectsOnUse.json",
  "$schema": "http://json-schema.org/draft-07/schema#",
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
        "additionalProperties": false,
        "properties": {
          "Strength": {
            "type": ["number", "null"],
            "default": null
          },
          "DurationSeconds": {
            "type": ["number", "null"],
            "default": null
          }
        },
        "required": [
          "Strength",
          "DurationSeconds"
        ]
      },
      "_newEffect": {
        "type": "object",
        "properties": {
          "CanonicalName": { "type": ["string", "null"] },
          "Unit": { "type": ["string", "null"] },
          "IsPositive": { "type": ["boolean", "null"] },
          "Description": { "type": ["string", "null"] }
        }
      }
    },
    "required": [
      "Name",
      "Values"
    ]
  }
}

export const Tiers = {
  "$id": "https://entropianexus.com/schemas/Tiers.json",
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "array",
  "minItems": 0,
  "maxItems": 10,
  "items": {
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "Properties": {
        "type": "object",
        "properties": {
          "Tier": {
            "type": ["integer", "null"],
            "default": null
          }
        },
        "required": [
          "Tier"
        ]
      },
      "Materials": {
        "type": "array",
        "minItems": 5,
        "maxItems": 5,
        "items": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "Material": {
              "type": "object",
              "properties": {
                "Name": {
                  "type": ["string", "null"],
                  "default": null
                }
              },
              "required": [
                "Name"
              ]
            },
            "Amount": {
              "type": ["integer", "null"],
              "default": null
            }
          },
          "required": [
            "Material",
            "Amount"
          ]
        }
      }
    },
    "required": [
      "Properties",
      "Materials"
    ]
  }
}

export const NamedEntity = {
  "$id": "https://entropianexus.com/schemas/NamedEntity.json",
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "Name": {
      "type": ["string", "null"],
      "default": null
    }
  },
  "required": [
    "Name"
  ]
}