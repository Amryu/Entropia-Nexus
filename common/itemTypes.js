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
  'Weapon', 'Armor', 'ArmorPlating', 'ArmorSet', 'Vehicle',
  'WeaponAmplifier', 'WeaponVisionAttachment',
  'Finder', 'FinderAmplifier', 'Excavator', 'Refiner', 'Scanner',
  'TeleportationChip', 'EffectChip', 'MedicalChip',
  'MiscTool', 'MedicalTool', 'MindforceImplant', 'Pet',
]);

/** ID offset for pet items (Items.Id = Pets.Id + PET_ID_OFFSET) */
export const PET_ID_OFFSET = 11000000;

/** ID offset for armor set items (ItemId = ArmorSets.Id + ARMOR_SET_OFFSET) */
export const ARMOR_SET_OFFSET = 13000000;

/**
 * Maps item type names to their global ID offsets in the Items table.
 * Items.Id = EntityTable.Id + offset
 */
export const TYPE_ID_OFFSETS = {
  Material:                1000000,
  Weapon:                  2000000,
  Armor:                   3000000,
  Tool:                    4000000,
  MedicalTool:             4100000,
  MiscTool:                4200000,
  Refiner:                 4300000,
  Scanner:                 4400000,
  Finder:                  4500000,
  Excavator:               4600000,
  BlueprintBook:           4700000,
  MedicalChip:             4800000,
  TeleportationChip:       4810000,
  EffectChip:              4820000,
  Attachment:              5000000,
  WeaponAmplifier:         5100000,
  WeaponVisionAttachment:  5200000,
  Absorber:                5300000,
  FinderAmplifier:         5400000,
  ArmorPlating:            5500000,
  Enhancer:                5600000,
  MindforceImplant:        5700000,
  Blueprint:               6000000,
  Vehicle:                 7000000,
  Clothing:                8000000,
  Furniture:               9100000,
  Decoration:              9200000,
  StorageContainer:        9300000,
  Sign:                    9400000,
  Consumable:              10000000,
  Capsule:                 10100000,
  Pet:                     11000000,
  Strongbox:               12000000,
  ArmorSet:                13000000,
};

/**
 * Convert a global Items.Id to the entity's own table ID.
 * @param {number} globalId - The ID from the Items table (with offset baked in)
 * @param {string} type - The item type (e.g., 'Weapon', 'Material')
 * @returns {number|null} The entity-specific ID, or null if type is unknown
 */
export function globalIdToEntityId(globalId, type) {
  const offset = TYPE_ID_OFFSETS[type];
  if (offset == null) return null;
  return globalId - offset;
}

/** Number of armor plates in a full set */
export const PLATE_SET_SIZE = 7;

/** Types that support tiering (Tier + TiR) */
export const TIERABLE_TYPES = new Set([
  'Weapon',
  'Armor',
  'ArmorSet',
  'Finder',
  'Excavator',
  'MedicalTool',
]);

/** Material sub-types (from Materials.Type) that use absolute markup despite being stackable */
export const ABSOLUTE_MARKUP_MATERIAL_TYPES = new Set(['Deed', 'Token', 'Share']);

/** Item types that require gender selection in exchange */
export const GENDERED_TYPES = new Set(['Armor', 'ArmorSet', 'Clothing']);

/** Valid gender values for exchange orders */
export const VALID_ORDER_GENDERS = new Set(['Male', 'Female']);

/** All valid item types in the database */
export const ALL_ITEM_TYPES = new Set([
  'Absorber',
  'Armor',
  'ArmorPlating',
  'ArmorSet',
  'Blueprint',
  'BlueprintBook',
  'Capsule',
  'Clothing',
  'Consumable',
  'Decoration',
  'EffectChip',
  'Enhancer',
  'Excavator',
  'Finder',
  'FinderAmplifier',
  'Furniture',
  'Material',
  'MedicalChip',
  'MedicalTool',
  'MindforceImplant',
  'MiscTool',
  'Pet',
  'Refiner',
  'Scanner',
  'Sign',
  'StorageContainer',
  'Strongbox',
  'TeleportationChip',
  'Vehicle',
  'Weapon',
  'WeaponAmplifier',
  'WeaponVisionAttachment',
]);

/** Item types allowed in rental item sets */
export const RENTAL_ALLOWED_ITEM_TYPES = new Set([
  // Weapons
  'Weapon',
  // Armor
  'Armor',
  'ArmorPlating',
  // Clothing
  'Clothing',
  // Vehicles
  'Vehicle',
  // Pets
  'Pet',
  // Blueprints (non-(L) only — checked separately)
  'Blueprint',
  // Attachments (not Enhancers)
  'Absorber',
  'WeaponAmplifier',
  'WeaponVisionAttachment',
  'FinderAmplifier',
  // Tools
  'Finder',
  'Excavator',
  'Refiner',
  'Scanner',
  'MiscTool',
  'TeleportationChip',
  // Medical Tools/Chips
  'MedicalTool',
  'MedicalChip',
  'EffectChip',
  'MindforceImplant',
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
 * @param {string|null} subType - Material sub-type (e.g., 'Deed', 'Token') for absolute markup override
 * @returns {boolean}
 */
export function isPercentMarkupType(type, name, subType = null) {
  if (isStackableType(type, name)) {
    // Deed/Token materials use absolute markup despite being stackable
    if (subType && ABSOLUTE_MARKUP_MATERIAL_TYPES.has(subType)) return false;
    return true;
  }
  // (L) items with condition use percent markup
  if (isLimitedByName(name) && CONDITION_TYPES.has(type)) return true;
  return false;
}
