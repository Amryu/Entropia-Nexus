// @ts-nocheck
import { hasItemTag } from '$lib/util';

/**
 * Armor vs Mob calculations.
 *
 * Core model:
 *   - Armor is treated as a full set (not per-piece).
 *   - Defense is applied in sequential layers (ice shield -> plates -> armor).
 *     Each layer reduces damage per type, then the remaining total damage is
 *     redistributed over the original damage distribution before hitting the
 *     next layer.
 *   - Mobs deal flat damage per type (50%-100% range).
 *
 * Data shapes come from common/schemas/ArmorSet.js, ArmorPlating.js, Mob.js.
 */

export const DEFENSE_TYPES = [
  'Impact', 'Cut', 'Stab', 'Penetration', 'Shrapnel',
  'Burn', 'Cold', 'Acid', 'Electric'
];

// Default attack name from the Mob schema (see common/schemas/Mob.js).
// Used as the preferred default when picking which attack to display.
export const DEFAULT_ATTACK_NAME = 'Primary';

// Midpoint of each Damage Potential bucket, capped at 500.
// Source: sql/nexus/migrations/026_seed_enumerations.sql "Damage Potential".
// Buckets are inclusive on the lower bound; the upper bound is the next
// bucket's lower bound minus one (or 500 for the topmost bucket).
export const DAMAGE_POTENTIAL_MIDPOINTS = {
  Minimal:  10,
  Small:    24.5,
  Limited:  34.5,
  Medium:   49.5,
  Large:    80,
  Great:    130.5,
  Huge:     215.5,
  Immense:  313,
  Gigantic: 427.5,
  Colossal: 500
};

export function damagePotentialMidpoint(name) {
  return DAMAGE_POTENTIAL_MIDPOINTS[name] ?? null;
}

/**
 * Returns a version of the maturity where any attack missing TotalDamage has
 * it synthesised from the maturity's DamagePotential bucket midpoint. Used
 * to let the gear advisor score mobs that only have a bucket classification.
 * @returns {{ maturity: object, approximated: boolean }}
 */
export function applyDamagePotentialFallback(maturity) {
  const dp = maturity?.Properties?.DamagePotential;
  const mid = damagePotentialMidpoint(dp);
  if (mid == null) return { maturity, approximated: false };
  const attacks = Array.isArray(maturity?.Attacks) ? maturity.Attacks : [];
  let touched = false;
  const newAttacks = attacks.map(atk => {
    if ((atk?.TotalDamage ?? 0) > 0) return atk;
    touched = true;
    return { ...atk, TotalDamage: mid };
  });
  if (!touched) return { maturity, approximated: false };
  return { maturity: { ...maturity, Attacks: newAttacks }, approximated: true };
}

/** True when the mob has any attack with real TotalDamage OR any maturity
 *  classified with a DamagePotential bucket. Use in place of hasDamageData
 *  for guards that should allow DP-based approximation. */
export function hasDamageDataOrPotential(mob) {
  if (hasDamageData(mob)) return true;
  for (const mat of mob?.Maturities || []) {
    if (mat?.Properties?.DamagePotential) return true;
  }
  return false;
}

/**
 * Distinct attack names across all maturities of a mob, in stable first-seen
 * order, with DEFAULT_ATTACK_NAME ("Primary") hoisted to the front when
 * present. Missing/empty attack names fall back to DEFAULT_ATTACK_NAME.
 * @param {object} mob
 * @returns {string[]}
 */
export function getMobAttackNames(mob) {
  const seen = new Set();
  const ordered = [];
  for (const mat of mob?.Maturities || []) {
    for (const atk of mat?.Attacks || []) {
      const name = atk?.Name || DEFAULT_ATTACK_NAME;
      if (!seen.has(name)) {
        seen.add(name);
        ordered.push(name);
      }
    }
  }
  const idx = ordered.indexOf(DEFAULT_ATTACK_NAME);
  if (idx > 0) {
    ordered.splice(idx, 1);
    ordered.unshift(DEFAULT_ATTACK_NAME);
  }
  return ordered;
}

const ICE_SHIELD_TYPES = ['Impact', 'Stab', 'Cut', 'Shrapnel', 'Penetration', 'Burn'];
export const ICE_SHIELD_VALUE = 75;

// Singleton ice shield defense layer — used by reference to identify and
// exclude it from typeScore calculations (ice shield is a buff, not equipment).
const _iceShieldLayer = Object.freeze(
  Object.fromEntries(DEFENSE_TYPES.map(t => [t, ICE_SHIELD_TYPES.includes(t) ? ICE_SHIELD_VALUE : 0]))
);
export const MAX_ENHANCERS = 10;
export const ENHANCER_BONUS_PER_LEVEL = 0.05;

const DAMAGE_MIN_FRACTION = 0.5;
const DAMAGE_MAX_FRACTION = 1.0;
const DAMAGE_AVG_FRACTION = (DAMAGE_MIN_FRACTION + DAMAGE_MAX_FRACTION) / 2; // 0.75

// Crit model: up to 2× max damage, pierces 20% of armor defense.
export const CRIT_MULTIPLIER = 2.0;
export const CRIT_ARMOR_PIERCE = 0.20;

/**
 * Compute defense as sequential layers: [iceShield?, plate?, armor].
 * Each layer is a Record<string, number> of defense by type.
 * Order: outermost (ice shield) to innermost (armor).
 * @param {object} armorSet - armor set entity
 * @param {object|null} plating - optional plating entity
 * @param {boolean} iceShield - whether Ice Shield buff is active
 * @param {number} enhancers - defense enhancers equipped (0..10)
 * @returns {Record<string, number>[]} defense layers
 */
export function computeDefenseLayers(armorSet, plating, iceShield, enhancers) {
  const enhancerMult = 1 + (Math.max(0, Math.min(MAX_ENHANCERS, enhancers ?? 0)) * ENHANCER_BONUS_PER_LEVEL);
  const layers = [];

  if (iceShield) {
    layers.push(_iceShieldLayer);
  }

  if (plating) {
    const plateDef = {};
    for (const type of DEFENSE_TYPES) {
      plateDef[type] = plating?.Properties?.Defense?.[type] ?? 0;
    }
    layers.push(plateDef);
  }

  const armorDef = {};
  for (const type of DEFENSE_TYPES) {
    armorDef[type] = (armorSet?.Properties?.Defense?.[type] ?? 0) * enhancerMult;
  }
  layers.push(armorDef);

  return layers;
}

/**
 * Apply one defense layer: each type blocks up to its defense value,
 * then the remaining total is returned (caller redistributes before
 * feeding the next layer).
 */
function applyDefenseLayer(totalDamage, pctByType, layerDef) {
  if (totalDamage <= 0) return 0;
  let blocked = 0;
  for (const type of DEFENSE_TYPES) {
    const incoming = totalDamage * (pctByType[type] ?? 0);
    blocked += Math.min(incoming, layerDef[type] ?? 0);
  }
  return totalDamage - blocked;
}

/**
 * Process damage through sequential defense layers with redistribution.
 * After each layer reduces per-type damage, the remaining total is
 * redistributed over the original damage distribution for the next layer.
 */
function computeLayeredRemaining(totalDamage, pctByType, layers) {
  let remaining = totalDamage;
  for (const layer of layers) {
    remaining = applyDefenseLayer(remaining, pctByType, layer);
  }
  return remaining;
}

const INTEGRATION_STEPS = 20;

/**
 * Expected damage taken with layered defense, integrated over uniform
 * roll X in [DAMAGE_MIN_FRACTION, DAMAGE_MAX_FRACTION] using the trapezoidal
 * rule. The endpoints X_min and X_max are sampled explicitly (weight 0.5)
 * so an armor that fails only at the top of the roll range still produces
 * a non-zero expected-taken value — midpoint rule with 10 bins silently
 * zeroed those cases because it never evaluated at X=1.0.
 */
function expectedTakenLayered(totalBase, pctByType, layers) {
  if (totalBase <= 0) return 0;
  const X0 = DAMAGE_MIN_FRACTION;
  const X1 = DAMAGE_MAX_FRACTION;
  const N = INTEGRATION_STEPS;
  const dX = (X1 - X0) / N;
  let sum = 0;
  for (let i = 0; i <= N; i++) {
    const X = X0 + i * dX;
    const w = (i === 0 || i === N) ? 0.5 : 1.0;
    sum += w * computeLayeredRemaining(totalBase * X, pctByType, layers);
  }
  return sum / N;
}

/**
 * Expected total decay (PEC) with layered defense, integrated over uniform
 * roll X in [DAMAGE_MIN_FRACTION, DAMAGE_MAX_FRACTION] via trapezoidal rule.
 * Each layer's blocked amount is multiplied by its own decay rate.
 */
function expectedDecayLayered(totalBase, pctByType, layers, decayRates) {
  if (totalBase <= 0) return 0;
  const X0 = DAMAGE_MIN_FRACTION;
  const X1 = DAMAGE_MAX_FRACTION;
  const N = INTEGRATION_STEPS;
  const dX = (X1 - X0) / N;
  let decaySum = 0;
  for (let i = 0; i <= N; i++) {
    const X = X0 + i * dX;
    const w = (i === 0 || i === N) ? 0.5 : 1.0;
    let remaining = totalBase * X;
    let layerDecay = 0;
    for (let j = 0; j < layers.length; j++) {
      const prev = remaining;
      remaining = applyDefenseLayer(remaining, pctByType, layers[j]);
      layerDecay += (prev - remaining) * (decayRates[j] ?? 0);
    }
    decaySum += w * layerDecay;
  }
  return decaySum / N;
}

/** Sum all layers into a single defense-by-type map (for typeScore calculations). */
export function sumLayers(layers) {
  const result = {};
  for (const type of DEFENSE_TYPES) {
    let s = 0;
    for (const layer of layers || []) s += layer?.[type] ?? 0;
    result[type] = s;
  }
  return result;
}

/**
 * Identify the defense type that leaks the most damage for a given mob
 * against a summed per-type defense map. Iterates every attack on every
 * maturity, accumulates (incoming − effectiveDefense) per type at max roll,
 * and returns the type with the highest cumulative leak. Returns null when
 * all attacks are fully absorbed (armor has zero weak spots for this mob).
 *
 * @param {object} mob  mob entity (or synthetic single-maturity mob)
 * @param {Record<string, number>} effectiveDefenseByType  per-type defense
 *   summed across every layer (armor + plate + ice shield)
 * @returns {{ type: string, leak: number, incoming: number } | null}
 */
export function findWeakestDefenseType(mob, effectiveDefenseByType) {
  const leakPerType = Object.fromEntries(DEFENSE_TYPES.map(t => [t, 0]));
  const incomingPerType = Object.fromEntries(DEFENSE_TYPES.map(t => [t, 0]));
  for (const mat of mob?.Maturities || []) {
    for (const atk of mat?.Attacks || []) {
      const total = atk?.TotalDamage ?? 0;
      if (total <= 0) continue;
      for (const t of DEFENSE_TYPES) {
        const pct = (atk?.Damage?.[t] ?? 0) / 100;
        if (pct <= 0) continue;
        const incoming = total * pct;
        incomingPerType[t] += incoming;
        const leak = Math.max(0, incoming - (effectiveDefenseByType?.[t] ?? 0));
        leakPerType[t] += leak;
      }
    }
  }
  let maxType = null, maxLeak = 0;
  for (const t of DEFENSE_TYPES) {
    if (leakPerType[t] > maxLeak) { maxLeak = leakPerType[t]; maxType = t; }
  }
  return maxLeak > 0 ? { type: maxType, leak: maxLeak, incoming: incomingPerType[maxType] } : null;
}

/**
 * Compute damage breakdown for a single attack vs layered defense.
 *
 * Data shape:
 *   attack.TotalDamage — scalar total damage per hit (e.g. 230)
 *   attack.Damage[type] — percentage composition 0–100 (e.g. Stab: 33.33)
 *
 * Damage per type at 100% roll = TotalDamage * (percentage / 100).
 * Mob rolls are 50%–100% of base each hit (linear scaling).
 *
 * @param {object} attack - mob attack
 * @param {Record<string, number>[]} defenseLayers - sequential defense layers
 * @param {number} dmgMultiplier - pre-mitigation damage multiplier (1 = unmodified)
 * @param {number[]} [decayRates] - per-layer decay rates (PEC/unit absorbed)
 */
export function computeAttackBreakdown(attack, defenseLayers, dmgMultiplier = 1, decayRates = null) {
  const totalDmg = (attack?.TotalDamage ?? 0) * dmgMultiplier;

  const pctByType = {};
  for (const type of DEFENSE_TYPES) {
    pctByType[type] = (attack?.Damage?.[type] ?? 0) / 100;
  }

  const incomingMin = totalDmg * DAMAGE_MIN_FRACTION;
  const incomingAvg = totalDmg * DAMAGE_AVG_FRACTION;
  const incomingMax = totalDmg * DAMAGE_MAX_FRACTION;

  const takenMin = computeLayeredRemaining(incomingMin, pctByType, defenseLayers);
  const takenMax = computeLayeredRemaining(incomingMax, pctByType, defenseLayers);
  const expectedTaken = expectedTakenLayered(totalDmg, pctByType, defenseLayers);

  const blockedMin = incomingMin - takenMin;
  const blockedAvg = incomingAvg - (incomingAvg > 0 ? computeLayeredRemaining(incomingAvg, pctByType, defenseLayers) : 0);
  const blockedMax = incomingMax - takenMax;
  const expectedBlocked = incomingAvg - expectedTaken;
  const mitigation = incomingAvg > 0 ? expectedBlocked / incomingAvg : 0;

  // Crit: 2× max damage, all defense layers reduced by pierce fraction.
  const critIncoming = totalDmg * CRIT_MULTIPLIER;
  const piercedDefMult = 1 - CRIT_ARMOR_PIERCE;
  const piercedLayers = defenseLayers.map(layer => {
    const p = {};
    for (const type of DEFENSE_TYPES) p[type] = (layer[type] ?? 0) * piercedDefMult;
    return p;
  });
  const critTaken = computeLayeredRemaining(critIncoming, pctByType, piercedLayers);

  const expectedDecay = decayRates
    ? expectedDecayLayered(totalDmg, pctByType, defenseLayers, decayRates)
    : null;

  return {
    name: attack?.Name || 'Attack',
    totalMin: incomingMin,
    totalAvg: incomingAvg,
    totalMax: incomingMax,
    blockedMin, blockedAvg, blockedMax,
    takenMin, takenAvg: incomingAvg - blockedAvg, takenMax,
    expectedTaken,
    expectedBlocked,
    expectedDecay,
    mitigation,
    critIncoming,
    critTaken
  };
}

/**
 * Fast single-pass maturity scorer — computes typeScore, mitigation and
 * damageTaken in a single walk over the maturity's attacks.
 * Uses layered defense model with redistribution between layers.
 * @param {number[]} [decayRates] - per-layer decay rates; when provided,
 *   returns decayPerAttack computed from per-layer blocked amounts.
 */
function scoreMaturityAll(maturity, defenseLayers, dmgMultiplier = 1, decayRates = null) {
  const attacks = Array.isArray(maturity?.Attacks) ? maturity.Attacks : [];
  if (attacks.length === 0) return { typeScore: null, mitigation: null, damageTaken: null, damageDeflected: null, decayPerAttack: null };

  // Sum only equipment layers (exclude ice shield) for typeScore — ice shield
  // is a constant buff that doesn't reflect armor/plate composition quality.
  const equipLayers = defenseLayers.filter(l => l !== _iceShieldLayer);
  const equipDef = sumLayers(equipLayers);

  let typeScoreSum = 0, typeScoreCount = 0;
  let totalBlocked = 0, totalIncoming = 0;
  let takenSum = 0, takenCount = 0;
  let decaySum = 0;

  for (const atk of attacks) {
    const totalDmg = (atk?.TotalDamage ?? 0) * dmgMultiplier;
    let hasComp = false;
    let weightedDef = 0;
    let totalDef = 0;

    const pctByType = {};
    for (const type of DEFENSE_TYPES) {
      const pct = (atk?.Damage?.[type] ?? 0) / 100;
      pctByType[type] = pct;
      if (pct > 0) hasComp = true;
      const def = equipDef[type];
      totalDef += def;
      weightedDef += pct * def;
    }

    if (hasComp) {
      const attackTypeScoreVal = totalDef > 0 ? weightedDef / totalDef : 0;
      typeScoreSum += attackTypeScoreVal;
      typeScoreCount++;
    }
    if (totalDmg > 0 && hasComp) {
      // Max-roll (X = 1.0) semantics for display metrics:
      //   taken    = damage that leaks through at the mob's strongest hit
      //   deflected = damage absorbed at that strongest hit (totalDmg - taken)
      //   mitigation = deflected / totalDmg
      // This gives a clean worst-case framing where full absorption ->
      // taken=0, deflected=totalDmg, mit=100% — matching player intuition
      // instead of the previous roll-averaged metric that capped deflected
      // at 75% of totalDmg.
      const takenAtMax = computeLayeredRemaining(totalDmg, pctByType, defenseLayers);
      const deflectedAtMax = totalDmg - takenAtMax;
      totalBlocked += deflectedAtMax;
      totalIncoming += totalDmg;
      takenSum += takenAtMax;
      takenCount++;
      if (decayRates) {
        // Decay accumulates over many hits, so the expected value across
        // the full roll distribution is the right metric here.
        decaySum += expectedDecayLayered(totalDmg, pctByType, defenseLayers, decayRates);
      }
    }
  }

  return {
    typeScore: typeScoreCount > 0 ? typeScoreSum / typeScoreCount : null,
    mitigation: totalIncoming > 0 ? totalBlocked / totalIncoming : null,
    damageTaken: takenCount > 0 ? takenSum / takenCount : null,
    damageDeflected: takenCount > 0 ? totalBlocked / takenCount : null,
    decayPerAttack: takenCount > 0 && decayRates ? decaySum / takenCount : null
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
export function scoreMob(mob, defenseLayers, scope = 'average', dmgMultiplier = 1, decayRates = null) {
  const mats = sortedMaturities(mob);
  if (mats.length === 0) return null;

  // Drop mobs with no attacks at all — they can't be scored at all
  const anyAttacks = mats.some(m => Array.isArray(m?.Attacks) && m.Attacks.length > 0);
  if (!anyAttacks) return null;

  // Apply DamagePotential fallback per maturity so DP-classified mobs still
  // produce mitigation/damageTaken numbers instead of falling to group 2.
  function scoreOne(mat) {
    const { maturity: matWithFallback, approximated } = applyDamagePotentialFallback(mat);
    const s = scoreMaturityAll(matWithFallback, defenseLayers, dmgMultiplier, decayRates);
    return {
      typeScore: s.typeScore,
      mitigation: s.mitigation,
      damageTaken: s.damageTaken,
      damageDeflected: s.damageDeflected,
      decayPerAttack: s.decayPerAttack,
      approximated,
      label: mat?.Name ?? null,
      level: mat?.Properties?.Level ?? null
    };
  }

  let aggregated;
  let label = null;
  let level = null;
  let approximated = false;

  if (scope === 'lowest' || scope === 'highest') {
    const mat = scope === 'lowest' ? mats[0] : mats[mats.length - 1];
    aggregated = scoreOne(mat);
    aggregated.decayPerAttackMin = aggregated.decayPerAttack;
    aggregated.decayPerAttackMax = aggregated.decayPerAttack;
    label = aggregated.label;
    level = aggregated.level;
    approximated = aggregated.approximated === true;
  } else {
    const scored = mats.map(scoreOne);
    const withComp = scored.filter(s => s.typeScore != null);
    const chosen = withComp.length > 0 ? withComp : scored;
    const withDamage = chosen.filter(s => s.mitigation != null);

    let decayMin = null, decayMax = null;
    if (withDamage.length > 0) {
      for (const s of withDamage) {
        if (s.decayPerAttack != null) {
          if (decayMin == null || s.decayPerAttack < decayMin) decayMin = s.decayPerAttack;
          if (decayMax == null || s.decayPerAttack > decayMax) decayMax = s.decayPerAttack;
        }
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
      damageDeflected: withDamage.length > 0
        ? withDamage.reduce((a, s) => a + (s.damageDeflected ?? 0), 0) / withDamage.length
        : null,
      decayPerAttack: withDamage.length > 0 && withDamage[0].decayPerAttack != null
        ? withDamage.reduce((a, s) => a + (s.decayPerAttack ?? 0), 0) / withDamage.length
        : null,
      decayPerAttackMin: decayMin,
      decayPerAttackMax: decayMax
    };
    label = chosen.length === 1 ? chosen[0].label : `avg of ${chosen.length}`;
    approximated = chosen.some(s => s.approximated === true);
  }

  return {
    typeScore: aggregated.typeScore,
    mitigation: aggregated.mitigation,
    damageTaken: aggregated.damageTaken,
    damageDeflected: aggregated.damageDeflected,
    decayPerAttack: aggregated.decayPerAttack,
    decayPerAttackMin: aggregated.decayPerAttackMin,
    decayPerAttackMax: aggregated.decayPerAttackMax,
    hasTotalDamage: aggregated.mitigation != null,
    hasComposition: aggregated.typeScore != null,
    approximated,
    maturityLabel: label,
    maturityLevel: level
  };
}

/**
 * Compute per-layer decay rates (PEC per unit damage absorbed) matching
 * the layer order from computeDefenseLayers: [iceShield?, plate?, armor].
 * Ice shield: 0 (buff, no decay). Plate/armor: durability-based rate.
 */
export function computeLayerDecayRates(armorSet, plating, iceShield) {
  const rates = [];
  if (iceShield) rates.push(0);
  if (plating) {
    const dur = plating?.Properties?.Economy?.Durability ?? 0;
    rates.push((100000 - dur) / 100000 * 0.05);
  }
  const armorDur = armorSet?.Properties?.Economy?.Durability ?? 0;
  rates.push((100000 - armorDur) / 100000 * 0.05);
  return rates;
}

/**
 * Sort entries into three data-quality groups, then sort within each by the
 * user-selected metric. Damage-dependent metrics (mitigation, damageTaken,
 * deflected) fall back to type-match when the entry doesn't have TotalDamage.
 *
 * @param {'typeMatch'|'mitigation'|'damageTaken'|'deflected'} rankBy
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
    let cmp;
    if (rankBy === 'typeMatch') cmp = (b.typeScore ?? 0) - (a.typeScore ?? 0);
    else if (rankBy === 'damageTaken') cmp = (a.damageTaken ?? Infinity) - (b.damageTaken ?? Infinity);
    else if (rankBy === 'deflected') cmp = (b.damageDeflected ?? -Infinity) - (a.damageDeflected ?? -Infinity);
    else cmp = (b.mitigationPct ?? 0) - (a.mitigationPct ?? 0); // default: mitigation
    if (cmp !== 0) return cmp;
    // Tiebreaker: exact-damage rows win over DamagePotential-approximated rows.
    return (a.approximated ? 1 : 0) - (b.approximated ? 1 : 0);
  };
}

/**
 * Build a mob-ranking for a given armor configuration.
 * @returns {Array} sorted: damage-known first (by mitigation % desc),
 *                  then damage-unknown (by type score desc)
 */
/** Async/chunked per-maturity ranking — one entry per (mob × maturity). */
export async function rankMaturitiesChunked(mobs, defenseLayers, dmgMultiplier, rankBy, decayRates, { chunkSize = 100, signal, hideApproximated = false } = {}) {
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
      const { maturity: matWithFallback, approximated } = applyDamagePotentialFallback(mat);
      if (hideApproximated && approximated) continue;
      const s = scoreMaturityAll(matWithFallback, defenseLayers, dmgMultiplier, decayRates);
      if (s.typeScore == null) continue;
      results.push({
        mob, maturity: mat,
        name: mob.Name,
        typeScore: s.typeScore,
        mitigationPct: s.mitigation != null ? s.mitigation * 100 : null,
        damageTaken: s.damageTaken,
        damageDeflected: s.damageDeflected,
        decayPerAttack: s.decayPerAttack,
        decayPerAttackMin: s.decayPerAttack,
        decayPerAttackMax: s.decayPerAttack,
        hasTotalDamage: s.mitigation != null,
        hasComposition: s.typeScore != null,
        approximated,
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
export async function rankMobsChunked(mobs, defenseLayers, scope, dmgMultiplier, rankBy, decayRates, { chunkSize = 100, signal, hideApproximated = false } = {}) {
  const results = [];
  const sortFn = makeSortByMetric(rankBy);
  const list = mobs || [];
  for (let i = 0; i < list.length; i++) {
    if (signal?.aborted) return null;
    const mob = list[i];
    const score = scoreMob(mob, defenseLayers, scope, dmgMultiplier, decayRates);
    if (score != null && !(hideApproximated && score.approximated)) {
      results.push({
        mob,
        name: mob.Name,
        typeScore: score.typeScore,
        mitigationPct: score.mitigation != null ? score.mitigation * 100 : null,
        damageTaken: score.damageTaken,
        damageDeflected: score.damageDeflected,
        decayPerAttack: score.decayPerAttack,
        decayPerAttackMin: score.decayPerAttackMin,
        decayPerAttackMax: score.decayPerAttackMax,
        hasTotalDamage: score.hasTotalDamage,
        hasComposition: score.hasComposition,
        approximated: score.approximated === true,
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

export function rankMobs(mobs, defenseLayers, scope, dmgMultiplier = 1, rankBy = 'mitigation', decayRates = null, { hideApproximated = false } = {}) {
  const results = [];
  for (const mob of mobs || []) {
    const score = scoreMob(mob, defenseLayers, scope, dmgMultiplier, decayRates);
    if (score == null) continue;
    if (hideApproximated && score.approximated) continue;
    results.push({
      mob,
      name: mob.Name,
      typeScore: score.typeScore,
      mitigationPct: score.mitigation != null ? score.mitigation * 100 : null,
      damageTaken: score.damageTaken,
      damageDeflected: score.damageDeflected,
      decayPerAttack: score.decayPerAttack,
      decayPerAttackMin: score.decayPerAttackMin,
      decayPerAttackMax: score.decayPerAttackMax,
      hasTotalDamage: score.hasTotalDamage,
      hasComposition: score.hasComposition,
      approximated: score.approximated === true,
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
    armorEnhancers = null,  // Record<armorName, number> — per-armor enhancer overrides
    hideApproximated = false // drop rows that used DamagePotential fallback
  } = options;
  const sortFn = makeSortByMetric(rankBy);
  const defaultEnhancerMult = 1 + (Math.max(0, Math.min(MAX_ENHANCERS, enhancers ?? 0)) * ENHANCER_BONUS_PER_LEVEL);

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

  const iceLayer = iceShield ? _iceShieldLayer : null;
  const iceDecayRate = 0;

  function scoreFromLayers(armorSet, plating, layers, decayRates) {
    const score = scoreMob(mob, layers, scope, dmgMultiplier, decayRates);
    if (score == null) return null;
    if (hideApproximated && score.approximated) return null;
    return {
      armorSet, plating, name: armorSet.Name,
      typeScore: score.typeScore,
      mitigationPct: score.mitigation != null ? score.mitigation * 100 : null,
      damageTaken: score.damageTaken,
      damageDeflected: score.damageDeflected,
      decayPerAttack: score.decayPerAttack,
      decayPerAttackMin: score.decayPerAttackMin,
      decayPerAttackMax: score.decayPerAttackMax,
      hasTotalDamage: score.hasTotalDamage,
      hasComposition: score.hasComposition,
      approximated: score.approximated === true,
      maturityLabel: score.maturityLabel,
      maturityLevel: score.maturityLevel
    };
  }

  const results = [];
  const sets = (armorFilter
    ? (armorSets || []).filter(a => armorFilter.has(a?.Name))
    : (armorSets || []));

  for (let i = 0; i < sets.length; i++) {
    if (signal?.aborted) return null;
    const armorSet = sets[i];
    const thisEnhancerMult = enhancerMultFor(armorSet?.Name);

    const armorDef = {};
    for (const type of DEFENSE_TYPES) {
      armorDef[type] = (armorSet?.Properties?.Defense?.[type] ?? 0) * thisEnhancerMult;
    }

    const armorDecayRate = (100000 - (armorSet?.Properties?.Economy?.Durability ?? 0)) / 100000 * 0.05;

    // Bare armor: [ice?, armor]
    const bareLayers = iceLayer ? [iceLayer, armorDef] : [armorDef];
    const bareDecayRates = iceLayer ? [iceDecayRate, armorDecayRate] : [armorDecayRate];
    const bare = scoreFromLayers(armorSet, null, bareLayers, bareDecayRates);
    if (bare) results.push(bare);

    if (includePlates && platesToUse.length > 0) {
      const plateCombos = [];
      for (const plate of platesToUse) {
        const plateDef = {};
        for (const type of DEFENSE_TYPES) {
          plateDef[type] = plate?.Properties?.Defense?.[type] ?? 0;
        }
        const plateDecayRate = (100000 - (plate?.Properties?.Economy?.Durability ?? 0)) / 100000 * 0.05;
        // Layers: [ice?, plate, armor]
        const layers = iceLayer ? [iceLayer, plateDef, armorDef] : [plateDef, armorDef];
        const decayRates = iceLayer ? [iceDecayRate, plateDecayRate, armorDecayRate] : [plateDecayRate, armorDecayRate];
        const combo = scoreFromLayers(armorSet, plate, layers, decayRates);
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
  const { includePlates = true, platesPerArmor = 3, ulPlatesOnly = false, hideApproximated = false } = options;
  const sortFn = makeSortByMetric(rankBy);
  const enhancerMult = 1 + (Math.max(0, Math.min(MAX_ENHANCERS, enhancers ?? 0)) * ENHANCER_BONUS_PER_LEVEL);
  // Pre-filter plates
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

  const iceLayer = iceShield ? _iceShieldLayer : null;
  const iceDecayRate = 0;

  function scoreFromLayers(armorSet, plating, layers, decayRates) {
    const score = scoreMob(mob, layers, scope, dmgMultiplier, decayRates);
    if (score == null) return null;
    if (hideApproximated && score.approximated) return null;
    return {
      armorSet,
      plating,
      name: armorSet.Name,
      typeScore: score.typeScore,
      mitigationPct: score.mitigation != null ? score.mitigation * 100 : null,
      damageTaken: score.damageTaken,
      decayPerAttack: score.decayPerAttack,
      decayPerAttackMin: score.decayPerAttackMin,
      decayPerAttackMax: score.decayPerAttackMax,
      hasTotalDamage: score.hasTotalDamage,
      hasComposition: score.hasComposition,
      approximated: score.approximated === true,
      maturityLabel: score.maturityLabel,
      maturityLevel: score.maturityLevel
    };
  }

  const results = [];

  for (const armorSet of armorSets || []) {
    const armorDef = {};
    for (const type of DEFENSE_TYPES) {
      armorDef[type] = (armorSet?.Properties?.Defense?.[type] ?? 0) * enhancerMult;
    }

    const armorDecayRate = (100000 - (armorSet?.Properties?.Economy?.Durability ?? 0)) / 100000 * 0.05;

    const bareLayers = iceLayer ? [iceLayer, armorDef] : [armorDef];
    const bareDecayRates = iceLayer ? [iceDecayRate, armorDecayRate] : [armorDecayRate];
    const bare = scoreFromLayers(armorSet, null, bareLayers, bareDecayRates);
    if (bare) results.push(bare);

    if (!includePlates || platesToUse.length === 0) continue;

    const plateCombos = [];
    for (const plate of platesToUse) {
      const plateDef = {};
      for (const type of DEFENSE_TYPES) {
        plateDef[type] = plate?.Properties?.Defense?.[type] ?? 0;
      }
      const plateDecayRate = (100000 - (plate?.Properties?.Economy?.Durability ?? 0)) / 100000 * 0.05;
      const layers = iceLayer ? [iceLayer, plateDef, armorDef] : [plateDef, armorDef];
      const decayRates = iceLayer ? [iceDecayRate, plateDecayRate, armorDecayRate] : [plateDecayRate, armorDecayRate];
      const combo = scoreFromLayers(armorSet, plate, layers, decayRates);
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
export function buildDetails(mob, defenseLayers, dmgMultiplier = 1) {
  const mats = sortedMaturities(mob);
  return mats.map(mat => {
    const { maturity: matWithFallback, approximated } = applyDamagePotentialFallback(mat);
    const rawAttacks = Array.isArray(mat?.Attacks) ? mat.Attacks : [];
    const attacks = (Array.isArray(matWithFallback?.Attacks) ? matWithFallback.Attacks : rawAttacks).map((atk, idx) => {
      const breakdown = computeAttackBreakdown(atk, defenseLayers, dmgMultiplier);
      const realTotal = rawAttacks[idx]?.TotalDamage;
      breakdown.approximated = approximated && (realTotal == null || realTotal <= 0);
      return breakdown;
    });
    return {
      name: mat?.Name ?? '',
      level: mat?.Properties?.Level ?? null,
      approximated,
      attacks
    };
  });
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
