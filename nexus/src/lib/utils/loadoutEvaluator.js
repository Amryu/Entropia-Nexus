// @ts-nocheck
// Converts a loadout + resolved entities into computed stats and an "active effects" summary.
// No Svelte stores, no fetch; callers pass in everything needed.

import { hasItemTag } from '$lib/util.js';
import * as LoadoutCalc from '$lib/utils/loadoutCalculations.js';
import {
  getEffectStrength,
  getCatalogPolarity,
  summarizeEffects,
  getOffensiveTotals,
  groupEffects
} from '$lib/utils/loadoutEffects.js';

const DEFAULT_ARMOR_SLOTS = ['Head', 'Torso', 'Arms', 'Hands', 'Legs', 'Shins', 'Feet'];

const defaultIsLimitedName = (name) => !!name && hasItemTag(name, 'L');

function findByName(list, name) {
  if (!name || !Array.isArray(list)) return null;
  return list.find(x => x?.Name === name) || null;
}

function uniqueEffectsByNameHighestPieces(effects, getPieces) {
  const list = Array.isArray(effects) ? effects : [];
  const pieceCount = Number(getPieces?.()) || 0;
  return list
    .filter(effect => (effect?.MinSetPieces ?? effect?.Values?.MinSetPieces ?? 0) <= pieceCount)
    .sort((a, b) => (b?.MinSetPieces ?? b?.Values?.MinSetPieces ?? 0) - (a?.MinSetPieces ?? a?.Values?.MinSetPieces ?? 0))
    .filter((value, index, self) => self.findIndex(effect => effect?.Name === value?.Name) === index);
}

function getActiveArmorSetEffects(loadout, armorSlots, armors, armorSets) {
  const slotList = armorSlots || DEFAULT_ARMOR_SLOTS;
  const manageIndividual = !!loadout?.Gear?.Armor?.ManageIndividual;
  const setName = loadout?.Gear?.Armor?.SetName || null;

  const equippedArmors = slotList
    .map(slot => findByName(armors, loadout?.Gear?.Armor?.[slot]?.Name))
    .filter(Boolean);

  const setsFromGear = equippedArmors
    .map(armor => armor?.Set)
    .filter(Boolean);

  const uniqueSetNames = [...new Set(setsFromGear.map(set => set?.Name).filter(Boolean))];

  // Piece count per set is derived from actual equipped armor items (not just selected set name).
  const pieceCountBySet = new Map();
  equippedArmors.forEach(armor => {
    const name = armor?.Set?.Name;
    if (!name) return;
    pieceCountBySet.set(name, (pieceCountBySet.get(name) || 0) + 1);
  });

  const result = [];
  if (!manageIndividual && setName) {
    const set = findByName(armorSets, setName);
    // In set mode, assume full set — individual pieces may not exist in the database
    const pieces = pieceCountBySet.get(setName) || slotList.length;
    if (!set?.EffectsOnSetEquip) return [];
    return uniqueEffectsByNameHighestPieces(set.EffectsOnSetEquip, () => pieces);
  }

  if (manageIndividual) {
    uniqueSetNames.forEach(name => {
      const set = findByName(armorSets, name);
      const pieces = pieceCountBySet.get(name) || 0;
      if (!set?.EffectsOnSetEquip) return;
      result.push(...uniqueEffectsByNameHighestPieces(set.EffectsOnSetEquip, () => pieces));
    });
  }

  return result;
}

function getClothingEquipEffects(loadout, clothing) {
  const list = loadout?.Gear?.Clothing || [];
  return list.flatMap(entry => {
    const item = findByName(clothing, entry?.Name);
    return item?.EffectsOnEquip ?? [];
  });
}

function getClothingSetEffects(loadout, clothing) {
  const list = loadout?.Gear?.Clothing || [];
  const bySet = new Map();

  list.forEach(entry => {
    const item = findByName(clothing, entry?.Name);
    if (!item?.Set?.Name || !item?.Set?.EffectsOnSetEquip?.length) return;
    const setName = item.Set.Name;
    const existing = bySet.get(setName) || { items: [], effects: item.Set.EffectsOnSetEquip };
    existing.items.push(item);
    bySet.set(setName, existing);
  });

  const effects = [];
  bySet.forEach(({ items, effects: setEffects }) => {
    const pieceCount = items.length;
    const activeEffects = (setEffects || [])
      .filter(effect => effect?.Values?.MinSetPieces == null || effect.Values.MinSetPieces <= pieceCount)
      .sort((a, b) => (b?.Values?.MinSetPieces ?? 0) - (a?.Values?.MinSetPieces ?? 0))
      .filter((value, index, self) => self.findIndex(effect => effect?.Name === value?.Name) === index);
    effects.push(...activeEffects);
  });

  return effects;
}

function getPetEffectStrength(effect) {
  return effect?.Properties?.Strength ?? effect?.Values?.Strength ?? effect?.Values?.Value ?? 0;
}

function getPetEffectKey(effect) {
  const name = effect?.Name || '';
  const strength = getPetEffectStrength(effect);
  return `${name}::${strength}`;
}

function getActivePetEffect(loadout, pets) {
  if (!loadout?.Gear?.Pet?.Name || !loadout.Gear.Pet.Effect) return null;
  const pet = findByName(pets, loadout.Gear.Pet.Name);
  if (!pet?.Effects) return null;
  const target = loadout.Gear.Pet.Effect;
  const keyedMatch = pet.Effects.find(effect => getPetEffectKey(effect) === target);
  if (keyedMatch) return keyedMatch;
  return pet.Effects.find(effect => effect?.Name === target) || null;
}

function buildConsumableEffects(loadout, stimulants, effectsCatalog) {
  // Only the strongest instance per effect name counts (positive/negative separated by IsPositive).
  const consumableList = loadout?.Gear?.Consumables || [];
  const best = new Map();

  consumableList.forEach(entry => {
    const item = findByName(stimulants, entry?.Name);
    (item?.EffectsOnConsume || []).forEach(effect => {
      const name = effect?.Name;
      if (!name) return;
      const strength = getEffectStrength(effect);
      const polarity = getCatalogPolarity(effectsCatalog, name) || 'positive';
      const current = best.get(name) || { positive: 0, negative: 0 };
      if (polarity === 'negative') {
        if (strength > current.negative) current.negative = strength;
      } else {
        if (strength > current.positive) current.positive = strength;
      }
      best.set(name, current);
    });
  });

  const effects = [];
  best.forEach((value, name) => {
    if (value.positive) effects.push({ Name: name, Values: { Strength: value.positive } });
    if (value.negative) effects.push({ Name: name, Values: { Strength: value.negative } });
  });
  return effects;
}

function getWeaponEquipEffects(loadout, entities) {
  const weapon = findByName(entities.weapons, loadout?.Gear?.Weapon?.Name);
  if (!weapon) return [];

  const amplifier = findByName(entities.amplifiers, loadout?.Gear?.Weapon?.Amplifier?.Name);
  const scope = findByName(entities.scopes, loadout?.Gear?.Weapon?.Scope?.Name);
  const scopeSight = findByName(entities.sights, loadout?.Gear?.Weapon?.Scope?.Sight?.Name);
  const sight = findByName(entities.sights, loadout?.Gear?.Weapon?.Sight?.Name);
  const matrix = findByName(entities.matrices, loadout?.Gear?.Weapon?.Matrix?.Name);
  const implant = findByName(entities.implants, loadout?.Gear?.Weapon?.Implant?.Name);
  const absorber = findByName(entities.absorbers, loadout?.Gear?.Weapon?.Absorber?.Name);

  return [
    ...(weapon.EffectsOnEquip ?? []),
    ...(amplifier?.EffectsOnEquip ?? []),
    ...(scope?.EffectsOnEquip ?? []),
    ...(scopeSight?.EffectsOnEquip ?? []),
    ...(sight?.EffectsOnEquip ?? []),
    ...(matrix?.EffectsOnEquip ?? []),
    ...(implant?.EffectsOnEquip ?? []),
    ...(absorber?.EffectsOnEquip ?? [])
  ];
}

function getWeaponUseEffects(loadout, entities) {
  const weapon = findByName(entities.weapons, loadout?.Gear?.Weapon?.Name);
  if (!weapon) return [];

  const amplifier = findByName(entities.amplifiers, loadout?.Gear?.Weapon?.Amplifier?.Name);
  const scope = findByName(entities.scopes, loadout?.Gear?.Weapon?.Scope?.Name);
  const scopeSight = findByName(entities.sights, loadout?.Gear?.Weapon?.Scope?.Sight?.Name);
  const sight = findByName(entities.sights, loadout?.Gear?.Weapon?.Sight?.Name);
  const matrix = findByName(entities.matrices, loadout?.Gear?.Weapon?.Matrix?.Name);
  const implant = findByName(entities.implants, loadout?.Gear?.Weapon?.Implant?.Name);
  const absorber = findByName(entities.absorbers, loadout?.Gear?.Weapon?.Absorber?.Name);

  return [
    ...(weapon.EffectsOnUse ?? []),
    ...(amplifier?.EffectsOnUse ?? []),
    ...(scope?.EffectsOnUse ?? []),
    ...(scopeSight?.EffectsOnUse ?? []),
    ...(sight?.EffectsOnUse ?? []),
    ...(matrix?.EffectsOnUse ?? []),
    ...(implant?.EffectsOnUse ?? []),
    ...(absorber?.EffectsOnUse ?? [])
  ];
}

function getArmorEquipEffects(loadout, armorSlots, entities) {
  const slotList = armorSlots || DEFAULT_ARMOR_SLOTS;
  return slotList.flatMap(slot => {
    const armor = findByName(entities.armors, loadout?.Gear?.Armor?.[slot]?.Name);
    if (!armor) return [];
    const plate = findByName(entities.armorPlatings, loadout?.Gear?.Armor?.[slot]?.Plate?.Name);
    return [
      ...(armor.EffectsOnEquip ?? []),
      ...(plate?.EffectsOnEquip ?? [])
    ];
  });
}

function getMarkupCost(item, markupPercent) {
  return LoadoutCalc.calculateMarkupCost(item, markupPercent);
}

function calcArmorMarkupCost(loadout, armorSlots, entities, isLimitedName) {
  if (!loadout?.Markup) return null;
  const slotList = armorSlots || DEFAULT_ARMOR_SLOTS;
  let total = 0;
  let hasAny = false;
  slotList.forEach(slot => {
    const armorName = loadout?.Gear?.Armor?.[slot]?.Name;
    if (!armorName || !isLimitedName(armorName)) return;
    const armor = findByName(entities.armors, armorName);
    const markup = loadout?.Gear?.Armor?.ManageIndividual
      ? loadout.Markup?.Armors?.[slot]
      : loadout.Markup?.ArmorSet;
    const cost = getMarkupCost(armor, markup);
    if (cost == null) return;
    total += cost;
    hasAny = true;
  });
  return hasAny ? total : null;
}

function calcPlateMarkupCost(loadout, armorSlots, entities, isLimitedName) {
  if (!loadout?.Markup) return null;
  const slotList = armorSlots || DEFAULT_ARMOR_SLOTS;
  let total = 0;
  let hasAny = false;
  slotList.forEach(slot => {
    const plateName = loadout?.Gear?.Armor?.[slot]?.Plate?.Name;
    if (!plateName || !isLimitedName(plateName)) return;
    const plate = findByName(entities.armorPlatings, plateName);
    const markup = loadout?.Gear?.Armor?.ManageIndividual
      ? loadout.Markup?.Plates?.[slot]
      : loadout.Markup?.PlateSet;
    const cost = getMarkupCost(plate, markup);
    if (cost == null) return;
    total += cost;
    hasAny = true;
  });
  return hasAny ? total : null;
}

export function evaluateLoadout(loadout, context = {}, options = {}) {
  if (!loadout) {
    return {
      stats: {},
      effects: { all: [], offensive: [], defensive: [], utility: [] },
      offensiveTotals: { damage: 0, reload: 0, critChance: 0, critDamage: 0 }
    };
  }

  const armorSlots = context.armorSlots || DEFAULT_ARMOR_SLOTS;
  const entities = {
    weapons: context.weapons || [],
    amplifiers: context.amplifiers || [],
    scopes: context.scopes || [],
    sights: context.sights || [],
    absorbers: context.absorbers || [],
    matrices: context.matrices || [],
    implants: context.implants || [],
    armors: context.armors || [],
    armorPlatings: context.armorPlatings || [],
    armorSets: context.armorSets || [],
    clothing: context.clothing || [],
    pets: context.pets || [],
    stimulants: context.stimulants || [],
    medicalTools: context.medicalTools || []
  };

  const effectsCatalog = options.effectsCatalog || [];
  const effectCaps = options.effectCaps || {};
  const isLimitedName = options.isLimitedName || defaultIsLimitedName;

  // ---------- Effects ----------
  const weaponEquipEffects = getWeaponEquipEffects(loadout, entities);
  const weaponUseEffects = getWeaponUseEffects(loadout, entities);
  const armorEquipEffects = getArmorEquipEffects(loadout, armorSlots, entities);
  const armorSetEffects = getActiveArmorSetEffects(loadout, armorSlots, entities.armors, entities.armorSets) || [];
  const clothingEquipEffects = getClothingEquipEffects(loadout, entities.clothing);
  const clothingSetEffects = getClothingSetEffects(loadout, entities.clothing);

  // Healing tool effects
  const healingTool = findByName(entities.medicalTools, loadout?.Gear?.Healing?.Name);
  const healingEquipEffects = healingTool?.EffectsOnEquip ?? [];
  const healingUseEffects = healingTool?.EffectsOnUse ?? [];

  // Bonus stats: count toward Total cap only (ignore Item/Action caps).
  const bonusEffects = [
    { Name: 'Damage Increased', Values: { Strength: Number(loadout?.Properties?.BonusDamage ?? 0) || 0 } },
    { Name: 'Critical Chance Added', Values: { Strength: Number(loadout?.Properties?.BonusCritChance ?? 0) || 0 } },
    { Name: 'Critical Damage Added', Values: { Strength: Number(loadout?.Properties?.BonusCritDamage ?? 0) || 0 } },
    { Name: 'Reload Speed Increased', Values: { Strength: Number(loadout?.Properties?.BonusReload ?? 0) || 0 } }
  ].filter(effect => Math.abs(getEffectStrength(effect)) > 0.0001);

  const consumableEffects = buildConsumableEffects(loadout, entities.stimulants, effectsCatalog);
  const petEffect = getActivePetEffect(loadout, entities.pets);

  const itemEffects = [
    ...weaponEquipEffects,
    ...weaponUseEffects,
    ...armorEquipEffects,
    ...armorSetEffects,
    ...clothingEquipEffects,
    ...clothingSetEffects,
    ...healingEquipEffects,
    ...healingUseEffects
  ];
  if (petEffect) itemEffects.push(petEffect);

  const allEffects = summarizeEffects(
    {
      itemEffects,
      actionEffects: consumableEffects,
      bonusEffects
    },
    { effectsCatalog, effectCaps }
  );

  const offensiveTotals = getOffensiveTotals(allEffects);
  const { offensive, defensive, utility } = groupEffects(allEffects);

  // ---------- Stats ----------
  const weapon = findByName(entities.weapons, loadout?.Gear?.Weapon?.Name);
  const amplifier = findByName(entities.amplifiers, loadout?.Gear?.Weapon?.Amplifier?.Name);
  const absorber = findByName(entities.absorbers, loadout?.Gear?.Weapon?.Absorber?.Name);
  const implant = findByName(entities.implants, loadout?.Gear?.Weapon?.Implant?.Name);
  const scope = findByName(entities.scopes, loadout?.Gear?.Weapon?.Scope?.Name);
  const scopeSight = findByName(entities.sights, loadout?.Gear?.Weapon?.Scope?.Sight?.Name);
  const sight = findByName(entities.sights, loadout?.Gear?.Weapon?.Sight?.Name);
  const matrix = findByName(entities.matrices, loadout?.Gear?.Weapon?.Matrix?.Name);

  const armorPieces = armorSlots.map(slot => findByName(entities.armors, loadout?.Gear?.Armor?.[slot]?.Name));
  const platePieces = armorSlots.map(slot => findByName(entities.armorPlatings, loadout?.Gear?.Armor?.[slot]?.Plate?.Name));

  const totalDamage = LoadoutCalc.calculateTotalDamage(
    weapon,
    loadout?.Gear?.Weapon?.Enhancers?.Damage ?? 0,
    offensiveTotals.damage ?? 0,
    amplifier
  );

  const critAbility = LoadoutCalc.calculateCritAbility(
    weapon,
    loadout?.Skill?.Hit ?? 0,
    loadout?.Gear?.Weapon?.Enhancers?.SkillMod ?? 0
  );

  const critChance = LoadoutCalc.calculateCritChance(
    critAbility,
    loadout?.Gear?.Weapon?.Enhancers?.Accuracy ?? 0,
    offensiveTotals.critChance ?? 0
  );

  const critDamage = LoadoutCalc.calculateCritDamage(offensiveTotals.critDamage ?? 0);

  const hitAbility = LoadoutCalc.calculateHitAbility(
    weapon,
    loadout?.Skill?.Hit ?? 0,
    loadout?.Gear?.Weapon?.Enhancers?.SkillMod ?? 0
  );

  const damageInterval = LoadoutCalc.calculateDamageInterval(
    weapon,
    loadout?.Skill?.Dmg ?? 0,
    loadout?.Gear?.Weapon?.Enhancers?.SkillMod ?? 0,
    totalDamage
  );

  const effectiveDamage = LoadoutCalc.calculateEffectiveDamage(damageInterval, critChance, critDamage, hitAbility);

  const range = LoadoutCalc.calculateRange(
    weapon,
    loadout?.Skill?.Hit ?? 0,
    loadout?.Gear?.Weapon?.Enhancers?.SkillMod ?? 0,
    loadout?.Gear?.Weapon?.Enhancers?.Range ?? 0
  );

  const reload = LoadoutCalc.calculateReload(
    weapon,
    loadout?.Skill?.Hit ?? 0,
    loadout?.Gear?.Weapon?.Enhancers?.SkillMod ?? 0,
    offensiveTotals.reload ?? 0
  );

  const decay = LoadoutCalc.calculateDecay(
    weapon,
    loadout?.Gear?.Weapon?.Enhancers?.Damage ?? 0,
    loadout?.Gear?.Weapon?.Enhancers?.Economy ?? 0,
    absorber,
    implant,
    amplifier,
    scope,
    scopeSight,
    sight,
    matrix,
    loadout?.Markup || {}
  );

  const ammo = LoadoutCalc.calculateAmmoBurn(
    weapon,
    loadout?.Gear?.Weapon?.Enhancers?.Damage ?? 0,
    loadout?.Gear?.Weapon?.Enhancers?.Economy ?? 0,
    amplifier
  );

  const cost = LoadoutCalc.calculateCost(decay, ammo, loadout?.Markup?.Ammo ?? 100);

  const dpp = LoadoutCalc.calculateDPP(effectiveDamage, cost);
  const dps = LoadoutCalc.calculateDPS(effectiveDamage, reload);

  const weaponCost = LoadoutCalc.calculateWeaponCost(
    weapon,
    loadout?.Gear?.Weapon?.Enhancers?.Damage ?? 0,
    loadout?.Gear?.Weapon?.Enhancers?.Economy ?? 0
  );

  const efficiency = LoadoutCalc.calculateEfficiency(
    weapon,
    weaponCost,
    loadout?.Gear?.Weapon?.Enhancers?.Damage ?? 0,
    loadout?.Gear?.Weapon?.Enhancers?.Economy ?? 0,
    absorber,
    amplifier,
    scope,
    scopeSight,
    sight,
    matrix
  );

  const armorDefense = LoadoutCalc.calculateArmorDefense(armorPieces, loadout?.Gear?.Armor?.Enhancers?.Defense ?? 0);
  const plateDefense = LoadoutCalc.calculatePlateDefense(platePieces);
  const totalDefense = LoadoutCalc.calculateTotalDefense(armorDefense, plateDefense);

  const armorDefenseByType = LoadoutCalc.calculateArmorDefenseByType(
    armorPieces,
    loadout?.Gear?.Armor?.Enhancers?.Defense ?? 0
  );
  const plateDefenseByType = LoadoutCalc.calculatePlateDefenseByType(platePieces);
  const totalDefenseByType = LoadoutCalc.calculateTotalDefenseByType(armorDefenseByType, plateDefenseByType);
  const topDefenseTypesShort = LoadoutCalc.formatTopDefenseTypesShort(totalDefenseByType, 3);

  const armorDurability = LoadoutCalc.calculateArmorDurability(armorPieces, loadout?.Gear?.Armor?.Enhancers?.Durability ?? 0);
  const plateDurability = LoadoutCalc.calculatePlateDurability(platePieces);
  const totalAbsorption = LoadoutCalc.calculateTotalAbsorption(
    armorPieces,
    platePieces,
    loadout?.Gear?.Armor?.Enhancers?.Defense ?? 0,
    loadout?.Gear?.Armor?.Enhancers?.Durability ?? 0
  );

  const blockChance = LoadoutCalc.calculateBlockChance(platePieces);

  const skillModification = LoadoutCalc.calculateSkillModification(scope, scopeSight, sight);
  const skillBonus = LoadoutCalc.calculateSkillBonus(scope, scopeSight, sight);

  const lowestTotalUses = LoadoutCalc.calculateLowestTotalUses(
    weapon,
    loadout?.Gear?.Weapon?.Enhancers?.Damage ?? 0,
    loadout?.Gear?.Weapon?.Enhancers?.Economy ?? 0,
    absorber,
    implant,
    amplifier,
    scope,
    scopeSight,
    sight,
    matrix
  );

  const armorMarkupCost = calcArmorMarkupCost(loadout, armorSlots, entities, isLimitedName);
  const plateMarkupCost = calcPlateMarkupCost(loadout, armorSlots, entities, isLimitedName);

  // ---------- Healing Stats ----------
  const healEnhancers = loadout?.Gear?.Healing?.Enhancers?.Heal ?? 0;
  const healEcoEnhancers = loadout?.Gear?.Healing?.Enhancers?.Economy ?? 0;
  const healSkillModEnhancers = loadout?.Gear?.Healing?.Enhancers?.SkillMod ?? 0;

  const totalHeal = LoadoutCalc.calculateTotalHeal(healingTool, healEnhancers);
  const healInterval = LoadoutCalc.calculateHealInterval(
    healingTool,
    loadout?.Skill?.Heal ?? 0,
    healSkillModEnhancers,
    healEnhancers
  );
  const effectiveHeal = LoadoutCalc.calculateEffectiveHeal(healInterval);
  const healReload = LoadoutCalc.calculateHealReload(
    healingTool,
    loadout?.Skill?.Heal ?? 0,
    healSkillModEnhancers
  );
  const healDecay = LoadoutCalc.calculateHealDecay(
    healingTool,
    healEnhancers,
    healEcoEnhancers,
    loadout?.Markup?.HealingTool ?? 100
  );
  const hps = LoadoutCalc.calculateHPS(effectiveHeal, healReload);
  const hpp = LoadoutCalc.calculateHPP(effectiveHeal, healDecay);
  const healTotalUses = LoadoutCalc.calculateHealTotalUses(
    healingTool,
    healEnhancers,
    healEcoEnhancers
  );

  return {
    offensiveTotals,
    effects: {
      all: allEffects,
      offensive,
      defensive,
      utility
    },
    stats: {
      totalDamage,
      effectiveDamage,
      damageInterval,
      hitAbility,
      critAbility,
      critChance,
      critDamage,
      range,
      reload,
      decay,
      ammo,
      cost,
      dpp,
      dps,
      weaponCost,
      efficiency,
      armorDefense,
      plateDefense,
      totalDefense,
      armorDefenseByType,
      plateDefenseByType,
      totalDefenseByType,
      topDefenseTypesShort,
      armorDurability,
      plateDurability,
      totalAbsorption,
      blockChance,
      skillModification,
      skillBonus,
      lowestTotalUses,
      armorMarkupCost,
      plateMarkupCost,
      totalHeal,
      healInterval,
      effectiveHeal,
      healReload,
      healDecay,
      hps,
      hpp,
      healTotalUses
    }
  };
}
