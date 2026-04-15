// @ts-nocheck
import { loading } from "../stores";
import { goto, invalidateAll } from "$app/navigation";
import { browser } from "$app/environment";
import { MAX_PENDING_CREATES } from "$lib/constants";
import { TYPE_ID_OFFSETS, isPercentMarkupType, PLATE_SET_SIZE } from "$lib/common/itemTypes.js";

export function removeItemTag(currentName, tag) {
  // Extract the base name and the existing tags
  const match = currentName.match(/^(.*) \((.*)\)$/);
  const baseName = match ? match[1] : currentName;
  let existingTags = match ? match[2].split(',') : [];

  // Remove the tag if it exists
  const index = existingTags.indexOf(tag);
  if (index !== -1) {
    existingTags.splice(index, 1);
  }

  // Add the tags to the base name
  const newName = existingTags.length > 0 ? `${baseName} (${existingTags.join(',')})` : baseName;

  return newName;
}

export function hasItemTag(currentName, tag) {
  if (!currentName) return false;

  // Extract the existing tags
  const match = currentName.match(/^(.*) \((.*)\)$/);
  const existingTags = match ? match[2].split(',') : [];

  // Check if the tag exists in the existing tags
  return existingTags.includes(tag);
}

/**
 * Copy text to clipboard with fallback for non-secure contexts.
 * @param {string} text - The text to copy
 * @returns {Promise<boolean>} - True if copy was successful
 */
export async function copyToClipboard(text) {
  // Guard against SSR - clipboard operations only work in browser
  if (!browser) {
    return false;
  }

  // Try modern clipboard API first
  if (navigator?.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (err) {
      // Fall through to fallback
    }
  }

  // Fallback for non-secure contexts or older browsers
  try {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    // Avoid scrolling to bottom
    textArea.style.top = '0';
    textArea.style.left = '0';
    textArea.style.position = 'fixed';
    textArea.style.opacity = '0';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    const successful = document.execCommand('copy');
    document.body.removeChild(textArea);
    return successful;
  } catch (err) {
    console.error('Failed to copy to clipboard:', err);
    return false;
  }
}

export function clampDecimals(num, minDecimals = 0, maxDecimals = 10) {
  if (num === null || num === undefined) {
    return num;
  }
  let str = num.toFixed(maxDecimals);  // Convert to string with maxDecimals decimal places
  str = str.replace(/0+$/, '');  // Remove trailing zeros
  if (str.indexOf('.') === str.length - 1) {
    str = str.slice(0, -1);  // Remove trailing decimal point
  }
  const actualDecimals = (str.split('.')[1] || '').length;
  if (actualDecimals < minDecimals) {
    return num.toFixed(minDecimals);  // Ensure minimum decimal places
  }
  return str;
}

async function getAcquisitionInfo(fetch, itemName) {
  if (!itemName || itemName.length === 0) {
    return {
      Blueprints: [],
      Loots: [],
      VendorOffers: [],
      RefiningRecipes: []
    };
  }

  if (Array.isArray(itemName)) {
    return await apiCall(fetch, `/acquisition?items=${itemName.map(x => encodeURIComponent(x)).join(',')}`);
  }

  return await apiCall(fetch, `/acquisition/${encodeURIComponent(itemName)}`);
}

async function getUsageInfo(fetch, itemName) {
  if (!itemName || itemName.length === 0) {
    return {
      Blueprints: [],
      VendorOffers: [],
      RefiningRecipes: []
    };
  }

  if (Array.isArray(itemName)) {
    return await apiCall(fetch, `/usage?items=${itemName.map(x => encodeURIComponent(x)).join(',')}`);
  }

  return await apiCall(fetch, `/usage/${encodeURIComponent(itemName)}`);
}

export function getMainPlanetName(planetName) {
  if (planetName === 'Asteroid F.O.M.A.' || planetName === 'Crystal Palace' || planetName === 'Space' || planetName === 'Setesh') {
    return 'Calypso';
  } else if (planetName === 'Arkadia Moon' || planetName === 'Arkadia Underground') {
    return 'Arkadia';
  } else if (planetName === 'HELL' || planetName === 'Secret Island' || planetName === 'Hunt The THING') {
    return 'ROCKtropia';
  } else if (planetName === 'Ancient Greece') {
    return 'Next Island';
  } else if (planetName === 'DSEC9') {
    return 'Monria';
  } else {
    return planetName;
  }
}

export function getItemLink(item, subtype = null) {
  if (!item) {
    return null;
  }

  if (item.Links?.$ItemUrl != null) {
    return item.Links.$ItemUrl;
  }

  if (typeof window === 'undefined') {
    return null;
  }

  const name = item.Name;
  const type = item.Properties?.Type;

  if (!name || !type) {
    return null;
  }

  return getTypeLink(name, type, subtype);
}

export function getTypeLink(name, type, subType = null, id = null) {
  switch (type) {
    case 'Weapon':
      return `/items/weapons/${encodeURIComponentSafe(name)}`;
    case 'Armor':
    case 'ArmorSet':
      return `/items/armorsets/${encodeURIComponentSafe(name)}`;
    case 'MedicalTool':
      return `/items/medicaltools/tools/${encodeURIComponentSafe(name)}`;
    case 'MedicalChip':
      return `/items/medicaltools/chips/${encodeURIComponentSafe(name)}`;
    case 'Refiner':
      return `/items/tools/refiners/${encodeURIComponentSafe(name)}`;
    case 'Scanner':
      return `/items/tools/scanners/${encodeURIComponentSafe(name)}`;
    case 'Finder':
      return `/items/tools/finders/${encodeURIComponentSafe(name)}`;
    case 'Excavator':
      return `/items/tools/excavators/${encodeURIComponentSafe(name)}`;
    case 'TeleportationChip':
      return `/items/tools/teleportationchips/${encodeURIComponentSafe(name)}`;
    case 'EffectChip':
      return `/items/tools/effectchips/${encodeURIComponentSafe(name)}`;
    case 'MiscTool':
      return `/items/tools/misctools/${encodeURIComponentSafe(name)}`;
    case 'Blueprint':
      return `/items/blueprints/${encodeURIComponentSafe(name)}`;
    case 'Material':
      return `/items/materials/${encodeURIComponentSafe(name)}`;
    case 'Vehicle':
      return `/items/vehicles/${encodeURIComponentSafe(name)}`;
    case 'Pet':
      return `/items/pets/${encodeURIComponentSafe(name)}`;
    case 'Consumable':
      return `/items/consumables/stimulants/${encodeURIComponentSafe(name)}`;
    case 'Capsule':
      return `/items/consumables/capsules/${encodeURIComponentSafe(name)}`;
    case 'Furniture':
      return `/items/furnishings/furniture/${encodeURIComponentSafe(name)}`;
    case 'Decoration':
      return `/items/furnishings/decorations/${encodeURIComponentSafe(name)}`;
    case 'StorageContainer':
      return `/items/furnishings/storagecontainers/${encodeURIComponentSafe(name)}`;
    case 'Sign':
      return `/items/furnishings/signs/${encodeURIComponentSafe(name)}`;
    case 'Clothing':
      return `/items/clothing/${encodeURIComponentSafe(name)}`;
    case 'WeaponAmplifier':
      return `/items/attachments/weaponamplifiers/${encodeURIComponentSafe(name)}`;
    case 'WeaponVisionAttachment':
      return `/items/attachments/weaponvisionattachments/${encodeURIComponentSafe(name)}`;
    case 'Absorber':
      return `/items/attachments/absorbers/${encodeURIComponentSafe(name)}`;
    case 'ArmorPlating':
      return `/items/attachments/armorplatings/${encodeURIComponentSafe(name)}`;
    case 'FinderAmplifier':
      return `/items/attachments/finderamplifiers/${encodeURIComponentSafe(name)}`;
    case 'Enhancer':
      return `/items/attachments/enhancers/${encodeURIComponentSafe(name)}`;
    case 'MindforceImplant':
      return `/items/attachments/mindforceimplants/${encodeURIComponentSafe(name)}`;
    case 'FishingRod':
      return `/items/tools/fishingrods/${encodeURIComponentSafe(name)}`;
    case 'FishingReel':
      return `/items/attachments/fishingreels/${encodeURIComponentSafe(name)}`;
    case 'FishingBlank':
      return `/items/attachments/fishingblanks/${encodeURIComponentSafe(name)}`;
    case 'FishingLine':
      return `/items/attachments/fishinglines/${encodeURIComponentSafe(name)}`;
    case 'FishingLure':
      return `/items/attachments/fishinglures/${encodeURIComponentSafe(name)}`;
    case 'Fish':
      // Fish items surface as Type='Fish' in the Items view; route to the
      // Information page, not an items page.
      return `/information/fishes/${encodeURIComponentSafe(name)}`;
    case 'Food':
      // Food is stored in Consumables with Type='Food'; still uses the
      // consumables stimulants route.
      return `/items/consumables/stimulants/${encodeURIComponentSafe(name)}`;
    case 'Mob':
      return `/information/mobs/${encodeURIComponentSafe(name)}`;
    case 'MobMaturity':
      return `/information/mobs/${encodeURIComponentSafe(name)}?view=maturities${id != null ? `&maturity=${id}` : ''}`;
    case 'Location':
    case 'Area': {
      const planet = getMainPlanetName(subType);
      if (!planet) return null;
      return `/maps/${planet.replace(/[^0-9a-zA-Z]/g, '').toLowerCase()}/${id != null ? id : encodeURIComponentSafe(name)}`;
    }
    case 'Map':
      return `/maps/${name.replace(/[^0-9a-zA-Z]/g, '').toLowerCase()}`;
    case 'Skill':
      return `/information/skills/${encodeURIComponentSafe(name)}`;
    case 'Profession':
      return `/information/professions/${encodeURIComponentSafe(name)}`;
      case 'Vendor':
        return `/information/vendors/${encodeURIComponentSafe(name)}`;
      case 'Mission':
        return `/information/missions/${encodeURIComponentSafe(name)}`;
      case 'MissionChain':
        return `/information/missions/${encodeURIComponentSafe(name)}?view=chains`;
      case 'User':
        return `/users/${encodeURIComponentSafe(name)}`;
      case 'Society':
        return `/societies/${encodeURIComponentSafe(name)}`;
      case 'Player':
      case 'Team':
        return `/globals/player/${encodeURIComponentSafe(name)}`;
      case 'Hunting':
      case 'Mining':
      case 'Crafting':
      case 'Rare Find':
      case 'Discovery':
      case 'Tier':
        return `/globals/target/${encodeURIComponentSafe(name)}`;
      default:
        return null;
    }
  }

export function getTypeName(type) {
  switch (type) {
    case 'Weapon':
      return 'Weapon';
    case 'Armor':
      return 'Armor';
    case 'ArmorSet':
      return 'Armor Set';
    case 'MedicalTool':
      return 'Medical Tool';
    case 'MedicalChip':
      return 'Medical Chip';
    case 'Refiner':
      return 'Refiner';
    case 'Scanner':
      return 'Scanner';
    case 'Finder':
      return 'Finder';
    case 'Excavator':
      return 'Excavator';
    case 'TeleportationChip':
      return 'Teleportation Chip';
    case 'EffectChip':
      return 'Effect Chip';
    case 'MiscTool':
      return 'Misc Tool';
    case 'Blueprint':
      return 'Blueprint';
    case 'BlueprintBook':
      return 'Blueprint Book';
    case 'Material':
      return 'Material';
    case 'Vehicle':
      return 'Vehicle';
    case 'Pet':
      return 'Pet';
    case 'Consumable':
      return 'Stimulant';
    case 'Capsule':
      return 'Capsule';
    case 'Furniture':
      return 'Furniture';
    case 'Decoration':
      return 'Decoration';
    case 'StorageContainer':
      return 'Storage Container';
    case 'Sign':
      return 'Sign';
    case 'Clothing':
      return 'Clothing';
    case 'WeaponAmplifier':
      return 'Weapon Amplifier';
    case 'WeaponVisionAttachment':
      return 'Sight/Scope';
    case 'Absorber':
      return 'Absorber';
    case 'ArmorPlating':
      return 'Armor Plating';
    case 'FinderAmplifier':
      return 'Finder Amplifier';
    case 'Enhancer':
      return 'Enhancer';
    case 'MindforceImplant':
      return 'Mindforce Implant';
    case 'Mob':
      return 'Mob';
    case 'MobMaturity':
      return 'Mob Maturity';
    case 'Location':
      return 'Location';
    case 'Area':
      return 'Area';
    case 'Skill':
      return 'Skill';
    case 'Profession':
      return 'Profession';
      case 'Vendor':
        return 'Vendor';
      case 'Mission':
        return 'Mission';
      case 'MissionChain':
        return 'Mission Chain';
      case 'Shop':
        return 'Shop';
      case 'User':
        return 'User';
      case 'Society':
        return 'Society';
      case 'Map':
        return 'Maps';
      case 'Player':
        return 'Player';
      case 'Team':
        return 'Team';
      case 'Hunting':
        return 'Hunting';
      case 'Mining':
        return 'Mining';
      case 'Crafting':
        return 'Crafting';
      case 'Rare Find':
        return 'Rare Find';
      case 'Discovery':
        return 'Discovery';
      case 'Tier':
        return 'Tier';
      case 'Target':
        return 'Target';
      default:
        return 'N/A';
  }
}

export function getTimeString(duration) {
  const days = Math.floor(duration / (24 * 60 * 60));
  const hours = Math.floor((duration % (24 * 60 * 60)) / (60 * 60));
  const minutes = Math.floor((duration % (60 * 60)) / 60);
  const seconds = duration % 60;

  let display = '';
  if (days > 0) display += `${days}d `;
  if (hours > 0) display += `${hours}h `;
  if (minutes > 0) display += `${minutes}min `;
  if (seconds > 0) display += `${seconds}s`

  return display;
}

export function groupBy(array, keyFunction) {
  return array.reduce((result, currentItem) => {
    (result[keyFunction(currentItem)] = result[keyFunction(currentItem)] || []).push(currentItem);
    return result;
  }, {});
}

export async function navigate(url) {
  loading.set(true);

  await goto(url);
  //await invalidateAll();

  loading.set(false);
}

export async function loadPendingChangesData(fetch, sessionUser, config) {
  const result = {
    pendingChange: null,
    userPendingCreates: [],
    userPendingUpdates: [],
    canCreateNew: true,
    pendingCreatesCount: 0
  };

  if (!sessionUser || !config.hasEditGrant) return result;

  const { entity, entityId, changeId, isAdmin } = config;
  const userId = sessionUser.id;

  // Helper to safely fetch a changes list endpoint
  async function fetchChanges(url) {
    try {
      const res = await fetch(url);
      return res.ok ? (await res.json()) || [] : [];
    } catch {
      return [];
    }
  }

  // Helper for the sequential changeId → entityId fallback lookup
  async function lookupPendingChange() {
    if (changeId) {
      try {
        const changeRes = await fetch(`/api/changes/${changeId}`);
        if (changeRes.ok) {
          const change = await changeRes.json();
          if (change && (change.author_id === userId || isAdmin)) {
            return change;
          }
        }
      } catch {
        // Expected when no change exists
      }
    }
    if (entityId) {
      const changes = await fetchChanges(
        `/api/changes?entity=${entity}&entityId=${entityId}&state=Pending,Draft`
      );
      if (changes.length > 0) {
        return changes.sort((a, b) =>
          new Date(b.created_at) - new Date(a.created_at)
        )[0];
      }
    }
    return null;
  }

  // Run all three lookups in parallel — creates/updates don't depend on the change lookup
  const [pendingChange, creates, updates] = await Promise.all([
    lookupPendingChange(),
    fetchChanges(`/api/changes?entity=${entity}&type=Create&authorId=${userId}&state=Pending,Draft`),
    fetchChanges(`/api/changes?entity=${entity}&type=Update&authorId=${userId}&state=Pending,Draft`)
  ]);

  result.pendingChange = pendingChange;
  result.userPendingCreates = creates;
  result.pendingCreatesCount = creates.length;
  result.userPendingUpdates = updates;

  if (!isAdmin && result.pendingCreatesCount >= MAX_PENDING_CREATES) {
    result.canCreateNew = false;
  }

  return result;
}

/**
 * Lazy-load edit dependencies client-side (called from +page.svelte when edit mode activates).
 * Results are cached per URL so navigating between items in the same route doesn't re-fetch.
 * @param {Array<{key: string, url: string}>} deps - Dependencies to fetch
 * @returns {Promise<Record<string, any>>} Loaded data keyed by `key`
 */
const _editDepsCache = new Map();
export async function loadEditDeps(deps) {
  const apiBase = getApiBase();
  const results = {};
  await Promise.all(deps.map(async ({ key, url }) => {
    if (_editDepsCache.has(url)) {
      results[key] = _editDepsCache.get(url);
      return;
    }
    try {
      const target = url.startsWith('/api/') ? (apiBase + url.slice(4)) : url;
      const res = await fetch(target);
      const data = res.ok ? await res.json() : [];
      _editDepsCache.set(url, data);
      results[key] = data;
    } catch {
      results[key] = [];
    }
  }));
  return results;
}

export function getLatestPendingUpdate(changes, entityId) {
  if (!changes || !entityId) return null;
  const matches = changes.filter(change => {
    const changeEntityId = change?.data?.Id ?? change?.data?.ItemId;
    return changeEntityId && String(changeEntityId) === String(entityId);
  });
  if (matches.length === 0) return null;
  return matches.sort((a, b) =>
    new Date(b.last_update || b.created_at) - new Date(a.last_update || a.created_at)
  )[0];
}

// Removed GET response caching to prevent stale data issues during edits/auth changes
// Helper to get API base depending on environment (browser vs SSR)
function getApiBase() {
  return browser ? (import.meta.env.VITE_API_URL || "https://api.entropianexus.com") : (process.env.INTERNAL_API_URL || "http://api:3000");
}

export async function apiCall(fetch, url, apiUrl = getApiBase()) {
  const target = url.startsWith('/api/') ? url : (apiUrl + url);

  try {
    let response = await fetch(target);

    if (!response.ok) {
      return null;
    }

    return await response.json();
  } catch (e) {
    console.error(`apiCall failed for ${url}:`, e.message || e);
    return null;
  }
}

export async function apiPost(fetch, url, body, apiUrl = getApiBase()) {
  const target = url.startsWith('/api/') ? url : (apiUrl + url);

  let response = await fetch(target, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  });

  try {
    return await response.json();
  } catch {
    return null;
  }
}

export async function apiPut(fetch, url, body, apiUrl = getApiBase()) {
  const target = url.startsWith('/api/') ? url : (apiUrl + url);

  const response = await fetch(target, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  });
  
  if (!response.ok) {
    try {
      const errorData = await response.json();
      return errorData;
    } catch {
      return { error: `HTTP ${response.status}: ${response.statusText}` };
    }
  }
  
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export async function apiDelete(fetch, url, apiUrl = getApiBase()) {
  const target = url.startsWith('/api/') ? url : (apiUrl + url);

  const response = await fetch(target, {
    method: 'DELETE'
  });
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export function pageResponse(items, object = null, additional = null, error = null) {
  return {
    items,
    object,
    additional,
    error
  };
}

export function getErrorMessage(error) {
  if (error === 404) {
    return 'The requested item was not found.';
  } else {
    return 'An error occurred while fetching the requested item.';
  }
}

export async function handlePageLoad(fetch, items, config) {
  let isMultiType = Array.isArray(config.items);
  config.isItem ??= true;
  config.isArmorSet ??= false;

  if (!items) {
    if (isMultiType) {
      await Promise
        .all(config.items.map(x => apiCall(fetch, `/${x}`)))
        .then((x) => {
          items = Object.fromEntries(config.types.map((key, i) => [key.type, x[i] || []]));
        });
      }
    else {
      items = await apiCall(fetch, `/${config.items}`);
    }
  }

  // Guard against null items (API failure) — return empty list instead of crashing
  if (!items) {
    items = [];
  }
  if (isMultiType) {
    for (const t of config.types) {
      if (!items[t.type]) items[t.type] = [];
    }
  }

  if ((!config.type && isMultiType) || !config.name) {
    return { items: items, response: pageResponse(items, null, { type: config.type }) };
  }

  const itemsList = isMultiType ? items[config.type] : items;
  if (!Array.isArray(itemsList) || itemsList.find(x => x.Name === config.name) === undefined) {
    return { items: items, response: pageResponse(items, null, { type: config.type }, 404) };
  }

  let endpoint, tierable, itemId;

  if (!isMultiType) {
    endpoint = config.items;
    tierable = config.types.tierable;
    itemId = config.isArmorSet
    ? items.find(x => x.Name === config.name)?.Id
    : items.find(x => x.Name === config.name)?.ItemId;
  }
  else {
    endpoint = config.items[config.types.findIndex(x => x.type === config.type)];
    tierable = config.types.find(x => x.type === config.type).tierable;
    itemId = items[config.type].find(x => x.Name === config.name)?.ItemId;
  }

  let [object, tierInfo, acquisition, usage] = await Promise.all([
    apiCall(fetch, `/${endpoint}/${encodeURIComponent(config.name)}`),
    tierable
      ? apiCall(fetch, `/tiers?ItemId=${itemId}&IsArmorSet=${config.isArmorSet ? 1 : 0}`)
      : Promise.resolve(null),
    (config.isItem && !config.isArmorSet)
      ? getAcquisitionInfo(fetch, config.name)
      : Promise.resolve(null),
    (config.isItem && !config.isArmorSet)
      ? getUsageInfo(fetch, config.name)
      : Promise.resolve(null)
  ]);

  if (config.isArmorSet && object && Array.isArray(object.Armors)) {
    let armorNames = object.Armors.flatMap(x => x.map(y => y.Name));
    if (armorNames.length > 0) {
      acquisition = await getAcquisitionInfo(fetch, armorNames);
      usage = await getUsageInfo(fetch, armorNames);
    }

    // Fetch exchange orders for each individual armor piece
    const allPieces = object.Armors.flat().filter(p => p.ItemId != null);
    if (allPieces.length > 0 && (acquisition || usage)) {
      const orderResults = await Promise.all(
        allPieces.map(async (piece) => {
          const orders = await apiCall(fetch, `/api/market/exchange/orders/item/${piece.ItemId}`);
          return { name: piece.Name, exchangeItemId: piece.ItemId, maxTT: piece.Properties?.Economy?.MaxTT, orders };
        })
      );

      const allSellOrders = [];
      const allBuyOrders = [];
      for (const { name, exchangeItemId, maxTT, orders } of orderResults) {
        if (!orders) continue;
        if (orders.sell?.length > 0) {
          for (const o of orders.sell) {
            if (o.computed_state !== 'active' && o.computed_state !== 'stale') continue;
            const isNeg = o.markup === null || o.markup === undefined;
            const mu = isNeg ? null : Number(o.markup);
            const ct = Number(o.details?.CurrentTT);
            const isSet = Number(o.quantity) === PLATE_SET_SIZE;
            const tt = ct > 0 ? ct : maxTT;
            const effectiveTT = isSet && tt != null ? tt * PLATE_SET_SIZE : tt;
            allSellOrders.push({
              seller_name: o.seller_name || 'Anonymous',
              markup: mu,
              formattedMarkup: isNeg ? 'Negotiable' : `+${mu.toFixed(2)}`,
              unitPrice: !isNeg && effectiveTT != null ? effectiveTT + mu : null,
              quantity: o.quantity,
              planet: o.planet || 'Any',
              state: o.computed_state,
              item_name: name,
              is_set: isSet,
              _exchangeItemId: exchangeItemId,
              negotiable: isNeg,
            });
          }
        }
        if (orders.buy?.length > 0) {
          for (const o of orders.buy) {
            if (o.computed_state !== 'active' && o.computed_state !== 'stale') continue;
            const isNeg = o.markup === null || o.markup === undefined;
            const mu = isNeg ? null : Number(o.markup);
            allBuyOrders.push({
              buyer_name: o.seller_name || 'Anonymous',
              markup: mu,
              formattedMarkup: isNeg ? 'Negotiable' : `+${mu.toFixed(2)}`,
              quantity: o.quantity,
              planet: o.planet || 'Any',
              state: o.computed_state,
              item_name: name,
              is_set: Number(o.quantity) === PLATE_SET_SIZE,
              _exchangeItemId: exchangeItemId,
              negotiable: isNeg,
            });
          }
        }
      }

      if (allSellOrders.length > 0 && acquisition) {
        acquisition.ExchangeOrders = allSellOrders;
        acquisition._isMultiItem = true;
      }
      if (allBuyOrders.length > 0 && usage) {
        usage.ExchangeBuyOrders = allBuyOrders;
        usage._isMultiItem = true;
      }
    }
  }

  if (object === null) {
    return { items: items, response: pageResponse(items, null, { type: config.type }, 404) };
  }

  // Fetch and attach exchange sell orders to acquisition data
  // Map API endpoint slugs to canonical entity type names from itemTypes.js
  // Built from TYPE_ID_OFFSETS keys: lowercase + 's' covers most endpoints
  const ENDPOINT_ENTITY_TYPE = Object.fromEntries(
    Object.keys(TYPE_ID_OFFSETS).map(t => [t.toLowerCase() + 's', t])
  );
  // Overrides for endpoints that don't follow the lowercase+s pattern
  Object.assign(ENDPOINT_ENTITY_TYPE, {
    clothings: 'Clothing', stimulants: 'Consumable', furniture: 'Furniture',
    strongboxes: 'Strongbox', tools: 'MedicalTool', chips: 'MedicalChip',
  });
  const resolvedEndpoint = isMultiType ? config.type : endpoint;
  const entityType = ENDPOINT_ENTITY_TYPE[resolvedEndpoint] || '';
  const exchangeItemId = itemId || object?.ItemId
    || (object?.Id != null && entityType && TYPE_ID_OFFSETS[entityType] != null ? object.Id + TYPE_ID_OFFSETS[entityType] : null);
  const exchangeOrders = (config.isItem && !config.isArmorSet && exchangeItemId)
    ? await apiCall(fetch, `/api/market/exchange/orders/item/${exchangeItemId}`)
    : null;

  // Shared markup-type info for exchange order formatting
  const exItemName = object?.Name || '';
  const exSubType = object?.Properties?.Type; // Material sub-type (Deed, Token, Share)
  const isPercent = isPercentMarkupType(entityType, exItemName, exSubType);

  // Always attach the exchange item ID so empty-state views can link to it
  if (exchangeItemId && acquisition) acquisition._exchangeItemId = exchangeItemId;
  if (exchangeItemId && usage) usage._exchangeItemId = exchangeItemId;

  if (exchangeOrders?.sell?.length > 0 && acquisition) {
    const isBpNonL = entityType === 'Blueprint' && !hasItemTag(exItemName, 'L');
    const maxTT = object?.Properties?.Economy?.MaxTT ?? object?.Value ?? null;

    acquisition.ExchangeOrders = exchangeOrders.sell
      .filter(o => o.computed_state === 'active' || o.computed_state === 'stale')
      .map(o => {
        const isNegotiable = o.markup === null || o.markup === undefined;
        const mu = isNegotiable ? null : Number(o.markup);
        let unitPrice = null;
        if (!isNegotiable) {
          if (isBpNonL) {
            const qr = Number(o.details?.QualityRating) || 0;
            const tt = qr > 0 ? qr / 100 : null;
            unitPrice = tt != null ? tt + mu : mu > 0 ? mu : null;
          } else if (isPercent) {
            const ct = Number(o.details?.CurrentTT);
            const tt = ct > 0 ? ct : maxTT;
            unitPrice = tt != null ? tt * (mu / 100) : null;
          } else {
            const ct = Number(o.details?.CurrentTT);
            const isSet = entityType === 'ArmorPlating' && Number(o.quantity) === PLATE_SET_SIZE;
            const tt = ct > 0 ? ct : maxTT;
            const effectiveTT = isSet && tt != null ? tt * PLATE_SET_SIZE : tt;
            unitPrice = effectiveTT != null ? effectiveTT + mu : null;
          }
        }
        return {
          seller_name: o.seller_name || 'Anonymous',
          markup: mu,
          formattedMarkup: isNegotiable ? 'Negotiable' : (isPercent ? `${mu.toFixed(2)}%` : `+${mu.toFixed(2)}`),
          unitPrice,
          quantity: o.quantity,
          planet: o.planet || 'Any',
          state: o.computed_state,
          is_set: entityType === 'ArmorPlating' && Number(o.quantity) === PLATE_SET_SIZE,
          negotiable: isNegotiable,
        };
      });
  }

  if (exchangeOrders?.buy?.length > 0 && usage) {
    usage.ExchangeBuyOrders = exchangeOrders.buy
      .filter(o => o.computed_state === 'active' || o.computed_state === 'stale')
      .map(o => {
        const isNegotiable = o.markup === null || o.markup === undefined;
        const mu = isNegotiable ? null : Number(o.markup);
        return {
          buyer_name: o.seller_name || 'Anonymous',
          markup: mu,
          formattedMarkup: isNegotiable ? 'Negotiable' : (isPercent ? `${mu.toFixed(2)}%` : `+${mu.toFixed(2)}`),
          quantity: o.quantity,
          planet: o.planet || 'Any',
          state: o.computed_state,
          is_set: entityType === 'ArmorPlating' && Number(o.quantity) === PLATE_SET_SIZE,
          negotiable: isNegotiable,
        };
      });
  }

  // Fetch forum trading threads mentioning this item
  if (acquisition && itemId) {
    try {
      const forumResult = await apiCall(fetch, `/api/forum/threads/item/${itemId}?limit=10`);
      if (forumResult?.threads?.length > 0) {
        acquisition.ForumThreads = forumResult.threads;
      }
    } catch (_) { /* forum data is optional */ }
  }

  return { items: items, response: pageResponse(items, object, { type: config.type, tierInfo, acquisition, usage }) };
}

export function encodeURIComponentSafe(str) {
  if (!str) return str;
  // Pre-escape literal ~ as %7E, then URL encode (makes it %257E), then use ~ for spaces
  return encodeURIComponent(str.replace(/~/g, '%7E')).replace(/%20/g, '~');
}

export function decodeURIComponentSafe(str) {
  if (!str) return str;
  try {
    // Restore ~ to %20, URL decode (converts %257E to %7E), then restore %7E to ~
    return decodeURIComponent(str.replace(/~/g, '%20')).replace(/%7E/g, '~');
  } catch (e) {
    // Fallback for names containing % which cause invalid percent-encoding sequences
    return str.replace(/~/g, ' ');
  }
}

// Cache for resolved item links
const itemLinkCache = new Map();

export async function resolveItemLink(fetch, item) {
  if (item == null) {
    return null;
  }

  // Check cache first
  const cacheKey = `${item.Properties.Type}-${item.Name}`;
  if (itemLinkCache.has(cacheKey)) {
    return itemLinkCache.get(cacheKey);
  }

  let subtype = null;

  if (item.Properties.Type === 'Armor') {
    if (!item.Set) {
      let armor = await apiCall(fetch, item.Links.$Url);
  
      if (armor != null) {
        item.Set = armor.Set;
      }
    }

    const result = getTypeLink(item.Set?.Name, 'Armor', null);
    itemLinkCache.set(cacheKey, result);
    return result;
  }

  const result = getTypeLink(item.Name, item.Properties.Type, subtype);
  itemLinkCache.set(cacheKey, result);
  return result;
}

export function getResponse(response, status) {
  return new Response(JSON.stringify(response), {
    status,
    headers: {
      'Content-Type': 'application/json'
    }
  });
}

