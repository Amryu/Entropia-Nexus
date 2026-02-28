// @ts-nocheck
/**
 * Shared utility functions for service calculations
 */

/**
 * Calculate reload speed bonus from primary equipment (healing-specific)
 * Clothing + Armor: capped at 15%
 * Consumables (non-enhancers): capped at 20%
 * Total: capped at 30%
 * @param {object} enabledConsumables - Map of consumable names to enabled state
 */
export function getHealingReloadSpeedBonus(service, clothingItems, armorSets, consumables, enabledConsumables = {}) {
  if (!service.equipment) return { equipment: 0, consumables: 0, total: 0 };
  
  let equipmentBonus = 0;
  let consumableBonus = 0;
  const primaryEquipment = service.equipment.filter(e => e.is_primary);
  const allConsumables = service.equipment.filter(e => e.item_type === 'consumables');
  
  for (const equip of primaryEquipment) {
    // Check clothing for reload speed effects
    if (equip.item_type === 'clothings' && equip.item_name) {
      const clothingItem = clothingItems.find(item => item.Name === equip.item_name);
      if (clothingItem?.EffectsOnEquip) {
        for (const effect of clothingItem.EffectsOnEquip) {
          if (effect.Name === 'Reload Speed Increased') {
            equipmentBonus += parseFloat(effect.Values?.Strength) || 0;
          }
        }
      }
    }
    
    // Check armor sets for reload speed effects
    if (equip.item_type === 'armorsets' && equip.item_name) {
      const armorSet = armorSets.find(item => item.Name === equip.item_name);
      if (armorSet?.EffectsOnSetEquip) {
        for (const effect of armorSet.EffectsOnSetEquip) {
          if (effect.Name === 'Reload Speed Increased') {
            equipmentBonus += parseFloat(effect.Values?.Strength) || 0;
          }
        }
      }
    }
  }
  
  // Check enabled consumables for reload speed effects (excluding enhancers)
  // Consumables don't stack - only the strongest effect applies
  let strongestConsumableBonus = 0;
  for (const equip of allConsumables) {
    if (equip.item_name && enabledConsumables[equip.item_name]) {
      const consumable = consumables.find(item => item.Name === equip.item_name);
      if (consumable?.EffectsOnConsume) {
        const isEnhancer = consumable.Properties?.Type === 'Enhancer';
        
        // Skip enhancers - they affect heal amount, not reload speed
        if (!isEnhancer) {
          for (const effect of consumable.EffectsOnConsume) {
            if (effect.Name === 'Reload Speed Increased') {
              const effectStrength = parseFloat(effect.Values?.Strength) || 0;
              strongestConsumableBonus = Math.max(strongestConsumableBonus, effectStrength);
            }
          }
        }
      }
    }
  }
  consumableBonus = strongestConsumableBonus;
  
  // Apply caps
  equipmentBonus = Math.min(equipmentBonus, 15); // Equipment cap: 15%
  consumableBonus = Math.min(consumableBonus, 20); // Consumable cap: 20%
  const totalBonus = Math.min(equipmentBonus + consumableBonus, 30); // Total cap: 30%
  
  return { 
    equipment: equipmentBonus, 
    consumables: consumableBonus, 
    total: totalBonus 
  };
}

/**
 * Calculate heal amount bonus from enhancers (healing-specific)
 * Enhancers boost the base healing value multiplicatively with reload speed
 * Consumable enhancers don't stack - only strongest applies
 * @param {object} enabledTierEnhancers - Map of equipment names to tier enhancer enabled state
 */
export function getHealingEnhancerBonus(service, consumables, enabledConsumables = {}, enabledTierEnhancers = {}) {
  if (!service.equipment) return 0;
  
  // Consumable enhancers don't stack - only strongest applies
  let strongestEnhancerBonus = 0;
  const allConsumables = service.equipment.filter(e => e.item_type === 'consumables');
  
  for (const equip of allConsumables) {
    if (equip.item_name && enabledConsumables[equip.item_name]) {
      const consumable = consumables.find(item => item.Name === equip.item_name);
      if (consumable?.EffectsOnConsume && consumable.Properties?.Type === 'Enhancer') {
        for (const effect of consumable.EffectsOnConsume) {
          // Enhancers typically boost "Healing" or similar effects
          if (effect.Name === 'Healing' || effect.Name === 'Healing Increased') {
            const effectStrength = parseFloat(effect.Values?.Strength) || 0;
            strongestEnhancerBonus = Math.max(strongestEnhancerBonus, effectStrength);
          }
        }
      }
    }
  }
  
  return strongestEnhancerBonus;
}

/**
 * Calculate estimated HPS (Healing Per Second) for healing services
 * Enhancers boost heal amount, reload speed consumables boost frequency
 * Both interact multiplicatively
 * Tiers provide same multiplier as tier-count enhancers (5% per tier)
 */
export function getEstimatedHealingHPS(service, medicalTools, medicalChips, clothingItems, armorSets, consumables, activeMedical = null, enabledConsumables = {}, enabledTierEnhancers = {}) {
  if (!service.equipment) return { base: 'TBD', buffed: 'TBD' };
  
  // Use provided active medical or find primary medical tool or chip
  const primaryMedical = activeMedical || service.equipment.find(e => 
    e.is_primary && (e.item_type === 'medicaltools' || e.item_type === 'medicalchips')
  );
  
  if (!primaryMedical) return { base: 'TBD', buffed: 'TBD' };
  
  // Look up the tool/chip data
  const allMedicalItems = [...medicalTools, ...medicalChips];
  const medicalItem = allMedicalItems.find(item => item.Name === primaryMedical.item_name);
  
  if (!medicalItem?.Properties) return { base: 'TBD', buffed: 'TBD' };
  
  // Get heal interval (average of min and max)
  const minHeal = medicalItem.Properties.MinHeal || 0;
  const maxHeal = medicalItem.Properties.MaxHeal || 0;
  const avgHeal = (minHeal + maxHeal) / 2;
  
  // Get uses per minute (this is the reload speed)
  const usesPerMinute = medicalItem.Properties.UsesPerMinute || 0;
  if (usesPerMinute === 0) return { base: 'TBD', buffed: 'TBD' };
  
  // Apply tier bonus only if tier enhancers are enabled: 5% per tier (additive)
  const tier = primaryMedical.tier || 0;
  const tierEnabled = enabledTierEnhancers[primaryMedical.item_name] !== false;
  const tierMultiplier = (tierEnabled && tier > 0) ? (1 + (tier * 0.05)) : 1;
  
  // Get reload speed bonus (from equipment and consumables, excluding enhancers)
  const reloadBonus = getHealingReloadSpeedBonus(service, clothingItems, armorSets, consumables, enabledConsumables);
  const reloadMultiplier = 1 + (reloadBonus.total / 100);
  
  // Get heal amount bonus from enhancers (consumable enhancers only - strongest applies)
  const enhancerBonus = getHealingEnhancerBonus(service, consumables, enabledConsumables, enabledTierEnhancers);
  const healMultiplier = 1 + (enhancerBonus / 100);
  
  // Calculate HPS: (base heal * heal multiplier) * (uses per minute / 60) * tier multiplier * reload multiplier
  // Enhancers affect heal amount, reload affects frequency - they multiply together
  const baseHPS = avgHeal * healMultiplier * (usesPerMinute / 60);
  const hpsValue = Math.round(baseHPS * tierMultiplier * reloadMultiplier);
  
  return { base: hpsValue, buffed: hpsValue };
}

/**
 * Calculate maximum decay per hour for healing services
 * More uses per hour (from reload speed) = more decay
 * Tiers increase uses per hour if enabled
 */
export function getMaxHealingDecayPerHour(service, medicalTools, medicalChips, clothingItems, armorSets, consumables, activeMedical = null, enabledConsumables = {}, enabledTierEnhancers = {}) {
  if (!service.equipment) return { base: 'TBD', buffed: 'TBD' };
  
  // Use provided active medical or find primary medical tool or chip
  const primaryMedical = activeMedical || service.equipment.find(e => 
    e.is_primary && (e.item_type === 'medicaltools' || e.item_type === 'medicalchips')
  );
  
  if (!primaryMedical) return { base: 'TBD', buffed: 'TBD' };
  
  // Look up the tool/chip data
  const allMedicalItems = [...medicalTools, ...medicalChips];
  const medicalItem = allMedicalItems.find(item => item.Name === primaryMedical.item_name);
  
  if (!medicalItem?.Properties?.Economy?.Decay) return { base: 'TBD', buffed: 'TBD' };
  
  // Get decay in PEC per use
  const decayPerUse = medicalItem.Properties.Economy.Decay;
  
  // Get uses per minute
  const usesPerMinute = medicalItem.Properties.UsesPerMinute || 0;
  if (usesPerMinute === 0) return { base: 'TBD', buffed: 'TBD' };
  
  // Calculate base decay per hour in PEC
  const baseDecayPerHour = decayPerUse * usesPerMinute * 60;
  
  // Apply tier bonus only if tier enhancers are enabled: 5% per tier (additive) - more uses = more decay
  const tier = primaryMedical.tier || 0;
  const tierEnabled = enabledTierEnhancers[primaryMedical.item_name] !== false;
  const tierMultiplier = (tierEnabled && tier > 0) ? (1 + (tier * 0.05)) : 1;
  
  // Get reload speed bonus (affects frequency of use, thus decay)
  const reloadBonus = getHealingReloadSpeedBonus(service, clothingItems, armorSets, consumables, enabledConsumables);
  const reloadMultiplier = 1 + (reloadBonus.total / 100);
  
  // Calculate decay (enhancers don't affect decay, only reload speed does)
  const decayPEC = baseDecayPerHour * tierMultiplier * reloadMultiplier;
  let costPED = decayPEC / 100;
  
  // Add ammo cost if applicable (medical chips use ammo)
  if (medicalItem.Properties.Economy.AmmoBurn) {
    const ammoBurnPerUse = medicalItem.Properties.Economy.AmmoBurn;
    const ammoBurn = ammoBurnPerUse * usesPerMinute * 60 * tierMultiplier * reloadMultiplier;
    // 1 ammo = 0.0001 PED
    costPED += ammoBurn * 0.0001;
  }
  
  return { base: costPED.toFixed(2), buffed: costPED.toFixed(2) };
}

/**
 * Get appropriate cost label for healing services (Cost/h if uses ammo, Decay/h if not)
 */
export function getHealingCostLabel(service, medicalTools, medicalChips) {
  if (!service.equipment) return 'Max Decay/h';
  
  const primaryMedical = service.equipment.find(e => 
    e.is_primary && (e.item_type === 'medicaltools' || e.item_type === 'medicalchips')
  );
  
  if (!primaryMedical) return 'Max Decay/h';
  
  const allMedicalItems = [...medicalTools, ...medicalChips];
  const medicalItem = allMedicalItems.find(item => item.Name === primaryMedical.item_name);
  
  if (medicalItem?.Properties?.Economy?.AmmoBurn) {
    return 'Maximum Cost/h';
  }
  
  return 'Maximum Decay/h';
}

/**
 * Helper to get clothing slot from preloaded clothing items
 */
export function getClothingSlot(itemName, clothingItems) {
  if (!itemName || !clothingItems.length) return null;
  const clothingItem = clothingItems.find(item => item.Name === itemName);
  if (clothingItem?.Properties?.Slot) {
    return clothingItem.Properties.Slot.toLowerCase().replace(/\s+/g, '_');
  }
  return null;
}

/**
 * Get location display string for a service
 * @param {object} service - Service object with planet_id, planet_name, willing_to_travel, travel_fee
 * @param {array} planets - Array of planet objects with Id and Name
 * @returns {string} Formatted location string
 */
export function getLocationDisplay(service, planets = []) {
  // For transportation services, show current ship location
  if (service.type === 'transportation' && service.transportation_details) {
    const currentPlanetId = service.transportation_details.current_planet_id;
    if (currentPlanetId && planets.length > 0) {
      const planet = planets.find(p => p.Id === currentPlanetId);
      if (planet) {
        return `Currently at ${planet.Name}`;
      }
    }
    return 'Location not set';
  }

  // For other services, use base planet
  let planetName = service.planet_name;

  // If not available, look it up from planets array
  if (!planetName && service.planet_id && planets.length > 0) {
    const planet = planets.find(p => p.Id === service.planet_id);
    if (planet) {
      planetName = planet.Name;
    }
  }

  const basePlanet = planetName || 'No base';

  if (service.willing_to_travel) {
    if (service.travel_fee) {
      return `${basePlanet} (willing to travel - ${parseFloat(service.travel_fee).toFixed(2)} PED fee)`;
    }
    return `${basePlanet} (will travel)`;
  }

  return basePlanet;
}

/* ============================================
 * DPS SERVICE CALCULATIONS
 * ============================================ */

import * as LoadoutCalc from '$lib/utils/loadoutCalculations.js';

/**
 * Calculate reload speed bonus for DPS services
 * Unlike healing, DPS doesn't filter effects - ALL reload speed effects apply
 * Equipment: no specific cap mentioned
 * Consumables: no specific cap mentioned
 * @param {object} service - Service object with equipment array
 * @param {array} clothingItems - All clothing items
 * @param {array} armorSets - All armor sets
 * @param {array} consumables - All consumables
 * @param {object} pets - All pets
 * @param {object} enabledConsumables - Map of consumable names to enabled state
 * @param {object} activePetEffects - Map of pet effect names to enabled state
 * @returns {object} { equipment: number, consumables: number, pets: number, total: number }
 */
export function getDPSReloadSpeedBonus(service, clothingItems, armorSets, consumables, pets, enabledConsumables = {}, activePetEffects = {}) {
  if (!service.equipment) return { equipment: 0, consumables: 0, pets: 0, total: 0 };
  
  let equipmentBonus = 0;
  let consumableBonus = 0;
  let petBonus = 0;
  
  const primaryEquipment = service.equipment.filter(e => e.is_primary);
  const allConsumables = service.equipment.filter(e => e.item_type === 'consumables');
  const allPets = service.equipment.filter(e => e.item_type === 'pets');
  
  // Check equipment for reload speed effects
  for (const equip of primaryEquipment) {
    // Check clothing
    if (equip.item_type === 'clothings' && equip.item_name) {
      const clothingItem = clothingItems.find(item => item.Name === equip.item_name);
      if (clothingItem?.EffectsOnEquip) {
        for (const effect of clothingItem.EffectsOnEquip) {
          if (effect.Name === 'Reload Speed Increased') {
            equipmentBonus += parseFloat(effect.Values?.Strength) || 0;
          }
        }
      }
    }
    
    // Check armor sets
    if (equip.item_type === 'armorsets' && equip.item_name) {
      const armorSet = armorSets.find(item => item.Name === equip.item_name);
      if (armorSet?.EffectsOnSetEquip) {
        for (const effect of armorSet.EffectsOnSetEquip) {
          if (effect.Name === 'Reload Speed Increased') {
            equipmentBonus += parseFloat(effect.Values?.Strength) || 0;
          }
        }
      }
    }
  }
  
  // Check enabled consumables (consumables don't stack - strongest applies)
  let strongestConsumableBonus = 0;
  for (const equip of allConsumables) {
    if (equip.item_name && enabledConsumables[equip.item_name]) {
      const consumable = consumables.find(item => item.Name === equip.item_name);
      if (consumable?.EffectsOnConsume) {
        for (const effect of consumable.EffectsOnConsume) {
          if (effect.Name === 'Reload Speed Increased') {
            const effectStrength = parseFloat(effect.Values?.Strength) || 0;
            strongestConsumableBonus = Math.max(strongestConsumableBonus, effectStrength);
          }
        }
      }
    }
  }
  consumableBonus = strongestConsumableBonus;
  
  // Check active pet effects (only one pet can be active at a time)
  for (const equip of allPets) {
    const activeAbilityKey = activePetEffects[equip.item_name];
    if (equip.item_name && activeAbilityKey) {
      const pet = pets.find(item => item.Name === equip.item_name);
      if (pet?.Effects) {
        const activeEffect = pet.Effects.find((e, i) => {
          const key = `${e.Id}-${e.Properties?.Strength || 0}-${i}`;
          return key === activeAbilityKey;
        });
        if (activeEffect && (activeEffect.Name === 'Reload Speed Increased' || activeEffect.Name === 'Reload Speed Added')) {
          petBonus += parseFloat(activeEffect.Properties?.Strength) || 0;
        }
      }
    }
  }
  
  const totalBonus = equipmentBonus + consumableBonus + petBonus;
  
  return { 
    equipment: equipmentBonus, 
    consumables: consumableBonus,
    pets: petBonus,
    total: totalBonus 
  };
}

/**
 * Calculate damage bonus from consumables and pets for DPS services
 * Consumables don't stack - strongest applies
 * @param {object} service - Service object with equipment array
 * @param {array} consumables - All consumables
 * @param {array} pets - All pets
 * @param {object} enabledConsumables - Map of consumable names to enabled state
 * @param {object} activePetEffects - Map of pet effect names to enabled state
 * @returns {object} { consumables: number, pets: number, total: number }
 */
export function getDPSDamageBonus(service, consumables, pets, enabledConsumables = {}, activePetEffects = {}) {
  if (!service.equipment) return { consumables: 0, pets: 0, total: 0 };
  
  let consumableBonus = 0;
  let petBonus = 0;
  
  const allConsumables = service.equipment.filter(e => e.item_type === 'consumables');
  const allPets = service.equipment.filter(e => e.item_type === 'pets');
  
  // Check enabled consumables (strongest applies)
  let strongestConsumableBonus = 0;
  for (const equip of allConsumables) {
    if (equip.item_name && enabledConsumables[equip.item_name]) {
      const consumable = consumables.find(item => item.Name === equip.item_name);
      if (consumable?.EffectsOnConsume) {
        for (const effect of consumable.EffectsOnConsume) {
          if (effect.Name === 'Damage Done Increased') {
            const effectStrength = parseFloat(effect.Values?.Strength) || 0;
            strongestConsumableBonus = Math.max(strongestConsumableBonus, effectStrength);
          }
        }
      }
    }
  }
  consumableBonus = strongestConsumableBonus;
  
  // Check active pet effects
  for (const equip of allPets) {
    const activeAbilityKey = activePetEffects[equip.item_name];
    if (equip.item_name && activeAbilityKey) {
      const pet = pets.find(item => item.Name === equip.item_name);
      if (pet?.Effects) {
        const activeEffect = pet.Effects.find((e, i) => {
          const key = `${e.Id}-${e.Properties?.Strength || 0}-${i}`;
          return key === activeAbilityKey;
        });
        if (activeEffect && (activeEffect.Name === 'Damage Done Increased' || activeEffect.Name === 'Damage Added')) {
          petBonus += parseFloat(activeEffect.Properties?.Strength) || 0;
        }
      }
    }
  }
  
  const totalBonus = consumableBonus + petBonus;
  
  return { 
    consumables: consumableBonus,
    pets: petBonus,
    total: totalBonus 
  };
}

/**
 * Calculate critical chance bonus from equipment, consumables, and pets for DPS services
 * @param {object} service - Service object with equipment array
 * @param {array} clothingItems - All clothing items
 * @param {array} armorSets - All armor sets
 * @param {array} consumables - All consumables
 * @param {array} pets - All pets
 * @param {object} enabledConsumables - Map of consumable names to enabled state
 * @param {object} activePetEffects - Map of pet effect names to enabled state
 * @returns {object} { equipment: number, consumables: number, pets: number, total: number }
 */
export function getDPSCritChanceBonus(service, clothingItems, armorSets, consumables, pets, enabledConsumables = {}, activePetEffects = {}) {
  if (!service.equipment) return { equipment: 0, consumables: 0, pets: 0, total: 0 };
  
  let equipmentBonus = 0;
  let consumableBonus = 0;
  let petBonus = 0;
  
  const primaryEquipment = service.equipment.filter(e => e.is_primary);
  const allConsumables = service.equipment.filter(e => e.item_type === 'consumables');
  const allPets = service.equipment.filter(e => e.item_type === 'pets');
  
  // Check equipment
  for (const equip of primaryEquipment) {
    if (equip.item_type === 'clothings' && equip.item_name) {
      const clothingItem = clothingItems.find(item => item.Name === equip.item_name);
      if (clothingItem?.EffectsOnEquip) {
        for (const effect of clothingItem.EffectsOnEquip) {
          if (effect.Name === 'Critical Chance Increased' || effect.Name === 'Critical Chance Added') {
            equipmentBonus += parseFloat(effect.Values?.Strength) || 0;
          }
        }
      }
    }
    
    if (equip.item_type === 'armorsets' && equip.item_name) {
      const armorSet = armorSets.find(item => item.Name === equip.item_name);
      if (armorSet?.EffectsOnSetEquip) {
        for (const effect of armorSet.EffectsOnSetEquip) {
          if (effect.Name === 'Critical Chance Increased' || effect.Name === 'Critical Chance Added') {
            equipmentBonus += parseFloat(effect.Values?.Strength) || 0;
          }
        }
      }
    }
  }
  
  // Check consumables (strongest applies)
  let strongestConsumableBonus = 0;
  for (const equip of allConsumables) {
    if (equip.item_name && enabledConsumables[equip.item_name]) {
      const consumable = consumables.find(item => item.Name === equip.item_name);
      if (consumable?.EffectsOnConsume) {
        for (const effect of consumable.EffectsOnConsume) {
          if (effect.Name === 'Critical Chance Increased' || effect.Name === 'Critical Chance Added') {
            const effectStrength = parseFloat(effect.Values?.Strength) || 0;
            strongestConsumableBonus = Math.max(strongestConsumableBonus, effectStrength);
          }
        }
      }
    }
  }
  consumableBonus = strongestConsumableBonus;
  
  // Check pets
  for (const equip of allPets) {
    const activeAbilityKey = activePetEffects[equip.item_name];
    if (equip.item_name && activeAbilityKey) {
      const pet = pets.find(item => item.Name === equip.item_name);
      if (pet?.Effects) {
        const activeEffect = pet.Effects.find((e, i) => {
          const key = `${e.Id}-${e.Properties?.Strength || 0}-${i}`;
          return key === activeAbilityKey;
        });
        if (activeEffect && (activeEffect.Name === 'Critical Chance Increased' || activeEffect.Name === 'Critical Chance Added')) {
          petBonus += parseFloat(activeEffect.Properties?.Strength) || 0;
        }
      }
    }
  }
  
  const totalBonus = equipmentBonus + consumableBonus + petBonus;
  
  return { 
    equipment: equipmentBonus, 
    consumables: consumableBonus,
    pets: petBonus,
    total: totalBonus 
  };
}

/**
 * Calculate critical damage bonus from equipment, consumables, and pets for DPS services
 * @param {object} service - Service object with equipment array
 * @param {array} clothingItems - All clothing items
 * @param {array} armorSets - All armor sets
 * @param {array} consumables - All consumables
 * @param {array} pets - All pets
 * @param {object} enabledConsumables - Map of consumable names to enabled state
 * @param {object} activePetEffects - Map of pet effect names to enabled state
 * @returns {object} { equipment: number, consumables: number, pets: number, total: number }
 */
export function getDPSCritDamageBonus(service, clothingItems, armorSets, consumables, pets, enabledConsumables = {}, activePetEffects = {}) {
  if (!service.equipment) return { equipment: 0, consumables: 0, pets: 0, total: 0 };
  
  let equipmentBonus = 0;
  let consumableBonus = 0;
  let petBonus = 0;
  
  const primaryEquipment = service.equipment.filter(e => e.is_primary);
  const allConsumables = service.equipment.filter(e => e.item_type === 'consumables');
  const allPets = service.equipment.filter(e => e.item_type === 'pets');
  
  // Check equipment
  for (const equip of primaryEquipment) {
    if (equip.item_type === 'clothings' && equip.item_name) {
      const clothingItem = clothingItems.find(item => item.Name === equip.item_name);
      if (clothingItem?.EffectsOnEquip) {
        for (const effect of clothingItem.EffectsOnEquip) {
          if (effect.Name === 'Critical Damage Increased' || effect.Name === 'Critical Damage Added') {
            equipmentBonus += parseFloat(effect.Values?.Strength) || 0;
          }
        }
      }
    }
    
    if (equip.item_type === 'armorsets' && equip.item_name) {
      const armorSet = armorSets.find(item => item.Name === equip.item_name);
      if (armorSet?.EffectsOnSetEquip) {
        for (const effect of armorSet.EffectsOnSetEquip) {
          if (effect.Name === 'Critical Damage Increased' || effect.Name === 'Critical Damage Added') {
            equipmentBonus += parseFloat(effect.Values?.Strength) || 0;
          }
        }
      }
    }
  }
  
  // Check consumables (strongest applies)
  let strongestConsumableBonus = 0;
  for (const equip of allConsumables) {
    if (equip.item_name && enabledConsumables[equip.item_name]) {
      const consumable = consumables.find(item => item.Name === equip.item_name);
      if (consumable?.EffectsOnConsume) {
        for (const effect of consumable.EffectsOnConsume) {
          if (effect.Name === 'Critical Damage Increased' || effect.Name === 'Critical Damage Added') {
            const effectStrength = parseFloat(effect.Values?.Strength) || 0;
            strongestConsumableBonus = Math.max(strongestConsumableBonus, effectStrength);
          }
        }
      }
    }
  }
  consumableBonus = strongestConsumableBonus;
  
  // Check pets
  for (const equip of allPets) {
    const activeAbilityKey = activePetEffects[equip.item_name];
    if (equip.item_name && activeAbilityKey) {
      const pet = pets.find(item => item.Name === equip.item_name);
      if (pet?.Effects) {
        const activeEffect = pet.Effects.find((e, i) => {
          const key = `${e.Id}-${e.Properties?.Strength || 0}-${i}`;
          return key === activeAbilityKey;
        });
        if (activeEffect && (activeEffect.Name === 'Critical Damage Increased' || activeEffect.Name === 'Critical Damage Added')) {
          petBonus += parseFloat(activeEffect.Properties?.Strength) || 0;
        }
      }
    }
  }
  
  const totalBonus = equipmentBonus + consumableBonus + petBonus;
  
  return { 
    equipment: equipmentBonus, 
    consumables: consumableBonus,
    pets: petBonus,
    total: totalBonus 
  };
}

/**
 * Calculate total HP from base HP and equipment/consumable/pet effects
 * @param {number} baseHP - Player's configured base HP
 * @param {object} service - Service object with equipment array
 * @param {array} clothingItems - All clothing items
 * @param {array} armorSets - All armor sets
 * @param {array} consumables - All consumables
 * @param {array} pets - All pets
 * @param {object} enabledConsumables - Map of consumable names to enabled state
 * @param {object} activePetEffects - Map of pet effect names to enabled state
 * @returns {object} { equipment: number, consumables: number, pets: number, total: number }
 */
export function getTotalHP(baseHP, service, clothingItems, armorSets, consumables, pets, enabledConsumables = {}, activePetEffects = {}) {
  if (!service.equipment) return { equipment: 0, consumables: 0, pets: 0, total: baseHP };
  
  let equipmentBonus = 0;
  let consumableBonus = 0;
  let petBonus = 0;
  
  const primaryEquipment = service.equipment.filter(e => e.is_primary);
  const allConsumables = service.equipment.filter(e => e.item_type === 'consumables');
  const allPets = service.equipment.filter(e => e.item_type === 'pets');
  
  // Check equipment
  for (const equip of primaryEquipment) {
    if (equip.item_type === 'clothings' && equip.item_name) {
      const clothingItem = clothingItems.find(item => item.Name === equip.item_name);
      if (clothingItem?.EffectsOnEquip) {
        for (const effect of clothingItem.EffectsOnEquip) {
          if (effect.Name === 'Health Increased' || effect.Name === 'Health Added') {
            equipmentBonus += parseFloat(effect.Values?.Strength) || 0;
          }
        }
      }
    }
    
    if (equip.item_type === 'armorsets' && equip.item_name) {
      const armorSet = armorSets.find(item => item.Name === equip.item_name);
      if (armorSet?.EffectsOnSetEquip) {
        for (const effect of armorSet.EffectsOnSetEquip) {
          if (effect.Name === 'Health Increased' || effect.Name === 'Health Added') {
            equipmentBonus += parseFloat(effect.Values?.Strength) || 0;
          }
        }
      }
    }
  }
  
  // Check enabled consumables (strongest applies)
  let strongestConsumableBonus = 0;
  for (const equip of allConsumables) {
    if (equip.item_name && enabledConsumables[equip.item_name]) {
      const consumable = consumables.find(item => item.Name === equip.item_name);
      if (consumable?.EffectsOnConsume) {
        for (const effect of consumable.EffectsOnConsume) {
          if (effect.Name === 'Health Increased' || effect.Name === 'Health Added') {
            const effectStrength = parseFloat(effect.Values?.Strength) || 0;
            strongestConsumableBonus = Math.max(strongestConsumableBonus, effectStrength);
          }
        }
      }
    }
  }
  consumableBonus = strongestConsumableBonus;
  
  // Check active pet effects
  for (const equip of allPets) {
    const activeAbilityKey = activePetEffects[equip.item_name];
    if (equip.item_name && activeAbilityKey) {
      const pet = pets.find(item => item.Name === equip.item_name);
      if (pet?.Effects) {
        const activeEffect = pet.Effects.find((e, i) => {
          const key = `${e.Id}-${e.Properties?.Strength || 0}-${i}`;
          return key === activeAbilityKey;
        });
        if (activeEffect && (activeEffect.Name === 'Health Increased' || activeEffect.Name === 'Health Added')) {
          petBonus += parseFloat(activeEffect.Properties?.Strength) || 0;
        }
      }
    }
  }
  
  const totalHP = baseHP + equipmentBonus + consumableBonus + petBonus;
  
  return { 
    equipment: equipmentBonus, 
    consumables: consumableBonus,
    pets: petBonus,
    total: totalHP 
  };
}

/**
 * Calculate protection stats from armor
 * Returns defense and absorption for all damage types plus block chance
 * @param {object} service - Service object with equipment array
 * @param {array} armors - All armor items
 * @param {array} armorPlatings - All armor plating items
 * @param {array} defenseEnhancers - Defense tier enhancers
 * @param {array} durabilityEnhancers - Durability tier enhancers
 * @param {object} enabledDefenseEnhancers - Map of armor pieces to defense enhancer enabled state
 * @param {object} enabledDurabilityEnhancers - Map of armor pieces to durability enhancer enabled state
 * @returns {object} Protection stats by damage type plus block chance
 */
export function getProtectionStats(service, armors, armorPlatings, defenseEnhancers, durabilityEnhancers, enabledDefenseEnhancers = {}, enabledDurabilityEnhancers = {}) {
  if (!service.equipment) {
    return {
      burn: { defense: 0, absorption: 0 },
      cold: { defense: 0, absorption: 0 },
      acid: { defense: 0, absorption: 0 },
      electric: { defense: 0, absorption: 0 },
      cut: { defense: 0, absorption: 0 },
      impact: { defense: 0, absorption: 0 },
      penetration: { defense: 0, absorption: 0 },
      shrapnel: { defense: 0, absorption: 0 },
      stab: { defense: 0, absorption: 0 },
      blockChance: 0
    };
  }
  
  // Get armor pieces and platings from service equipment
  const armorEquipment = service.equipment.filter(e => e.item_type === 'armors');
  const platingEquipment = service.equipment.filter(e => e.item_type === 'armorplatings');
  
  // Build armor pieces array for calculations
  const armorPieces = armorEquipment
    .map(equip => {
      const armor = armors.find(a => a.Name === equip.item_name);
      if (!armor) return null;
      
      return {
        ...armor,
        tier: equip.tier || 0
      };
    })
    .filter(Boolean);
  
  // Build plating pieces array
  const platePieces = platingEquipment
    .map(equip => {
      const plating = armorPlatings.find(p => p.Name === equip.item_name);
      if (!plating) return null;
      
      return {
        ...plating,
        tier: equip.tier || 0
      };
    })
    .filter(Boolean);
  
  // TODO: Apply enabled enhancers - for now pass empty arrays
  const defenseEnhancerArray = [];
  const durabilityEnhancerArray = [];
  
  // Calculate defense for each damage type
  const armorDefense = LoadoutCalc.calculateArmorDefense(armorPieces, defenseEnhancerArray);
  const plateDefense = LoadoutCalc.calculatePlateDefense(platePieces);
  const totalDefense = LoadoutCalc.calculateTotalDefense(armorDefense, plateDefense);
  
  // Calculate absorption
  const totalAbsorption = LoadoutCalc.calculateTotalAbsorption(
    armorPieces, 
    platePieces, 
    defenseEnhancerArray, 
    durabilityEnhancerArray
  );
  
  // Calculate block chance
  const blockChance = LoadoutCalc.calculateBlockChance(platePieces);
  
  // Build result object
  const result = {
    burn: { defense: totalDefense.Burn || 0, absorption: totalAbsorption.Burn || 0 },
    cold: { defense: totalDefense.Cold || 0, absorption: totalAbsorption.Cold || 0 },
    acid: { defense: totalDefense.Acid || 0, absorption: totalAbsorption.Acid || 0 },
    electric: { defense: totalDefense.Electric || 0, absorption: totalAbsorption.Electric || 0 },
    cut: { defense: totalDefense.Cut || 0, absorption: totalDefense.Cut || 0 },
    impact: { defense: totalDefense.Impact || 0, absorption: totalDefense.Impact || 0 },
    penetration: { defense: totalDefense.Penetration || 0, absorption: totalDefense.Penetration || 0 },
    shrapnel: { defense: totalDefense.Shrapnel || 0, absorption: totalDefense.Shrapnel || 0 },
    stab: { defense: totalDefense.Stab || 0, absorption: totalDefense.Stab || 0 },
    blockChance: blockChance
  };
  
  return result;
}

/**
 * Calculate estimated DPS using loadout calculations
 * @param {object} service - Service object
 * @param {object} weapon - Active weapon
 * @param {object} attachments - Weapon attachments { amplifier, absorber, scope, sight, matrix, implant }
 * @param {string} enhancerType - 'Damage', 'Accuracy', or 'Economy'
 * @param {array} enhancerTiers - Array of tier levels enabled
 * @param {array} consumables - All consumables
 * @param {array} pets - All pets
 * @param {array} clothingItems - All clothing items
 * @param {array} armorSets - All armor sets
 * @param {object} enabledConsumables - Map of consumable names to enabled state
 * @param {object} activePetEffects - Map of pet effect names to enabled state
 * @returns {number} DPS value
 */
export function getEstimatedDPS(service, weapon, attachments, enhancerType, enhancerTiers, consumables, pets, clothingItems, armorSets, enabledConsumables = {}, activePetEffects = {}) {
  if (!weapon) return 0;
  
  // Get damage bonuses from consumables/pets
  const damageBonus = getDPSDamageBonus(service, consumables, pets, enabledConsumables, activePetEffects);
  
  // Calculate total damage with enhancers
  // enhancerTiers is an array of tier levels (e.g., [1,2,3,4,5,6,7,8,9,10])
  // Count them for the calculation
  const damageEnhancers = enhancerType === 'Damage' ? enhancerTiers.length : 0;
  const totalDamage = LoadoutCalc.calculateTotalDamage(
    weapon,
    damageEnhancers,
    damageBonus.total,
    attachments.amplifier
  );
  
  if (totalDamage == null) return 0;
  
  // Get weapon skill data (TODO: get from player profile or service)
  const hitSkill = 1000;
  const dmgSkill = 1000;
  
  // Calculate skill modification from sights
  const skillModEnhancers = enhancerType === 'Accuracy' ? enhancerTiers.length : 0;
  const skillMod = LoadoutCalc.calculateSkillModification(
    attachments.scope,
    attachments.scopeSight,
    attachments.sight
  );
  
  // Calculate damage interval
  const damageInterval = LoadoutCalc.calculateDamageInterval(
    weapon,
    dmgSkill,
    skillModEnhancers,
    totalDamage
  );
  
  if (damageInterval == null) return 0;
  
  // Calculate hit ability and crit
  const hitAbility = LoadoutCalc.calculateHitAbility(weapon, hitSkill, skillModEnhancers);
  const critAbility = LoadoutCalc.calculateCritAbility(weapon, hitSkill, skillModEnhancers);
  
  if (hitAbility == null || critAbility == null) return 0;
  
  const accuracyEnhancers = enhancerType === 'Accuracy' ? enhancerTiers.length : 0;
  const critChance = LoadoutCalc.calculateCritChance(critAbility, accuracyEnhancers, 0);
  const critDamage = LoadoutCalc.calculateCritDamage(0);
  
  // Calculate effective damage
  const effectiveDamage = LoadoutCalc.calculateEffectiveDamage(
    damageInterval,
    critChance,
    critDamage,
    hitAbility
  );
  
  if (effectiveDamage == null) return 0;
  
  // Get reload speed bonuses
  const reloadBonus = getDPSReloadSpeedBonus(
    service, 
    clothingItems, 
    armorSets, 
    consumables, 
    pets,
    enabledConsumables, 
    activePetEffects
  );
  
  // Calculate reload time
  const reload = LoadoutCalc.calculateReload(
    weapon,
    hitSkill,
    skillModEnhancers,
    reloadBonus.total
  );
  
  if (reload == null) return 0;
  
  // Calculate DPS
  const dps = LoadoutCalc.calculateDPS(effectiveDamage, reload);
  
  return dps ?? 0;
}

/**
 * Calculate maximum cost per hour for DPS
 * @param {object} service - Service object
 * @param {object} weapon - Active weapon
 * @param {object} attachments - Weapon attachments
 * @param {string} enhancerType - 'Damage', 'Accuracy', or 'Economy'
 * @param {array} enhancerTiers - Array of tier levels enabled
 * @param {array} consumables - All consumables
 * @param {array} pets - All pets
 * @param {array} clothingItems - All clothing items
 * @param {array} armorSets - All armor sets
 * @param {object} enabledConsumables - Map of consumable names to enabled state
 * @param {object} activePetEffects - Map of pet effect names to enabled state
 * @param {object} markups - Markup values for ammo, weapon, etc.
 * @returns {number} Cost per hour in PED
 */
export function getMaxCostPerHour(service, weapon, attachments, enhancerType, enhancerTiers, consumables, pets, clothingItems, armorSets, enabledConsumables = {}, activePetEffects = {}, markups = {}) {
  if (!weapon) return 0;
  
  // Get reload speed bonus
  const reloadBonus = getDPSReloadSpeedBonus(
    service, 
    clothingItems, 
    armorSets, 
    consumables, 
    pets,
    enabledConsumables, 
    activePetEffects
  );
  
  const hitSkill = 1000;
  const skillModEnhancers = enhancerType === 'Accuracy' ? enhancerTiers.length : 0;
  
  // Calculate reload time
  const reload = LoadoutCalc.calculateReload(
    weapon,
    hitSkill,
    skillModEnhancers,
    reloadBonus.total
  );
  
  if (reload == null) return 0;
  
  // Calculate shots per hour
  const shotsPerHour = (3600 / reload);
  
  // Calculate decay and ammo burn per shot
  const damageEnhancers = enhancerType === 'Damage' ? enhancerTiers.length : 0;
  const economyEnhancers = enhancerType === 'Economy' ? enhancerTiers.length : 0;
  
  const decay = LoadoutCalc.calculateDecay(
    weapon,
    damageEnhancers,
    economyEnhancers,
    attachments.absorber,
    attachments.implant,
    attachments.amplifier,
    attachments.scope,
    attachments.scopeSight,
    attachments.sight,
    attachments.matrix,
    markups
  );
  
  const ammoBurn = LoadoutCalc.calculateAmmoBurn(
    weapon,
    damageEnhancers,
    economyEnhancers,
    attachments.amplifier
  );
  
  if (decay == null || ammoBurn == null) return 0;
  
  const cost = LoadoutCalc.calculateCost(decay, ammoBurn, markups.ammo || 100);
  
  if (cost == null) return 0;
  
  // Cost per hour in PED
  const costPerHour = (cost * shotsPerHour) / 100;
  
  return costPerHour ?? 0;
}
