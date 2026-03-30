import { CONDITION_TYPES, ABSOLUTE_MARKUP_MATERIAL_TYPES } from '$lib/common/itemTypes.js';

// Utility to decide which items use absolute markup (non-stackable display)
/**
 * @param {any} item
 */
function isNonStackable(item) {
  const t = item?.Properties?.Type || item?.Type || item?.type || item?.t || '';
  // Items with condition/TT that can be damaged
  if (CONDITION_TYPES.has(t)) return true;
  // Deed/Token materials use absolute markup despite being stackable
  if (ABSOLUTE_MARKUP_MATERIAL_TYPES.has(t)) return true;
  return false;
}

// New alias for future condition-based logic. Keep current behavior identical.
/**
 * @param {any} item
 */
export function hasCondition(item) {
  return isNonStackable(item);
}

