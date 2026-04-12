import Ajv from "ajv";
import { EffectsOnEquip, EffectsOnSetEquip, EffectsOnUse, NamedEntity, Tiers } from "./common/schemas/SharedSchemas.js";
import { EntitySchemas } from "./common/EntitySchemas.js";

const Validators = {};

let shared = [EffectsOnEquip, EffectsOnSetEquip, EffectsOnUse, NamedEntity, Tiers];
const ENTITY_TYPE_MAP = {
  TeleportChip: 'TeleportationChip',
  CreatureControlCapsule: 'Capsule',
  Area: 'Location'
};

function resolveSchemaType(type) {
  return ENTITY_TYPE_MAP[type] || type;
}

function getValidator(type) {
  const schemaType = resolveSchemaType(type);

  if (!Validators[schemaType]) {
    const schema = EntitySchemas[schemaType];
    if (!schema) {
      console.error(`No schema found for entity type "${type}" (resolved as "${schemaType}")`);
      return null;
    }

    Validators[schemaType] = new Ajv({ schemas: shared, strict: false, removeAdditional: 'all', allErrors: true }).compile(schema);
  }

  return Validators[schemaType];
}

export function validate(type, data) {
  let validator = getValidator(type);
  if (!validator) {
    return false;
  }

  let success = validator(data);

  if (!success) {
    console.log(`Validation failed for ${type}:`, validator.errors);
  }

  removeEmpty(data);

  return success;
}

function removeEmpty(obj) {
  for (let key in obj) {
    if (obj[key] && typeof obj[key] === 'object') {
      removeEmpty(obj[key]);
      if (Object.keys(obj[key]).length === 0 && obj[key].constructor === Object || Array.isArray(obj[key]) && obj[key].length === 0) {
        delete obj[key];
      }
    }
  }
}

function formatDataValue(value, maxLength = 30) {
  let str;
  if (typeof value === 'string') {
    str = value;
  } else {
    str = JSON.stringify(value);
  }

  if (str.length > maxLength) {
    return str.substring(0, maxLength - 3) + '...';
  }
  return str;
}

function printTreeView(obj, indent = 0, maxListItems = 3) {
  const spaces = '  '.repeat(indent);
  let result = [];

  if (obj === null) return ['null'];
  if (obj === undefined) return ['undefined'];
  if (typeof obj !== 'object') return [String(obj)];

  if (Array.isArray(obj)) {
    result.push(`[${obj.length} items]`);
    for (let i = 0; i < Math.min(obj.length, maxListItems); i++) {
      const itemLines = printTreeView(obj[i], indent + 1, maxListItems);
      result.push(`${spaces}  [${i}] ${itemLines[0]}`);
      for (let j = 1; j < itemLines.length; j++) {
        result.push(`${spaces}      ${itemLines[j]}`);
      }
    }
    if (obj.length > maxListItems) {
      result.push(`${spaces}  ... ${obj.length - maxListItems} more items`);
    }
  } else {
    result.push('{');
    const keys = Object.keys(obj).sort(); // Sort keys alphabetically
    for (const key of keys) {
      const valueLines = printTreeView(obj[key], indent + 1, maxListItems);
      result.push(`${spaces}  ${key}: ${valueLines[0]}`);
      for (let j = 1; j < valueLines.length; j++) {
        result.push(`${spaces}      ${valueLines[j]}`);
      }
    }
    result.push(`${spaces}}`);
  }

  return result;
}

export function printSideBySide(oldObj, newObj, title = 'Comparison') {
  const oldLines = printTreeView(oldObj);
  const newLines = printTreeView(newObj);
  const maxLines = Math.max(oldLines.length, newLines.length);
  const maxWidth = Math.max(...oldLines.map(line => line.length), 40);

  console.log(`\n=== ${title} ===`);
  console.log(`${'OLD'.padEnd(maxWidth)} | NEW`);
  console.log(`${'-'.repeat(maxWidth)} | ${'-'.repeat(maxWidth)}`);

  for (let i = 0; i < maxLines; i++) {
    const oldLine = (oldLines[i] || '').padEnd(maxWidth);
    const newLine = newLines[i] || '';
    console.log(`${oldLine} | ${newLine}`);
  }
  console.log('');
}

/**
 * Array item identifiers - functions to extract identifying values from array items.
 * Items are matched by these identifiers rather than by array position.
 * Mirrors the identifiers in nexus/src/lib/utils/compareJson.js
 */
const arrayIdentifiers = [
  x => x?.Name,
  // For nested arrays (e.g., Armors grouped by slot), check first/second element's Name
  x => Array.isArray(x) && x.length > 0 ? x[0]?.Name : null,
  x => Array.isArray(x) && x.length > 1 ? x[1]?.Name : null,
  x => x?.Properties?.Tier,
  x => x?.Material?.Name,
  // For mob spawns - match by Shape, Data and Altitude
  x => x?.Properties?.Shape && x?.Properties?.Data && x?.Properties?.Coordinates?.Altitude !== undefined
    ? `${x.Properties.Shape}_${JSON.stringify(x.Properties.Data)}_${x.Properties.Coordinates.Altitude}`
    : null,
  // For loots - match by Item.Name and Maturity.Name
  x => x?.Item?.Name && x?.Maturity?.Name ? `${x.Item.Name}_${x.Maturity.Name}` : null,
  // For loots without maturity
  x => x?.Item?.Name ? x.Item.Name : null,
  // For effects - match by Name
  x => x?.Effect?.Name,
  // For maturities - match by Name
  x => x?.Maturity?.Name,
];

/**
 * Context keys - preserved in output even when unchanged
 */
const contextKeys = ['Name', 'Tier'];

/**
 * Keys to ignore during comparison - API-only fields
 */
const ignoredKeys = ['Links', '$Url', 'ItemId'];

/**
 * Deep equality check, ignoring API-only fields.
 * For objects, only compares keys that exist in BOTH objects.
 * Uses identifier-based matching for arrays.
 */
function deepEqual(a, b) {
  if (a === b) return true;
  if (a == null && b == null) return true;
  if (a == null || b == null) return false;
  if (typeof a !== typeof b) return false;

  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) return false;

    const bItems = [...b];
    for (const aItem of a) {
      let matchIndex = -1;
      for (const identifier of arrayIdentifiers) {
        const aId = identifier(aItem);
        if (aId != null) {
          for (let j = 0; j < bItems.length; j++) {
            if (identifier(bItems[j]) === aId) {
              matchIndex = j;
              break;
            }
          }
          if (matchIndex >= 0) break;
        }
      }

      if (matchIndex < 0) {
        for (let j = 0; j < bItems.length; j++) {
          if (deepEqual(aItem, bItems[j])) {
            matchIndex = j;
            break;
          }
        }
      }

      if (matchIndex < 0) return false;
      if (!deepEqual(aItem, bItems[matchIndex])) return false;
      bItems.splice(matchIndex, 1);
    }
    return true;
  }

  if (typeof a === 'object') {
    const keysA = Object.keys(a).filter(k => !ignoredKeys.includes(k));
    const keysB = Object.keys(b).filter(k => !ignoredKeys.includes(k));
    const sharedKeys = keysA.filter(k => keysB.includes(k));

    if (sharedKeys.length === 0) return true;

    for (const key of sharedKeys) {
      if (!deepEqual(a[key], b[key])) return false;
    }
    return true;
  }

  return false;
}

/**
 * Extract a human-readable identifier from an array item using arrayIdentifiers.
 * Used to keep diff output identifiable even when the matched fields are
 * unchanged (and would otherwise be stripped from the result).
 */
function extractIdentifier(item) {
  if (item == null) return null;
  for (const fn of arrayIdentifiers) {
    const id = fn(item);
    if (id != null) return id;
  }
  return null;
}

/**
 * Find a matching item in an array using identifiers
 */
function findMatchByIdentifier(item, candidates) {
  for (const identifier of arrayIdentifiers) {
    const itemId = identifier(item);
    if (itemId != null) {
      for (let i = 0; i < candidates.length; i++) {
        if (identifier(candidates[i]) === itemId) {
          return i;
        }
      }
    }
  }
  return -1;
}

/**
 * Find an identical item in an array using deep equality
 */
function findIdenticalItem(item, candidates) {
  for (let i = 0; i < candidates.length; i++) {
    if (deepEqual(item, candidates[i])) {
      return i;
    }
  }
  return -1;
}

/**
 * Compare two JSON structures and return a diff result.
 * Uses the same logic as nexus/src/lib/utils/compareJson.js
 * but with string output format for Discord readability.
 */
export function compareJson(oldJson, newJson) {
  let anyChanges = false;

  oldJson = oldJson ?? (Array.isArray(newJson) ? [] : {});
  newJson = newJson ?? (Array.isArray(oldJson) ? [] : {});

  let result = Array.isArray(oldJson) || Array.isArray(newJson) ? [] : {};

  const keys = new Set([...Object.keys(newJson), ...Object.keys(oldJson)]);

  for (const key of keys) {
    // Skip ignored keys
    if (ignoredKeys.includes(key)) continue;

    const oldValue = oldJson[key];
    const newValue = newJson[key];

    // Both are arrays - use smart matching
    if (Array.isArray(oldValue) && Array.isArray(newValue)) {
      const oldItems = [...oldValue];
      const arrayResult = [];

      for (let i = 0; i < newValue.length; i++) {
        let match;
        let matchIndex = -1;

        // Try to find by identifier first
        matchIndex = findMatchByIdentifier(newValue[i], oldItems);

        if (matchIndex >= 0) {
          match = compareJson(oldItems[matchIndex], newValue[i]);
          oldItems.splice(matchIndex, 1);
        } else {
          // Try to find identical item
          matchIndex = findIdenticalItem(newValue[i], oldItems);

          if (matchIndex >= 0) {
            oldItems.splice(matchIndex, 1);
            match = null;
          } else {
            // No match found - this is a new item
            match = compareJson(null, newValue[i]);
          }
        }

        if (match) {
          anyChanges = true;
          const identifier = extractIdentifier(newValue[i]);
          const entry = { ...match, _status: matchIndex >= 0 ? 'changed' : 'added' };
          if (identifier != null) entry._identifier = identifier;
          arrayResult.push(entry);
        }
      }

      // Remaining old items were removed
      for (const oldItem of oldItems) {
        const removedDiff = compareJson(oldItem, null);
        if (removedDiff) {
          anyChanges = true;
          const identifier = extractIdentifier(oldItem);
          const entry = { ...removedDiff, _status: 'removed' };
          if (identifier != null) entry._identifier = identifier;
          arrayResult.push(entry);
        }
      }

      if (arrayResult.length > 0) {
        result[key] = arrayResult;
      }
    }
    // One or both are objects (but not arrays)
    else if (
      (typeof newValue === 'object' && newValue !== null) ||
      (typeof oldValue === 'object' && oldValue !== null)
    ) {
      const subResult = compareJson(oldValue, newValue);

      if (subResult) {
        anyChanges = true;

        if (Array.isArray(result)) {
          result.push(subResult);
        } else {
          result[key] = subResult;
        }
      }
    }
    // Primitive values
    else {
      if (oldValue === newValue || (oldValue == null && newValue == null)) {
        if (!Array.isArray(result) && contextKeys.includes(key)) {
          result[key] = newValue;
        }
        continue;
      }

      anyChanges = true;

      let oldStr = oldValue;
      let newStr = newValue;

      // Special formatting for Data fields to save space
      if (key === 'Data') {
        oldStr = oldStr != null ? formatDataValue(oldStr) : oldStr;
        newStr = newStr != null ? formatDataValue(newStr) : newStr;
      }

      if (Array.isArray(result)) {
        result.push(`${oldStr ?? '<empty>'} -> ${newStr ?? '<empty>'}`);
      } else {
        result[key] = `${oldStr ?? '<empty>'} -> ${newStr ?? '<empty>'}`;
      }
    }
  }

  return anyChanges && Object.keys(result).length > 0 ? result : null;
}
