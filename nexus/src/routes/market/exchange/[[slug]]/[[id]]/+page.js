// @ts-nocheck
import { apiCall } from '$lib/util';

export async function load({ fetch, params, url }) {
  // Fetch all items from the API
  const items = await apiCall(fetch, '/items');
  
  // Fetch detailed weapon and armor data from specific endpoints
  const [weapons, weaponAmplifiers, weaponVisionAttachments, absorbers, mindforceImplants, armorSets, armors, armorPlatings, clothings, medicalTools, finders, finderAmplifiers, excavators, scanners, miscTools, enhancers, blueprints, materials] = await Promise.all([
    apiCall(fetch, '/weapons'),
    apiCall(fetch, '/weaponamplifiers'),
    apiCall(fetch, '/weaponvisionattachments'),
    apiCall(fetch, '/absorbers'),
    apiCall(fetch, '/mindforceimplants'),
    apiCall(fetch, '/armorsets'),
    apiCall(fetch, '/armors'),
    apiCall(fetch, '/armorplatings'),
    apiCall(fetch, '/clothings'),
    apiCall(fetch, '/medicaltools'),
    apiCall(fetch, '/finders'),
    apiCall(fetch, '/finderamplifiers'),
    apiCall(fetch, '/excavators'),
    apiCall(fetch, '/scanners'),
    apiCall(fetch, '/misctools'),
    apiCall(fetch, '/enhancers'),
    apiCall(fetch, '/blueprints'),
    apiCall(fetch, '/materials')
  ]);
  
  if (!items) {
    return {
      items: [],
      categorizedItems: {},
      error: 'Failed to fetch items'
    };
  }

  // Categorize items based on their Type and Properties
  const categorizedItems = categorizeItems(items, {
    weapons,
    weaponAmplifiers,
    weaponVisionAttachments,
    absorbers,
    mindforceImplants,
    armorSets,
    armors,
    armorPlatings,
    clothings,
    medicalTools,
    finders,
    finderAmplifiers,
    excavators,
    scanners,
    miscTools,
    enhancers,
    blueprints,
    materials
  });

  return {
    items,
    categorizedItems,
    weaponData: {
      weapons,
      weaponAmplifiers,
      weaponVisionAttachments,
      absorbers,
      mindforceImplants
    },
    armorData: {
      armorSets,
      armors,
      armorPlatings,
      clothings
    },
    toolData: {
      medicalTools,
      finders,
      finderAmplifiers,
      excavators,
      scanners,
      miscTools
    }
  };
}

function categorizeItems(items, weaponData = {}) {
  const categorized = {
    weapons: {
      melee: {
        sword: {
          blades: []
        },
        knife: {
          blades: []
        },
        club: {
          clubs: []
        },
        powerfist: {
          fists: []
        },
        whip: {
          whips: []
        },
        amplifiers: [],
        matrices: []
      },
      ranged: {
        rifle: {
          laser: [],
          blp: [],
          plasma: [],
          gauss: []
        },
        pistol: {
          laser: [],
          blp: [],
          plasma: [],
          gauss: []
        },
        support: {
          laser: [],
          blp: [],
          plasma: []
        },
        attached: {
          laser: [],
          blp: [],
          support: [],
          mining: []
        },
        cannon: {
          laser: [],
          blp: [],
          plasma: []
        },
        amplifiers: [],
        scopes: [],
        sights: []
      },
      mindforce: {
        chip: {
          pyrokinetic: [],
          electrokinetic: [],
          cryogenic: []
        },
        implants: [],
        amplifiers: []
      },
      absorbers: []
    },
    armor: {
      sets: [],
      pieces: [],
      attachments: [],
      accessories: []
    },
    tools: {
      medical: [],
      mining: {
        finders: [],
        amplifiers: [],
        excavators: []
      },
      scanning: [],
      harvesting: [],
      mindforce: [],
      beauty: [],
      design: [],
      vehicle: [],
      misc: []
    },
    enhancers: {
      weapon: [],
      armor: [],
      medical: [],
      mining_finder: [],
      mining_excavator: []
    },
    clothes: {
      boots: [],
      coats: [],
      dresses: [],
      gloves: [],
      hats: [],
      jackets: [],
      pants: [],
      shades: [],
      shirts: [],
      shoes: [],
      skirts: [],
      underwear: [],
      other: []
    },
    blueprints: {
      mechanical_component: [],
      electrical_component: [],
      metal_component: [],
      textile: [],
      furniture: [],
      weapon: [],
      attachment: [],
      vehicle: [],
      other: []
    },
    materials: {
      animal_oils: [],
      leather: [],
      robot_parts: [],
      timber: [],
      fragments: [],
      forageables: [],
      extractors: [],
      ores: { raw: [], refined: [] },
      enmatter: { raw: [], refined: [] },
      treasure: { raw: [], refined: [] },
      crafted_components: [],
      looted_components: [],
      designing: {
        textures: [],
        paint_cans: [],
        beauty_products: []
      },
      other: []
    },
    consumables: {
      stimulants: [],
      ammo: []
    },
    vehicles: {
      land: [],
      air: [],
      sea: [],
      amphibious: [],
      space: []
    },
    pets: [],
    skill_implants: [],
    furnishings: {
      furniture: [],
      decorations: [],
      storage: [],
      sign: []
    },
    financial: {
      shares: [],
      estate_deeds: [],
      tokens: []
    }
  };

  items.forEach(item => {
    const type = item.Type?.toLowerCase();
    const itemClass = item.Properties?.Class?.toLowerCase();
    
    // Categorize based on Type and Class
    if (type === 'weapon') {
      categorizeWeapon(item, categorized.weapons, itemClass, weaponData);
    } else if (type === 'armor') {
      categorizeArmor(item, categorized.armor);
    } else if (type === 'tool') {
      categorizeTool(item, categorized.tools);
    } else if (type === 'enhancer') {
      categorized.enhancers.push(item);
    } else if (type === 'clothing') {
      categorizeClothing(item, categorized.clothes);
    } else if (type === 'blueprint') {
      categorizeBlueprint(item, categorized.blueprints);
    } else if (type === 'material') {
      categorizeMaterial(item, categorized.materials);
    } else if (type === 'consumable') {
      categorizeConsumable(item, categorized.consumables);
    } else if (type === 'vehicle') {
      categorizeVehicle(item, categorized.vehicles);
    } else if (type === 'pet') {
      categorized.pets.push(item);
    } else if (type === 'skillimplant') {
      categorized.skill_implants.push(item);
    } else if (type === 'furnishing') {
      categorizeFurnishing(item, categorized.furnishings);
    } else if (type === 'financial') {
      categorizeFinancial(item, categorized.financial);
    }
  });

  // Add detailed weapon data from specific endpoints
  if (weaponData.weapons) {
    weaponData.weapons.forEach(weapon => {
      categorizeDetailedWeapon(weapon, categorized.weapons);
    });
  }
  
  if (weaponData.weaponAmplifiers) {
    weaponData.weaponAmplifiers.forEach(amplifier => {
      categorizeWeaponAmplifier(amplifier, categorized.weapons);
    });
  }
  
  if (weaponData.weaponVisionAttachments) {
    weaponData.weaponVisionAttachments.forEach(attachment => {
      categorizeVisionAttachment(attachment, categorized.weapons);
    });
  }
  
  if (weaponData.absorbers) {
    weaponData.absorbers.forEach(absorber => {
      categorizeDetailedAbsorber(absorber, categorized.weapons.absorbers);
    });
  }
  
  if (weaponData.mindforceImplants) {
    weaponData.mindforceImplants.forEach(implant => {
      categorized.weapons.mindforce.implants.push(implant);
    });
  }

  // Add detailed armor data from specific endpoints
  if (weaponData.armorSets) {
    weaponData.armorSets.forEach(armorSet => {
      categorized.armor.sets.push(armorSet);
    });
  }
  
  if (weaponData.armors) {
    weaponData.armors.forEach(armor => {
      categorized.armor.pieces.push(armor);
    });
  }
  
  if (weaponData.armorPlatings) {
    weaponData.armorPlatings.forEach(plating => {
      categorized.armor.attachments.push(plating);
    });
  }
  
  if (weaponData.clothings) {
    weaponData.clothings.forEach(clothing => {
      // Only add clothing items that have special effects
      if (clothing.EffectsOnEquip && clothing.EffectsOnEquip.length > 0) {
        categorized.armor.accessories.push(clothing);
      }
    });
  }

  // Add detailed tool data from specific endpoints
  if (weaponData.medicalTools) {
    weaponData.medicalTools.forEach(tool => {
      categorized.tools.medical.push(tool);
    });
  }
  
  if (weaponData.finders) {
    weaponData.finders.forEach(finder => {
      categorized.tools.mining.finders.push(finder);
    });
  }
  
  if (weaponData.finderAmplifiers) {
    weaponData.finderAmplifiers.forEach(amplifier => {
      categorized.tools.mining.amplifiers.push(amplifier);
    });
  }
  
  if (weaponData.excavators) {
    weaponData.excavators.forEach(excavator => {
      categorized.tools.mining.excavators.push(excavator);
    });
  }
  
  if (weaponData.scanners) {
    weaponData.scanners.forEach(scanner => {
      categorized.tools.scanning.push(scanner);
    });
  }
  
  if (weaponData.miscTools) {
    weaponData.miscTools.forEach(tool => {
      // Categorize misc tools based on their Type property
      const type = tool.Properties?.Type?.toLowerCase() || '';
      
      if (type === 'harvester') {
        categorized.tools.harvesting.push(tool);
      } else if (type === 'beauty') {
        categorized.tools.beauty.push(tool);
      } else if (type === 'texturizing' || type === 'colorator' || type === 'bleacher') {
        categorized.tools.design.push(tool);
      } else if (type === 'vehicle repair') {
        categorized.tools.vehicle.push(tool);
      } else {
        categorized.tools.misc.push(tool);
      }
    });
  }

  // Add detailed enhancer data from specific endpoint
  if (weaponData.enhancers) {
    weaponData.enhancers.forEach(enhancer => {
      // Categorize enhancers based on their Tool property
      const tool = enhancer.Properties?.Tool?.toLowerCase() || '';
      
      if (tool === 'weapon') {
        categorized.enhancers.weapon.push(enhancer);
      } else if (tool === 'armor') {
        categorized.enhancers.armor.push(enhancer);
      } else if (tool === 'medical tool') {
        categorized.enhancers.medical.push(enhancer);
      } else if (tool === 'mining finder') {
        categorized.enhancers.mining_finder.push(enhancer);
      } else if (tool === 'mining excavator') {
        categorized.enhancers.mining_excavator.push(enhancer);
      }
    });
  }

  // Add detailed blueprint data from specific endpoint
  if (weaponData.blueprints) {
    weaponData.blueprints.forEach(blueprint => {
      categorizeBlueprint(blueprint, categorized.blueprints);
    });
  }

  // Add detailed material data from specific endpoint
  if (weaponData.materials) {
    weaponData.materials.forEach(material => {
      categorizeMaterial(material, categorized.materials);
    });
  }

  return categorized;
}

function categorizeWeapon(item, weapons, itemClass, weaponData = {}) {
  const category = item.Properties?.Category?.toLowerCase() || '';
  const type = item.Properties?.Type?.toLowerCase() || '';
  
  switch (itemClass) {
    case 'melee':
      categorizeMeleeWeapon(item, weapons.melee, category, type);
      break;
    case 'ranged':
      categorizeRangedWeapon(item, weapons.ranged, category, type);
      break;
    case 'mindforce':
      categorizeMindforceWeapon(item, weapons.mindforce, category, type);
      break;
  }
}

function categorizeMeleeWeapon(item, melee, category, type) {
  if (category === 'sword') {
    melee.sword.blades.push(item);
  } else if (category === 'knife') {
    melee.knife.blades.push(item);
  } else if (category === 'club') {
    melee.club.clubs.push(item);
  } else if (category === 'powerfist') {
    melee.powerfist.fists.push(item);
  } else if (category === 'whip') {
    melee.whip.whips.push(item);
  } else {
    // Default to sword/blades if we can't determine
    melee.sword.blades.push(item);
  }
}

function categorizeRangedWeapon(item, ranged, category, type) {
  // Determine damage type
  let damageType = 'laser'; // default
  if (type === 'blp') damageType = 'blp';
  else if (type === 'plasma') damageType = 'plasma';
  else if (type === 'gauss') damageType = 'gauss';
  else if (type === 'laser') damageType = 'laser';
  
  // Determine weapon category
  if (category === 'rifle') {
    ranged.rifle[damageType].push(item);
  } else if (category === 'pistol') {
    // Only laser, blp, plasma for pistols (no gauss)
    if (damageType === 'gauss') damageType = 'laser';
    ranged.pistol[damageType].push(item);
  } else if (category === 'support') {
    // No gauss for support weapons
    if (damageType === 'gauss') damageType = 'laser';
    ranged.support[damageType].push(item);
  } else if (category === 'attached') {
    if (type === 'mining') {
      ranged.attached.mining.push(item);
    } else if (type === 'support') {
      ranged.attached.support.push(item);
    } else {
      ranged.attached[damageType].push(item);
    }
  } else if (category === 'cannon') {
    // No gauss for cannons
    if (damageType === 'gauss') damageType = 'laser';
    ranged.cannon[damageType].push(item);
  } else {
    // Default to rifle
    ranged.rifle[damageType].push(item);
  }
}

function categorizeMindforceWeapon(item, mindforce, category, type) {
  // Determine mindforce type for chips
  let mfType = 'pyrokinetic'; // default
  if (type === 'electrokinetic') mfType = 'electrokinetic';
  else if (type === 'cryogenic') mfType = 'cryogenic';
  else if (type === 'pyrokinetic') mfType = 'pyrokinetic';
  
  // All mindforce weapons are chips
  mindforce.chip[mfType].push(item);
}

function categorizeDetailedAbsorber(absorber, absorbers) {
  // Absorbers are simple attachments with no sub-categorization
  absorbers.push(absorber);
}

function categorizeClothing(item, clothes) {
  const type = item.Properties?.Type?.toLowerCase() || '';
  
  if (type === 'boots') {
    clothes.boots.push(item);
  } else if (type === 'coats') {
    clothes.coats.push(item);
  } else if (type === 'dress' || type === 'dresses') {
    clothes.dresses.push(item);
  } else if (type === 'gloves') {
    clothes.gloves.push(item);
  } else if (type === 'hats') {
    clothes.hats.push(item);
  } else if (type === 'jackets') {
    clothes.jackets.push(item);
  } else if (type === 'pants') {
    clothes.pants.push(item);
  } else if (type === 'shades') {
    clothes.shades.push(item);
  } else if (type === 'shirt' || type === 'shirts') {
    clothes.shirts.push(item);
  } else if (type === 'shoes') {
    clothes.shoes.push(item);
  } else if (type === 'skirt' || type === 'skirts') {
    clothes.skirts.push(item);
  } else if (type === 'underwear') {
    clothes.underwear.push(item);
  } else {
    // Everything else goes to other category
    clothes.other.push(item);
  }
}

function categorizeBlueprint(item, blueprints) {
  const type = item.Properties?.Type?.toLowerCase() || '';
  
  if (type === 'mechanical component') {
    blueprints.mechanical_component.push(item);
  } else if (type === 'electrical component') {
    blueprints.electrical_component.push(item);
  } else if (type === 'metal component') {
    blueprints.metal_component.push(item);
  } else if (type === 'textile') {
    blueprints.textile.push(item);
  } else if (type === 'furniture') {
    blueprints.furniture.push(item);
  } else if (type === 'weapon') {
    blueprints.weapon.push(item);
  } else if (type === 'attachment') {
    blueprints.attachment.push(item);
  } else if (type === 'vehicle') {
    blueprints.vehicle.push(item);
  } else {
    // Everything else goes to other category
    blueprints.other.push(item);
  }
}

function categorizeMaterial(item, materials) {
  const type = item.Properties?.Type?.toLowerCase() || '';
  const name = item.Name?.toLowerCase() || '';
  
  // Leather: All leather, textile and wool that are natural materials
  if (type === 'texture leathers' || type === 'tailoring materials') {
    materials.leather.push(item);
  }
  // Timber: Any kind of wood, veneer etc.
  else if (type === 'wood' || type === 'wood component') {
    materials.timber.push(item);
  }
  // Fragments: Nova and Blazar Fragments (check exact fragment names)
  else if (type === 'fragment' || name === 'nova fragment' || name === 'blazar fragment') {
    materials.fragments.push(item);
  }
  // Forageables: fruit, stone and dung mostly, also broken elysian chips
  else if (type === 'food') {
    materials.forageables.push(item);
  }
  // Extractors: All of them should have it in their name but try to check for type over name where possible
  else if (type === 'texture extractor') {
    materials.extractors.push(item);
  }
  // Animal Oils: Based on type
  else if (type === 'animal oils') {
    materials.animal_oils.push(item);
  }
  // Robot Parts: Based on type
  else if (type === 'robot parts' || type === 'robot component') {
    materials.robot_parts.push(item);
  }
  // Ores: raw and refined
  else if (type === 'ore') {
    materials.ores.raw.push(item);
  }
  else if (type === 'refined ore') {
    materials.ores.refined.push(item);
  }
  // Enmatter: raw and refined
  else if (type === 'enmatter') {
    materials.enmatter.raw.push(item);
  }
  else if (type === 'refined enmatter') {
    materials.enmatter.refined.push(item);
  }
  // Treasure: raw and refined
  else if (type === 'treasure') {
    materials.treasure.raw.push(item);
  }
  else if (type === 'refined treasure') {
    materials.treasure.refined.push(item);
  }
  // Looted components: All naturally dropped components (enhancer, tier, socket components)
  else if (type === 'enhancer component') {
    materials.looted_components.push(item);
  }
  // Crafted components: Non-looted components
  else if (type === 'mechanical component' || type === 'electronic component' || type === 'metal component' || type === 'generic component') {
    materials.crafted_components.push(item);
  }
  // Designing: textures, paint cans and beauty products (with sub-categories)
  else if (type === 'texture material') {
    materials.designing.textures.push(item);
  }
  else if (type === 'paint cans') {
    materials.designing.paint_cans.push(item);
  }
  else if (type === 'beauty' || type === 'make up') {
    materials.designing.beauty_products.push(item);
  }
  // Natural materials that are forageables (specific items)
  else if (type === 'natural materials') {
    materials.forageables.push(item);
  }
  // Special cases for materials with specific types
  else if (type === 'crystal' || type === 'precious stones') {
    materials.other.push(item);
  }
  else if (type === 'dna') {
    materials.other.push(item);
  }
  else if (type === 'skulls') {
    materials.other.push(item);
  }
  else if (type === 'residue') {
    materials.other.push(item);
  }
  else if (type === 'material' || type === 'refined material') {
    materials.other.push(item);
  }
  // Everything else goes to other category
  else {
    materials.other.push(item);
  }
}
