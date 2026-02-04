// @ts-nocheck
import { loading } from "../stores";
import { goto, invalidateAll } from "$app/navigation";
import { browser } from "$app/environment";
import { MAX_PENDING_CREATES } from "$lib/constants";

export function addItemTag(currentName, tag) {
  // Extract the base name and the existing tags
  const match = currentName.match(/^(.*) \((.*)\)$/);
  const baseName = match ? match[1] : currentName;
  let existingTags = match ? match[2].split(',') : [];

  // Add the tag if it doesn't already exist
  if (!existingTags.includes(tag)) {
    existingTags.push(tag);
  }

  // Sort the tags in the order M or F, C, L, P
  const order = ['M', 'F', 'C', 'L', 'P'];
  existingTags.sort((a, b) => order.indexOf(a) - order.indexOf(b));

  // Add the tags to the base name
  const newName = `${baseName} (${existingTags.join(',')})`;

  return newName;
}

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

export async function getAcquisitionInfo(fetch, itemName) {
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

export async function getUsageInfo(fetch, itemName) {
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

export function getPlanetName(planetName) {
  if (planetName === 'calypso') {
    return 'Calypso';
  }
  else if (planetName === 'aris') {
    return 'ARIS';
  }
  else if (planetName === 'arkadia') {
    return 'Arkadia';
  }
  else if (planetName === 'arkadiaunderground') {
    return 'Arkadia Underground';
  }
  else if (planetName === 'arkadiamoon') {
    return 'Arkadia Moon';
  }
  else if (planetName === 'rocktropia') {
    return 'ROCKtropia';
  }
  else if (planetName === 'huntthething') {
    return 'Hunt The THING';
  }
  else if (planetName === 'hell') {
    return 'HELL';
  }
  else if (planetName === 'secretisland') {
    return 'Secret Island';
  }
  else if (planetName === 'nextisland') {
    return 'Next Island';
  }
  else if (planetName === 'ancientgreece') {
    return 'Ancient Greece';
  }
  else if (planetName === 'monria') {
    return 'Monria';
  }
  else if (planetName === 'dsec9') {
    return 'DSEC9';
  }
  else if (planetName === 'cyrene') {
    return 'Cyrene';
  }
  else if (planetName === 'toulan') {
    return 'Toulan';
  }
  else if (planetName === 'space') {
    return 'Space';
  }
  else if (planetName === 'asteroidfoma') {
    return 'Asteroid F.O.M.A.';
  }
  else if (planetName === 'crystalpalace') {
    return 'Crystal Palace';
  }
  else if (planetName === 'setesh') {
    return 'Setesh';
  }
  else {
    return null;
  }
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

export function getTypeLink(name, type, subType = null) {
  switch (type) {
    case 'Weapon':
      return `/items/weapons/${encodeURIComponentSafe(name)}`;
    case 'Armor':
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
    case 'CreatureControlCapsule':
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
    case 'Mob':
      return `/information/mobs/${encodeURIComponentSafe(name)}`;
    case 'Location':
      return `/maps/${getMainPlanetName(subType).replace(/[^0-9a-zA-Z]/g, '').toLowerCase()}/${encodeURIComponentSafe(name)}`;
    case 'Area':
      return `/maps/${getMainPlanetName(subType).replace(/[^0-9a-zA-Z]/g, '').toLowerCase()}/${encodeURIComponentSafe(name)}`;
    case 'Skill':
      return `/information/skills/${encodeURIComponentSafe(name)}`;
    case 'Profession':
      return `/information/professions/${encodeURIComponentSafe(name)}`;
    case 'Vendor':
      return `/information/vendors/${encodeURIComponentSafe(name)}`;
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
    case 'Material':
      return 'Material';
    case 'Vehicle':
      return 'Vehicle';
    case 'Pet':
      return 'Pet';
    case 'Consumable':
      return 'Stimulant';
    case 'CreatureControlCapsule':
      return 'Creature Control Capsule';
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
    case 'Shop':
      return 'Shop';
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

  if (!sessionUser) return result;

  const { entity, entityId, changeId, isAdmin } = config;
  const userId = sessionUser.id;

  // API returns 200 with null instead of 404 to avoid console spam
  if (changeId) {
    try {
      const changeRes = await fetch(`/api/changes/${changeId}`);
      if (changeRes.ok) {
        const change = await changeRes.json();
        if (change && (change.author_id === userId || isAdmin)) {
          result.pendingChange = change;
        }
      }
    } catch (err) {
      // Expected when no change exists - silently ignore
    }
  }

  if (entityId && !result.pendingChange) {
    try {
      const changeRes = await fetch(
        `/api/changes?entity=${entity}&entityId=${entityId}&state=Pending,Draft`
      );
      if (changeRes.ok) {
        const changes = await changeRes.json();
        if (changes && changes.length > 0) {
          const sorted = changes.sort((a, b) =>
            new Date(b.created_at) - new Date(a.created_at)
          );
          result.pendingChange = sorted[0];
        }
      }
    } catch (err) {
      // Expected when no pending changes exist - silently ignore
    }
  }

  try {
    const createRes = await fetch(
      `/api/changes?entity=${entity}&type=Create&authorId=${userId}&state=Pending,Draft`
    );
    if (createRes.ok) {
      const creates = await createRes.json();
      result.userPendingCreates = creates || [];
      result.pendingCreatesCount = creates?.length || 0;
    }
  } catch (err) {
    // Expected when no creates exist - silently ignore
  }

  try {
    const updateRes = await fetch(
      `/api/changes?entity=${entity}&type=Update&authorId=${userId}&state=Pending,Draft`
    );
    if (updateRes.ok) {
      const updates = await updateRes.json();
      result.userPendingUpdates = updates || [];
    }
  } catch (err) {
    // Expected when no updates exist - silently ignore
  }

  if (!isAdmin && result.pendingCreatesCount >= MAX_PENDING_CREATES) {
    result.canCreateNew = false;
  }

  return result;
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

  let response = await fetch(target);

  if (!response.ok) {
    return null;
  }

  return await response.json();
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
          items = Object.fromEntries(config.types.map((key, i) => [key.type, x[i]]));
        });
      }
    else {
      items = await apiCall(fetch, `/${config.items}`);
    }
  }

  if ((!config.type && isMultiType) || !config.name) {
    return { items: items, response: pageResponse(items, null, { type: config.type }) };
  }

  if ((isMultiType ? items[config.type] : items).find(x => x.Name === config.name) === undefined) {
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
  }

  if (object === null) {
    return { items: items, response: pageResponse(items, null, { type: config.type }, 404) };
  }

  return { items: items, response: pageResponse(items, object, { type: config.type, tierInfo, acquisition, usage }) };
}

export function encodeURIComponentSafe(str) {
  return encodeURIComponent(str?.replace(/ /g, '~'));
}

export function decodeURIComponentSafe(str) {
  return str?.replace(/~/g, ' ');
}

export function getParams(page) {
  return Object.fromEntries(
    Object.entries(page.params).map(([key, value]) => [
      key,
      value != null ? decodeURIComponentSafe(value) : null
    ])
  );
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
