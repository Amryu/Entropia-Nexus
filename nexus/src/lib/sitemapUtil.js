//@ts-nocheck
import { apiCall, encodeURIComponentSafe, getMainPlanetName } from "./util";

function getSimplePlanetName(planetName) {
  return planetName.replace(/[^0-9a-zA-Z]/g, '').trim().toLowerCase();
}

export async function getAllLinks(fetch) {
  const [items, weapons, armorSets, mobs, planets, professions, skills, vendors] = await Promise.all([
    apiCall(fetch, `/items`),
    apiCall(fetch, `/weapons`),
    apiCall(fetch, `/armorsets`),
    apiCall(fetch, `/mobs`),
    apiCall(fetch, `/planets`),
    apiCall(fetch, `/professions`),
    apiCall(fetch, `/skills`),
    apiCall(fetch, `/vendors`),
  ]);
  
  const MEDICAL_TOOL_TYPES = ['MedicalTool', 'MedicalChip'];

  const TOOL_TYPES = [
    'Refiner', 'Scanner', 'Finder', 'Excavator', 'TeleportationChip', 'MedicalTool', 'MedicalChip', 'EffectChip', 'MiscTool'
  ];

  const ATTACHMENT_TYPES = [
    'WeaponAmplifier', 'WeaponVisionAttachment', 'Absorber', 'FinderAmplifier', 'ArmorPlating', 'Enhancer', 'MindforceImplant'
  ];

  const CONSUMABLE_TYPES = [
    'Consumable', 'Capsule'
  ];

  const FURNISHING_TYPES = [
    'Furniture', 'Decoration', 'StorageContainer', 'Sign' 
  ];

  const ITEM_TYPES = [
    {Type: 'Weapon', Route: 'weapons'},

    {Type: 'MedicalTool', Route: 'tools'},
    {Type: 'MedicalChip', Route: 'chips'},

    {Type: 'Refiner', Route: 'refiners'},
    {Type: 'Scanner', Route: 'scanners'},
    {Type: 'Finder', Route: 'finders'},
    {Type: 'Excavator', Route: 'excavators'},
    {Type: 'TeleportationChip', Route: 'teleportationchips'},
    {Type: 'EffectChip', Route: 'effectchips'},
    {Type: 'MiscTool', Route: 'misctools'},

    {Type: 'WeaponAmplifier', Route: 'weaponamplifiers'},
    {Type: 'WeaponVisionAttachment', Route: 'weaponvisionattachments'},
    {Type: 'Absorber', Route: 'absorbers'},
    {Type: 'FinderAmplifier', Route: 'finderamplifiers'},
    {Type: 'ArmorPlating', Route: 'armorplatings'},
    {Type: 'Enhancer', Route: 'enhancers'},
    {Type: 'MindforceImplant', Route: 'mindforceimplants'},

    {Type: 'Blueprint', Route: 'blueprints'},
    {Type: 'Material', Route: 'materials'},
    {Type: 'Pet', Route: 'pets'},

    {Type: 'Consumable', Route: 'stimulants'},
    {Type: 'Capsule', Route: 'capsules'},

    {Type: 'Vehicle', Route: 'vehicles'},

    {Type: 'Furniture', Route: 'furniture'},
    {Type: 'Decoration', Route: 'decorations'},
    {Type: 'StorageContainer', Route: 'storagecontainers'},
    {Type: 'Sign', Route: 'signs'},

    {Type: 'Clothing', Route: 'clothing'},

    {Type: 'Strongbox', Route: 'strongboxes'},
  ];

  const itemsXML = items.filter(x => x.Properties.Type !== 'Armor' && x.Properties.Type !== 'BlueprintBook').map(item => {
    let typeEntry = ITEM_TYPES.find(x => x.Type === item.Properties.Type);
    if (!typeEntry) return null;
    let route = typeEntry.Route;

    if (MEDICAL_TOOL_TYPES.includes(item.Properties.Type)) {
      return `/items/medicaltools/${route}/${encodeURIComponentSafe(item.Name)}`;
    } else if (TOOL_TYPES.includes(item.Properties.Type)) {
      return `/items/tools/${route}/${encodeURIComponentSafe(item.Name)}`;
    } else if (ATTACHMENT_TYPES.includes(item.Properties.Type)) {
      return `/items/attachments/${route}/${encodeURIComponentSafe(item.Name)}`;
    } else if (CONSUMABLE_TYPES.includes(item.Properties.Type)) {
      return `/items/consumables/${route}/${encodeURIComponentSafe(item.Name)}`;
    } else if (FURNISHING_TYPES.includes(item.Properties.Type)) {
      return `/items/furnishings/${route}/${encodeURIComponentSafe(item.Name)}`;
    } else {
      return `/items/${route}/${encodeURIComponentSafe(item.Name)}`;
    }
  }).filter(Boolean);

  let armorSetsXML = armorSets.map(armorSet => `/items/armorsets/${encodeURIComponentSafe(armorSet.Name)}`);
  let mobsXML = mobs.map(mob => `/information/mobs/${encodeURIComponentSafe(mob.Name)}`);
  let planetsXML = planets.filter(x => x.Id > 0).map(planet => `/maps/${getSimplePlanetName(planet.Name)}`);
  let professionsXML = professions.map(profession => `/information/professions/${encodeURIComponentSafe(profession.Name)}`);
  let skillsXML = skills.map(skill => `/information/skills/${encodeURIComponentSafe(skill.Name)}`);
  let vendorsXML = vendors.map(vendor => `/information/vendors/${encodeURIComponentSafe(vendor.Name)}`);

  return {
    general: ['/tools/loadouts'],
    items: itemsXML,
    armorSets: armorSetsXML,
    mobs: mobsXML,
    planets: planetsXML,
    professions: professionsXML,
    skills: skillsXML,
    vendors: vendorsXML,
  };
}