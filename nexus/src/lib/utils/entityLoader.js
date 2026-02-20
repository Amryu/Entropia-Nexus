// @ts-nocheck
/**
 * Entity Loader - Lazy loading utility for game entities
 *
 * Provides client-side caching and parallel loading of entity data
 * to reduce initial page load time.
 */

import { browser } from '$app/environment';
import { writable, get } from 'svelte/store';

// Cache for loaded entities (persists for session)
const entityCache = new Map();

// Loading state stores
const loadingStates = writable({});

// API base URL
function getApiBase() {
  return browser
    ? (import.meta.env.VITE_API_URL || "https://api.entropianexus.com")
    : (process.env.INTERNAL_API_URL || "http://api:3000");
}

// Entity endpoint mappings
const ENTITY_ENDPOINTS = {
  clothings: '/clothings',
  medicalTools: '/medicaltools',
  medicalChips: '/medicalchips',
  armorSets: '/armorsets',
  consumables: '/stimulants',
  weapons: '/weapons',
  pets: '/pets',
  armors: '/armors',
  armorPlatings: '/armorplatings',
  weaponAmplifiers: '/weaponamplifiers',
  absorbers: '/absorbers',
  weaponVisionAttachments: '/weaponvisionattachments',
  mindforceImplants: '/mindforceimplants',
  planets: '/planets',
  enhancers: '/enhancers'
};

/**
 * Load a single entity type
 * @param {string} entityType - The type of entity to load
 * @returns {Promise<any[]>} - The loaded entity data
 */
export async function loadEntity(entityType) {
  // Return from cache if available
  if (entityCache.has(entityType)) {
    return entityCache.get(entityType);
  }

  const endpoint = ENTITY_ENDPOINTS[entityType];
  if (!endpoint) {
    console.warn(`Unknown entity type: ${entityType}`);
    return [];
  }

  // Update loading state
  loadingStates.update(states => ({ ...states, [entityType]: true }));

  try {
    const response = await fetch(getApiBase() + endpoint);
    if (!response.ok) {
      console.error(`Failed to load ${entityType}: ${response.status}`);
      return [];
    }
    const data = await response.json();

    // Cache the result
    entityCache.set(entityType, data || []);

    return data || [];
  } catch (error) {
    console.error(`Error loading ${entityType}:`, error);
    return [];
  } finally {
    loadingStates.update(states => ({ ...states, [entityType]: false }));
  }
}

/**
 * Load multiple entity types in parallel
 * @param {string[]} entityTypes - Array of entity types to load
 * @returns {Promise<Object>} - Object with entity types as keys and data as values
 */
export async function loadEntities(entityTypes) {
  const results = {};

  // Filter out already cached entities
  const toLoad = entityTypes.filter(type => !entityCache.has(type));
  const fromCache = entityTypes.filter(type => entityCache.has(type));

  // Get cached results immediately
  for (const type of fromCache) {
    results[type] = entityCache.get(type);
  }

  // Load uncached entities in parallel
  if (toLoad.length > 0) {
    const promises = toLoad.map(async (type) => {
      const data = await loadEntity(type);
      return { type, data };
    });

    const loaded = await Promise.all(promises);
    for (const { type, data } of loaded) {
      results[type] = data;
    }
  }

  return results;
}

/**
 * Check if an entity type is currently loading
 * @param {string} entityType - The entity type to check
 * @returns {boolean}
 */
export function isLoading(entityType) {
  return get(loadingStates)[entityType] || false;
}

/**
 * Get the loading states store
 * @returns {import('svelte/store').Writable}
 */
export function getLoadingStates() {
  return loadingStates;
}

/**
 * Check if any entities are loading
 * @param {string[]} entityTypes - Entity types to check
 * @returns {boolean}
 */
export function isAnyLoading(entityTypes) {
  const states = get(loadingStates);
  return entityTypes.some(type => states[type]);
}

/**
 * Clear the entity cache (useful for testing or forced refresh)
 * @param {string} [entityType] - Specific type to clear, or all if not specified
 */
export function clearCache(entityType) {
  if (entityType) {
    entityCache.delete(entityType);
  } else {
    entityCache.clear();
  }
}

/**
 * Preload commonly used entities for service pages
 * This can be called early to start loading in background
 */
export function preloadServiceEntities() {
  // Load common entities used across service types
  const commonEntities = [
    'clothings',
    'consumables',
    'armorSets',
    'pets'
  ];

  // Start loading but don't await
  loadEntities(commonEntities);
}

/**
 * Load entities required for a specific service type
 * @param {string} serviceType - 'healing', 'dps', 'transportation', or 'custom'
 * @returns {Promise<Object>}
 */
export async function loadServiceTypeEntities(serviceType) {
  let entityTypes = ['clothings', 'consumables', 'armorSets', 'pets'];

  switch (serviceType) {
    case 'healing':
      entityTypes = [...entityTypes, 'medicalTools', 'medicalChips'];
      break;
    case 'dps':
      entityTypes = [
        ...entityTypes,
        'weapons',
        'armors',
        'armorPlatings',
        'weaponAmplifiers',
        'absorbers',
        'weaponVisionAttachments',
        'mindforceImplants'
      ];
      break;
    case 'transportation':
      entityTypes = [...entityTypes, 'planets'];
      break;
    case 'custom':
      // Custom services may need various equipment
      entityTypes = [
        ...entityTypes,
        'weapons',
        'medicalTools',
        'medicalChips',
        'armors',
        'armorPlatings'
      ];
      break;
  }

  return loadEntities(entityTypes);
}

/**
 * Load all entities needed for the services list page
 * @returns {Promise<Object>}
 */
export async function loadAllServiceEntities() {
  return loadEntities([
    'clothings',
    'medicalTools',
    'medicalChips',
    'armorSets',
    'consumables',
    'weapons',
    'pets',
    'armors',
    'armorPlatings',
    'weaponAmplifiers',
    'absorbers',
    'weaponVisionAttachments',
    'mindforceImplants'
  ]);
}

/**
 * Load all entities needed for the loadout calculator
 * @returns {Promise<Object>}
 */
export async function loadLoadoutEntities() {
  return loadEntities([
    'weapons',
    'weaponAmplifiers',
    'weaponVisionAttachments',
    'absorbers',
    'mindforceImplants',
    'armorSets',
    'armors',
    'armorPlatings',
    'enhancers',
    'pets',
    'clothings',
    'consumables',
    'medicalTools'
  ]);
}
