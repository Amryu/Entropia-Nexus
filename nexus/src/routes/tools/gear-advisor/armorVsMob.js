// @ts-nocheck
import { hasItemTag } from '$lib/util';

/**
 * Armor vs Mob calculations.
 *
 * Core model:
 *   - Armor is treated as a full set (not per-piece).
 *   - Effective defense per type = armorSet.Defense * (1 + 0.05 * enhancers)
 *                                + plating.Defense
 *                                + iceShieldBonus
 *   - Mobs deal flat damage per type (50%-100% range).
 *   - Armor provides flat damage reduction per type, capped at incoming damage.
 *
 * Data shapes come from common/schemas/ArmorSet.js, ArmorPlating.js, Mob.js.
 */

export const DEFENSE_TYPES = [
  'Impact', 'Cut', 'Stab', 'Penetration', 'Shrapnel',
  'Burn', 'Cold', 'Acid', 'Electric'
];

const ICE_SHIELD_TYPES = ['Impact', 'Stab', 'Cut', 'Shrapnel', 'Penetration', 'Burn'];
export const ICE_SHIELD_VALUE = 75;
export const MAX_ENHANCERS = 10;
export const ENHANCER_BONUS_PER_LEVEL = 0.05;

const DAMAGE_MIN_FRACTION = 0.5;
const DAMAGE_MAX_FRACTION = 1.0;
const DAMAGE_AVG_FRACTION = (DAMAGE_MIN_FRACTION + DAMAGE_MAX_FRACTION) / 2; // 0.75

// Crit model: up to 2× max damage, pierces 20% of armor defense.
export const CRIT_MULTIPLIER = 2.0;
export const CRIT_ARMOR_PIERCE = 0.20;

/**
 * Compute effective armor defense broken down by damage type.
 * @param {object} armorSet - armor set entity
 * @param {object|null} plating - optional plating entity
 * @param {boolean} iceShield - whether Ice Shield buff is active
 * @param {number} enhancers - defense enhancers equipped (0..10)
 * @returns {Record<string, number>} defense by type
 */
export function computeEffectiveDefense(armorSet, plating, iceShield, enhancers) {
  const enhancerMult = 1 + (Math.max(0, Math.min(MAX_ENHANCERS, enhancers ?? 0)) * ENHANCER_BONUS_PER_LEVEL);
  const result = {};
  for (const type of DEFENSE_TYPES) {
    const armorVal = (armorSet?.Properties?.Defense?.[type] ?? 0) * enhancerMult;
    const plateVal = plating?.Properties?.Defense?.[type] ?? 0;
    const iceVal = iceShield && ICE_SHIELD_TYPES.includes(type) ? ICE_SHIELD_VALUE : 0;
    result[type] = armorVal + plateVal + iceVal;
  }
  return result;
}

/**
 * Compute per-damage-type blocked/taken values for a single attack and
 * the three damage-range points (min/avg/max).
 *
 * Data shape:
 *   attack.TotalDamage — scalar total damage per hit (e.g. 230)
 *   attack.Damage[type] — percentage composition 0–100 (e.g. Stab: 33.33)
 *
 * Damage per type at 100% roll = TotalDamage * (percentage / 100).
 * Mob rolls are 50%–100% of base each hit (linear scaling).
 *
 * @param {object} attack - mob attack
 * @param {Record<string, number>} defense - effective armor defense by type
 * @param {number} dmgMultiplier - pre-mitigation damage multiplier (1 = unmodified)
 */
/**
 * Expected damage taken per damage type, integrated over a uniform roll
 * X ∈ [DAMAGE_MIN_FRACTION, DAMAGE_MAX_FRACTION].
 *
 *   B = base damage per type at 100% roll (= TotalDamage × pct)
 *   def = armor defense for this type
 *
 *   if B ≤ def                  → E[taken] = 0 (always fully blocked)
 *   if B × DAMAGE_MIN ≥ def     → E[taken] = B × DAMAGE_AVG − def (def never covers)
 *   otherwise (mixed)           → E[taken] = (B − def)² / (2·(DAMAGE_MAX − DAMAGE_MIN)·B)
 *                                          × (here: (B − def)² / B since range is 0.5)
 */
function expectedTakenPerType(base, def) {
  if (base <= 0) return 0;
  const maxD = base * DAMAGE_MAX_FRACTION;
  const minD = base * DAMAGE_MIN_FRACTION;
  if (def >= maxD) return 0;                       // never pierces
  if (def <= minD) return base * DAMAGE_AVG_FRACTION - def; // always pierces
  // Mixed case. Crossover X* = def/base in (MIN, MAX).
  // E[taken] = (1/(MAX-MIN)) × ∫[X*, MAX] (B·X − def) dX
  //          = (1/0.5)       × [B·X²/2 − def·X] from X* to MAX
  // Simplified: (B − def)² / B    (uses MIN=0.5, MAX=1.0, range=0.5)
  return (base - def) * (base - def) / base;
}

export function computeAttackBreakdown(attack, defense, dmgMultiplier = 1) {
  const totalDmg = (attack?.TotalDamage ?? 0) * dmgMultiplier;
  const byType = {};
  let incomingMin = 0, incomingAvg = 0, incomingMax = 0;
  let blockedMin = 0, blockedAvg = 0, blockedMax = 0;
  let expectedTaken = 0;
  let critIncoming = 0, critBlocked = 0;
  const piercedDefMult = 1 - CRIT_ARMOR_PIERCE;

  for (const type of DEFENSE_TYPES) {
    const pct = (attack?.Damage?.[type] ?? 0) / 100;
    const base = totalDmg * pct;
    if (base === 0) continue;

    const minD = base * DAMAGE_MIN_FRACTION;
    const avgD = base * DAMAGE_AVG_FRACTION;
    const maxD = base * DAMAGE_MAX_FRACTION;
    const def = defense?.[type] ?? 0;
    const bMin = Math.min(minD, def);
    const bAvg = Math.min(avgD, def);
    const bMax = Math.min(maxD, def);

    // Crit: 2× max damage vs armor reduced by pierce fraction.
    const critD = base * CRIT_MULTIPLIER;
    const piercedDef = def * piercedDefMult;
    const bCrit = Math.min(critD, piercedDef);

    byType[type] = {
      min: minD, avg: avgD, max: maxD,
      blockedMin: bMin, blockedAvg: bAvg, blockedMax: bMax,
      takenMin: minD - bMin, takenAvg: avgD - bAvg, takenMax: maxD - bMax
    };

    incomingMin += minD;
    incomingAvg += avgD;
    incomingMax += maxD;
    blockedMin += bMin;
    blockedAvg += bAvg;
    blockedMax += bMax;
    expectedTaken += expectedTakenPerType(base, def);
    critIncoming += critD;
    critBlocked += bCrit;
  }

  const takenMin = incomingMin - blockedMin;
  const takenAvg = incomingAvg - blockedAvg;
  const takenMax = incomingMax - blockedMax;
  // incomingAvg = 0.75 × totalDmg is the true expected incoming damage
  // (mean of a uniform distribution on [0.5, 1.0] × TotalDamage).
  const expectedBlocked = incomingAvg - expectedTaken;
  const mitigation = incomingAvg > 0 ? (expectedBlocked / incomingAvg) : 0;
  const critTaken = critIncoming - critBlocked;

  return {
    name: attack?.Name || 'Attack',
    totalMin: incomingMin,
    totalAvg: incomingAvg,
    totalMax: incomingMax,
    blockedMin, blockedAvg, blockedMax,
    takenMin, takenAvg, takenMax,
    expectedTaken,     // true average damage taken per hit
    expectedBlocked,   // true average damage blocked per hit
    mitigation,        // 0..1, expected-value based
    critIncoming,
    critTaken,
    byType
  };
}

/**
 * Fast single-pass maturity scorer — computes typeScore, mitigation and
 * damageTaken in a single walk over the maturity's attacks. Used by
 * scoreMob() on the hot path (rankArmors loops thousands of armor/plate
 * combos, so this is 3× faster than calling three separate functions).
 */
function scoreMaturityAll(maturity, defense, dmgMultiplier = 1) {
  const attacks = Array.isArray(maturity?.Attacks) ? maturity.Attacks : [];
  if (attacks.length === 0) return { typeScore: null, mitigation: null, damageTaken: null };

  let typeScoreSum = 0, typeScoreCount = 0;
  let totalBlocked = 0, totalIncoming = 0; // damage-weighted mitigation
  let takenSum = 0, takenCount = 0;         // per-attack mean damage taken

  for (const atk of attacks) {
    const totalDmg = (atk?.TotalDamage ?? 0) * dmgMultiplier;
    let hasComp = false;
    let weightedDef = 0;
    let totalDef = 0;
    let incomingAvg = 0, expectedTaken = 0;

    for (const type of DEFENSE_TYPES) {
      const pct = (atk?.Damage?.[type] ?? 0) / 100;
      if (pct > 0) hasComp = true;
      const def = defense?.[type] ?? 0;
      totalDef += def;
      weightedDef += pct * def;

      if (totalDmg > 0 && pct > 0) {
        const base = totalDmg * pct;
        incomingAvg += base * DAMAGE_AVG_FRACTION;
        expectedTaken += expectedTakenPerType(base, def);
      }
    }

    // type-match = weighted-avg armor defense / total armor defense.
    // 0..1 fraction: how well the armor's defenses align with the mob's
    // damage composition. 1.0 = all defense is in types the mob uses.
    if (hasComp) {
      const attackTypeScoreVal = totalDef > 0 ? weightedDef / totalDef : 0;
      typeScoreSum += attackTypeScoreVal;
      typeScoreCount++;
    }
    if (incomingAvg > 0) {
      totalBlocked += (incomingAvg - expectedTaken);
      totalIncoming += incomingAvg;
      takenSum += expectedTaken;
      takenCount++;
    }
  }

  return {
    typeScore: typeScoreCount > 0 ? typeScoreSum / typeScoreCount : null,
    mitigation: totalIncoming > 0 ? totalBlocked / totalIncoming : null,
    damageTaken: takenCount > 0 ? takenSum / takenCount : null,
    blockedPerAttack: takenCount > 0 ? totalBlocked / takenCount : null
  };
}

/** Return maturities sorted by Level (nulls last, falling back to array order).
 *  Uses a paired array to avoid mutating the input maturity objects (which
 *  would break Svelte 5 $state reactivity when called inside a $derived). */
export function sortedMaturities(mob) {
  const mats = Array.isArray(mob?.Maturities) ? mob.Maturities : [];
  const indexed = mats.map((m, i) => ({ m, i }));
  indexed.sort((a, b) => {
    const la = a.m?.Properties?.Level;
    const lb = b.m?.Properties?.Level;
    if (la == null && lb == null) return a.i - b.i;
    if (la == null) return 1;
    if (lb == null) return -1;
    return la - lb;
  });
  return indexed.map(x => x.m);
}

/**
 * Score a mob for a given armor defense, scoped to lowest/average/highest maturity.
 *
 * Returns dual scores:
 *   - typeScore   : composition-weighted defense (always computable if the mob
 *                   has any damage composition, even without TotalDamage)
 *   - mitigation  : damage-weighted mitigation % (requires TotalDamage → may be null)
 *   - damageTaken : expected damage taken per attack (requires TotalDamage → may be null)
 *   - hasTotalDamage : true when mitigation/damageTaken are usable
 *
 * Returns null only if the mob has NO usable composition on any attack.
 */
export function scoreMob(mob, defense, scope = 'average', dmgMultiplier = 1) {
  const mats = sortedMaturities(mob);
  if (mats.length === 0) return null;

  // Drop mobs with no attacks at all — they can't be scored at all
  const anyAttacks = mats.some(m => Array.isArray(m?.Attacks) && m.Attacks.length > 0);
  if (!anyAttacks) return null;

  function scoreOne(mat) {
    const s = scoreMaturityAll(mat, defense, dmgMultiplier);
    return {
      typeScore: s.typeScore,
      mitigation: s.mitigation,
      damageTaken: s.damageTaken,
      blockedPerAttack: s.blockedPerAttack,
      label: mat?.Name ?? null,
      level: mat?.Properties?.Level ?? null
    };
  }

  let aggregated;
  let label = null;
  let level = null;

  if (scope === 'lowest' || scope === 'highest') {
    const mat = scope === 'lowest' ? mats[0] : mats[mats.length - 1];
    aggregated = scoreOne(mat);
    // Single maturity → no range
    aggregated.blockedPerAttackMin = aggregated.blockedPerAttack;
    aggregated.blockedPerAttackMax = aggregated.blockedPerAttack;
    label = aggregated.label;
    level = aggregated.level;
  } else {
    // Average across maturities. Fall back to all maturities if none have composition.
    const scored = mats.map(scoreOne);
    const withComp = scored.filter(s => s.typeScore != null);
    const chosen = withComp.length > 0 ? withComp : scored;
    const withDamage = chosen.filter(s => s.mitigation != null);

    let blockedMin = null, blockedMax = null;
    if (withDamage.length > 0) {
      for (const s of withDamage) {
        if (blockedMin == null || s.blockedPerAttack < blockedMin) blockedMin = s.blockedPerAttack;
        if (blockedMax == null || s.blockedPerAttack > blockedMax) blockedMax = s.blockedPerAttack;
      }
    }
    aggregated = {
      typeScore: withComp.length > 0
        ? withComp.reduce((a, s) => a + s.typeScore, 0) / withComp.length
        : null,
      mitigation: withDamage.length > 0
        ? withDamage.reduce((a, s) => a + s.mitigation, 0) / withDamage.length
        : null,
      damageTaken: withDamage.length > 0
        ? withDamage.reduce((a, s) => a + s.damageTaken, 0) / withDamage.length
        : null,
      blockedPerAttack: withDamage.length > 0
        ? withDamage.reduce((a, s) => a + s.blockedPerAttack, 0) / withDamage.length
        : null,
      blockedPerAttackMin: blockedMin,
      blockedPerAttackMax: blockedMax
    };
    label = chosen.length === 1 ? chosen[0].label : `avg of ${chosen.length}`;
  }

  return {
    typeScore: aggregated.typeScore,
    mitigation: aggregated.mitigation,
    damageTaken: aggregated.damageTaken,
    blockedPerAttack: aggregated.blockedPerAttack,
    blockedPerAttackMin: aggregated.blockedPerAttackMin,
    blockedPerAttackMax: aggregated.blockedPerAttackMax,
    hasTotalDamage: aggregated.mitigation != null,
    hasComposition: aggregated.typeScore != null,
    maturityLabel: label,
    maturityLevel: level
  };
}

/**
 * Per-unit-damage-absorbed decay rate (PEC per damage point) for a combined
 * armor + plating configuration. Mirrors the formula in loadoutCalculations.js
 * calculateTotalAbsorption, where the full-hit decay is
 *   maxDecay = totalDefense × (100000 − durability) / 100000 × 0.05
 * ⇒ per unit absorbed: (100000 − durability) / 100000 × 0.05.
 * Armor and plate contribute proportionally to their share of total defense.
 */
export function computeDecayRate(armorSet, plating) {
  const sumDef = item => {
    if (!item) return 0;
    let s = 0;
    for (const type of DEFENSE_TYPES) s += item?.Properties?.Defense?.[type] ?? 0;
    return s;
  };
  const armorDef = sumDef(armorSet);
  const plateDef = sumDef(plating);
  const totalDef = armorDef + plateDef;
  if (totalDef <= 0) return 0;

  const armorDur = armorSet?.Properties?.Economy?.Durability ?? 0;
  const plateDur = plating?.Properties?.Economy?.Durability ?? 0;

  const armorRate = armorDef > 0 ? (100000 - armorDur) / 100000 * 0.05 : 0;
  const plateRate = plateDef > 0 ? (100000 - plateDur) / 100000 * 0.05 : 0;

  const armorShare = armorDef / totalDef;
  const plateShare = plateDef / totalDef;

  return armorShare * armorRate + plateShare * plateRate;
}

/**
 * Sort entries into three data-quality groups, then sort within each by the
 * user-selected metric. Damage-dependent metrics (mitigation, damageTaken)
 * fall back to type-match when the entry doesn't have TotalDamage.
 *
 * @param {'typeMatch'|'mitigation'|'damageTaken'} rankBy
 */
function makeSortByMetric(rankBy = 'mitigation') {
  return function (a, b) {
    const groupA = !a.hasComposition ? 3 : !a.hasTotalDamage ? 2 : 1;
    const groupB = !b.hasComposition ? 3 : !b.hasTotalDamage ? 2 : 1;
    if (groupA !== groupB) return groupA - groupB;

    // Group 3: alphabetical
    if (groupA === 3) return (a.name || '').localeCompare(b.name || '');

    // Group 2: always type-match (the only available metric)
    if (groupA === 2) return (b.typeScore ?? 0) - (a.typeScore ?? 0);

    // Group 1: sort by user choice
    if (rankBy === 'typeMatch') return (b.typeScore ?? 0) - (a.typeScore ?? 0);
    if (rankBy === 'damageTaken') return (a.damageTaken ?? Infinity) - (b.damageTaken ?? Infinity);
    // default: mitigation
    return (b.mitigationPct ?? 0) - (a.mitigationPct ?? 0);
  };
}

/**
 * Build a mob-ranking for a given armor configuration.
 * @returns {Array} sorted: damage-known first (by mitigation % desc),
 *                  then damage-unknown (by type score desc)
 */
/** Async/chunked per-maturity ranking — one entry per (mob × maturity). */
export async function rankMaturitiesChunked(mobs, defense, dmgMultiplier, rankBy, decayRate, { chunkSize = 100, signal } = {}) {
  const results = [];
  const sortFn = makeSortByMetric(rankBy);
  const list = mobs || [];
  for (let i = 0; i < list.length; i++) {
    if (signal?.aborted) return null;
    const mob = list[i];
    const mats = sortedMaturities(mob);
    for (const mat of mats) {
      const attacks = Array.isArray(mat?.Attacks) ? mat.Attacks : [];
      if (attacks.length === 0) continue;
      const s = scoreMaturityAll(mat, defense, dmgMultiplier);
      if (s.typeScore == null) continue;
      const blocked = s.blockedPerAttack;
      results.push({
        mob, maturity: mat,
        name: mob.Name,
        typeScore: s.typeScore,
        mitigationPct: s.mitigation != null ? s.mitigation * 100 : null,
        damageTaken: s.damageTaken,
        decayPerAttack: blocked != null ? blocked * decayRate : null,
        decayPerAttackMin: blocked != null ? blocked * decayRate : null,
        decayPerAttackMax: blocked != null ? blocked * decayRate : null,
        hasTotalDamage: s.mitigation != null,
        hasComposition: s.typeScore != null,
        maturityLabel: mat?.Name ?? null,
        maturityLevel: mat?.Properties?.Level ?? null
      });
    }
    if ((i + 1) % chunkSize === 0) {
      await new Promise(resolve => setTimeout(resolve, 0));
      if (signal?.aborted) return null;
    }
  }
  results.sort(sortFn);
  return results;
}

/** Async/chunked mob ranking that yields to the browser every N mobs. */
export async function rankMobsChunked(mobs, defense, scope, dmgMultiplier, rankBy, decayRate, { chunkSize = 100, signal } = {}) {
  const results = [];
  const sortFn = makeSortByMetric(rankBy);
  const list = mobs || [];
  for (let i = 0; i < list.length; i++) {
    if (signal?.aborted) return null;
    const mob = list[i];
    const score = scoreMob(mob, defense, scope, dmgMultiplier);
    if (score != null) {
      results.push({
        mob,
        name: mob.Name,
        typeScore: score.typeScore,
        mitigationPct: score.mitigation != null ? score.mitigation * 100 : null,
        damageTaken: score.damageTaken,
        decayPerAttack: score.blockedPerAttack != null ? score.blockedPerAttack * decayRate : null,
        decayPerAttackMin: score.blockedPerAttackMin != null ? score.blockedPerAttackMin * decayRate : null,
        decayPerAttackMax: score.blockedPerAttackMax != null ? score.blockedPerAttackMax * decayRate : null,
        hasTotalDamage: score.hasTotalDamage,
        hasComposition: score.hasComposition,
        maturityLabel: score.maturityLabel,
        maturityLevel: score.maturityLevel
      });
    }
    if ((i + 1) % chunkSize === 0) {
      await new Promise(resolve => setTimeout(resolve, 0));
      if (signal?.aborted) return null;
    }
  }
  results.sort(sortFn);
  return results;
}

export function rankMobs(mobs, defense, scope, dmgMultiplier = 1, rankBy = 'mitigation', decayRate = 0) {
  const results = [];
  for (const mob of mobs || []) {
    const score = scoreMob(mob, defense, scope, dmgMultiplier);
    if (score == null) continue;
    results.push({
      mob,
      name: mob.Name,
      typeScore: score.typeScore,
      mitigationPct: score.mitigation != null ? score.mitigation * 100 : null,
      damageTaken: score.damageTaken,
      decayPerAttack: score.blockedPerAttack != null ? score.blockedPerAttack * decayRate : null,
      decayPerAttackMin: score.blockedPerAttackMin != null ? score.blockedPerAttackMin * decayRate : null,
      decayPerAttackMax: score.blockedPerAttackMax != null ? score.blockedPerAttackMax * decayRate : null,
      hasTotalDamage: score.hasTotalDamage,
      hasComposition: score.hasComposition,
      maturityLabel: score.maturityLabel,
      maturityLevel: score.maturityLevel
    });
  }
  results.sort(makeSortByMetric(rankBy));
  return results;
}

/**
 * Build an armor-ranking for a given mob. For each armor set, emits:
 *   - a bare-armor row
 *   - up to `platesPerArmor` rows for that armor paired with the top
 *     platings by the current rank metric
 * iceShield/enhancers/dmgMultiplier are applied uniformly to every candidate.
 *
 * @param {object} options
 * @param {boolean} [options.includePlates=true] - include plate pairings
 * @param {number} [options.platesPerArmor=3] - how many top plates per armor
 */
/** Async version of rankArmors that yields to the browser every N armor sets
 *  so the UI stays responsive (loading spinner can render, events can dispatch). */
export async function rankArmorsChunked(armorSets, armorPlatings, mob, config, scope, rankBy, options = {}, { chunkSize = 40, signal } = {}) {
  const { iceShield, enhancers, dmgMultiplier = 1 } = config;
  const {
    includePlates = true,
    platesPerArmor = 3,
    ulPlatesOnly = false,
    armorFilter = null,     // Set<string> of armor names — if set, only those are ranked
    plateFilter = null,     // Set<string> of plate names — if set, only those are used
    armorEnhancers = null   // Record<armorName, number> — per-armor enhancer overrides
  } = options;
  const sortFn = makeSortByMetric(rankBy);
  const defaultEnhancerMult = 1 + (Math.max(0, Math.min(MAX_ENHANCERS, enhancers ?? 0)) * ENHANCER_BONUS_PER_LEVEL);
  const ICE_SHIELD_SET = new Set(['Impact', 'Stab', 'Cut', 'Shrapnel', 'Penetration', 'Burn']);

  function enhancerMultFor(armorName) {
    if (armorEnhancers && armorName in armorEnhancers) {
      const v = Math.max(0, Math.min(MAX_ENHANCERS, armorEnhancers[armorName] ?? 0));
      return 1 + v * ENHANCER_BONUS_PER_LEVEL;
    }
    return defaultEnhancerMult;
  }

  // Pre-filter plates: drop those without defense in the mob's damage types,
  // and optionally drop "(L)" Limited plates (ulPlatesOnly).
  let platesToUse = [];
  if (includePlates) {
    const mobTypes = new Set();
    for (const mat of mob?.Maturities || []) {
      for (const atk of mat?.Attacks || []) {
        for (const type of DEFENSE_TYPES) {
          if ((atk?.Damage?.[type] ?? 0) > 0) mobTypes.add(type);
        }
      }
    }
    if (mobTypes.size > 0) {
      platesToUse = (armorPlatings || []).filter(plate => {
        if (ulPlatesOnly && hasItemTag(plate?.Name, 'L')) return false;
        if (plateFilter && !plateFilter.has(plate?.Name)) return false;
        for (const type of mobTypes) {
          if ((plate?.Properties?.Defense?.[type] ?? 0) > 0) return true;
        }
        return false;
      });
    }
  }

  function scoreFromDefense(armorSet, plating, defense) {
    const score = scoreMob(mob, defense, scope, dmgMultiplier);
    if (score == null) return null;
    const decayRate = computeDecayRate(armorSet, plating);
    return {
      armorSet, plating, name: armorSet.Name,
      typeScore: score.typeScore,
      mitigationPct: score.mitigation != null ? score.mitigation * 100 : null,
      damageTaken: score.damageTaken,
      decayPerAttack: score.blockedPerAttack != null ? score.blockedPerAttack * decayRate : null,
      decayPerAttackMin: score.blockedPerAttackMin != null ? score.blockedPerAttackMin * decayRate : null,
      decayPerAttackMax: score.blockedPerAttackMax != null ? score.blockedPerAttackMax * decayRate : null,
      hasTotalDamage: score.hasTotalDamage,
      hasComposition: score.hasComposition,
      maturityLabel: score.maturityLabel,
      maturityLevel: score.maturityLevel
    };
  }

  const results = [];
  const combinedDef = {};
  const sets = (armorFilter
    ? (armorSets || []).filter(a => armorFilter.has(a?.Name))
    : (armorSets || []));

  for (let i = 0; i < sets.length; i++) {
    if (signal?.aborted) return null;
    const armorSet = sets[i];
    const thisEnhancerMult = enhancerMultFor(armorSet?.Name);

    const baseDef = {};
    for (const type of DEFENSE_TYPES) {
      const armorVal = (armorSet?.Properties?.Defense?.[type] ?? 0) * thisEnhancerMult;
      const iceVal = iceShield && ICE_SHIELD_SET.has(type) ? ICE_SHIELD_VALUE : 0;
      baseDef[type] = armorVal + iceVal;
    }

    const bare = scoreFromDefense(armorSet, null, baseDef);
    if (bare) results.push(bare);

    if (includePlates && platesToUse.length > 0) {
      const plateCombos = [];
      for (const plate of platesToUse) {
        const plateDef = plate?.Properties?.Defense;
        for (const type of DEFENSE_TYPES) {
          combinedDef[type] = baseDef[type] + (plateDef?.[type] ?? 0);
        }
        const combo = scoreFromDefense(armorSet, plate, combinedDef);
        if (combo) plateCombos.push(combo);
      }
      plateCombos.sort(sortFn);
      for (let k = 0; k < platesPerArmor && k < plateCombos.length; k++) {
        results.push(plateCombos[k]);
      }
    }

    // Yield to browser every `chunkSize` armor sets
    if ((i + 1) % chunkSize === 0) {
      await new Promise(resolve => setTimeout(resolve, 0));
      if (signal?.aborted) return null;
    }
  }

  results.sort(sortFn);
  return results;
}

export function rankArmors(armorSets, armorPlatings, mob, config, scope, rankBy = 'mitigation', options = {}) {
  const { iceShield, enhancers, dmgMultiplier = 1 } = config;
  const { includePlates = true, platesPerArmor = 3, ulPlatesOnly = false } = options;
  const sortFn = makeSortByMetric(rankBy);
  const enhancerMult = 1 + (Math.max(0, Math.min(MAX_ENHANCERS, enhancers ?? 0)) * ENHANCER_BONUS_PER_LEVEL);
  const ICE_SHIELD_SET = new Set(['Impact', 'Stab', 'Cut', 'Shrapnel', 'Penetration', 'Burn']);

  // Pre-filter plates: drop those without defense in the mob's damage types,
  // and optionally drop "(L)" Limited plates (ulPlatesOnly).
  let platesToUse = [];
  if (includePlates) {
    const mobTypes = new Set();
    for (const mat of mob?.Maturities || []) {
      for (const atk of mat?.Attacks || []) {
        for (const type of DEFENSE_TYPES) {
          if ((atk?.Damage?.[type] ?? 0) > 0) mobTypes.add(type);
        }
      }
    }
    if (mobTypes.size > 0) {
      platesToUse = (armorPlatings || []).filter(plate => {
        if (ulPlatesOnly && hasItemTag(plate?.Name, 'L')) return false;
        for (const type of mobTypes) {
          if ((plate?.Properties?.Defense?.[type] ?? 0) > 0) return true;
        }
        return false;
      });
    }
  }

  function scoreFromDefense(armorSet, plating, defense) {
    const score = scoreMob(mob, defense, scope, dmgMultiplier);
    if (score == null) return null;
    const decayRate = computeDecayRate(armorSet, plating);
    return {
      armorSet,
      plating,
      name: armorSet.Name,
      typeScore: score.typeScore,
      mitigationPct: score.mitigation != null ? score.mitigation * 100 : null,
      damageTaken: score.damageTaken,
      decayPerAttack: score.blockedPerAttack != null ? score.blockedPerAttack * decayRate : null,
      decayPerAttackMin: score.blockedPerAttackMin != null ? score.blockedPerAttackMin * decayRate : null,
      decayPerAttackMax: score.blockedPerAttackMax != null ? score.blockedPerAttackMax * decayRate : null,
      hasTotalDamage: score.hasTotalDamage,
      hasComposition: score.hasComposition,
      maturityLabel: score.maturityLabel,
      maturityLevel: score.maturityLevel
    };
  }

  const results = [];
  // Scratch buffer reused for combined (armor+plate) defense to avoid
  // allocating a fresh object per plate per armor (~30k allocations).
  const combinedDef = {};

  for (const armorSet of armorSets || []) {
    // Precompute armor base defense once: (armor × enhancer) + ice shield
    const baseDef = {};
    for (const type of DEFENSE_TYPES) {
      const armorVal = (armorSet?.Properties?.Defense?.[type] ?? 0) * enhancerMult;
      const iceVal = iceShield && ICE_SHIELD_SET.has(type) ? ICE_SHIELD_VALUE : 0;
      baseDef[type] = armorVal + iceVal;
    }

    const bare = scoreFromDefense(armorSet, null, baseDef);
    if (bare) results.push(bare);

    if (!includePlates || platesToUse.length === 0) continue;

    // Top-N plate pairings — add plate defense on top of baseDef in-place
    const plateCombos = [];
    for (const plate of platesToUse) {
      const plateDef = plate?.Properties?.Defense;
      for (const type of DEFENSE_TYPES) {
        combinedDef[type] = baseDef[type] + (plateDef?.[type] ?? 0);
      }
      const combo = scoreFromDefense(armorSet, plate, combinedDef);
      if (combo) plateCombos.push(combo);
    }
    plateCombos.sort(sortFn);
    for (let i = 0; i < platesPerArmor && i < plateCombos.length; i++) {
      results.push(plateCombos[i]);
    }
  }

  results.sort(sortFn);
  return results;
}

/**
 * Build detailed per-maturity breakdown for the armor-vs-mob details view.
 * Each maturity entry contains all attacks with their computed breakdown.
 */
export function buildDetails(mob, defense, dmgMultiplier = 1) {
  const mats = sortedMaturities(mob);
  return mats.map(mat => ({
    name: mat?.Name ?? '',
    level: mat?.Properties?.Level ?? null,
    attacks: (Array.isArray(mat?.Attacks) ? mat.Attacks : [])
      .map(atk => computeAttackBreakdown(atk, defense, dmgMultiplier))
  }));
}

/** True when no maturity of the mob has any attack with non-zero damage. */
export function hasDamageData(mob) {
  const mats = Array.isArray(mob?.Maturities) ? mob.Maturities : [];
  for (const mat of mats) {
    const attacks = Array.isArray(mat?.Attacks) ? mat.Attacks : [];
    for (const atk of attacks) {
      if ((atk?.TotalDamage ?? 0) > 0) return true;
    }
  }
  return false;
}
