//@ts-nocheck
import { apiCall } from '$lib/util.js';
import { ARMOR_SET_OFFSET } from '$lib/common/itemTypes.js';

// Match market cache refresh cadence for item catalog data.
const ITEMS_REFRESH_MS = 15 * 60 * 1000; // 15m
const ARMOR_SET_MAX_ID = ARMOR_SET_OFFSET + 999999;

let itemTypeCache = {
  expiresAt: 0,
  itemsById: new Map(),
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
  for (const item of items) {
    const itemId = toNumberId(item?.ItemId ?? item?.Id);
    if (!itemId) continue;
    itemsById.set(itemId, item);
    if (item?.Name) itemIdByName.set(item.Name, itemId);
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

