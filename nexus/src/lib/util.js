// @ts-nocheck
import { loading } from "../stores";
import { goto } from "$app/navigation";

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
  // Extract the existing tags
  const match = currentName.match(/^(.*) \((.*)\)$/);
  const existingTags = match ? match[2].split(',') : [];

  // Check if the tag exists in the existing tags
  return existingTags.includes(tag);
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

  const [blueprints, mobloots, vendoroffers, refiningrecipes] = await Promise.all([
    apiCall(fetch, `/blueprints?Product=${encodeURIComponent(itemName)}`),
    apiCall(fetch, `/mobloots?Item=${encodeURIComponent(itemName)}`),
    apiCall(fetch, `/vendoroffers?Item=${encodeURIComponent(itemName)}`),
    apiCall(fetch, `/refiningrecipes?Product=${encodeURIComponent(itemName)}`)
  ]);

  return {
    Blueprints: blueprints,
    Loots: mobloots,
    VendorOffers: vendoroffers,
    RefiningRecipes: refiningrecipes
  };
}

export function getPlanetName(planetName) {
  if (planetName === 'calypso') {
    return 'Calypso';
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
  else {
    return null;
  }
}

export function getMainPlanetName(planetName) {
  if (planetName === 'Asteroid F.O.M.A.' || planetName === 'Crystal Palace') {
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
  return getTypeLink(item.Name, item.Properties.Type, subtype);
}

export function getTypeLink(name, type, subType = null) {
  switch (type) {
    case 'Weapon':
      return subType != null
      ? `/items/weapons/${encodeURIComponent(subType).toLowerCase()}/${encodeURIComponent(name)}`
      : `/items/weapons/${encodeURIComponent(name)}`;
    case 'Armor':
      return `/items/armors/${encodeURIComponent(name)}`;
    case 'MedicalTool':
      return `/items/medicaltools/tools/${encodeURIComponent(name)}`;
    case 'MedicalChip':
      return `/items/medicaltools/chips/${encodeURIComponent(name)}`;
    case 'Refiner':
      return `/items/tools/refiners/${encodeURIComponent(name)}`;
    case 'Scanner':
      return `/items/tools/scanners/${encodeURIComponent(name)}`;
    case 'Finder':
      return `/items/tools/finders/${encodeURIComponent(name)}`;
    case 'Excavator':
      return `/items/tools/excavators/${encodeURIComponent(name)}`;
    case 'TeleportationChip':
      return `/items/tools/teleportationchips/${encodeURIComponent(name)}`;
    case 'EffectChip':
      return `/items/tools/effectchips/${encodeURIComponent(name)}`;
    case 'MiscTool':
      return `/items/tools/misctools/${encodeURIComponent(name)}`;
    case 'Blueprint':
      return `/items/blueprints/${encodeURIComponent(name)}`;
    case 'Material':
      return `/items/materials/${encodeURIComponent(name)}`;
    case 'Vehicle':
      return `/items/vehicles/${encodeURIComponent(name)}`;
    case 'Pet':
      return `/items/pets/${encodeURIComponent(name)}`;
    case 'Consumable':
      return `/items/consumables/consumables/${encodeURIComponent(name)}`;
    case 'CreatureControlCapsule':
      return `/items/consumables/creaturecontrolcapsules/${encodeURIComponent(name)}`;
    case 'Furniture':
      return `/items/furnishings/furniture/${encodeURIComponent(name)}`;
    case 'Decoration':
      return `/items/furnishings/decoration/${encodeURIComponent(name)}`;
    case 'StorageContainer':
      return `/items/furnishings/storagecontainers/${encodeURIComponent(name)}`;
    case 'Sign':
      return `/items/furnishings/signs/${encodeURIComponent(name)}`;
    case 'WeaponAmplifier':
      return `/items/attachments/weaponamplifiers/${encodeURIComponent(name)}`;
    case 'WeaponVisionAttachment':
      return `/items/attachments/weaponvisionattachments/${encodeURIComponent(name)}`;
    case 'Absorber':
      return `/items/attachments/absorbers/${encodeURIComponent(name)}`;
    case 'ArmorPlating':
      return `/items/attachments/armorplatings/${encodeURIComponent(name)}`;
    case 'FinderAmplifier':
      return `/items/attachments/finderamplifiers/${encodeURIComponent(name)}`;
    case 'Enhancer':
      return `/items/attachments/enhancers/${encodeURIComponent(name)}`;
    case 'MindforceImplant':
      return `/items/attachments/mindforceimplants/${encodeURIComponent(name)}`;
    case 'Mob':
      return `/creatures/mobs/${getMainPlanetName(subType).toLowerCase()}/${encodeURIComponent(name)}`;
    case 'Location':
      return `/maps/${getMainPlanetName(subType).replace(/[^0-9a-zA-Z]/, '').toLowerCase()}/${encodeURIComponent(name)}`;
    case 'Area':
      return `/maps/${getMainPlanetName(subType).replace(/[^0-9a-zA-Z]/, '').toLowerCase()}/${encodeURIComponent(name)}`;
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
      return 'Consumable';
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

  loading.set(false);
}

export async function apiCall(fetch, url) {
  let response = await fetch(import.meta.env.VITE_API_URL + url);

  if (!response.ok) {
    return null;
  }

  return await response.json();
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

export async function handlePageLoad(fetch, items, config, slug, type = null, isItem = true, isArmorSet = false) {
  let isMultiType = Array.isArray(config.items);

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

  if ((!type && isMultiType) || !slug) {
    return { items: items, response: pageResponse(items) };
  }

  if ((isMultiType ? items[type] : items).find(x => x.Name === slug) === undefined) {
    return { items: items, response: pageResponse(items, null, null, 404) };
  }

  let endpoint, tierable, itemId;

  if (!isMultiType) {
    endpoint = config.items;
    tierable = config.types.tierable;
    itemId = isArmorSet
    ? items.find(x => x.Name === slug)?.Id
    : items.find(x => x.Name === slug)?.ItemId;
  }
  else {
    endpoint = config.items[config.types.findIndex(x => x.type === type)];
    tierable = config.types.find(x => x.type === type).tierable;
    itemId = items[type].find(x => x.Name === slug)?.ItemId;
  }

  const [object, tierInfo, acquisition] = await Promise.all([
    apiCall(fetch, `/${endpoint}/${encodeURIComponent(slug)}`),
    tierable
      ? apiCall(fetch, `/tiers?ItemId=${itemId}&IsArmorSet=${isArmorSet ? 1 : 0}`)
      : Promise.resolve(null),
    isItem
      ? getAcquisitionInfo(fetch, slug)
      : Promise.resolve(null)
  ]);

  if (object === null) {
    return { items: items, response: pageResponse(items, null, null, 404) };
  }

  return { items: items, response: pageResponse(items, object, { type: type, tierInfo, acquisition }) };
}