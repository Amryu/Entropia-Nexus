//@ts-nocheck
import { apiCall } from '$lib/util.js';
import { ARMOR_SET_OFFSET, STRONGBOX_OFFSET } from '$lib/common/itemTypes.js';

// Match market cache refresh cadence for item catalog data.
const ITEMS_REFRESH_MS = 15 * 60 * 1000; // 15m
const ARMOR_SET_MAX_ID = ARMOR_SET_OFFSET + 999999;
const STRONGBOX_MAX_ID = STRONGBOX_OFFSET + 999999;

let itemTypeCache = {
  expiresAt: 0,
  itemsById: new Map(),
  itemIdByName: new Map(),
  itemIdByNameLower: new Map(),
  materialSubTypeByItemId: new Map()
};
let refreshPromise = null;

function toNumberId(value) {
  if (value == null) return null;
  const n = Number(value);
  return Number.isInteger(n) && n > 0 ? n : null;
}

async function rebuildCache(fetch) {
  const [items, materials] = await Promise.all([
    apiCall(fetch, '/items'),
    apiCall(fetch, '/materials')
  ]);

  if (!Array.isArray(items) || items.length === 0) {
    return null;
  }

  const itemsById = new Map();
  const itemIdByName = new Map();
  const itemIdByNameLower = new Map();
  for (const item of items) {
    const itemId = toNumberId(item?.ItemId ?? item?.Id);
    if (!itemId) continue;
    itemsById.set(itemId, item);
    if (item?.Name) {
      itemIdByName.set(item.Name, itemId);
      itemIdByNameLower.set(item.Name.toLowerCase(), itemId);
    }
  }

  const materialSubTypeByItemId = new Map();
  if (Array.isArray(materials)) {
    for (const material of materials) {
      const itemId =
        toNumberId(material?.ItemId ?? material?.Id) ||
        (material?.Name ? itemIdByName.get(material.Name) || null : null);
      if (!itemId) continue;

      const subType = material?.Properties?.Type ?? material?.Type ?? null;
      materialSubTypeByItemId.set(itemId, subType);
    }
  }

  itemTypeCache = {
    expiresAt: Date.now() + ITEMS_REFRESH_MS,
    itemsById,
    itemIdByName,
    itemIdByNameLower,
    materialSubTypeByItemId
  };
  return itemTypeCache;
}

async function getCachedItemTypeData(fetch) {
  if (itemTypeCache.itemsById.size > 0 && Date.now() < itemTypeCache.expiresAt) {
    return itemTypeCache;
  }

  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = rebuildCache(fetch)
    .catch(() => null)
    .finally(() => {
      refreshPromise = null;
    });

  const rebuilt = await refreshPromise;
  return rebuilt || itemTypeCache;
}

export async function resolveItemTypesByItemId(itemIds, fetch) {
  const map = {};
  if (!Array.isArray(itemIds) || itemIds.length === 0) return map;

  const unresolved = [];
  for (const itemId of itemIds) {
    if (itemId >= ARMOR_SET_OFFSET && itemId <= ARMOR_SET_MAX_ID) {
      map[itemId] = { type: 'ArmorSet', subType: null };
    } else if (itemId >= STRONGBOX_OFFSET && itemId <= STRONGBOX_MAX_ID) {
      map[itemId] = { type: 'Strongbox', subType: null };
    } else {
      unresolved.push(itemId);
    }
  }

  if (unresolved.length === 0 || !fetch) return map;

  const cache = await getCachedItemTypeData(fetch);
  for (const itemId of unresolved) {
    const item = cache.itemsById.get(itemId);
    const type = item?.Properties?.Type ?? item?.Type ?? null;
    if (!type) continue;

    map[itemId] = {
      type,
      subType: type === 'Material'
        ? (cache.materialSubTypeByItemId.get(itemId) ?? null)
        : null
    };
  }

  return map;
}

/**
 * Resolve item data by item ID, returning type info plus the raw item object
 * for TT value computation.
 * @returns {{ [itemId: number]: { type: string, subType: string|null, item: object|null } }}
 */
export async function resolveItemDataByItemId(itemIds, fetch) {
  const map = {};
  if (!Array.isArray(itemIds) || itemIds.length === 0) return map;

  const unresolved = [];
  for (const itemId of itemIds) {
    if (itemId >= ARMOR_SET_OFFSET && itemId <= ARMOR_SET_MAX_ID) {
      map[itemId] = { type: 'ArmorSet', subType: null, item: null };
    } else if (itemId >= STRONGBOX_OFFSET && itemId <= STRONGBOX_MAX_ID) {
      map[itemId] = { type: 'Strongbox', subType: null, item: null };
    } else {
      unresolved.push(itemId);
    }
  }

  if (unresolved.length === 0 || !fetch) return map;

  const cache = await getCachedItemTypeData(fetch);
  for (const itemId of unresolved) {
    const item = cache.itemsById.get(itemId);
    const type = item?.Properties?.Type ?? item?.Type ?? null;
    if (!type) continue;

    map[itemId] = {
      type,
      subType: type === 'Material'
        ? (cache.materialSubTypeByItemId.get(itemId) ?? null)
        : null,
      item: item || null
    };
  }

  return map;
}

/**
 * Resolve an item name to its item ID using the cached /items data.
 * Tries exact match first, then case-insensitive fallback.
 * @param {string} name
 * @param {Function} fetch
 * @returns {Promise<number|null>}
 */
export async function resolveItemIdByName(name, fetch) {
  if (!name || !fetch) return null;
  const cache = await getCachedItemTypeData(fetch);
  const exact = cache.itemIdByName?.get(name);
  if (exact) return exact;
  const lower = cache.itemIdByNameLower?.get(name.toLowerCase());
  return lower || null;
}

/**
 * Resolve an item ID by prefix match (for truncated OCR names).
 * Returns { itemId, resolvedName } or null if no unique match.
 * Only returns a result if exactly one item matches the prefix.
 * @param {string} prefix - The truncated name to match
 * @param {Function} fetch - SvelteKit fetch
 * @returns {Promise<{ itemId: number, resolvedName: string } | null>}
 */
export async function resolveItemByPrefix(prefix, fetch) {
  if (!prefix || prefix.length < 4 || !fetch) return null;
  const cache = await getCachedItemTypeData(fetch);
  const lowerPrefix = prefix.toLowerCase();
  const matches = [];
  for (const [nameLower, itemId] of cache.itemIdByNameLower) {
    if (nameLower.startsWith(lowerPrefix)) {
      const item = cache.itemsById.get(itemId);
      matches.push({ itemId, resolvedName: item?.Name ?? nameLower });
      if (matches.length > 1) return null; // Ambiguous — skip
    }
  }
  return matches.length === 1 ? matches[0] : null;
}

