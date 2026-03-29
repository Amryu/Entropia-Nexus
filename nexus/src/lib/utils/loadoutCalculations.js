// @ts-nocheck
// Loadout calculation utilities
// These functions are extracted from the loadout manager and operate on individual parameters
// rather than the entire loadout object for better reusability and testability

// ========== Helper Functions ==========

export function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

export function getLerpProgress(start, end, current) {
  // Just a hack to avoid making fully maxed weapons unusable just because we don't know the max value
  if (start == null || end == null) return 1;
  
  return clamp((current - start) / (end - start), 0, 1);
}

export function weightedAverage(weightA, valueA, weightB, valueB) {
  return (valueA * weightA + valueB * weightB) / (weightA + weightB);
}

// ========== Weapon Damage Calculations ==========

export function calculateTotalDamage(weapon, damageEnhancers, bonusDamagePercent, amplifier) {
  if (weapon == null) return null;

  const baseDamage = (weapon.Properties?.Damage?.Impact
    + weapon.Properties?.Damage?.Cut
    + weapon.Properties?.Damage?.Stab
    + weapon.Properties?.Damage?.Penetration
    + weapon.Properties?.Damage?.Shrapnel
    + weapon.Properties?.Damage?.Burn
    + weapon.Properties?.Damage?.Cold
    + weapon.Properties?.Damage?.Acid
    + weapon.Properties?.Damage?.Electric) || null;

  if (baseDamage == null) return null;

  let totalDamage = baseDamage;
  totalDamage *= 1 + (damageEnhancers * 0.1);

  if (amplifier != null) {
    const amplifierDamage = (amplifier.Properties?.Damage?.Impact
      + amplifier.Properties?.Damage?.Cut
      + amplifier.Properties?.Damage?.Stab
      + amplifier.Properties?.Damage?.Penetration
      + amplifier.Properties?.Damage?.Shrapnel
      + amplifier.Properties?.Damage?.Burn
      + amplifier.Properties?.Damage?.Cold
      + amplifier.Properties?.Damage?.Acid
      + amplifier.Properties?.Damage?.Electric) || null;
    
    if (amplifierDamage != null) {
      totalDamage += Math.min(baseDamage / 2, amplifierDamage);
    }
  }

  return totalDamage * (1 + (bonusDamagePercent ?? 0) / 100);
}

export function calculateDamageInterval(weapon, dmgSkill, skillModEnhancers, totalDamage) {
  if (weapon == null || totalDamage == null || !weapon.Properties || !weapon.Properties.Skill) return null;
  
  const effectiveDmgSkill = dmgSkill + (skillModEnhancers ?? 0) * 0.5;

  if (weapon.Properties.Skill.IsSiB) {
    const progress = getLerpProgress(
      weapon.Properties.Skill.Dmg.LearningIntervalStart,
      weapon.Properties.Skill.Dmg.LearningIntervalEnd,
      effectiveDmgSkill
    );

    return { 
      min: totalDamage * 0.25 * (1 + progress),
      max: totalDamage * 0.5 * (1 + progress)
    };
  }
  else {
    return { 
      min: totalDamage * 0.25 + (totalDamage * 0.25 * Math.min(effectiveDmgSkill / 100, 1)),
      max: totalDamage
    };
  }
}

export function calculateHitAbility(weapon, hitSkill, skillModEnhancers) {
  if (weapon == null || !weapon.Properties || !weapon.Properties.Skill) return null;
  
  const effectiveHitSkill = hitSkill + (skillModEnhancers ?? 0) * 0.5;

  if (weapon.Properties.Skill.IsSiB) {
    if (effectiveHitSkill < weapon.Properties.Skill.Hit.LearningIntervalStart) {
      return 0;
    }

    const progress = getLerpProgress(
      weapon.Properties.Skill.Hit.LearningIntervalStart,
      weapon.Properties.Skill.Hit.LearningIntervalEnd,
      effectiveHitSkill
    );

    return clamp(3 + 7 * progress, 0, 10);
  }
  else {
    return clamp(4 + 6 * (effectiveHitSkill / 100), 0, 10);
  }
}

export function calculateCritAbility(weapon, hitSkill, skillModEnhancers) {
  if (weapon == null || !weapon.Properties || !weapon.Properties.Skill) return null;
  
  const effectiveHitSkill = hitSkill + (skillModEnhancers ?? 0) * 0.5;

  if (weapon.Properties.Skill.IsSiB) {
    const progress = getLerpProgress(
      weapon.Properties.Skill.Hit.LearningIntervalStart,
      weapon.Properties.Skill.Hit.LearningIntervalEnd,
      effectiveHitSkill
    );

    return clamp(Math.sqrt(progress * 100), 0, 10);
  }
  else {
    return clamp(Math.min(10, Math.sqrt(effectiveHitSkill)), 0, 10);
  }
}

export function calculateCritChance(critAbility, accuracyEnhancers, bonusCritChancePercent) {
  return clamp(
    0.01 + (critAbility / 1000) + accuracyEnhancers * 0.002 + ((bonusCritChancePercent ?? 0) / 100),
    0.01,
    1
  );
}

export function calculateCritDamage(bonusCritDamagePercent) {
  return 1 + ((bonusCritDamagePercent ?? 0) / 100);
}

export function calculateEffectiveDamage(damageInterval, critChance, critDamage, hitAbility) {
  if (critChance == null || critDamage == null || hitAbility == null || damageInterval == null) return null;
  
  const averageDamage = (damageInterval.min + damageInterval.max) / 2;
  const hitChance = 0.8 + (hitAbility / 100);

  return averageDamage * (hitChance - critChance) + (averageDamage + critDamage * damageInterval.max) * critChance;
}

export function calculateRange(weapon, hitSkill, skillModEnhancers, rangeEnhancers) {
  if (weapon == null || !weapon.Properties) return null;

  const effectiveHitSkill = hitSkill + (skillModEnhancers ?? 0) * 0.5;
  const rangeEnhancerFactor = 1 + rangeEnhancers * 0.05;

  if (weapon.Properties.Class === 'Melee') {
    return weapon.Properties.Range * rangeEnhancerFactor;
  }

  if (weapon.Properties.Skill && effectiveHitSkill < weapon.Properties.Skill.Hit.LearningIntervalStart) {
    return weapon.Properties.Range * 10/11 * rangeEnhancerFactor;
  }

  if (weapon.Properties.Skill && weapon.Properties.Skill.IsSiB) {
    const progress = getLerpProgress(
      weapon.Properties.Skill.Hit.LearningIntervalStart,
      weapon.Properties.Skill.Hit.LearningIntervalEnd,
      effectiveHitSkill
    );

    return weapon.Properties.Range * (0.935 + 0.065 * progress) * rangeEnhancerFactor;
  }
  else {
    return weapon.Properties.Range * Math.min(1, 0.945 + 0.055 * (effectiveHitSkill / 100)) * rangeEnhancerFactor;
  }
}

export function calculateReload(weapon, hitSkill, skillModEnhancers, bonusReloadPercent) {
  if (weapon == null || !weapon.Properties || !weapon.Properties.UsesPerMinute) return null;

  const effectiveHitSkill = hitSkill + (skillModEnhancers ?? 0) * 0.5;
  const bonusFactor = 1/(1 + (bonusReloadPercent ?? 0) / 100);

  if (!weapon.Properties.Skill || !weapon.Properties.Skill.IsSiB) {
    return (60 / weapon.Properties.UsesPerMinute) * bonusFactor;
  }

  if (effectiveHitSkill < weapon.Properties.Skill.Hit.LearningIntervalStart) {
    return (60 / (weapon.Properties.UsesPerMinute * 0.45)) * bonusFactor;
  }
  else {
    const intervalSize = weapon.Properties.Skill.Hit.LearningIntervalEnd - weapon.Properties.Skill.Hit.LearningIntervalStart;
    const scalingRange = intervalSize * 0.25;

    const progress = getLerpProgress(
      weapon.Properties.Skill.Hit.LearningIntervalStart,
      weapon.Properties.Skill.Hit.LearningIntervalEnd != null ? weapon.Properties.Skill.Hit.LearningIntervalEnd + scalingRange : null,
      effectiveHitSkill
    );

    return (60 / (weapon.Properties.UsesPerMinute * 0.8 + weapon.Properties.UsesPerMinute * 0.2 * progress)) * bonusFactor;
  }
}

export function calculateDPS(effectiveDamage, reload) {
  return effectiveDamage && reload
    ? effectiveDamage / reload
    : null;
}

// ========== Economy Calculations ==========

export function calculateDecay(
  weapon,
  damageEnhancers,
  economyEnhancers,
  absorber,
  implant,
  amplifier,
  scope,
  scopeSight,
  sight,
  matrix,
  markups,
  weaponClass
) {
  if (weapon == null || !weapon.Properties || !weapon.Properties.Economy || weapon.Properties.Economy.Decay == null) return null;

  let weaponDecay = weapon.Properties.Economy.Decay * (1 + damageEnhancers * 0.1) * (1 - economyEnhancers * 0.01111);

  let decay = 0;

  if (absorber?.Properties?.Economy?.Absorption != null) {
    const absorberDecay = weaponDecay * absorber.Properties.Economy.Absorption;
    decay += absorberDecay * (markups.Implant ?? 100) / 100;
    weaponDecay -= absorberDecay;
  }

  // Implant absorption only applies with Mindforce weapons; effects apply to all
  if (weaponClass === 'Mindforce' && implant?.Properties?.Economy?.Absorption != null) {
    const implantDecay = weaponDecay * implant.Properties.Economy.Absorption;
    decay += implantDecay * (markups.Implant ?? 100) / 100;
    weaponDecay -= implantDecay;
  }

  // Mining amplifier absorption (mining amps act as absorber for mining weapons)
  if (weapon?.Properties?.Type?.startsWith('Mining Laser') && amplifier?.Properties?.Economy?.Absorption != null) {
    const miningAmpAbsorption = weaponDecay * amplifier.Properties.Economy.Absorption;
    decay += miningAmpAbsorption * (markups.Amplifier ?? 100) / 100;
    weaponDecay -= miningAmpAbsorption;
  }

  decay += weaponDecay * (markups.Weapon ?? 100) / 100;

  if (amplifier?.Properties?.Economy?.Decay != null) {
    decay += amplifier.Properties.Economy.Decay * (markups.Amplifier ?? 100) / 100;
  }

  if (scope?.Properties?.Economy?.Decay != null) {
    decay += scope.Properties.Economy.Decay * (markups.Scope ?? 100) / 100;
  }

  if (scopeSight?.Properties?.Economy?.Decay != null) {
    decay += scopeSight.Properties.Economy.Decay * (markups.ScopeSight ?? 100) / 100;
  }

  if (sight?.Properties?.Economy?.Decay != null) {
    decay += sight.Properties.Economy.Decay * (markups.Sight ?? 100) / 100;
  }

  if (matrix?.Properties?.Economy?.Decay != null) {
    decay += matrix.Properties.Economy.Decay * (markups.Matrix ?? 100) / 100;
  }

  return decay;
}

export function calculateAmmoBurn(weapon, damageEnhancers, economyEnhancers, amplifier) {
  if (weapon == null || !weapon.Properties || !weapon.Properties.Economy || weapon.Properties.Economy.AmmoBurn === null) return null;

  let ammoBurn = weapon.Properties.Economy.AmmoBurn * (1 + damageEnhancers * 0.1) * (1 - economyEnhancers * 0.01111);

  if (amplifier?.Properties?.Economy?.AmmoBurn != null) {
    ammoBurn += amplifier.Properties.Economy.AmmoBurn;
  }

  return ammoBurn;
}

export function calculateCost(decay, ammoBurn, ammoMarkup) {
  if (decay === null) return null;

  // decay is in PEC. ammoBurn is in ammo units (÷100 = PEC).
  // ammoMarkup is a percentage (÷100 to apply). Result in PEC.
  return decay + ((ammoBurn ?? 0) / 100) * (ammoMarkup ?? 100) / 100;
}

export function calculateDPP(effectiveDamage, cost) {
  return effectiveDamage && cost
    ? effectiveDamage / cost
    : null;
}

export function calculateWeaponCost(weapon, damageEnhancers, economyEnhancers) {
  if (weapon == null) return null;

  const baseCost = (weapon.Properties?.Economy?.Decay != null && (weapon.Properties?.Economy?.AmmoBurn == undefined || weapon.Properties?.Economy?.AmmoBurn >= 0))
    ? (weapon.Properties?.Economy?.Decay + (weapon.Properties?.Economy?.AmmoBurn ?? 0) / 100)
    : null;

  if (baseCost == null) return null;

  return baseCost * (1 + damageEnhancers * 0.1) * (1 - economyEnhancers * 0.01111);
}

export function calculateEfficiency(
  weapon,
  weaponCost,
  damageEnhancers,
  economyEnhancers,
  absorber,
  amplifier,
  scope,
  scopeSight,
  sight,
  matrix
) {
  if (weapon == null || weapon.Properties.Economy.Efficiency === null) return null;

  let cost = weaponCost;
  let efficiency = weapon.Properties.Economy.Efficiency;

  if (absorber?.Properties?.Economy?.Absorption != null && absorber?.Properties?.Economy?.Efficiency != null) {
    const weaponDecay = weapon.Properties.Economy.Decay * (1 + damageEnhancers * 0.1) * (1 - economyEnhancers * 0.01111);
    const absorberCost = weaponDecay * absorber.Properties.Economy.Absorption;
    cost -= absorberCost;
    efficiency = weightedAverage(cost, efficiency, absorberCost, absorber.Properties.Economy.Efficiency);
    cost += absorberCost;
  }

  if (amplifier?.Properties?.Economy?.Efficiency != null && amplifier?.Properties?.Economy?.Decay != null) {
    const ampCost = (amplifier.Properties?.Economy?.AmmoBurn == undefined || amplifier.Properties?.Economy?.AmmoBurn >= 0)
      ? (amplifier.Properties.Economy.Decay + (amplifier.Properties?.Economy?.AmmoBurn ?? 0) / 100)
      : null;

    if (ampCost !== null) {
      efficiency = weightedAverage(cost, efficiency, ampCost, amplifier.Properties.Economy.Efficiency);
      cost += ampCost;
    }
  }

  if (scope?.Properties?.Economy?.Efficiency != null && scope?.Properties?.Economy?.Decay != null) {
    const scopeCost = (scope.Properties?.Economy?.AmmoBurn == undefined || scope.Properties?.Economy?.AmmoBurn >= 0)
      ? (scope.Properties.Economy.Decay + (scope.Properties?.Economy?.AmmoBurn ?? 0) / 100)
      : null;

    if (scopeCost !== null) {
      efficiency = weightedAverage(cost, efficiency, scopeCost, scope.Properties.Economy.Efficiency);
      cost += scopeCost;
    }
  }

  if (scopeSight?.Properties?.Economy?.Efficiency != null && scopeSight?.Properties?.Economy?.Decay != null) {
    const scopeSightCost = (scopeSight.Properties?.Economy?.AmmoBurn == undefined || scopeSight.Properties?.Economy?.AmmoBurn >= 0)
      ? (scopeSight.Properties.Economy.Decay + (scopeSight.Properties?.Economy?.AmmoBurn ?? 0) / 100)
      : null;

    if (scopeSightCost !== null) {
      efficiency = weightedAverage(cost, efficiency, scopeSightCost, scopeSight.Properties.Economy.Efficiency);
      cost += scopeSightCost;
    }
  }

  if (sight?.Properties?.Economy?.Efficiency != null && sight?.Properties?.Economy?.Decay != null) {
    const sightCost = (sight.Properties?.Economy?.AmmoBurn == undefined || sight.Properties?.Economy?.AmmoBurn >= 0)
      ? (sight.Properties.Economy.Decay + (sight.Properties?.Economy?.AmmoBurn ?? 0) / 100)
      : null;

    if (sightCost !== null) {
      efficiency = weightedAverage(cost, efficiency, sightCost, sight.Properties.Economy.Efficiency);
      cost += sightCost;
    }
  }

  if (matrix?.Properties?.Economy?.Efficiency != null && matrix?.Properties?.Economy?.Decay != null) {
    const matrixCost = (matrix.Properties?.Economy?.AmmoBurn == undefined || matrix.Properties?.Economy?.AmmoBurn >= 0)
      ? (matrix.Properties.Economy.Decay + (matrix.Properties?.Economy?.AmmoBurn ?? 0) / 100)
      : null;

    if (matrixCost !== null) {
      efficiency = weightedAverage(cost, efficiency, matrixCost, matrix.Properties.Economy.Efficiency);
      cost += matrixCost;
    }
  }

  return efficiency;
}

export function calculateLowestTotalUses(
  weapon,
  damageEnhancers,
  economyEnhancers,
  absorber,
  implant,
  amplifier,
  scope,
  scopeSight,
  sight,
  matrix,
  weaponClass
) {
  if (weapon == null) return null;

  // Implant absorption only applies with Mindforce weapons
  const implantAbsorption = (weaponClass === 'Mindforce' && implant != null) ? 1 - implant.Properties.Economy.Absorption : 1;
  // Mining amplifier absorption (mining amps act as absorber)
  const miningAmpAbsorption = (weapon?.Properties?.Type?.startsWith('Mining Laser') && amplifier?.Properties?.Economy?.Absorption != null)
    ? 1 - amplifier.Properties.Economy.Absorption : 1;
  const decayFactor = (absorber != null ? 1 - absorber.Properties.Economy.Absorption : 1) * implantAbsorption * miningAmpAbsorption;

  const weaponMaxTT = weapon.Properties?.Economy?.MaxTT ?? null;
  const weaponMinTT = weapon.Properties?.Economy?.MinTT ?? 0;
  const weaponDecay = (weapon.Properties?.Economy?.Decay * (1 + damageEnhancers * 0.1) * (1 - economyEnhancers * 0.01111)) * decayFactor;

  let totalUses = weaponMaxTT != null && weaponDecay != null
    ? Math.floor((weaponMaxTT - weaponMinTT) / (weaponDecay / 100))
    : null;

  if (totalUses === null) return null;

  const getTotalUses = (item) => {
    const maxTT = item.Properties?.Economy?.MaxTT || null;
    const minTT = item.Properties?.Economy?.MinTT ?? 0;
    const decay = item.Properties?.Economy?.Decay || null;

    return maxTT != null && decay != null
      ? Math.floor((maxTT - minTT) / (decay / 100))
      : null;
  };

  if (amplifier != null) {
    const ampUses = getTotalUses(amplifier);
    if (ampUses != null) totalUses = Math.min(totalUses, ampUses);
  }

  if (scope != null) {
    const scopeUses = getTotalUses(scope);
    if (scopeUses != null) totalUses = Math.min(totalUses, scopeUses);
  }

  if (scopeSight != null) {
    const scopeSightUses = getTotalUses(scopeSight);
    if (scopeSightUses != null) totalUses = Math.min(totalUses, scopeSightUses);
  }

  if (sight != null) {
    const sightUses = getTotalUses(sight);
    if (sightUses != null) totalUses = Math.min(totalUses, sightUses);
  }

  if (matrix != null) {
    const matrixUses = getTotalUses(matrix);
    if (matrixUses != null) totalUses = Math.min(totalUses, matrixUses);
  }

  if (absorber != null) {
    const absorberMaxTT = absorber.Properties?.Economy?.MaxTT || null;
    const absorberMinTT = absorber.Properties?.Economy?.MinTT ?? 0;
    const absorberDecay = absorber.Properties?.Economy?.Absorption != null 
      ? weapon.Properties?.Economy?.Decay * absorber.Properties?.Economy?.Absorption
      : null;

    const absorberUses = absorberMaxTT != null && absorberDecay != null
      ? Math.floor((absorberMaxTT - absorberMinTT) / (absorberDecay / 100))
      : null;

    if (absorberUses != null) totalUses = Math.min(totalUses, absorberUses);
  }

  // Implant durability only matters when absorption applies (Mindforce)
  if (weaponClass === 'Mindforce' && implant != null) {
    const implantUses = getTotalUses(implant);
    if (implantUses != null) totalUses = Math.min(totalUses, implantUses);
  }

  return totalUses;
}

// ========== Armor Defense Calculations ==========

function getTotalDefenseFromItem(item) {
  return (item.Properties?.Defense?.Impact ?? 0) + (item.Properties?.Defense?.Cut ?? 0) + (item.Properties?.Defense?.Stab ?? 0) + (item.Properties?.Defense?.Penetration ?? 0) + (item.Properties?.Defense?.Shrapnel ?? 0) + (item.Properties?.Defense?.Burn ?? 0) + (item.Properties?.Defense?.Cold ?? 0) + (item.Properties?.Defense?.Acid ?? 0) + (item.Properties?.Defense?.Electric ?? 0);
}

const DEFENSE_TYPES = [
  'Impact',
  'Cut',
  'Stab',
  'Penetration',
  'Shrapnel',
  'Burn',
  'Cold',
  'Acid',
  'Electric'
];

function getDefenseByTypeFromItem(item) {
  /** @type {Record<string, number>} */
  const out = {};
  for (const key of DEFENSE_TYPES) {
    out[key] = item?.Properties?.Defense?.[key] ?? 0;
  }
  return out;
}

function averageDefenseByType(current, next) {
  /** @type {Record<string, number>} */
  const out = {};
  for (const key of DEFENSE_TYPES) {
    const a = current?.[key] ?? 0;
    const b = next?.[key] ?? 0;
    out[key] = a === 0 ? b : (a + b) / 2;
  }
  return out;
}

function scaleDefenseByType(defenseByType, multiplier) {
  /** @type {Record<string, number>} */
  const out = {};
  for (const key of DEFENSE_TYPES) {
    out[key] = (defenseByType?.[key] ?? 0) * multiplier;
  }
  return out;
}

export function calculateArmorDefenseByType(armorPieces, defenseEnhancers) {
  /** @type {Record<string, number>} */
  let defenseByType = Object.fromEntries(DEFENSE_TYPES.map(k => [k, 0]));

  armorPieces.forEach(armor => {
    if (armor == null) return;
    defenseByType = averageDefenseByType(defenseByType, getDefenseByTypeFromItem(armor));
  });

  // Match calculateArmorDefense() scaling.
  const multiplier = 1 + ((defenseEnhancers ?? 0) * 0.05);
  return scaleDefenseByType(defenseByType, multiplier);
}

export function calculatePlateDefenseByType(platePieces) {
  /** @type {Record<string, number>} */
  let defenseByType = Object.fromEntries(DEFENSE_TYPES.map(k => [k, 0]));

  platePieces.forEach(plate => {
    if (plate == null) return;
    defenseByType = averageDefenseByType(defenseByType, getDefenseByTypeFromItem(plate));
  });

  return defenseByType;
}

export function calculateTotalDefenseByType(armorDefenseByType, plateDefenseByType) {
  /** @type {Record<string, number>} */
  const out = {};
  for (const key of DEFENSE_TYPES) {
    out[key] = (armorDefenseByType?.[key] ?? 0) + (plateDefenseByType?.[key] ?? 0);
  }
  return out;
}

export function formatTopDefenseTypesShort(defenseByType, max = 3) {
  const abbr = {
    Impact: 'Imp',
    Cut: 'Cut',
    Stab: 'Stb',
    Penetration: 'Pen',
    Shrapnel: 'Shr',
    Burn: 'Brn',
    Cold: 'Cld',
    Acid: 'Acd',
    Electric: 'Ele'
  };

  const entries = DEFENSE_TYPES
    .map(k => [k, defenseByType?.[k] ?? 0])
    .filter(([, v]) => v > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, Math.max(0, max));

  if (entries.length === 0) return '-';
  return entries.map(([k]) => abbr[k] ?? k.slice(0, 3)).join('/');
}

export function calculateArmorDefense(armorPieces, defenseEnhancers) {
  let totalDefense = 0;

  armorPieces.forEach(armor => {
    if (armor == null) return;

    totalDefense = totalDefense === 0
      ? getTotalDefenseFromItem(armor)
      : (totalDefense + getTotalDefenseFromItem(armor)) / 2;
  });

  totalDefense *= 1 + (defenseEnhancers * 0.05);

  return totalDefense;
}

export function calculatePlateDefense(platePieces) {
  let totalDefense = 0;

  platePieces.forEach(plate => {
    if (plate == null) return;

    totalDefense = totalDefense === 0
      ? getTotalDefenseFromItem(plate)
      : (totalDefense + getTotalDefenseFromItem(plate)) / 2;
  });

  return totalDefense;
}

export function calculateTotalDefense(armorDefense, plateDefense) {
  return armorDefense + plateDefense;
}

export function calculateArmorDurability(armorPieces, durabilityEnhancers) {
  let totalDurability = 0;

  armorPieces.forEach(armor => {
    if (armor == null) return;

    totalDurability = totalDurability === 0
      ? armor.Properties.Economy.Durability
      : (totalDurability + armor.Properties.Economy.Durability) / 2;
  });

  totalDurability *= 1 + (durabilityEnhancers * 0.05);

  return totalDurability || null;
}

export function calculatePlateDurability(platePieces) {
  let totalDurability = 0;

  platePieces.forEach(plate => {
    if (plate == null) return;

    totalDurability = totalDurability === 0
      ? plate.Properties.Economy.Durability
      : (totalDurability + plate.Properties.Economy.Durability) / 2;
  });

  return totalDurability || null;
}

export function calculateTotalAbsorption(armorPieces, platePieces, defenseEnhancers, durabilityEnhancers) {
  let totalAbsorption = 0;

  armorPieces.forEach(armor => {
    if (armor == null) return;

    const totalDefense = getTotalDefenseFromItem(armor) * (1 + defenseEnhancers * 0.05);
    const durability = armor.Properties?.Economy.Durability * (1 + durabilityEnhancers * 0.1);

    const maxDecay = totalDefense * ((100000 - durability) / 100000) * 0.05;
    totalAbsorption += totalDefense * ((armor.Properties?.Economy.MaxTT - (armor.Properties?.Economy.MinTT ?? 0)) / (maxDecay / 100));
  });

  platePieces.forEach(plate => {
    if (plate == null) return;

    const totalDefense = getTotalDefenseFromItem(plate);

    const maxDecay = totalDefense * ((100000 - plate.Properties?.Economy.Durability) / 100000) * 0.05;
    totalAbsorption += totalDefense * ((plate.Properties?.Economy.MaxTT - (plate.Properties?.Economy.MinTT ?? 0)) / (maxDecay / 100));
  });

  return totalAbsorption;
}

export function calculateBlockChance(platePieces) {
  let blockChance = 0;

  platePieces.forEach(plate => {
    if (plate == null) return;

    blockChance = blockChance === 0
      ? plate.Properties.Defense.Block ?? 0
      : (blockChance + plate.Properties.Defense.Block ?? 0) / 2;
  });

  return blockChance || null;
}

// ========== Skill Calculations ==========

export function calculateSkillModification(scope, scopeSight, sight) {
  let skillMod = 0;

  if (scope?.Properties?.SkillModification != null) {
    skillMod += scope.Properties.SkillModification;
  }

  if (scopeSight?.Properties?.SkillModification != null) {
    skillMod += scopeSight.Properties.SkillModification;
  }

  if (sight?.Properties?.SkillModification != null) {
    skillMod += sight.Properties.SkillModification;
  }

  return skillMod;
}

export function calculateSkillBonus(scope, scopeSight, sight) {
  let skillBonus = 0;

  if (scope?.Properties?.SkillBonus != null) {
    skillBonus += scope.Properties.SkillBonus;
  }

  if (scopeSight?.Properties?.SkillBonus != null) {
    skillBonus += scopeSight.Properties.SkillBonus;
  }

  if (sight?.Properties?.SkillBonus != null) {
    skillBonus += sight.Properties.SkillBonus;
  }

  return skillBonus;
}

// ========== Generic Item Preview Helpers ==========
// These mirror the simplified "picker preview" calculations used in the loadout manager UI.
// They intentionally do not account for skills/enhancers unless explicitly passed in.

export function calculateItemTotalDamage(item) {
  if (!item?.Properties?.Damage) return null;

  return (item.Properties.Damage.Impact
    + item.Properties.Damage.Cut
    + item.Properties.Damage.Stab
    + item.Properties.Damage.Penetration
    + item.Properties.Damage.Shrapnel
    + item.Properties.Damage.Burn
    + item.Properties.Damage.Cold
    + item.Properties.Damage.Acid
    + item.Properties.Damage.Electric) || null;
}

export function calculateItemEffectiveDamagePreview(item) {
  const totalDamage = calculateItemTotalDamage(item);
  return totalDamage != null
    ? totalDamage * (0.88 * 0.75 + 0.02 * 1.75)
    : null;
}

export function calculateItemReloadSeconds(item) {
  return item?.Properties?.UsesPerMinute != null
    ? 60 / item.Properties.UsesPerMinute
    : null;
}

export function calculateItemCostPerUse(item) {
  const decay = item?.Properties?.Economy?.Decay;
  const ammoBurn = item?.Properties?.Economy?.AmmoBurn;
  if (decay == null) return null;
  if (ammoBurn != null && ammoBurn < 0) return null;
  return decay + (ammoBurn ?? 0) / 100;
}

export function calculateItemDpsPreview(item) {
  const reload = calculateItemReloadSeconds(item);
  const effectiveDamage = calculateItemEffectiveDamagePreview(item);
  return effectiveDamage != null && reload != null
    ? effectiveDamage / reload
    : null;
}

export function calculateItemDppPreview(item) {
  const cost = calculateItemCostPerUse(item);
  const effectiveDamage = calculateItemEffectiveDamagePreview(item);
  return effectiveDamage > 0 && cost != null
    ? effectiveDamage / cost
    : null;
}

export function calculateItemTotalUses(item) {
  const maxTT = item?.Properties?.Economy?.MaxTT ?? null;
  const minTT = item?.Properties?.Economy?.MinTT ?? 0;
  const decay = item?.Properties?.Economy?.Decay ?? null;
  return maxTT != null && decay != null
    ? Math.floor((maxTT - minTT) / (decay / 100))
    : null;
}

export function calculateAbsorberTotalUses(absorber, weapon) {
  const maxTT = absorber?.Properties?.Economy?.MaxTT ?? null;
  const minTT = absorber?.Properties?.Economy?.MinTT ?? 0;
  const absorption = absorber?.Properties?.Economy?.Absorption;
  const weaponDecay = weapon?.Properties?.Economy?.Decay;
  const decay = absorption != null && weaponDecay != null
    ? weaponDecay * absorption
    : null;
  return maxTT != null && decay != null
    ? Math.floor((maxTT - minTT) / (decay / 100))
    : null;
}

export function calculateMarkupCost(item, markupPercent) {
  const maxTT = item?.Properties?.Economy?.MaxTT;
  const minTT = item?.Properties?.Economy?.MinTT ?? 0;
  if (maxTT == null || maxTT <= minTT) return null;
  return (maxTT - minTT) * (markupPercent ?? 100) / 100;
}

export function calculateItemTotalDefense(item) {
  if (!item?.Properties?.Defense) return null;
  return (item.Properties.Defense.Impact ?? 0)
    + (item.Properties.Defense.Cut ?? 0)
    + (item.Properties.Defense.Stab ?? 0)
    + (item.Properties.Defense.Penetration ?? 0)
    + (item.Properties.Defense.Shrapnel ?? 0)
    + (item.Properties.Defense.Burn ?? 0)
    + (item.Properties.Defense.Cold ?? 0)
    + (item.Properties.Defense.Acid ?? 0)
    + (item.Properties.Defense.Electric ?? 0);
}

export function calculateItemMaxDefenseDecay(item) {
  const durability = item?.Properties?.Economy?.Durability;
  const totalDefense = calculateItemTotalDefense(item);
  return durability && totalDefense
    ? totalDefense * ((100000 - durability) / 100000) * 0.05
    : null;
}

export function calculateItemTotalAbsorptionPreview(item) {
  const maxTT = item?.Properties?.Economy?.MaxTT;
  const minTT = item?.Properties?.Economy?.MinTT ?? 0;
  const maxDecay = calculateItemMaxDefenseDecay(item);
  const totalDefense = calculateItemTotalDefense(item);
  return maxTT && maxDecay && totalDefense
    ? totalDefense * ((maxTT - minTT) / (maxDecay / 100))
    : null;
}

// ========== Healing Calculations ==========

export function calculateTotalHeal(tool, healEnhancers) {
  if (tool == null || tool.Properties?.MaxHeal == null) return null;
  return tool.Properties.MaxHeal * (1 + (healEnhancers ?? 0) * 0.1);
}

export function calculateHealInterval(tool, healSkill, skillModEnhancers, healEnhancers) {
  if (tool == null || !tool.Properties || tool.Properties.MaxHeal == null || tool.Properties.MinHeal == null) return null;

  const effectiveHealSkill = healSkill + (skillModEnhancers ?? 0) * 0.5;
  const healBoost = 1 + (healEnhancers ?? 0) * 0.1;
  const maxHeal = tool.Properties.MaxHeal * healBoost;
  const minHeal = tool.Properties.MinHeal * healBoost;

  if (tool.Properties.Skill?.IsSiB) {
    const progress = getLerpProgress(
      tool.Properties.Skill.LearningIntervalStart,
      tool.Properties.Skill.LearningIntervalEnd,
      effectiveHealSkill
    );

    return {
      min: minHeal * 0.5 * (1 + progress),
      max: maxHeal * 0.5 * (1 + progress)
    };
  }
  else {
    return {
      min: minHeal * 0.5 * (1 + Math.min(effectiveHealSkill / 100, 1)),
      max: maxHeal
    };
  }
}

export function calculateEffectiveHeal(healInterval) {
  if (healInterval == null) return null;
  return (healInterval.min + healInterval.max) / 2;
}

export function calculateHealReload(tool, healSkill, skillModEnhancers) {
  if (tool == null || !tool.Properties) return null;

  // Chips with Mindforce cooldown: use cooldown directly (no SIB scaling)
  if (tool.Properties.Mindforce?.Cooldown) {
    return tool.Properties.Mindforce.Cooldown;
  }

  if (!tool.Properties.UsesPerMinute) return null;

  const effectiveHealSkill = healSkill + (skillModEnhancers ?? 0) * 0.5;

  if (!tool.Properties.Skill || !tool.Properties.Skill.IsSiB) {
    return 60 / tool.Properties.UsesPerMinute;
  }

  if (effectiveHealSkill < tool.Properties.Skill.LearningIntervalStart) {
    return 60 / (tool.Properties.UsesPerMinute * 0.45);
  }
  else {
    const intervalSize = tool.Properties.Skill.LearningIntervalEnd - tool.Properties.Skill.LearningIntervalStart;
    const scalingRange = intervalSize * 0.25;

    const progress = getLerpProgress(
      tool.Properties.Skill.LearningIntervalStart,
      tool.Properties.Skill.LearningIntervalEnd != null ? tool.Properties.Skill.LearningIntervalEnd + scalingRange : null,
      effectiveHealSkill
    );

    return 60 / (tool.Properties.UsesPerMinute * 0.8 + tool.Properties.UsesPerMinute * 0.2 * progress);
  }
}

export function calculateHealDecay(tool, healEnhancers, economyEnhancers, markup) {
  if (tool == null || tool.Properties?.Economy?.Decay == null) return null;
  return tool.Properties.Economy.Decay * (1 + (healEnhancers ?? 0) * 0.1) * (1 - (economyEnhancers ?? 0) * 0.01111) * ((markup ?? 100) / 100);
}

export function calculateHPS(effectiveHeal, reload) {
  return effectiveHeal != null && reload != null && reload > 0
    ? effectiveHeal / reload
    : null;
}

export function calculateHPP(effectiveHeal, healDecay) {
  return effectiveHeal != null && healDecay != null && healDecay > 0
    ? effectiveHeal / healDecay
    : null;
}

export function calculateHealAmmoBurn(tool) {
  if (tool == null || tool.Properties?.Economy?.AmmoBurn == null) return null;
  return tool.Properties.Economy.AmmoBurn;
}

export function calculateHealCost(healDecay, healAmmoBurn) {
  if (healDecay == null) return null;
  // healDecay in PEC. healAmmoBurn in ammo units (÷100 = PEC). Result in PEC.
  return healDecay + (healAmmoBurn ?? 0) / 100;
}

export function calculateHealTotalUses(tool, healEnhancers, economyEnhancers) {
  if (tool == null) return null;
  const maxTT = tool.Properties?.Economy?.MaxTT ?? null;
  const minTT = tool.Properties?.Economy?.MinTT ?? 0;
  const baseDecay = tool.Properties?.Economy?.Decay;
  if (maxTT == null || baseDecay == null) return null;
  const decay = baseDecay * (1 + (healEnhancers ?? 0) * 0.1) * (1 - (economyEnhancers ?? 0) * 0.01111);
  return Math.floor((maxTT - minTT) / (decay / 100));
}

export function calculateHotBreakdown(tool, effectiveHeal) {
  if (tool == null || effectiveHeal == null) return null;
  const hotEffect = tool.EffectsOnUse?.find(e => e.Name === 'Heal Over Time');
  if (!hotEffect) return null;

  const hotPercent = Number(hotEffect.Values?.Strength ?? hotEffect.Strength ?? 0);
  const hotDuration = Number(hotEffect.DurationSeconds ?? hotEffect.Values?.DurationSeconds ?? 0);
  if (hotPercent <= 0 || hotDuration <= 0) return null;

  let instantHeal, hotHeal;
  if (hotPercent >= 100) {
    // Above 100%: no instant heal, HoT is 150% of the base heal
    instantHeal = 0;
    hotHeal = effectiveHeal * 1.5;
  } else {
    instantHeal = effectiveHeal * (1 - hotPercent / 100);
    hotHeal = effectiveHeal * (hotPercent / 100);
  }

  return {
    hotPercent,
    hotDuration,
    instantHeal,
    hotHeal,
    hotHPS: hotHeal / hotDuration
  };
}

export function calculateHealMultiplier(allEffects) {
  if (!Array.isArray(allEffects)) return 1;
  // "Healing Increased"/"Healing Decreased" are prefix-summarized (base: "Healing", type: "mult")
  // signedTotal can be negative if Healing Decreased outweighs Increased
  const healingEffect = allEffects.find(e =>
    e?.prefix?.type === 'mult' && e?.prefix?.base === 'Healing'
  );
  const healingPct = healingEffect?.signedTotal ?? 0;

  // "Electrotherapy" is a standalone effect (no suffix rule)
  const electroEffect = allEffects.find(e => e?.name === 'Electrotherapy');
  const electroPct = electroEffect?.signedTotal ?? 0;

  if (Math.abs(healingPct) < 0.0001 && Math.abs(electroPct) < 0.0001) return 1;

  // Multiplicative stacking (this might be wrong — could be additive instead)
  return (1 + healingPct / 100) * (1 + electroPct / 100);
}

export function calculateLifestealHPS(dps, allEffects) {
  if (dps == null || dps <= 0 || !Array.isArray(allEffects)) return null;
  const lifestealEffect = allEffects.find(e => e?.name === 'Lifesteal Added');
  const lifestealPct = lifestealEffect?.signedTotal ?? 0;
  if (lifestealPct <= 0) return null;
  return dps * lifestealPct / 100;
}
