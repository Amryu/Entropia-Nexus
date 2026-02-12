import { CONDITION_TYPES, ABSOLUTE_MARKUP_MATERIAL_TYPES } from '$lib/common/itemTypes.js';

// Utility to decide which items use absolute markup (non-stackable display)
/**
 * @param {any} item
 */
export function isNonStackable(item) {
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

// Build display text for stacks and markup
/**
 * @param {any} entry
 * @param {any} item
 */
export function buildStackMuDisplay(entry, item) {
  const stack = Number(entry.StackSize ?? entry.stack_size ?? 0);
  const mu = Number(entry.Markup ?? entry.markup ?? 0);
  const stackText = stack > 0 ? `stacks: ${stack}` : '';
  let muText = '';
  if (!Number.isNaN(mu) && mu > 0) {
    muText = isNonStackable(item) ? `+${mu}` : `${mu.toFixed(0)}%`;
  }
  return { stackText, muText };
}
