// @ts-nocheck
/**
 * Shared helpers for the wiki contribution CTA components.
 *
 * `categoryLabel` maps the internal category key to a human phrase used
 * inside ContributeDialog bodies. Keep the phrasing neutral - the dialog
 * wraps it in sentences like "add this {label}".
 */

export const CONTRIBUTE_CATEGORIES = [
  'mob',
  'item',
  'weapon',
  'armor',
  'vendor',
  'shop',
  'profession',
  'skill',
  'mapping',
  'blueprint',
  'mission',
  'location',
  'refining',
  'effect',
  'general',
];

const LABELS = {
  mob: 'mob data',
  item: 'item data',
  weapon: 'weapon data',
  armor: 'armor data',
  vendor: 'vendor data',
  shop: 'shop data',
  profession: 'profession data',
  skill: 'skill data',
  mapping: 'location data',
  blueprint: 'blueprint data',
  mission: 'mission data',
  location: 'location data',
  refining: 'refining data',
  effect: 'effect data',
  general: 'wiki data',
};

export function categoryLabel(category) {
  return LABELS[category] || LABELS.general;
}

/**
 * Treats null / undefined / empty string / NaN as missing. Numbers (including
 * 0) and booleans (including false) are real data. Empty arrays and empty
 * plain objects are treated as missing since they convey no information.
 */
export function isMissing(value) {
  if (value === null || value === undefined) return true;
  if (typeof value === 'number') return Number.isNaN(value);
  if (typeof value === 'string') return value.trim() === '';
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === 'object') return Object.keys(value).length === 0;
  return false;
}
