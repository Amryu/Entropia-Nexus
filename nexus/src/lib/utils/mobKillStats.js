// @ts-nocheck
// Closed-form expected kill stats for a mob maturity given a loadout.
// Derivation: renewal theory asymptotic E[N(t)] = t/μ + E[Y²]/(2μ²), where Y is per-trigger
// damage (including miss spike). The resulting shots count is the player-facing average,
// including overshoot (last-shot overkill), mob armor (flat per-type subtraction), and
// HP regeneration (continuous drain per trigger reload cycle).

import { DAMAGE_TYPES } from './loadoutCalculations.js';

export function computeApplicableArmor(damagePerType, defense) {
  if (!damagePerType || !defense) return 0;
  let total = 0;
  for (const type of DAMAGE_TYPES) {
    if ((damagePerType[type] ?? 0) > 0) total += defense[type] ?? 0;
  }
  return total;
}

const NULL_RESULT = { shots: null, cost: null, time: null };

export function computeMobKillStats({ loadoutStats, maturity }) {
  if (!loadoutStats || !maturity) return NULL_RESULT;

  const hp = maturity?.Properties?.Health;
  if (hp == null || hp <= 0) return NULL_RESULT;

  const {
    effectiveDamage,
    damageInterval,
    critChance,
    critDamage,
    hitAbility,
    reload,
    dpp,
    damagePerType
  } = loadoutStats;

  if (effectiveDamage == null || !(effectiveDamage > 0)) return NULL_RESULT;
  if (damageInterval == null) return NULL_RESULT;
  if (critChance == null || critDamage == null || hitAbility == null) return NULL_RESULT;

  const { min, max } = damageInterval;
  const avg = (min + max) / 2;
  const varHit = (max - min) ** 2 / 12;
  const h = 0.8 + (hitAbility / 100);
  const c = critChance;
  const critBonus = critDamage * max;

  // Armor: flat subtraction on each hit for each damage type the weapon uses.
  // Note: this approximates when armor exceeds the weapon's lowest per-type roll (clamped-tail case).
  const armor = computeApplicableArmor(damagePerType, maturity?.Properties?.Defense);

  const normalMean = avg - armor;
  const critMean = avg + critBonus - armor;

  // Second moment per hit (variance invariant to shift):
  const e2Normal = varHit + normalMean * normalMean;
  const e2Crit = varHit + critMean * critMean;
  const pNormalGivenHit = (h - c) / h;
  const pCritGivenHit = c / h;
  const e2Hit = pNormalGivenHit * e2Normal + pCritGivenHit * e2Crit;

  // Per-trigger moments (miss contributes nothing):
  const meanTrigger = effectiveDamage - h * armor;
  const e2Trigger = h * e2Hit;

  if (meanTrigger <= 0) return NULL_RESULT;

  // Regen: continuous drain at regenAmount/regenInterval HP/sec, sampled per trigger cycle.
  const regenAmount = maturity?.Properties?.RegenerationAmount ?? 0;
  const regenInterval = maturity?.Properties?.RegenerationInterval ?? 0;
  const regenPerTrigger = (regenInterval > 0 && reload > 0 && regenAmount > 0)
    ? (reload * regenAmount / regenInterval)
    : 0;

  const netMeanTrigger = meanTrigger - regenPerTrigger;
  if (netMeanTrigger <= 0) return NULL_RESULT;

  // Renewal-theory overshoot correction uses pre-regen trigger variance; regen is a continuous
  // drain and doesn't reshape the overshoot distribution of the killing shot.
  const correction = e2Trigger / (2 * meanTrigger * meanTrigger);
  const minShots = 1 / h;
  const shots = Math.max(minShots, hp / netMeanTrigger + correction);

  const costPerTrigger = dpp > 0 ? effectiveDamage / dpp / 100 : null;
  const cost = costPerTrigger != null ? shots * costPerTrigger : null;
  const time = reload > 0 ? Math.max(0, shots - 1) * reload : null;

  return { shots, cost, time };
}
