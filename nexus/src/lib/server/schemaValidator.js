// @ts-nocheck
import Ajv from "ajv";
import { EffectsOnEquip, EffectsOnSetEquip, EffectsOnUse, NamedEntity, Tiers } from "$lib/common/schemas/SharedSchemas.js";
import { EntitySchemas } from "$lib/common/EntitySchemas.js";

const shared = [EffectsOnEquip, EffectsOnSetEquip, EffectsOnUse, NamedEntity, Tiers];

/**
 * Maps entity type names to their EntitySchemas keys.
 * Includes legacy compatibility mappings for old change records.
 */
const ENTITY_TYPE_MAP = {
  TeleportChip: 'TeleportationChip',
  CreatureControlCapsule: 'Capsule',
  Area: 'Location',
  Apartment: 'Location',
};

/**
 * Resolve an entity type name to its corresponding EntitySchemas key.
 */
function resolveSchemaKey(entityType) {
  return ENTITY_TYPE_MAP[entityType] || entityType;
}

/**
 * Cached Ajv validators keyed by resolved schema name.
 * Two caches: one for 'all' mode (audit), one for 'true' mode (changes).
 */
const ValidatorsAll = {};
const ValidatorsTrue = {};

/**
 * Get or create a cached Ajv validator for an entity type.
 * @param {string} entityType - Entity type name
 * @param {'all'|true} removeMode - 'all' strips aggressively (audit data), true preserves additionalProperties:true fields (changes)
 */
export function getValidator(entityType, removeMode = 'all') {
  const schemaKey = resolveSchemaKey(entityType);
  const cache = removeMode === 'all' ? ValidatorsAll : ValidatorsTrue;

  if (!cache[schemaKey]) {
    const schema = EntitySchemas[schemaKey];
    if (!schema) return null;

    cache[schemaKey] = new Ajv({
      schemas: shared,
      strict: false,
      removeAdditional: removeMode,
      useDefaults: true
    }).compile(schema);
  }

  return cache[schemaKey];
}

/**
 * Check if a JSON schema exists for the given entity type.
 */
export function hasSchema(entityType) {
  const schemaKey = resolveSchemaKey(entityType);
  return !!EntitySchemas[schemaKey];
}

/**
 * Validate entity data against its JSON schema, stripping extra properties.
 * Returns a cleaned deep clone of the data.
 * If no schema exists for the entity type, returns a plain deep clone.
 *
 * @param {string} entityType - Entity type name
 * @param {object} data - Entity data to validate
 * @param {'all'|true} removeMode - 'all' for audit data (aggressive), true for change data (preserves Payload)
 */
export function validateEntity(entityType, data, removeMode = 'all') {
  if (!data) return data;

  const clone = JSON.parse(JSON.stringify(data));
  const validator = getValidator(entityType, removeMode);

  if (validator) {
    validator(clone);
  }

  return clone;
}
