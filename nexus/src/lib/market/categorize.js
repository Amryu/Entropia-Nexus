// @ts-nocheck

// Public entry: categorize a flat list of items and enrich with detailed endpoint data
export function categorizeItems(items, {
  weapons,
  weaponAmplifiers,
  weaponVisionAttachments,
  absorbers,
  mindforceImplants,
  skills,
  armorSets,
  armors,
  armorPlatings,
  clothings,
  medicalTools,
  medicalChips,
  finders,
  finderAmplifiers,
  excavators,
  scanners,
  miscTools,
  enhancers,
  blueprints,
  materials,
  vehicles,
  strongboxes
} = {}) {
  const categorized = makeEmptyCategories();
  // If detailed datasets are provided, skip base-items for those types to avoid duplication
  const hasWeapons = Array.isArray(weapons) && weapons.length > 0;
  const hasArmor = (Array.isArray(armorSets) && armorSets.length > 0)
    || (Array.isArray(armors) && armors.length > 0)
    || (Array.isArray(armorPlatings) && armorPlatings.length > 0);
  const hasEnhancers = Array.isArray(enhancers) && enhancers.length > 0;
  const hasBlueprints = Array.isArray(blueprints) && blueprints.length > 0;
  const hasMaterials = Array.isArray(materials) && materials.length > 0;
  const hasVehicles = Array.isArray(vehicles) && vehicles.length > 0;
  const hasMiscTools = Array.isArray(miscTools) && miscTools.length > 0;

  // First pass: generic Items list
  (items || []).forEach(item => {
    const type = item.Properties?.Type?.toLowerCase?.() || item.Type?.toLowerCase?.();
    const itemClass = item.Properties?.Class?.toLowerCase?.();

    if (type === 'weapon') {
      // If a detailed /weapons dataset is provided, skip base items to avoid duplication.
      // Otherwise, categorize directly from base items.
      if (hasWeapons) return;
      categorizeWeapon(item, categorized.weapons, itemClass, item.Properties?.Type?.toLowerCase?.() || '');
      return;
    } else if (type === 'armor') {
      if (!hasArmor) categorizeArmor(item, categorized.armor);
    } else if (type === 'tool') {
      categorizeTool(item, categorized.tools);
    } else if (type === 'misctool') {
      // Skip base items when detailed /misctools endpoint provides them
      if (!hasMiscTools) categorized.tools.misc.push(item);
    } else if (type === 'refiner') {
      categorized.tools.harvesting.push(item);
    } else if (type === 'effectchip' || type === 'teleportationchip') {
      categorized.tools.mindforce.push(item);
    } else if (type === 'enhancer') {
      // Skip base items; detailed /enhancers endpoint will categorize properly
      if (!hasEnhancers) categorizeEnhancer(item, categorized.enhancers);
    } else if (type === 'blueprint') {
      if (!hasBlueprints) categorizeBlueprint(item, categorized.blueprints);
    } else if (type === 'blueprintbook') {
      categorized._unlisted.push(item);
    } else if (type === 'capsule') {
      categorizeConsumable(item, categorized.consumables);
    } else if (type === 'material') {
      // Base items have Properties.Type = 'Material'; detailed materials pass handles sub-types (Deed/Token/Share → financial)
      if (!hasMaterials) categorizeMaterial(item, categorized.materials);
    } else if (type === 'consumable') {
      categorizeConsumable(item, categorized.consumables);
    } else if (type === 'vehicle') {
      // Prefer detailed Vehicles dataset when available to use the new Vehicle Type
      if (!hasVehicles) categorizeVehicle(item, categorized.vehicles);
    } else if (type === 'pet') {
      categorized.pets.push(item);
    } else if (type === 'skillimplant') {
      // Skip base items when detailed /misctools endpoint provides them
      if (!hasMiscTools) categorized.skill_implants.push(item);
    } else if (type === 'furniture') {
      categorized.furnishings.furniture.push(item);
    } else if (type === 'decoration') {
      categorized.furnishings.decorations.push(item);
    } else if (type === 'storagecontainer') {
      categorized.furnishings.storage.push(item);
    } else if (type === 'sign') {
      categorized.furnishings.sign.push(item);
    } else {
      categorizeFinancial(item, categorized.financial);
    }
  });

  // Detailed endpoint data pass
  (weapons || []).forEach(w => categorizeDetailedWeapon(w, categorized.weapons));
  (weaponAmplifiers || []).forEach(a => categorizeWeaponAmplifier(a, categorized.weapons));
  (weaponVisionAttachments || []).forEach(v => categorizeVisionAttachment(v, categorized.weapons));
  (absorbers || []).forEach(a => categorizeDetailedAbsorber(a, categorized.weapons.absorbers));
  (mindforceImplants || []).forEach(m => categorized.weapons.mindforce.implants.push(m));
  (clothings || []).forEach(c => categorizeClothing(c, categorized.clothes));

  // Populate Skill Implants by matching names from /skills endpoint (fallback when /misctools not available)
  if (!hasMiscTools && Array.isArray(skills) && skills.length > 0) {
    try {
      const set = new Set();
      const addIfFound = (name) => {
        const found = (items || []).find(it => it?.Name === name);
        if (found && !set.has(found.Name)) {
          set.add(found.Name);
          // Avoid double-adding if base items already provided this implant
          if (!categorized.skill_implants.some(x => x?.Name === found?.Name)) {
            categorized.skill_implants.push(found);
          }
        }
      };
      for (const s of skills) {
        const skillName = s?.Name || s?.Skill || s?.DisplayName;
        if (!skillName) continue;
        addIfFound(`${skillName} Skill Implant (L)`);
      }
      addIfFound('Empty Skill Implant (L)');
    } catch {}
  }

  // Skip single-piece armor sets — they're redundant with the individual armor piece
  (armorSets || []).forEach(s => { if (!s.Armors || s.Armors.length > 1) categorized.armor.sets.push(s); });
  (armors || []).forEach(p => categorized.armor.pieces.push(p));
  (armorPlatings || []).forEach(att => categorized.armor.attachments.push(att));

  (medicalTools || []).forEach(t => categorized.tools.medical.push(t));
  (medicalChips || []).forEach(t => categorized.tools.medical.push(t));
  (finders || []).forEach(f => categorized.tools.mining.finders.push(f));
  (finderAmplifiers || []).forEach(a => categorized.tools.mining.amplifiers.push(a));
  (excavators || []).forEach(e => categorized.tools.mining.excavators.push(e));
  (scanners || []).forEach(s => categorized.tools.scanning.push(s));
  (miscTools || []).forEach(tool => categorizeMiscTool(tool, categorized.tools, categorized.skill_implants));

  (enhancers || []).forEach(e => categorizeEnhancer(e, categorized.enhancers));
  (blueprints || []).forEach(b => categorizeBlueprint(b, categorized.blueprints));
  (materials || []).forEach(m => {
    const mt = m?.Properties?.Type?.toLowerCase?.() || '';
    if (mt === 'deed' || mt === 'token' || mt === 'share') {
      categorizeFinancial(m, categorized.financial);
    } else {
      categorizeMaterial(m, categorized.materials);
    }
  });
  (vehicles || []).forEach(v => categorizeVehicle(v, categorized.vehicles));

  (strongboxes || []).forEach(s => categorized.strongboxes.push(s));

  return categorized;
}

function makeEmptyCategories() {
  return {
    weapons: {
      melee: {
        sword: { blades: [] },
        knife: { blades: [] },
        club: { clubs: [] },
        powerfist: { fists: [] },
        whip: { whips: [] },
        amplifiers: [],
        matrices: [],
        other: []
      },
      ranged: {
        rifle: { laser: [], blp: [], plasma: [], gauss: [] },
        pistol: { laser: [], blp: [], plasma: [], gauss: [] },
        support: { laser: [], blp: [], plasma: [] },
        attached: { laser: [], blp: [], support: [], mining: [] },
        cannon: { laser: [], blp: [], plasma: [] },
        amplifiers: { energy: [], blp: [] },
        scopes: [],
        sights: [],
        other: []
      },
      mindforce: { chip: { pyrokinetic: [], electrokinesis: [], cryogenic: [] }, implants: [], amplifiers: [] },
      absorbers: []
    },
    armor: { sets: [], pieces: [], attachments: [] },
    tools: {
      medical: [],
      mining: { finders: [], amplifiers: [], excavators: [] },
      scanning: [],
      harvesting: [],
      mindforce: [],
      beauty: [],
      design: [],
      vehicle: [],
      misc: []
    },
    enhancers: { weapon: [], armor: [], medical: [], mining_finder: [], mining_excavator: [] },
    clothes: {
      rings: { left: [], right: [], other: [] },
      boots: [], coats: [], dresses: [], gloves: [], hats: [], jackets: [], pants: [],
      shades: [], shirts: [], shoes: [], skirts: [], underwear: [], other: []
    },
    blueprints: {
      mechanical_component: [], electrical_component: [], metal_component: [], textile: [], furniture: [], weapon: [],
      attachment: [], vehicle: [], chemistry: [], other: []
    },
    materials: {
      animal_oils: [], leather: [], robot_parts: [], timber: [], fragments: [], forageables: [], extractors: [],
      ores: { raw: [], refined: [] }, enmatter: { raw: [], refined: [] }, treasure: { raw: [], refined: [] },
      crafted_components: [], looted_components: [], designing: { textures: [], paint_cans: [], beauty_products: [] }, other: []
    },
    consumables: { stimulants: [], ammo: [] },
    vehicles: { land: [], air: [], sea: [], amphibious: [], space: [] },
    pets: [],
    skill_implants: [],
    furnishings: { furniture: [], decorations: [], storage: [], sign: [] },
    strongboxes: [],
    financial: { shares: [], estate_deeds: [], tokens: [] },
    _unlisted: []
  };
}

function categorizeWeapon(item, weapons, itemClass, type) {
  const category = item.Properties?.Category?.toLowerCase?.() || '';
  const cls = itemClass || item.Properties?.Class?.toLowerCase?.() || '';
  const t = type || item.Properties?.Type?.toLowerCase?.() || '';

  switch (cls) {
    case 'melee':
      categorizeMeleeWeapon(item, weapons.melee, category, t);
      break;
    case 'ranged':
      categorizeRangedWeapon(item, weapons.ranged, category, t);
      break;
    case 'mindforce':
      categorizeMindforceWeapon(item, weapons.mindforce, category, t);
      break;
    default:
      // Fallback: try ranged buckets
       categorizeRangedWeapon(item, weapons.ranged, category, t);
      break;
  }
}

function categorizeMeleeWeapon(item, melee, category, type) {
  if (category === 'sword' || category === 'axe') melee.sword.blades.push(item);
  else if (category === 'knife') melee.knife.blades.push(item);
  else if (category === 'club') melee.club.clubs.push(item);
  else if (category === 'power fist') melee.powerfist.fists.push(item);
  else if (category === 'whip') melee.whip.whips.push(item);
  else melee.other.push(item);
}

function categorizeRangedWeapon(item, ranged, category, type) {
  let damageType = 'laser';
  if (type === 'blp') damageType = 'blp';
  else if (type === 'plasma') damageType = 'plasma';
  else if (type === 'gauss') damageType = 'gauss';
  else if (type === 'laser') damageType = 'laser';

  if (category === 'rifle' || category === 'carbine' || category === 'flamethrower') {
    ranged.rifle[damageType].push(item);
  } else if (category === 'pistol') {
    if (damageType === 'gauss') damageType = 'laser';
    ranged.pistol[damageType].push(item);
  } else if (category === 'support') {
    if (damageType === 'gauss') damageType = 'laser';
    ranged.support[damageType].push(item);
  } else if (category === 'hanging' || category === 'mounted' || category === 'turret') {
    if (type === 'mining') ranged.attached.mining.push(item);
    else if (type === 'support') ranged.attached.support.push(item);
    else ranged.attached[damageType].push(item);
  } else if (category === 'cannon') {
    if (damageType === 'gauss') damageType = 'laser';
    ranged.cannon[damageType].push(item);
  } else {
    // Unknown ranged category: place into a generic 'other' bucket
    ranged.other.push(item);
  }
}

function categorizeMindforceWeapon(item, mindforce, category, type) {
  // Only chips of offensive types are weapons. Others go to mindforce.other.
  const offensive = new Set(['pyrokinetic', 'electrokinesis', 'cryogenic']);
  if (category === 'chip' && offensive.has(type)) {
    mindforce.chip[type].push(item);
  } else {
    mindforce.other.push(item);
  }
}

function categorizeDetailedWeapon(weapon, weapons) {
  const cls = weapon?.Properties?.Class?.toLowerCase?.() || '';
  const cat = weapon?.Properties?.Category?.toLowerCase?.() || '';
  const type = weapon?.Properties?.Type?.toLowerCase?.() || '';
  categorizeWeapon(weapon, weapons, cls, type, cat);
}

function categorizeWeaponAmplifier(amplifier, weapons) {
  // Sort amplifiers and matrices by their Type string; API exposes Properties.Type on /weaponamplifiers
  const t = amplifier?.Properties?.Type?.toLowerCase?.() || '';

  const isMatrix = t === 'matrix';
  const isMelee = t === 'melee';
  const isMindforce = t === 'mindforce';
  const isBLP = t === 'blp';
  const isEnergy = t === 'energy';

  if (isMindforce) {
    weapons.mindforce.amplifiers.push(amplifier);
    return;
  }

  if (isMatrix) {
    weapons.melee.matrices.push(amplifier);
    return;
  }

  if (isMelee) {
    weapons.melee.amplifiers.push(amplifier);
    return;
  }

  const bucket = isBLP ? 'blp' : 'energy';
  weapons.ranged.amplifiers[bucket].push(amplifier);
}

function categorizeVisionAttachment(attachment, weapons) {
  const t = attachment?.Properties?.Type?.toLowerCase?.() || '';
  if (t.includes('scope')) weapons.ranged.scopes.push(attachment);
  else if (t.includes('sight')) weapons.ranged.sights.push(attachment);
  else weapons.ranged.scopes.push(attachment);
}

function categorizeDetailedAbsorber(absorber, absorbers) {
  absorbers.push(absorber);
}

function categorizeArmor(item, armor) {
  const t = item?.Properties?.Type?.toLowerCase?.() || '';
  if (t === 'armorplating') armor.attachments.push(item);
  else armor.pieces.push(item);
}

function categorizeTool(item, tools) {
  const t = item?.Properties?.Type?.toLowerCase?.() || '';
  if (t === 'medicaltool' || t === 'medicalchip') tools.medical.push(item);
  else if (t === 'finder') tools.mining.finders.push(item);
  else if (t === 'amplifier') tools.mining.amplifiers.push(item);
  else if (t === 'excavator') tools.mining.excavators.push(item);
  else if (t === 'scanner') tools.scanning.push(item);
  else if (t === 'harvester') tools.harvesting.push(item);
  else if (t.includes('beauty')) tools.beauty.push(item);
  else if (t.includes('texture') || t.includes('color') || t.includes('bleach')) tools.design.push(item);
  else if (t === 'vehicle repair') tools.vehicle.push(item);
  else tools.misc.push(item);
}

function categorizeMiscTool(tool, tools, skillImplants) {
  const t = tool?.Properties?.Type?.toLowerCase?.() || '';
  if (t === 'skill implant') skillImplants.push(tool);
  else if (t === 'harvester') tools.harvesting.push(tool);
  else if (t === 'beauty') tools.beauty.push(tool);
  else if (t === 'texturizing' || t === 'colorator' || t === 'bleacher') tools.design.push(tool);
  else if (t === 'vehicle repair') tools.vehicle.push(tool);
  else tools.misc.push(tool);
}

function categorizeEnhancer(enhancer, enhancers) {
  const tool = enhancer?.Properties?.Tool?.toLowerCase?.() || '';
  if (tool === 'weapon') enhancers.weapon.push(enhancer);
  else if (tool === 'armor') enhancers.armor.push(enhancer);
  else if (tool === 'medical tool') enhancers.medical.push(enhancer);
  else if (tool === 'mining finder') enhancers.mining_finder.push(enhancer);
  else if (tool === 'mining excavator') enhancers.mining_excavator.push(enhancer);
  // Skip unrecognized enhancer types
}

function categorizeClothing(item, clothes) {
  const t = (item?.Properties?.Type || item?.Type || '').toLowerCase();

  if (t === 'ring') {
    const slot = (item?.Properties?.Slot || '').toLowerCase();
    if (slot.includes('left')) clothes.rings.left.push(item);
    else if (slot.includes('right')) clothes.rings.right.push(item);
    else clothes.rings.other.push(item);
    return;
  }

  // Normalize and map many variants into existing buckets
  if (t.includes('boot')) {
    clothes.boots.push(item);
    return;
  }

  if (t.includes('coat') || t.includes('cloak')) {
    clothes.coats.push(item);
    return;
  }

  if (t.includes('dress')) {
    clothes.dresses.push(item);
    return;
  }

  if (t.includes('glove')) {
    clothes.gloves.push(item);
    return;
  }

  if (t.includes('hat') || t.includes('horn')) {
    clothes.hats.push(item);
    return;
  }

  if (t.includes('jacket') || t.includes('jacket')) {
    clothes.jackets.push(item);
    return;
  }

  // Pants, slacks, shorts, rucksack/shorts -> pants bucket for simplicity
  if (t.includes('pant') || t.includes('slack') || t.includes('short')) {
    clothes.pants.push(item);
    return;
  }

  if (t.includes('shade') || t.includes('sunglass')) {
    clothes.shades.push(item);
    return;
  }

  if (t.includes('shirt')) {
    clothes.shirts.push(item);
    return;
  }

  if (t === 'shoes' || t.includes('shoe')) {
    clothes.shoes.push(item);
    return;
  }

  if (t.includes('skirt')) {
    clothes.skirts.push(item);
    return;
  }

  if (t.includes('underwear')) {
    clothes.underwear.push(item);
    return;
  }

  // Accessories and odd types map to 'other'
  clothes.other.push(item);
}

function categorizeBlueprint(item, blueprints) {
  const t = item?.Properties?.Type?.toLowerCase?.() || '';
  if (t === 'mechanical component') blueprints.mechanical_component.push(item);
  else if (t === 'electrical component') blueprints.electrical_component.push(item);
  else if (t === 'metal component') blueprints.metal_component.push(item);
  else if (t === 'textile') blueprints.textile.push(item);
  else if (t === 'furniture') blueprints.furniture.push(item);
  else if (t === 'weapon') blueprints.weapon.push(item);
  else if (t === 'attachment') blueprints.attachment.push(item);
  else if (t === 'vehicle') blueprints.vehicle.push(item);
  else if (t === 'chemistry') blueprints.chemistry.push(item);
  else blueprints.other.push(item);
}

function categorizeMaterial(item, materials) {
  const t = item?.Properties?.Type?.toLowerCase?.() || '';
  const name = item?.Name?.toLowerCase?.() || '';

  if (t === 'texture leathers' || t === 'tailoring materials') materials.leather.push(item);
  else if (t === 'wood' || t === 'wood component') materials.timber.push(item);
  else if (t === 'fragment' || name === 'nova fragment' || name === 'blazar fragment') materials.fragments.push(item);
  else if (t === 'food') materials.forageables.push(item);
  else if (t === 'texture extractor') materials.extractors.push(item);
  else if (t === 'animal oils') materials.animal_oils.push(item);
  else if (t === 'robot parts' || t === 'robot component') materials.robot_parts.push(item);
  else if (t === 'ore') materials.ores.raw.push(item);
  else if (t === 'refined ore') materials.ores.refined.push(item);
  else if (t === 'enmatter') materials.enmatter.raw.push(item);
  else if (t === 'refined enmatter') materials.enmatter.refined.push(item);
  else if (t === 'treasure') materials.treasure.raw.push(item);
  else if (t === 'refined treasure') materials.treasure.refined.push(item);
  else if (t === 'enhancer component') materials.looted_components.push(item);
  else if (t === 'mechanical component' || t === 'electronic component' || t === 'metal component' || t === 'generic component') materials.crafted_components.push(item);
  else if (t === 'texture material') materials.designing.textures.push(item);
  else if (t === 'paint cans') materials.designing.paint_cans.push(item);
  else if (t === 'beauty' || t === 'make up') materials.designing.beauty_products.push(item);
  else if (t === 'natural materials') materials.forageables.push(item);
  else if (t === 'crystal' || t === 'precious stones' || t === 'dna' || t === 'skulls' || t === 'residue' || t === 'material' || t === 'refined material') materials.other.push(item);
  else materials.other.push(item);
}

function categorizeConsumable(item, consumables) {
  const t = item?.Properties?.Type?.toLowerCase?.() || '';
  const n = item?.Name?.toLowerCase?.() || '';
  // Specific ammo names
  const ammoNames = new Set(['mind essence', 'light mind essence', 'explosive projectiles']);
  if (ammoNames.has(n)) consumables.ammo.push(item);
  else if (t === 'ammo' || t === 'ammunition') consumables.ammo.push(item);
  else consumables.stimulants.push(item);
}

function categorizeVehicle(item, vehicles) {
  const t = item?.Properties?.Type?.toLowerCase?.() || '';
  if (t.includes('air')) vehicles.air.push(item);
  else if (t.includes('sea')) vehicles.sea.push(item);
  else if (t.includes('amphibious')) vehicles.amphibious.push(item);
  else if (t.includes('space')) vehicles.space.push(item);
  else vehicles.land.push(item);
}

function categorizeFinancial(item, financial) {
  const t = (item?.Properties?.Type || '').toLowerCase();
  if (t === 'deed') financial.estate_deeds.push(item);
  else if (t === 'token') financial.tokens.push(item);
  else if (t === 'share') financial.shares.push(item);
}

function isFinancialItem(item) {
  const t = (item?.Properties?.Type || '').toLowerCase();
  return t === 'deed' || t === 'token' || t === 'share';
}

// Static mapping from entity item_type to display category path.
// Mirrors the category structure from makeEmptyCategories().
const ITEM_TYPE_CATEGORY_MAP = {
  'Weapon': 'Weapons',
  'WeaponAmplifier': 'Weapons > Amplifiers',
  'WeaponVisionAttachment': 'Weapons > Ranged',
  'Absorber': 'Weapons > Absorbers',
  'MindforceImplant': 'Weapons > Mindforce',
  'Armor': 'Armor',
  'ArmorSet': 'Armor > Sets',
  'ArmorPlating': 'Armor > Attachments',
  'MedicalTool': 'Tools > Medical',
  'MedicalChip': 'Tools > Medical',
  'Finder': 'Tools > Mining',
  'FinderAmplifier': 'Tools > Mining',
  'Excavator': 'Tools > Mining',
  'Refiner': 'Tools > Harvesting',
  'Scanner': 'Tools > Scanning',
  'MiscTool': 'Tools',
  'Tool': 'Tools',
  'EffectChip': 'Tools > Mindforce',
  'TeleportationChip': 'Tools > Mindforce',
  'Enhancer': 'Enhancers',
  'Clothing': 'Clothes',
  'Blueprint': 'Blueprints',
  'Capsule': 'Consumables',
  'Material': 'Materials',
  'Consumable': 'Consumables',
  'Vehicle': 'Vehicles',
  'Pet': 'Pets',
  'SkillImplant': 'Skill Implants',
  'Furniture': 'Furnishings',
  'Decoration': 'Furnishings',
  'StorageContainer': 'Furnishings',
  'Sign': 'Furnishings',
  'Strongbox': 'Strongboxes'
};

/**
 * Map an item_type (and optional sub_type) to a display category path.
 * Used for grouping orders on user profiles.
 */
export function getItemCategoryPath(itemType, itemSubType) {
  if (!itemType) return 'Other';
  // Materials with financial sub-types go to Financial
  if (itemType === 'Material' && itemSubType) {
    const st = itemSubType.toLowerCase();
    if (st === 'deed' || st === 'token' || st === 'share') return 'Financial';
  }
  return ITEM_TYPE_CATEGORY_MAP[itemType] || 'Other';
}
