/**
 * Shared test data for wiki E2E tests
 *
 * This file centralizes wiki page definitions to maintain consistency
 * across all test files and avoid duplication.
 */

/**
 * All main wiki pages (base paths without subtypes)
 * Use this when you want to test the root page behavior
 */
export const WIKI_PAGES = [
  { path: '/items/weapons', name: 'Weapons' },
  { path: '/items/blueprints', name: 'Blueprints' },
  { path: '/items/materials', name: 'Materials' },
  { path: '/items/armorsets', name: 'Armor Sets' },
  { path: '/items/clothing', name: 'Clothing' },
  { path: '/items/tools', name: 'Tools' },
  { path: '/items/attachments', name: 'Attachments' },
  { path: '/items/consumables', name: 'Consumables' },
  { path: '/items/medicaltools', name: 'Medical Tools' },
  { path: '/items/vehicles', name: 'Vehicles' },
  { path: '/items/pets', name: 'Pets' },
  { path: '/items/furnishings', name: 'Furnishings' },
  { path: '/items/strongboxes', name: 'Strongboxes' },
  { path: '/information/professions', name: 'Professions' },
  { path: '/information/skills', name: 'Skills' },
  { path: '/information/vendors', name: 'Vendors' },
  { path: '/information/mobs', name: 'Mobs' },
  { path: '/information/missions', name: 'Missions' },
  { path: '/market/shops', name: 'Shops' },
] as const;

/**
 * Wiki pages with specific subtypes for detailed testing
 * Use this when you need to test specific item types with actual data
 * Multi-type pages include ALL subtypes for comprehensive coverage
 */
export const WIKI_PAGES_WITH_SUBTYPES = [
  // Single-type pages
  { path: '/items/weapons', name: 'Weapons' },
  { path: '/items/blueprints', name: 'Blueprints' },
  { path: '/items/materials', name: 'Materials' },
  { path: '/items/armorsets', name: 'Armor Sets' },
  { path: '/items/clothing', name: 'Clothing' },
  { path: '/items/vehicles', name: 'Vehicles' },
  { path: '/items/pets', name: 'Pets' },
  { path: '/items/strongboxes', name: 'Strongboxes' },

  // Tools - All 7 subtypes
  { path: '/items/tools/refiners', name: 'Refiners' },
  { path: '/items/tools/scanners', name: 'Scanners' },
  { path: '/items/tools/finders', name: 'Finders' },
  { path: '/items/tools/excavators', name: 'Excavators' },
  { path: '/items/tools/teleportationchips', name: 'TP Chips' },
  { path: '/items/tools/effectchips', name: 'Effect Chips' },
  { path: '/items/tools/misctools', name: 'Misc. Tools' },

  // Attachments - All 7 subtypes (including enhancers which are NOT editable)
  { path: '/items/attachments/weaponamplifiers', name: 'Weapon Amplifiers', editable: true },
  { path: '/items/attachments/weaponvisionattachments', name: 'Scopes', editable: true },
  { path: '/items/attachments/absorbers', name: 'Absorbers', editable: true },
  { path: '/items/attachments/finderamplifiers', name: 'Finder Amplifiers', editable: true },
  { path: '/items/attachments/armorplatings', name: 'Armor Platings', editable: true },
  { path: '/items/attachments/enhancers', name: 'Enhancers', editable: false }, // Database-generated, NOT editable
  { path: '/items/attachments/mindforceimplants', name: 'Mindforce Implants', editable: true },

  // Consumables - All 2 subtypes
  { path: '/items/consumables/stimulants', name: 'Stimulants' },
  { path: '/items/consumables/capsules', name: 'Control Capsules' },

  // Medical Tools - All 2 subtypes
  { path: '/items/medicaltools/tools', name: 'Medical Tools' },
  { path: '/items/medicaltools/chips', name: 'Medical Chips' },

  // Furnishings - All 4 subtypes
  { path: '/items/furnishings/furniture', name: 'Furniture' },
  { path: '/items/furnishings/decorations', name: 'Decorations' },
  { path: '/items/furnishings/storagecontainers', name: 'Storage Containers' },
  { path: '/items/furnishings/signs', name: 'Signs' },

  // Information pages
  { path: '/information/professions', name: 'Professions' },
  { path: '/information/skills', name: 'Skills' },
  { path: '/information/vendors', name: 'Vendors' },
  { path: '/information/mobs', name: 'Mobs' },
  { path: '/information/missions', name: 'Missions' },

  // Market pages
  { path: '/market/shops', name: 'Shops' },
] as const;

/**
 * Pages that support item/entity effects
 * Use this for testing effect-related functionality
 */
export const EFFECT_PAGES = [
  { path: '/items/clothing', name: 'Clothing' },
  { path: '/items/consumables/stimulants', name: 'Consumables' },
  { path: '/items/attachments/amplifiers', name: 'Attachments' },
  { path: '/items/medicaltools/faps', name: 'Medical Tools' },
  { path: '/items/armorsets', name: 'Armor Sets' },
  { path: '/items/weapons', name: 'Weapons' },
  { path: '/items/tools/finders', name: 'Tools' },
] as const;

/**
 * Simple array of paths for tests that only need the path strings
 */
export const WIKI_PAGE_PATHS = WIKI_PAGES.map(p => p.path);
