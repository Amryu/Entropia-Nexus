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
    case 'TeleportChip':
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
      return `/maps/${(subType || '').replace(/[^0-9a-zA-Z]/g, '').toLowerCase()}/${encodeURIComponentSafe(name)}`;
    case 'Area':
      return `/maps/${(subType || '').replace(/[^0-9a-zA-Z]/g, '').toLowerCase()}/${encodeURIComponentSafe(name)}`;
    case 'Skill':
      return `/information/skills/${encodeURIComponentSafe(name)}`;
    case 'Profession':
      return `/information/professions/${encodeURIComponentSafe(name)}`;
    case 'Vendor':
      return `/information/vendors/${encodeURIComponentSafe(name)}`;
    case 'ArmorSet':
      return `/items/armorsets/${encodeURIComponentSafe(name)}`;
    case 'Mission':
      return `/information/missions/${encodeURIComponentSafe(name)}`;
    case 'MissionChain':
      return `/information/missions/${encodeURIComponentSafe(name)}?view=chains`;
    case 'Strongbox':
      return `/items/strongboxes/${encodeURIComponentSafe(name)}`;
    case 'Shop':
      return `/market/shops/${encodeURIComponentSafe(name)}`;
    case 'Apartment':
      return `/maps/${(subType || '').replace(/[^0-9a-zA-Z]/g, '').toLowerCase()}/${encodeURIComponentSafe(name)}`;
    default:
      return null;
  }
}

function encodeURIComponentSafe(str) {
  return encodeURIComponent(str.replace(/ /g, '~'));
}
