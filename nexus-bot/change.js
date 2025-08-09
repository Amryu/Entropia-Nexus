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
    x => x?.Material?.Name,
    // For mob spawns - match by Shape, Data and Altitude
    x => x?.Properties?.Shape && x?.Properties?.Data && x?.Properties?.Coordinates?.Altitude !== undefined 
      ? `${x.Properties.Shape}_${JSON.stringify(x.Properties.Data)}_${x.Properties.Coordinates.Altitude}` 
      : null];
  const objectIdentifiers = ['Name', 'Tier'];

  let keys = new Set([...Object.keys(newJson), ...Object.keys(oldJson)]);

  for (const key of keys) {
    if (Array.isArray(oldJson[key]) && Array.isArray(newJson[key])) {
      console.log(`Comparing array field: ${key}, oldLength: ${oldJson[key].length}, newLength: ${newJson[key].length}`);
      
      // Create a copy of oldJson[key] to avoid modifying during iteration
      const oldItems = [...oldJson[key]];
      
      for (let i = 0; i < newJson[key].length; i++) {
        let match;

        // Find matching item in old array - prioritize ID matching over position
        for (let j = 0; j < oldItems.length; j++) {
          // First, try to match by identifier
          const hasMatchingId = arrayIdentifiers.some(x => x(newJson[key][i]) != null && x(newJson[key][i]) === x(oldItems[j]));
          
          if (hasMatchingId) {
            // Found exact match by identifier
            let subResult = compareJson(oldItems[j], newJson[key][i]);
            oldItems.splice(j, 1);
            match = subResult;
            break;
          }
        }
        
        // If no ID match found, try position-based matching as fallback
        if (match === undefined) {
          for (let j = 0; j < oldItems.length; j++) {
            let subResult = compareJson(oldItems[j], newJson[key][i]);
            
            if (!subResult) {
              // Items are identical, treat as match
              oldItems.splice(j, 1);
              match = subResult;
              break;
            }
          }
        }

        if (match === undefined) {
          match = compareJson(null, newJson[key][i]);
          if (key === 'Spawns') {
            console.log(`No match found for spawn ${i}, treating as new`);
          }
        }
        
        if (match) {
          anyChanges = true;
          result[key] = result[key] || [];
          result[key].push(match);
        }
      }

      // Check for any remaining items in oldItems that were not matched
      for (let i = 0; i < oldItems.length; i++) {
        let match = compareJson(oldItems[i], null);
      
        if (match) {
          anyChanges = true;
          result[key] = result[key] || [];
          result[key].push(match);
          if (key === 'Spawns') {
            console.log(`Remaining old spawn ${i} marked as removed`);
          }
        }
      }

      if (Array.isArray(result[key])) {
        result[key] = result[key].filter(x => x != null);
        if (key === 'Spawns') {
          console.log(`Final spawns result length: ${result[key].length}`);
        }
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

      // Special formatting for Data fields to save space
      let oldValue = oldJson[key];
      let newValue = newJson[key];
      
      if (key === 'Data') {
        oldValue = oldValue != null ? formatDataValue(oldValue) : oldValue;
        newValue = newValue != null ? formatDataValue(newValue) : newValue;
      }

      if (Array.isArray(result)) {
        result.push(`${oldValue ?? '<empty>'} -> ${newValue ?? '<empty>'}`);
      } else {
        result[key] = `${oldValue ?? '<empty>'} -> ${newValue ?? '<empty>'}`;
      }
    }
  }

  return anyChanges && Object.keys(result).length > 0 ? result : null;
}