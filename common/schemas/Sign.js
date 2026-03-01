export const Sign = {
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
        "Weight": {
          "type": ["number", "null"],
          "default": null
        },
        "ItemPoints": {
          "type": ["integer", "null"],
          "default": null
        },
        "Economy": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "MaxTT": {
              "type": ["number", "null"],
              "default": null
            },
            "Cost": {
              "type": ["number", "null"],
              "default": null
            }
          },
          "required": [
            "MaxTT",
            "Cost"
          ]
        },
        "Display": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "AspectRatio": {
              "type": ["string", "null"],
              "default": null
            },
            "CanShowLocalContentScreen": {
              "type": ["boolean", "null"],
              "default": null
            },
            "CanShowImagesAndText": {
              "type": ["boolean", "null"],
              "default": null
            },
            "CanShowEffects": {
              "type": ["boolean", "null"],
              "default": null
            },
            "CanShowMultimedia": {
              "type": ["boolean", "null"],
              "default": null
            },
            "CanShowParticipantContent": {
              "type": ["boolean", "null"],
              "default": null
            }
          },
          "required": [
            "AspectRatio",
            "CanShowLocalContentScreen",
            "CanShowImagesAndText",
            "CanShowEffects",
            "CanShowMultimedia",
            "CanShowParticipantContent"
          ]
        }
      },
      "required": [
        "Description",
        "Weight",
        "ItemPoints",
        "Economy",
        "Display"
      ]
    }
  },
  "required": [
    "Name",
    "Properties"
  ]
}