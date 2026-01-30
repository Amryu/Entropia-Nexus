/**
 * JSON Comparison Utility
 *
 * Compares two JSON objects/arrays using smart matching logic.
 * For arrays, matches items by identifiers (Name, Tier, etc.) rather than position.
 *
 * This mirrors the logic in nexus-bot/change.js to ensure consistent behavior
 * between the Discord bot and the web frontend.
 */

/**
 * Array item identifiers - functions to extract identifying values from array items.
 * Items are matched by these identifiers rather than by array position.
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
 * Object identifiers - keys that should be preserved in output for context
 * even when their values haven't changed
 */
const contextKeys = ['Name', 'Tier'];

/**
 * Keys to ignore during comparison - these are API-only fields that
 * don't represent actual data differences
 */
const ignoredKeys = [
  'Links',      // API navigation links
  '$Url',       // API self-URL
  'ItemId',     // Internal item reference ID
];

/**
 * Check if two values are deeply equal, ignoring API-only fields.
 * For objects, only compares keys that exist in BOTH objects - extra keys
 * in either object are ignored (handles API having additional fields).
 * For arrays, uses identifier-based matching rather than position-based.
 */
function deepEqual(a, b) {
  if (a === b) return true;
  if (a == null && b == null) return true;
  if (a == null || b == null) return false;
  if (typeof a !== typeof b) return false;

  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) return false;

    // Use identifier-based matching for arrays (not position-based)
    const bItems = [...b];
    for (const aItem of a) {
      // Try to find matching item by identifier
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

      // If no identifier match, try to find an identical item
      if (matchIndex < 0) {
        for (let j = 0; j < bItems.length; j++) {
          if (deepEqual(aItem, bItems[j])) {
            matchIndex = j;
            break;
          }
        }
      }

      if (matchIndex < 0) {
        // No match found - arrays are different
        return false;
      }

      // Check if matched items are equal
      if (!deepEqual(aItem, bItems[matchIndex])) {
        return false;
      }

      // Remove matched item to avoid double-matching
      bItems.splice(matchIndex, 1);
    }
    return true;
  }

  if (typeof a === 'object') {
    // Get keys excluding ignored ones
    const keysA = Object.keys(a).filter(k => !ignoredKeys.includes(k));
    const keysB = Object.keys(b).filter(k => !ignoredKeys.includes(k));

    // Only compare keys that exist in both objects
    // Extra keys in either object are ignored (API may have additional fields)
    const sharedKeys = keysA.filter(k => keysB.includes(k));

    // If one object has no keys and the other does, check if they're both "empty-ish"
    // (this handles cases like {} vs {Id: 123} where Id is just metadata)
    if (sharedKeys.length === 0) {
      // Both have no shared keys - consider them equal if at least one has keys
      // (means the other only has ignored/extra keys)
      return true;
    }

    for (const key of sharedKeys) {
      if (!deepEqual(a[key], b[key])) return false;
    }
    return true;
  }

  return false;
}

/**
 * Find a matching item in an array using identifiers
 * @param {*} item - The item to find a match for
 * @param {Array} candidates - Array of candidate items
 * @returns {number} Index of matching item, or -1 if not found
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
 * Find an identical item in an array
 * @param {*} item - The item to find
 * @param {Array} candidates - Array of candidate items
 * @returns {number} Index of identical item, or -1 if not found
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
 * Compare two JSON structures and return a diff result
 *
 * @param {*} oldJson - The old/previous value
 * @param {*} newJson - The new/current value
 * @returns {Object|null} Diff object with changes, or null if identical
 */
export function compareJson(oldJson, newJson) {
  let anyChanges = false;

  // Handle null/undefined cases
  oldJson = oldJson ?? (Array.isArray(newJson) ? [] : {});
  newJson = newJson ?? (Array.isArray(oldJson) ? [] : {});

  // Determine result type based on inputs
  let result = Array.isArray(oldJson) || Array.isArray(newJson) ? [] : {};

  const keys = new Set([...Object.keys(newJson), ...Object.keys(oldJson)]);

  for (const key of keys) {
    const oldValue = oldJson[key];
    const newValue = newJson[key];

    // Both are arrays - use smart matching
    if (Array.isArray(oldValue) && Array.isArray(newValue)) {
      const oldItems = [...oldValue]; // Copy to avoid mutation
      const arrayResult = [];

      // Process each item in new array
      for (let i = 0; i < newValue.length; i++) {
        let match;
        let matchIndex = -1;

        // Try to find by identifier first
        matchIndex = findMatchByIdentifier(newValue[i], oldItems);

        if (matchIndex >= 0) {
          // Found match by identifier
          match = compareJson(oldItems[matchIndex], newValue[i]);
          oldItems.splice(matchIndex, 1);
        } else {
          // Try to find identical item
          matchIndex = findIdenticalItem(newValue[i], oldItems);

          if (matchIndex >= 0) {
            // Found identical item - no diff needed
            oldItems.splice(matchIndex, 1);
            match = null;
          } else {
            // No match found - this is a new item
            match = compareJson(null, newValue[i]);
          }
        }

        if (match) {
          anyChanges = true;
          arrayResult.push({ ...match, _status: matchIndex >= 0 ? 'changed' : 'added' });
        }
      }

      // Remaining old items were removed
      for (const oldItem of oldItems) {
        const removedDiff = compareJson(oldItem, null);
        if (removedDiff) {
          anyChanges = true;
          arrayResult.push({ ...removedDiff, _status: 'removed' });
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
      // Check for equality (treating null and undefined as equal)
      if (oldValue === newValue || (oldValue == null && newValue == null)) {
        // Keep context keys even if unchanged
        if (!Array.isArray(result) && contextKeys.includes(key)) {
          result[key] = newValue;
        }
        continue;
      }

      // Values differ
      anyChanges = true;

      const oldStr = oldValue ?? '<empty>';
      const newStr = newValue ?? '<empty>';

      if (Array.isArray(result)) {
        result.push({ _key: key, _old: oldStr, _new: newStr });
      } else {
        result[key] = { _old: oldStr, _new: newStr, _changed: true };
      }
    }
  }

  return anyChanges && Object.keys(result).length > 0 ? result : null;
}

/**
 * Match array items between old and new arrays, returning matched pairs.
 * Used for rendering side-by-side comparisons.
 *
 * @param {Array} oldArray - The old array
 * @param {Array} newArray - The new array
 * @returns {Array} Array of { old, new, status } pairs
 */
export function matchArrayItems(oldArray = [], newArray = []) {
  const oldItems = [...oldArray];
  const results = [];

  // Match new items to old items
  for (const newItem of newArray) {
    let matchIndex = findMatchByIdentifier(newItem, oldItems);

    if (matchIndex >= 0) {
      results.push({
        old: oldItems[matchIndex],
        new: newItem,
        status: deepEqual(oldItems[matchIndex], newItem) ? 'unchanged' : 'changed'
      });
      oldItems.splice(matchIndex, 1);
    } else {
      matchIndex = findIdenticalItem(newItem, oldItems);

      if (matchIndex >= 0) {
        results.push({
          old: oldItems[matchIndex],
          new: newItem,
          status: 'unchanged'
        });
        oldItems.splice(matchIndex, 1);
      } else {
        results.push({
          old: null,
          new: newItem,
          status: 'added'
        });
      }
    }
  }

  // Add remaining old items as removed
  for (const oldItem of oldItems) {
    results.push({
      old: oldItem,
      new: null,
      status: 'removed'
    });
  }

  return results;
}

/**
 * Check if a value has changed between old and new
 * @param {*} oldValue
 * @param {*} newValue
 * @returns {boolean}
 */
export function hasChanged(oldValue, newValue) {
  return !deepEqual(oldValue, newValue);
}

/**
 * Get an identifying name for an item (for display purposes)
 * @param {*} item
 * @returns {string|null}
 */
export function getItemIdentifier(item) {
  if (!item || typeof item !== 'object') return null;

  // Try common identifier patterns
  if (item.Name) return item.Name;
  if (item.Item?.Name) return item.Item.Name;
  if (item.Material?.Name) return item.Material.Name;
  if (item.Effect?.Name) return item.Effect.Name;
  if (item.Maturity?.Name) return item.Maturity.Name;
  if (item.Properties?.Tier != null) return `Tier ${item.Properties.Tier}`;

  return null;
}
