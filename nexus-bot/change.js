import Ajv from "ajv";
import { EffectsOnEquip, EffectsOnSetEquip, EffectsOnUse, NamedEntity, Tiers } from "./common/schemas/SharedSchemas.js";
import { EntitySchemas } from "./common/EntitySchemas.js";

const Validators = {};

let shared = [EffectsOnEquip, EffectsOnSetEquip, EffectsOnUse, NamedEntity, Tiers];

function getValidator(type) {
  if (!Validators[type]) {
    Validators[type] = new Ajv({ schemas: shared, strict: false, removeAdditional: 'all', allErrors: true }).compile(EntitySchemas[type]);
  }

  return Validators[type];
}

export function validate(type, data) {
  let validator = getValidator(type);

  let success = validator(data);

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

export function compareJson(oldJson, newJson) {
  let anyChanges = false;

  oldJson ??= Array.isArray(newJson) ? [] : {};
  newJson ??= Array.isArray(oldJson) ? [] : {};

  let result = Array.isArray(oldJson) || Array.isArray(newJson) ? [] : {};

  const arrayIdentifiers = [
    x => x?.Name,
    x => Array.isArray(x) && x.length > 0 ? x[0]?.Name : null,
    x => Array.isArray(x) && x.length > 1 ? x[1]?.Name : null,
    x => x?.Properties?.Tier,
    x => x?.Material?.Name];
  const objectIdentifiers = ['Name', 'Tier'];

  let keys = new Set([...Object.keys(newJson), ...Object.keys(oldJson)]);

  for (const key of keys) {
    if (Array.isArray(oldJson[key]) && Array.isArray(newJson[key])) {
      for (let i = 0; i < Math.max(newJson[key].length, oldJson[key].length); i++) {
        let match;

        for (let j = 0; j < Math.max(newJson[key].length, oldJson[key].length); j++) {
          let subResult = compareJson(oldJson[key][j], newJson[key][i]);

          if (arrayIdentifiers.some(x => x(newJson[key][i]) != null && x(newJson[key][i]) === x(oldJson[key][j])) || !subResult) {
            oldJson[key].splice(j, 1);
            match = subResult;
            break;
          }
        }

        if (match === undefined) {
          match = compareJson(null, newJson[key][i]);
        }
        
        if (match) {
          anyChanges = true;
          result[key] = result[key] || [];
          result[key].push(match);
        }
      }

      // Check for any remaining items in oldJson that were not matched and removed
      for (let i = 0; i < oldJson[key].length; i++) {
        let match = compareJson(oldJson[key][i], null);
      
        if (match) {
          anyChanges = true;
          result[key] = result[key] || [];
          result[key].push(match);
        }
      }

      if (Array.isArray(result[key])) {
        result[key] = result[key].filter(x => x != null);
      }
    }
    else if ((typeof newJson[key] === 'object' && newJson[key] !== null) || (typeof oldJson[key] === 'object' && oldJson[key] !== null)) {
      let subResult = compareJson(oldJson[key], newJson[key]);

      if (subResult) {
        anyChanges = true;

        if (Array.isArray(result)) {
          result.push(subResult);
        } else {
          result[key] = subResult;
        }
      }
    }
    else {
      if (oldJson[key] === newJson[key] || (oldJson[key] == null && newJson[key] == null)) {
        if (!Array.isArray(result) && objectIdentifiers.includes(key)) {
          result[key] = newJson[key];
        }

        continue;
      }

      anyChanges = true;

      if (Array.isArray(result)) {
        result.push(`${oldJson[key] ?? '<empty>'} -> ${newJson[key] ?? '<empty>'}`);
      } else {
        result[key] = `${oldJson[key] ?? '<empty>'} -> ${newJson[key] ?? '<empty>'}`;
      }
    }
  }

  return anyChanges && Object.keys(result).length > 0 ? result : null;
}