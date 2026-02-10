/**
 * Shared item type classification constants and helpers.
 * Used by both client-side (orderUtils.ts) and server-side (exchange.js, trade-requests.js).
 */

/** Types that are always stackable (quantity > 1, percent markup) */
export const STACKABLE_TYPES = new Set([
  'Material',
  'Consumable',
  'Capsule',
  'Enhancer',
  'Strongbox',
]);

/** Types that have condition (can be damaged, have CurrentTT) */
export const CONDITION_TYPES = new Set([
  'Weapon', 'Armor', 'Vehicle',
  'WeaponAmplifier', 'WeaponVisionAttachment',
  'Finder', 'FinderAmplifier', 'Excavator', 'Refiner', 'Scanner',
  'TeleportationChip', 'EffectChip', 'MedicalChip',
  'MiscTool', 'MedicalTool', 'MindforceImplant', 'Pet',
]);

/** ID offset for pet items (Items.Id = Pets.Id + PET_ID_OFFSET) */
export const PET_ID_OFFSET = 11000000;

/** Types that support tiering (Tier + TiR) */
export const TIERABLE_TYPES = new Set([
  'Weapon',
  'Armor',
  'Finder',
  'Excavator',
  'MedicalTool',
]);

/**
 * Check if an item name has the (L) tag.
 * @param {string} name
 * @returns {boolean}
 */
export function isLimitedByName(name) {
  return /\(.*L.*\)/.test(name || '');
}

/**
 * Determine if an item type + name combination uses stackable behavior.
 * @param {string} type - Item type string
 * @param {string} name - Item name string
 * @returns {boolean}
 */
export function isStackableType(type, name) {
  if (STACKABLE_TYPES.has(type)) return true;
  if (type === 'Blueprint' && isLimitedByName(name)) return true;
  return false;
}

/**
 * Determine if an item type + name combination uses percent markup.
 * @param {string} type - Item type string
 * @param {string} name - Item name string
 * @returns {boolean}
 */
export function isPercentMarkupType(type, name) {
  if (isStackableType(type, name)) return true;
  // (L) items with condition use percent markup
  if (isLimitedByName(name) && CONDITION_TYPES.has(type)) return true;
  return false;
}
