// @ts-nocheck
/**
 * (L) Weapon Profitability Calculator
 *
 * Evaluates whether an (L) weapon's efficiency advantage generates enough
 * extra TT returns over its lifetime to justify the markup premium paid.
 *
 * Game mechanics:
 * - Efficiency adds linearly: X% efficiency returns X * 0.07% more of cycled PED
 * - TT cycling = full cost per use at TT rates (decay + ammo, all at 100% MU)
 * - Decay premium = per-use cost above TT on decay components only (not ammo)
 * - UL items have 0 premium (repairable at TT)
 */

import {
  calculateTotalDamage,
  calculateDPS,
  calculateDPP,
  calculateCost,
  calculateDecay,
  calculateAmmoBurn,
  calculateEfficiency,
  calculateLowestTotalUses,
  calculateWeaponCost,
  calculateItemTotalDamage
} from '$lib/utils/loadoutCalculations.js';

/** Simplified effective damage factor (no skill dependency):
 *  88% hit chance at 75% avg damage + 2% crit at 175% damage */
const EFFECTIVE_DAMAGE_FACTOR = 0.88 * 0.75 + 0.02 * 1.75;

/** Efficiency-to-returns multiplier: 7% spread over 0-100% efficiency */
const EFFICIENCY_RETURNS_FACTOR = 0.07;

/** All-100% markup object for TT-rate calculations */
const TT_MARKUPS = Object.freeze({
  Weapon: 100, Absorber: 100, Implant: 100, Amplifier: 100,
  Scope: 100, ScopeSight: 100, Sight: 100, Matrix: 100
});

// ========== Core Profitability Functions ==========

/**
 * Calculate the decay premium per use (PEC above TT on decay only).
 * Premium = totalDecayAtMU - totalDecayAtTT
 */
export function calculateDecayPremiumPerUse(
  weapon, dmgEnh, ecoEnh, absorber, implant, amplifier,
  scope, scopeSight, sight, matrix, markups, weaponClass
) {
  const decayAtMU = calculateDecay(
    weapon, dmgEnh, ecoEnh, absorber, implant, amplifier,
    scope, scopeSight, sight, matrix, markups, weaponClass
  );
  const decayAtTT = calculateDecay(
    weapon, dmgEnh, ecoEnh, absorber, implant, amplifier,
    scope, scopeSight, sight, matrix, TT_MARKUPS, weaponClass
  );
  if (decayAtMU == null || decayAtTT == null) return null;
  return decayAtMU - decayAtTT;
}

/**
 * Calculate the weapon's TT cost per use (weapon decay + ammo at TT).
 * This is the weapon's own cycle cost - attachment decay is not included
 * as those costs are not directly attributed to the weapon itself.
 * Returns PEC.
 */
export function calculateWeaponTTCostPerUse(weapon, dmgEnh, ecoEnh) {
  if (!weapon?.Properties?.Economy) return null;
  const decay = weapon.Properties.Economy.Decay;
  if (decay == null) return null;
  const weaponDecay = decay * (1 + (dmgEnh ?? 0) * 0.1) * (1 - (ecoEnh ?? 0) * 0.01111);
  const ammoBurn = weapon.Properties.Economy.AmmoBurn ?? 0;
  // decay in PEC + ammoBurn (ammo units, /100 = PEC) at TT (100%)
  return weaponDecay + ammoBurn / 100;
}

/**
 * Calculate efficiency savings rate per PED cycled at TT rates.
 * Returns a fraction (e.g. 0.00217 for a 3.1% efficiency delta).
 */
export function calculateEfficiencySavingsRate(effBase, effComp) {
  if (effBase == null || effComp == null) return null;
  return (effComp - effBase) * EFFICIENCY_RETURNS_FACTOR / 100;
}

/**
 * Whether an absorber should be applied to a weapon.
 * Rule: apply only if weapon item MU% > absorber item MU%.
 */
export function shouldApplyAbsorber(weaponMarkup, absorberMarkup) {
  if (weaponMarkup == null || absorberMarkup == null) return false;
  return weaponMarkup > absorberMarkup;
}

/**
 * Calculate the break-even markup for a comparison weapon.
 * This is the maximum MU% at which the (L) weapon is still economically viable
 * compared to the base weapon (net profitability >= 0).
 *
 * The weapon decay in calculateDecay is: remaining_weapon_decay * (weaponMU/100).
 * Only the Weapon markup varies; absorber/amp/scope/etc markups are fixed.
 * So we solve: efficiencySavings = premiumDiff for compWeaponMU.
 */
export function calculateBreakEvenMarkup(
  weapon, dmgEnh, ecoEnh, absorber, implant, amplifier,
  scope, scopeSight, sight, matrix, markups, weaponClass,
  totalUses, efficiencySavings, baseTotalPremiumPED
) {
  if (totalUses == null || totalUses <= 0 || efficiencySavings == null) return null;

  // Calculate the weapon's remaining decay (after absorber absorption) at TT
  let weaponDecay = weapon?.Properties?.Economy?.Decay;
  if (weaponDecay == null) return null;
  weaponDecay = weaponDecay * (1 + (dmgEnh ?? 0) * 0.1) * (1 - (ecoEnh ?? 0) * 0.01111);

  // Absorber absorption reduces the portion of decay that weapon MU applies to
  const absorberAbsorption = absorber?.Properties?.Economy?.Absorption ?? 0;
  const implantAbsorption = (weaponClass === 'Mindforce' && implant?.Properties?.Economy?.Absorption != null)
    ? implant.Properties.Economy.Absorption : 0;
  const miningAmpAbsorption = (weapon?.Properties?.Type?.startsWith('Mining Laser') && amplifier?.Properties?.Economy?.Absorption != null)
    ? amplifier.Properties.Economy.Absorption : 0;

  const remainingWeaponDecay = weaponDecay * (1 - absorberAbsorption) * (1 - implantAbsorption) * (1 - miningAmpAbsorption);
  if (remainingWeaponDecay <= 0) return null;

  // Total premium from non-weapon components (fixed, doesn't change with weapon MU)
  const decayAtMU = calculateDecay(
    weapon, dmgEnh, ecoEnh, absorber, implant, amplifier,
    scope, scopeSight, sight, matrix, markups, weaponClass
  );
  const decayAtTT = calculateDecay(
    weapon, dmgEnh, ecoEnh, absorber, implant, amplifier,
    scope, scopeSight, sight, matrix, TT_MARKUPS, weaponClass
  );
  if (decayAtMU == null || decayAtTT == null) return null;

  const totalPremiumPerUse = decayAtMU - decayAtTT;
  const weaponPremiumPerUse = remainingWeaponDecay * ((markups?.Weapon ?? 100) / 100 - 1);
  const otherPremiumPerUse = totalPremiumPerUse - weaponPremiumPerUse;

  // Target: comp_premium - base_premium = efficiency_savings
  // comp_premium = totalUses * (remainingWeaponDecay * (MU/100 - 1) + otherPremiumPerUse) / 100
  // Solve for MU:
  const targetTotalPremiumPED = efficiencySavings + (baseTotalPremiumPED ?? 0);
  const targetPremiumPerUsePEC = targetTotalPremiumPED * 100 / totalUses;
  const weaponMUFraction = (targetPremiumPerUsePEC - otherPremiumPerUse) / remainingWeaponDecay;

  return 100 * (1 + weaponMUFraction);
}

// ========== Weapon Stats Helper ==========

/**
 * Compute all stats for a single weapon configuration.
 * Returns an object with all relevant metrics.
 */
export function computeWeaponStats(config, entities) {
  const weapon = findByName(entities.weapons, config.weaponName);
  if (!weapon) return null;

  const amplifier = findByName(entities.amplifiers, config.amplifierName);
  const absorber = findByName(entities.absorbers, config.absorberName);
  const scope = findByName(entities.scopes, config.scopeName);
  const scopeSight = findByName(entities.sights, config.scopeSightName);
  const sight = findByName(entities.sights, config.sightName);
  const matrix = findByName(entities.matrices, config.matrixName);
  const implant = findByName(entities.implants, config.implantName);

  const dmgEnh = config.damageEnhancers ?? 0;
  const ecoEnh = config.economyEnhancers ?? 0;
  const weaponClass = weapon.Properties?.Class || null;

  const markups = {
    Weapon: config.markupPercent ?? 100,
    Absorber: config.absorberMarkup ?? 100,
    Implant: config.implantMarkup ?? 100,
    Amplifier: config.amplifierMarkup ?? 100,
    Scope: config.scopeMarkup ?? 100,
    ScopeSight: config.scopeSightMarkup ?? 100,
    Sight: config.sightMarkup ?? 100,
    Matrix: config.matrixMarkup ?? 100
  };

  const ammoMarkup = config.ammoMarkup ?? 100;

  const totalDamage = calculateTotalDamage(weapon, dmgEnh, 0, amplifier);
  const effectiveDamage = totalDamage != null ? totalDamage * EFFECTIVE_DAMAGE_FACTOR : null;
  const weaponCost = calculateWeaponCost(weapon, dmgEnh, ecoEnh);

  const decayAtMU = calculateDecay(
    weapon, dmgEnh, ecoEnh, absorber, implant, amplifier,
    scope, scopeSight, sight, matrix, markups, weaponClass
  );

  const ammoBurn = calculateAmmoBurn(weapon, dmgEnh, ecoEnh, amplifier);
  const costPerUse = calculateCost(decayAtMU, ammoBurn, ammoMarkup);

  // Weapon TT cost = weapon decay + ammo only (no attachment decay)
  const ttCostPerUse = calculateWeaponTTCostPerUse(weapon, dmgEnh, ecoEnh);

  const premiumPerUse = calculateDecayPremiumPerUse(
    weapon, dmgEnh, ecoEnh, absorber, implant, amplifier,
    scope, scopeSight, sight, matrix, markups, weaponClass
  );

  const efficiency = calculateEfficiency(
    weapon, weaponCost, dmgEnh, ecoEnh,
    absorber, amplifier, scope, scopeSight, sight, matrix
  );

  const totalUses = calculateLowestTotalUses(
    weapon, dmgEnh, ecoEnh, absorber, implant, amplifier,
    scope, scopeSight, sight, matrix, weaponClass
  );

  const reload = weapon.Properties?.UsesPerMinute
    ? 60 / weapon.Properties.UsesPerMinute
    : null;

  const dpp = calculateDPP(effectiveDamage, costPerUse);
  const dps = calculateDPS(effectiveDamage, reload);

  // Total cycle = total uses * weapon TT cost per use (PED)
  const totalCyclePED = totalUses != null && ttCostPerUse != null
    ? totalUses * ttCostPerUse / 100
    : null;

  return {
    weapon,
    amplifier, absorber, scope, scopeSight, sight, matrix, implant,
    weaponClass,
    markups,
    ammoMarkup,
    dmgEnh, ecoEnh,
    totalDamage,
    effectiveDamage,
    decayAtMU,
    ammoBurn,
    costPerUse,
    ttCostPerUse,
    totalCyclePED,
    premiumPerUse,
    efficiency,
    totalUses,
    reload,
    dpp,
    dps
  };
}

// ========== Full Analysis ==========

/**
 * Analyze profitability of one comparison weapon vs one base weapon.
 * Returns a comprehensive result object for display.
 */
export function analyzeWeaponProfitability(baseStats, compStats, mobHP) {
  if (!baseStats || !compStats) return null;

  const compTotalUses = compStats.totalUses;
  if (compTotalUses == null || compTotalUses <= 0) return null;

  // Total cycle (weapon decay + ammo at TT) over comp's lifetime
  const compTotalCyclePED = compStats.totalCyclePED;

  // Premium over comp's lifetime
  const compTotalPremiumPED = compStats.premiumPerUse != null
    ? compTotalUses * compStats.premiumPerUse / 100
    : null;

  // Base premium over same number of uses
  const baseTotalPremiumPED = baseStats.premiumPerUse != null
    ? compTotalUses * baseStats.premiumPerUse / 100
    : null;

  // Efficiency savings (applied to total cycle cost)
  const savingsRate = calculateEfficiencySavingsRate(baseStats.efficiency, compStats.efficiency);
  const efficiencySavingsPED = savingsRate != null && compTotalCyclePED != null
    ? savingsRate * compTotalCyclePED
    : null;

  // Premium differential
  const premiumDiffPED = compTotalPremiumPED != null && baseTotalPremiumPED != null
    ? compTotalPremiumPED - baseTotalPremiumPED
    : null;

  // Net profitability
  const netProfitabilityPED = efficiencySavingsPED != null && premiumDiffPED != null
    ? efficiencySavingsPED - premiumDiffPED
    : null;

  // Break-even markup
  const breakEvenMU = calculateBreakEvenMarkup(
    compStats.weapon, compStats.dmgEnh, compStats.ecoEnh,
    compStats.absorber, compStats.implant, compStats.amplifier,
    compStats.scope, compStats.scopeSight, compStats.sight, compStats.matrix,
    compStats.markups, compStats.weaponClass,
    compTotalUses, efficiencySavingsPED, baseTotalPremiumPED
  );

  // DPP/DPS comparison (informational)
  const dppDiffPct = baseStats.dpp && compStats.dpp
    ? ((compStats.dpp - baseStats.dpp) / baseStats.dpp) * 100
    : null;

  const dpsDiffPct = baseStats.dps && compStats.dps
    ? ((compStats.dps - baseStats.dps) / baseStats.dps) * 100
    : null;

  // Kill analysis
  let baseKillsPerHour = null;
  let compKillsPerHour = null;
  let extraKillsOverLifetime = null;

  if (mobHP && mobHP > 0) {
    if (baseStats.dps) baseKillsPerHour = (baseStats.dps * 3600) / mobHP;
    if (compStats.dps) compKillsPerHour = (compStats.dps * 3600) / mobHP;

    // Extra kills = difference in kills over comp's total uses, based on DPP
    if (baseStats.dpp && compStats.dpp && baseStats.costPerUse && compStats.costPerUse) {
      const compTotalDmg = compStats.totalDamage != null ? compTotalUses * compStats.totalDamage : null;
      const baseTotalCostPED = compTotalUses * (baseStats.costPerUse / 100);
      const baseTotalDmg = baseTotalCostPED * baseStats.dpp;
      if (compTotalDmg != null) {
        const compKills = compTotalDmg / mobHP;
        const baseKills = baseTotalDmg / mobHP;
        extraKillsOverLifetime = compKills - baseKills;
      }
    }
  }

  return {
    // Comp lifetime stats
    compTotalUses,
    compTotalCyclePED,
    compTotalPremiumPED,
    compPremiumPerUsePEC: compStats.premiumPerUse,

    // Base stats over same period
    baseTotalPremiumPED,
    basePremiumPerUsePEC: baseStats.premiumPerUse,

    // Efficiency
    baseEfficiency: baseStats.efficiency,
    compEfficiency: compStats.efficiency,
    efficiencyDelta: baseStats.efficiency != null && compStats.efficiency != null
      ? compStats.efficiency - baseStats.efficiency : null,
    savingsRate,
    efficiencySavingsPED,

    // Premium
    premiumDiffPED,

    // Net result
    netProfitabilityPED,
    breakEvenMU,

    // DPP/DPS (informational)
    baseDPP: baseStats.dpp,
    compDPP: compStats.dpp,
    dppDiffPct,
    baseDPS: baseStats.dps,
    compDPS: compStats.dps,
    dpsDiffPct,

    // Kills
    baseKillsPerHour,
    compKillsPerHour,
    extraKillsOverLifetime,

    // Per-use costs
    baseCostPerUsePEC: baseStats.costPerUse,
    compCostPerUsePEC: compStats.costPerUse,
    baseTTCostPerUsePEC: baseStats.ttCostPerUse,
    compTTCostPerUsePEC: compStats.ttCostPerUse
  };
}

// ========== Helpers ==========

function findByName(list, name) {
  if (!name || !Array.isArray(list)) return null;
  return list.find(x => x?.Name === name) || null;
}

/**
 * Filter amplifiers compatible with a weapon by type matching.
 * Mirrors getFilteredAmplifiers() from the loadout manager.
 */
export function getCompatibleAmplifiers(weapon, amplifiers) {
  if (!weapon || !Array.isArray(amplifiers)) return [];
  const cls = weapon.Properties?.Class;
  const type = weapon.Properties?.Type;
  return amplifiers.filter(amp => {
    if (cls === 'Ranged') {
      if (type === 'BLP') return amp.Properties?.Type === 'BLP';
      if (type === 'Explosive') return amp.Properties?.Type === 'Explosive';
      if (type?.startsWith('Mining Laser')) return amp.Properties?.Type === 'Mining';
      return amp.Properties?.Type === 'Energy';
    }
    if (cls === 'Melee') return amp.Properties?.Type === 'Melee';
    if (cls === 'Mindforce') return amp.Properties?.Type === 'Mindforce';
    return false;
  });
}

/**
 * Check if a weapon type uses ammo with variable markup (explosive).
 */
export function weaponUsesExplosiveAmmo(weapon) {
  return weapon?.Properties?.Type === 'Explosive';
}

/**
 * Create a default weapon config object.
 */
export function createDefaultWeaponConfig() {
  return {
    weaponName: null,
    damageEnhancers: 0,
    economyEnhancers: 0,
    amplifierName: null,
    amplifierMarkup: 100,
    amplifierMarkupSource: 'custom',
    absorberName: null,
    absorberMarkup: 100,
    absorberMarkupSource: 'custom',
    scopeName: null,
    scopeMarkup: 100,
    scopeMarkupSource: 'custom',
    scopeSightName: null,
    scopeSightMarkup: 100,
    scopeSightMarkupSource: 'custom',
    sightName: null,
    sightMarkup: 100,
    sightMarkupSource: 'custom',
    matrixName: null,
    matrixMarkup: 100,
    matrixMarkupSource: 'custom',
    implantName: null,
    implantMarkup: 100,
    implantMarkupSource: 'custom',
    markupPercent: 100,
    markupSource: 'custom',
    ammoMarkup: 100
  };
}

/**
 * Extract a weapon config from a loadout's weapon gear/markup data.
 */
export function extractConfigFromLoadout(gear, markup) {
  return {
    weaponName: gear?.Name ?? null,
    damageEnhancers: gear?.Enhancers?.Damage ?? 0,
    economyEnhancers: gear?.Enhancers?.Economy ?? 0,
    amplifierName: gear?.Amplifier?.Name ?? null,
    amplifierMarkup: markup?.Amplifier ?? 100,
    amplifierMarkupSource: 'custom',
    absorberName: gear?.Absorber?.Name ?? null,
    absorberMarkup: markup?.Absorber ?? 100,
    absorberMarkupSource: 'custom',
    scopeName: gear?.Scope?.Name ?? null,
    scopeMarkup: markup?.Scope ?? 100,
    scopeMarkupSource: 'custom',
    scopeSightName: gear?.Scope?.Sight?.Name ?? null,
    scopeSightMarkup: markup?.ScopeSight ?? 100,
    scopeSightMarkupSource: 'custom',
    sightName: gear?.Sight?.Name ?? null,
    sightMarkup: markup?.Sight ?? 100,
    sightMarkupSource: 'custom',
    matrixName: gear?.Matrix?.Name ?? null,
    matrixMarkup: markup?.Matrix ?? 100,
    matrixMarkupSource: 'custom',
    implantName: gear?.Implant?.Name ?? null,
    implantMarkup: markup?.Implant ?? 100,
    implantMarkupSource: 'custom',
    markupPercent: markup?.Weapon ?? 100,
    markupSource: 'custom',
    ammoMarkup: markup?.Ammo ?? 100
  };
}

/**
 * Format a PED value for display with sign and color class.
 */
export function formatPED(value, decimals = 2) {
  if (value == null) return { text: 'N/A', class: '' };
  const sign = value >= 0 ? '+' : '';
  return {
    text: `${sign}${value.toFixed(decimals)} PED`,
    class: value > 0.005 ? 'positive' : value < -0.005 ? 'negative' : 'neutral'
  };
}

/**
 * Format a percentage value for display.
 */
export function formatPct(value, decimals = 1) {
  if (value == null) return 'N/A';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}%`;
}

/**
 * Format a number with thousands separator.
 */
export function formatNumber(value, decimals = 0) {
  if (value == null) return 'N/A';
  return value.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
}
