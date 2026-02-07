/**
 * Construction Calculator - Tree building and calculation algorithms
 *
 * Handles crafting tree generation, step ordering, and shopping list aggregation
 * for the construction calculator tool.
 *
 * Crafting success model (hotspot-based):
 * - Each non-fail craft attempt produces a result at one of several value hotspots
 * - Each hotspot has ~10% variance following a Beta(2,2) distribution
 * - Results below blueprint cost = near-success (material refund only)
 * - Results at or above blueprint cost = success (product output)
 * - Fail: loses all materials, no output
 *
 * For SiB blueprints: max non-fail = 95% (5% fail minimum)
 * For non-SiB blueprints: max non-fail = 90% (10% fail minimum)
 */

import { hasItemTag } from '$lib/util.js';
import { hasCondition } from '$lib/shopUtils.js';

/** Default configuration values */
export const DEFAULT_CONFIG = {
  rollChance: 80, // % chance each material wins refund roll (0-100)
  certainty: 50, // % confidence level for attempt estimation (50-99)
};

/** Condition slider range */
export const CONDITION_MIN = 0;
export const CONDITION_MAX = 100;

/**
 * Calculate the condition multiplier from a condition percentage (0-100).
 * Formula: 1 + (conditionPercent / 100) * 6.5
 *
 * This multiplier:
 * - Divides the non-fail chance (increasing fail rate)
 * - Raises the success threshold (need conditionMult × blueprint cost for success)
 * - Does NOT scale product output multipliers (output ranges stay the same)
 *
 * @param {number} conditionPercent - Condition percentage (0-100)
 * @returns {number} - Condition multiplier (1.0 at 0%, 7.5 at 100%)
 */
export function getConditionMultiplier(conditionPercent) {
  const clamped = Math.max(CONDITION_MIN, Math.min(CONDITION_MAX, conditionPercent));
  return 1 + (clamped / 100) * 6.5;
}

/**
 * Find the condition percentage (0-20) that minimizes estimated craft attempts.
 * Iterates all possible values and picks the one with the fewest attempts.
 *
 * @param {object} blueprint - Blueprint object
 * @param {number} quantityWanted - Desired output quantity
 * @param {number} [nonFailChance] - Non-fail chance % (0-100), omit for max
 * @param {number} [certainty] - Confidence level % (50-99)
 * @returns {number} - Optimal condition percentage (0-20)
 */
export function findOptimalCondition(blueprint, quantityWanted, nonFailChance, certainty = DEFAULT_CONFIG.certainty) {
  let bestCondition = 0;
  let bestAttempts = Infinity;

  for (let c = CONDITION_MIN; c <= CONDITION_MAX; c++) {
    const { estimatedAttempts } = calculateCraftAttempts(blueprint, quantityWanted, nonFailChance, certainty, c);
    if (estimatedAttempts < bestAttempts) {
      bestAttempts = estimatedAttempts;
      bestCondition = c;
    }
  }

  return bestCondition;
}

/**
 * Find the condition percentage (0-100) that maximizes average output per attempt.
 * This optimizes for throughput efficiency rather than total attempts.
 *
 * @param {object} blueprint - Blueprint object
 * @param {number} [nonFailChance] - Non-fail chance % (0-100), omit for max
 * @param {number} [certainty] - Confidence level % (50-99)
 * @returns {number} - Optimal condition percentage (0-100)
 */
export function findOptimalOutputCondition(blueprint, nonFailChance, certainty = DEFAULT_CONFIG.certainty) {
  let bestCondition = 0;
  let bestOutputPerAttempt = 0;

  for (let c = CONDITION_MIN; c <= CONDITION_MAX; c++) {
    const { avgOutputPerAttempt } = calculateCraftAttempts(blueprint, 1, nonFailChance, certainty, c);
    if (avgOutputPerAttempt > bestOutputPerAttempt) {
      bestOutputPerAttempt = avgOutputPerAttempt;
      bestCondition = c;
    }
  }

  return bestCondition;
}

// ── Hotspot Model Constants ──────────────────────────────────────────────────

/** Hotspot variance: each hotspot varies ±this fraction, shaped by Beta(2,2) */
export const HOTSPOT_VARIANCE = 0.10;

/** Value multiplier threshold: >= this is a success, < this is near-success */
export const SUCCESS_THRESHOLD = 1.0;

/** Maximum value multiplier for product output (caps output range high) */
export const MAX_OUTPUT_MULTIPLIER = 7;

/** Output range low cap — output range low is min(effectiveMult * 0.9, this) */
export const OUTPUT_RANGE_LOW_CAP = 3;

/**
 * Compute the product output range for a given effective value multiplier.
 * Formula: [min(mult * 0.9, 3), min(mult * 1.1, 7)]
 * Uniform distribution within the range, floored to integer product units.
 *
 * @param {number} effectiveMult - Effective value multiplier (hotspot.multiplier * conditionMult)
 * @returns {[number, number]} - [low, high] output range
 */
export function computeOutputRange(effectiveMult) {
  return [
    Math.min(effectiveMult * 0.9, OUTPUT_RANGE_LOW_CAP),
    Math.min(effectiveMult * 1.1, MAX_OUTPUT_MULTIPLIER)
  ];
}

/**
 * Empirical hotspot definitions from KDE lognormal analysis.
 * Each entry: { multiplier, weight, outputRange? }
 * - multiplier: TT value as fraction of blueprint cost
 * - weight: probability of this hotspot (of non-fail outcomes)
 * - outputRange: [low, high] base output range (at conditionMult=1), for display only
 *   Actual output range is computed at runtime via computeOutputRange(mult * conditionMult)
 */
export const HOTSPOTS = [
  { multiplier: 0.20, weight: 0.078 },
  { multiplier: 0.50, weight: 0.2647 },
  { multiplier: 0.85, weight: 0.2010 },
  { multiplier: 1.10, weight: 0.4282, outputRange: [0.99, 1.21] },
  { multiplier: 2.50, weight: 0.0149, outputRange: [2.25, 2.75] },
  { multiplier: 5.00, weight: 0.0068, outputRange: [3.0, 5.5] },
  { multiplier: 10.0, weight: 0.0030, outputRange: [3.0, 7.0] },
];

/** Weight for outcomes above the highest defined hotspot */
export const HIGH_SUCCESS_WEIGHT = 0.0018;

/** Output range for >10x successes */
export const HIGH_SUCCESS_OUTPUT_RANGE = [3.0, 7.0];

/** Fraction of the 1.10x hotspot that overlaps into near-success (<1.0x) due to variance */
export const SPLIT_NEAR_SUCCESS_FRACTION = 0.047;

/** Default simulation iterations for refund calculation */
const SIMULATION_ITERATIONS = 2000;

// ── Seeded PRNG ──────────────────────────────────────────────────────────────

/**
 * Mulberry32 seeded PRNG. Fast, good distribution, 32-bit state.
 * Returns a function that produces numbers in [0, 1).
 * @param {number} seed - 32-bit integer seed
 * @returns {() => number}
 */
function createSeededRandom(seed) {
  let state = seed | 0;
  return function () {
    state = (state + 0x6D2B79F5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Module-level seeded random function, reset before each simulation */
let _rng = Math.random;

/** Z-scores for certainty levels (normal approximation) */
const CERTAINTY_Z_SCORES = {
  50: 0,
  60: 0.25,
  70: 0.52,
  75: 0.67,
  80: 0.84,
  85: 1.04,
  90: 1.28,
  95: 1.65,
  99: 2.33
};

/**
 * Get z-score for a certainty percentage (interpolates if needed)
 * @param {number} certainty - Certainty percentage (50-99)
 * @returns {number} - Z-score for normal distribution
 */
function getZScore(certainty) {
  const clamped = Math.max(50, Math.min(99, certainty));

  // Check for exact match
  if (CERTAINTY_Z_SCORES[clamped] !== undefined) {
    return CERTAINTY_Z_SCORES[clamped];
  }

  // Interpolate between known values
  const keys = Object.keys(CERTAINTY_Z_SCORES).map(Number).sort((a, b) => a - b);
  for (let i = 0; i < keys.length - 1; i++) {
    if (clamped > keys[i] && clamped < keys[i + 1]) {
      const t = (clamped - keys[i]) / (keys[i + 1] - keys[i]);
      return CERTAINTY_Z_SCORES[keys[i]] + t * (CERTAINTY_Z_SCORES[keys[i + 1]] - CERTAINTY_Z_SCORES[keys[i]]);
    }
  }

  return 0;
}

// ── Hotspot Breakdown ────────────────────────────────────────────────────────

/**
 * Compute the hotspot breakdown into near-success and success categories.
 * Condition-independent: both hotspot values and success threshold scale equally
 * with condition, so the relative breakdown stays the same.
 *
 * Cached since it depends only on constants, not blueprint-specific values.
 *
 * @returns {{ nearSuccess: Array, success: Array, totalNearSuccessWeight: number, totalSuccessWeight: number, totalWeight: number }}
 */
let _hotspotBreakdownCache = null;
export function getHotspotBreakdown() {
  if (_hotspotBreakdownCache) return _hotspotBreakdownCache;

  const nearSuccess = [];
  const success = [];

  for (const hotspot of HOTSPOTS) {
    const lowerBound = hotspot.multiplier * (1 - HOTSPOT_VARIANCE);
    const isSplit = hotspot.multiplier >= SUCCESS_THRESHOLD && lowerBound < SUCCESS_THRESHOLD;

    if (isSplit) {
      // Split hotspot: part near-success, part success
      const nearSuccessWeight = hotspot.weight * SPLIT_NEAR_SUCCESS_FRACTION;
      const successWeight = hotspot.weight * (1 - SPLIT_NEAR_SUCCESS_FRACTION);

      // Expected pool multiplier for the near-success portion:
      // Truncated Beta(2,2) mean on [0, tMax] where tMax maps threshold to beta space.
      const range = hotspot.multiplier * 2 * HOTSPOT_VARIANCE;
      const tMax = (SUCCESS_THRESHOLD - lowerBound) / range;
      const cdfMax = 3 * tMax * tMax - 2 * tMax * tMax * tMax;
      // Beta(2,2) PDF: f(t) = 6t(1-t), so integral of t*f(t) = 6*(t^3/3 - t^4/4)
      const meanNumerator = 6 * (tMax * tMax * tMax / 3 - tMax * tMax * tMax * tMax / 4);
      const truncatedMean = cdfMax > 0 ? meanNumerator / cdfMax : tMax / 2;
      const poolMultiplier = lowerBound + truncatedMean * range;
      nearSuccess.push({ multiplier: hotspot.multiplier, weight: nearSuccessWeight, poolMultiplier });

      // Success portion: carries multiplier for dynamic output range computation
      success.push({ multiplier: hotspot.multiplier, weight: successWeight, outputRange: hotspot.outputRange });
    } else if (hotspot.multiplier < SUCCESS_THRESHOLD) {
      // Pure near-success
      nearSuccess.push({ multiplier: hotspot.multiplier, weight: hotspot.weight, poolMultiplier: hotspot.multiplier });
    } else {
      // Pure success
      success.push({ multiplier: hotspot.multiplier, weight: hotspot.weight, outputRange: hotspot.outputRange });
    }
  }

  // Add >10x high success (multiplier 15 representative; always caps to [3, 7])
  success.push({ multiplier: 15, weight: HIGH_SUCCESS_WEIGHT, outputRange: HIGH_SUCCESS_OUTPUT_RANGE });

  const totalNearSuccessWeight = nearSuccess.reduce((s, h) => s + h.weight, 0);
  const totalSuccessWeight = success.reduce((s, h) => s + h.weight, 0);
  const totalWeight = totalNearSuccessWeight + totalSuccessWeight;

  _hotspotBreakdownCache = { nearSuccess, success, totalNearSuccessWeight, totalSuccessWeight, totalWeight };
  return _hotspotBreakdownCache;
}

/**
 * Build a map of product names to blueprints that produce them
 * Groups by base name (without L suffix) to enable L/non-L version selection
 * @param {Map<number, object>} blueprintCache - Map of blueprintId -> blueprint
 * @returns {Map<string, { limited: object[], unlimited: object[] }>}
 */
export function buildProductToBlueprintMap(blueprintCache) {
  const productMap = new Map(); // productName -> { limited: [], unlimited: [] }

  for (const [id, blueprint] of blueprintCache) {
    const productName = blueprint.Product?.Name;
    if (!productName) continue;

    if (!productMap.has(productName)) {
      productMap.set(productName, { limited: [], unlimited: [] });
    }

    const entry = productMap.get(productName);
    if (isLimitedBlueprint(blueprint)) {
      entry.limited.push(blueprint);
    } else {
      entry.unlimited.push(blueprint);
    }
  }

  return productMap;
}

/**
 * Get the preferred blueprint for a material based on config
 * @param {string} materialName - Name of the material/product to craft
 * @param {Map<string, { limited: object[], unlimited: object[] }>} productMap - Product to blueprints map
 * @param {object} materialCraftConfig - Config for material crafting preferences
 * @returns {object|null} - Selected blueprint or null if not craftable/not enabled
 */
export function getMaterialBlueprint(materialName, productMap, materialCraftConfig = {}) {
  const entry = productMap.get(materialName);
  if (!entry) return null;

  const config = materialCraftConfig[materialName] || {};

  // If crafting is disabled for this material, return null
  if (config.craft === false) return null;

  // Default to unlimited version (non-L)
  const preferLimited = config.preferLimited === true;

  // Try to get the preferred version, fallback to other if not available
  if (preferLimited) {
    if (entry.limited.length > 0) return entry.limited[0];
    if (entry.unlimited.length > 0) return entry.unlimited[0];
  } else {
    if (entry.unlimited.length > 0) return entry.unlimited[0];
    if (entry.limited.length > 0) return entry.limited[0];
  }

  return null;
}

/**
 * Get craftable blueprint info for a material
 * @param {string} materialName - Name of the material/product
 * @param {Map<string, { limited: object[], unlimited: object[] }>} productMap - Product to blueprints map
 * @returns {{ hasLimited: boolean, hasUnlimited: boolean, hasBoth: boolean, limited: object[], unlimited: object[] } | null}
 */
export function getMaterialCraftInfo(materialName, productMap) {
  const entry = productMap.get(materialName);
  if (!entry) return null;

  const hasLimited = entry.limited.length > 0;
  const hasUnlimited = entry.unlimited.length > 0;

  if (!hasLimited && !hasUnlimited) return null;

  return {
    hasLimited,
    hasUnlimited,
    hasBoth: hasLimited && hasUnlimited,
    limited: entry.limited,
    unlimited: entry.unlimited
  };
}

/** Maximum non-fail rates based on SiB */
export const MAX_NON_FAIL_SIB = 95;
export const MAX_NON_FAIL_NON_SIB = 90;

/**
 * Check if a blueprint is limited (consumed per craft attempt)
 * @param {object} blueprint - Blueprint object with Name property
 * @returns {boolean}
 */
export function isLimitedBlueprint(blueprint) {
  return !!blueprint?.Name && hasItemTag(blueprint.Name, 'L');
}

/**
 * Check if a blueprint has SiB (Skill Increase Bonus)
 * @param {object} blueprint - Blueprint object
 * @returns {boolean}
 */
export function hasSiB(blueprint) {
  return !!blueprint?.Properties?.Skill?.IsSiB;
}

/**
 * Get the maximum allowed non-fail chance for a blueprint
 * @param {object} blueprint - Blueprint object
 * @returns {number} - Maximum non-fail % (95 for SiB, 90 for non-SiB)
 */
export function getMaxNonFailChance(blueprint) {
  return hasSiB(blueprint) ? MAX_NON_FAIL_SIB : MAX_NON_FAIL_NON_SIB;
}

/**
 * Calculate success rates using hotspot-based model.
 * Hotspot weights are normalized to 100% of non-fail outcomes.
 * The success/near-success split is condition-independent (both hotspot values
 * and threshold scale equally). Condition only affects the non-fail chance.
 *
 * @param {number} nonFailChance - Non-fail chance % (0-100)
 * @returns {{ successRate: number, nearSuccessRate: number, failRate: number }}
 */
export function calculateSuccessRates(nonFailChance) {
  const nonFail = nonFailChance / 100;
  const { totalSuccessWeight, totalNearSuccessWeight, totalWeight } = getHotspotBreakdown();
  return {
    successRate: nonFail * (totalSuccessWeight / totalWeight),
    nearSuccessRate: nonFail * (totalNearSuccessWeight / totalWeight),
    failRate: 1 - nonFail
  };
}

/**
 * Calculate blueprint cost (total TT value of materials)
 * @param {object} blueprint - Blueprint with Materials
 * @returns {number} - Total material TT cost
 */
function calculateBlueprintCost(blueprint) {
  const materials = blueprint.Materials || [];
  let cost = 0;
  for (const mat of materials) {
    const matTT = mat.Item?.Properties?.Economy?.MaxTT || 0;
    cost += matTT * (mat.Amount || 0);
  }
  return cost;
}

/**
 * Calculate average output per success using the hotspot model.
 * For each success hotspot, compute expected product units from its output range,
 * then weight by normalized hotspot probability.
 *
 * Output range is computed dynamically from the effective multiplier:
 *   effectiveMult = hotspot.multiplier × conditionMult
 *   outputRange = [min(effectiveMult × 0.9, 3), min(effectiveMult × 1.1, 7)]
 * Product units = floor(outputRangeMult × B) where B = bpCost / productTT.
 *
 * @param {object} blueprint - Blueprint with Materials and Product
 * @param {number} maxOutput - Maximum product units per success
 * @param {number} [conditionMult=1] - Condition multiplier
 * @returns {number} - Expected average output per success (at least 1)
 */
function calculateHotspotAvgOutput(blueprint, maxOutput, conditionMult = 1) {
  const productTT = blueprint.Product?.Properties?.Economy?.MaxTT;
  if (!productTT || productTT <= 0) return 1;

  const bpCost = calculateBlueprintCost(blueprint);
  if (bpCost <= 0) return 1;

  const B = bpCost / productTT; // base output ratio
  const { success, totalSuccessWeight } = getHotspotBreakdown();
  if (totalSuccessWeight <= 0) return 1;

  let weightedOutput = 0;

  for (const hotspot of success) {
    const effectiveMult = hotspot.multiplier * conditionMult;
    const [rangeLow, rangeHigh] = computeOutputRange(effectiveMult);
    const normalizedWeight = hotspot.weight / totalSuccessWeight;

    // Convert output range multipliers to product units
    const scaledLow = rangeLow * B;
    const scaledHigh = rangeHigh * B;

    // maxOutput is the hard cap from blueprint (MaximumCraftAmount or formula max)
    const clampedLow = Math.max(1, scaledLow);
    const clampedHigh = Math.min(maxOutput + 0.999, scaledHigh);

    let contribution;
    if (clampedHigh <= clampedLow) {
      // Entire range is at or below minimum — output is 1 or maxOutput
      contribution = Math.max(1, Math.min(maxOutput, Math.floor(scaledLow)));
    } else {
      // Use weighted integer averaging for the clamped range
      // This properly handles the floor() at each integer boundary
      let avgForHotspot = calculateWeightedIntegerAverage(clampedLow, clampedHigh);

      // If part of the original range extends above maxOutput, that portion contributes maxOutput
      if (scaledHigh > maxOutput + 0.999) {
        const fractionAbove = (scaledHigh - (maxOutput + 0.999)) / (scaledHigh - scaledLow);
        const fractionBelow = 1 - fractionAbove;
        avgForHotspot = fractionBelow * avgForHotspot + fractionAbove * maxOutput;
      }

      contribution = Math.max(1, avgForHotspot);
    }

    weightedOutput += normalizedWeight * contribution;
  }

  return Math.max(1, weightedOutput);
}

/**
 * Calculate expected integer output using weighted average across integer buckets.
 * Assumes output is uniformly distributed over [lowRaw, highRaw] then floored.
 *
 * For each integer n in [floor(lowRaw), floor(highRaw)]:
 *   weight(n) = overlap of [n, n+1) with [lowRaw, highRaw]
 *   Expected output = sum(n * weight(n)) / total_range
 *
 * This handles threshold crossings smoothly - barely crossing into a new
 * integer bucket contributes very little to the average.
 *
 * @param {number} lowRaw - Lower bound of output range
 * @param {number} highRaw - Upper bound of output range
 * @returns {number} - Expected floored output value
 */
function calculateWeightedIntegerAverage(lowRaw, highRaw) {
  if (highRaw <= lowRaw) {
    return Math.floor(lowRaw);
  }

  const range = highRaw - lowRaw;
  const minInt = Math.floor(lowRaw);
  const maxInt = Math.floor(highRaw);

  // Calculate weighted sum: each integer contributes proportionally to
  // how much of the [lowRaw, highRaw] range falls into its bucket [n, n+1)
  let weightedSum = 0;
  for (let n = minInt; n <= maxInt; n++) {
    const bucketStart = Math.max(n, lowRaw);
    const bucketEnd = Math.min(n + 1, highRaw);
    const overlap = Math.max(0, bucketEnd - bucketStart);
    weightedSum += n * overlap;
  }

  return weightedSum / range;
}

/**
 * Calculate estimated craft attempts needed for a desired quantity.
 * Uses the hotspot model to determine average output per success.
 *
 * @param {object} blueprint - Blueprint with Properties.MinimumCraftAmount/MaximumCraftAmount
 * @param {number} quantityWanted - Desired output quantity
 * @param {number} nonFailChance - Non-fail chance % (0-100), defaults to max for blueprint
 * @param {number} certainty - Confidence level % (50-99), defaults to 50 (mean estimate)
 * @param {number} conditionPercent - Condition slider value (0-20), defaults to 0
 * @returns {{ estimatedAttempts: number, avgOutput: number, avgOutputPerAttempt: number, successRate: number, nearSuccessRate: number, failRate: number, nonFailChance: number, effectiveNonFailChance: number, conditionMultiplier: number }}
 */
export function calculateCraftAttempts(blueprint, quantityWanted, nonFailChance = null, certainty = DEFAULT_CONFIG.certainty, conditionPercent = 0) {
  const conditionMult = getConditionMultiplier(conditionPercent);

  // Products with condition (e.g., need residue) implicitly have maxOutput = 1
  const productHasCondition = blueprint.Product && hasCondition(blueprint.Product);

  // Calculate maximum product output per success
  const productTT = blueprint.Product?.Properties?.Economy?.MaxTT || 0;
  const bpCost = calculateBlueprintCost(blueprint);
  let maxOutput;

  if (productHasCondition) {
    maxOutput = 1;
  } else if (productTT > 0 && bpCost > 0) {
    // Formula-based max: output range high caps at MAX_OUTPUT_MULTIPLIER (7) regardless of condition
    // MaximumCraftAmount is the absolute hard cap from the game
    const formulaMax = Math.floor(bpCost * MAX_OUTPUT_MULTIPLIER / productTT);
    const maxCraft = blueprint.Properties?.MaximumCraftAmount;
    maxOutput = maxCraft ? Math.min(formulaMax, maxCraft) : formulaMax;
    maxOutput = Math.max(1, maxOutput);
  } else {
    maxOutput = 1;
  }

  // Calculate average output per success using hotspot model
  // Output range is computed dynamically from effectiveMult = hotspot.mult × conditionMult
  const avgOutput = productHasCondition ? 1 : calculateHotspotAvgOutput(blueprint, maxOutput, conditionMult);

  // Use provided non-fail chance or default to maximum for this blueprint
  const maxNonFail = getMaxNonFailChance(blueprint);
  const actualNonFail = nonFailChance !== null
    ? Math.min(nonFailChance, maxNonFail)
    : maxNonFail;

  // Condition divides the non-fail chance, reducing both success and near-success rates
  // The success/near-success SPLIT doesn't change (hotspot values and threshold scale equally)
  const effectiveNonFail = conditionMult > 1 ? actualNonFail / conditionMult : actualNonFail;
  const { successRate, nearSuccessRate, failRate } = calculateSuccessRates(effectiveNonFail);

  // Expected output per attempt = success_rate * avg_items_per_success
  const avgOutputPerAttempt = successRate * avgOutput;

  if (avgOutputPerAttempt <= 0) {
    return {
      estimatedAttempts: quantityWanted,
      avgOutput,
      avgOutputPerAttempt: 0,
      successRate,
      nearSuccessRate,
      failRate,
      nonFailChance: actualNonFail,
      effectiveNonFailChance: effectiveNonFail,
      conditionMultiplier: conditionMult
    };
  }

  // Number of successful crafts needed
  const successesNeeded = Math.ceil(quantityWanted / avgOutput);

  // Mean attempts using negative binomial distribution: mean = k / p
  const meanAttempts = successesNeeded / successRate;

  // Variance for negative binomial: var = k * (1-p) / p²
  const variance = successesNeeded * (1 - successRate) / (successRate * successRate);
  const stdDev = Math.sqrt(variance);

  // Apply certainty factor using z-score
  const zScore = getZScore(certainty);
  const adjustedAttempts = meanAttempts + zScore * stdDev;

  const estimatedAttempts = Math.ceil(Math.max(successesNeeded, adjustedAttempts));

  return {
    estimatedAttempts,
    avgOutput,
    avgOutputPerAttempt,
    successRate,
    nearSuccessRate,
    failRate,
    nonFailChance: actualNonFail,
    effectiveNonFailChance: effectiveNonFail,
    conditionMultiplier: conditionMult
  };
}

/**
 * Sample from a Beta(2,2) distribution.
 * Uses the property that Beta(2,2) = median of 3 uniform random variables.
 * @returns {number} - Sample in [0, 1]
 */
function sampleBeta22() {
  const a = _rng(), b = _rng(), c = _rng();
  // Median of three: max of the two smaller values
  return Math.max(Math.min(a, b), Math.min(Math.max(a, b), c));
}

/**
 * Sample a hotspot multiplier with Beta(2,2) variance.
 * Maps Beta(2,2) from [0,1] to [multiplier*(1-variance), multiplier*(1+variance)].
 * @param {number} multiplier - Center multiplier value
 * @returns {number} - Sampled multiplier with variance applied
 */
function sampleHotspotMultiplier(multiplier) {
  const beta = sampleBeta22();
  return multiplier * (1 - HOTSPOT_VARIANCE + 2 * HOTSPOT_VARIANCE * beta);
}

/**
 * Sample from the truncated Beta(2,2) hotspot distribution, conditioned on
 * the result being below `upperBound`. Uses inverse CDF sampling on the
 * truncated distribution to avoid rejection sampling inefficiency.
 *
 * Beta(2,2) CDF: F(x) = 3x^2 - 2x^3 for x in [0,1]
 * We need the portion of the hotspot range [low, high] that falls below upperBound.
 *
 * @param {number} multiplier - Center multiplier value of the hotspot
 * @param {number} upperBound - Maximum value (exclusive) for truncation
 * @returns {number} - Sampled multiplier < upperBound
 */
function sampleTruncatedHotspotMultiplier(multiplier, upperBound) {
  const low = multiplier * (1 - HOTSPOT_VARIANCE);
  const high = multiplier * (1 + HOTSPOT_VARIANCE);
  const range = high - low;

  // Map upperBound to Beta(2,2) space [0,1]
  const tMax = Math.min(1, (upperBound - low) / range);
  if (tMax <= 0) return low; // entire range is above bound

  // Beta(2,2) CDF: F(t) = 3t^2 - 2t^3
  const cdfAtMax = 3 * tMax * tMax - 2 * tMax * tMax * tMax;

  // Sample uniformly in [0, cdfAtMax], then invert CDF
  const u = _rng() * cdfAtMax;

  // Invert Beta(2,2) CDF: solve 3t^2 - 2t^3 = u using Newton's method
  let t = Math.min(tMax * 0.5, 0.5); // initial guess
  for (let iter = 0; iter < 10; iter++) {
    const f = 3 * t * t - 2 * t * t * t - u;
    const fPrime = 6 * t - 6 * t * t; // derivative: 6t(1-t)
    if (Math.abs(fPrime) < 1e-12) break;
    t = Math.max(0, Math.min(tMax, t - f / fPrime));
    if (Math.abs(f) < 1e-10) break;
  }

  return low + t * range;
}

/**
 * Simulate refund rates using hotspot-based pools via Monte Carlo.
 *
 * For each iteration, a near-success hotspot is chosen (weighted random),
 * its pool value is sampled with Beta(2,2) variance, then each material
 * rolls independently and winners are processed in random order.
 *
 * @param {Array<{name: string, amount: number, unitTT: number}>} materials - Materials to simulate
 * @param {number} rollChance - Per-material roll chance (0-100)
 * @param {number} iterations - Number of simulation runs
 * @param {number} [conditionMult=1] - Condition multiplier: scales refund pool and per-material refund cap
 * @returns {Map<string, number>} - materialName → expected refund fraction (0-1) per near-success
 */
export function simulateRefundRates(materials, rollChance, iterations = SIMULATION_ITERATIONS, conditionMult = 1) {
  // Filter out zero-cost materials (they would cause infinite refunds)
  const validMaterials = materials.filter(m => m.unitTT > 0);
  if (validMaterials.length === 0) {
    return new Map(materials.map(m => [m.name, m.unitTT > 0 ? 0 : 1]));
  }

  // Calculate blueprint total TT cost
  const blueprintCost = validMaterials.reduce((sum, m) => sum + m.amount * m.unitTT, 0);
  if (blueprintCost <= 0) {
    return new Map(materials.map(m => [m.name, 0]));
  }

  const { nearSuccess, totalNearSuccessWeight } = getHotspotBreakdown();
  if (totalNearSuccessWeight <= 0) {
    return new Map(materials.map(m => [m.name, 0]));
  }

  // Seed PRNG deterministically from material composition so same blueprint = same results.
  // Hash: combine material costs, amounts, and condition into a single seed value.
  let seed = validMaterials.length * 7919;
  for (const m of validMaterials) {
    seed = ((seed * 31) + (m.unitTT * 10000) + m.amount) | 0;
  }
  seed = ((seed * 31) + rollChance + Math.round(conditionMult * 10000)) | 0;
  _rng = createSeededRandom(seed);

  // Build cumulative weights for weighted random selection
  const cumulativeWeights = [];
  let cumSum = 0;
  for (const hs of nearSuccess) {
    cumSum += hs.weight / totalNearSuccessWeight;
    cumulativeWeights.push(cumSum);
  }

  // Track total refunded units per material
  const refundedUnits = new Map(validMaterials.map(m => [m.name, 0]));
  const rollProb = rollChance / 100;

  for (let i = 0; i < iterations; i++) {
    // Pick a near-success hotspot (weighted random)
    const r = _rng();
    let hotspotIdx = cumulativeWeights.findIndex(w => r < w);
    if (hotspotIdx === -1) hotspotIdx = nearSuccess.length - 1;
    const hotspot = nearSuccess[hotspotIdx];

    // Sample pool multiplier with Beta(2,2) variance.
    // For split hotspots (multiplier >= threshold), sample from the truncated
    // Beta(2,2) distribution conditioned on falling below the threshold.
    // The breakdown is condition-independent (both values and threshold scale equally).
    let poolMultiplier;
    if (hotspot.multiplier >= SUCCESS_THRESHOLD) {
      poolMultiplier = sampleTruncatedHotspotMultiplier(hotspot.multiplier, SUCCESS_THRESHOLD);
    } else {
      poolMultiplier = sampleHotspotMultiplier(hotspot.multiplier);
    }

    // Pool scales with conditionMult — condition multiplies the effective blueprint cost,
    // so near-success refund pools are proportionally larger
    let pool = Math.max(0, poolMultiplier * blueprintCost * conditionMult);

    // Each material rolls independently
    const winners = validMaterials.filter(() => _rng() < rollProb);

    // Random processing order (Fisher-Yates shuffle)
    for (let j = winners.length - 1; j > 0; j--) {
      const k = Math.floor(_rng() * (j + 1));
      [winners[j], winners[k]] = [winners[k], winners[j]];
    }

    // Process winners - each gets floor(pool / unitTT) units
    // Condition scales the max refund per material (2x multi = up to 2x material refunded)
    for (const mat of winners) {
      const unitsRefundable = Math.floor(pool / mat.unitTT);
      const maxRefund = Math.floor(mat.amount * conditionMult);
      const unitsRefunded = Math.min(unitsRefundable, maxRefund);
      if (unitsRefunded > 0) {
        refundedUnits.set(mat.name, (refundedUnits.get(mat.name) || 0) + unitsRefunded);
        pool -= unitsRefunded * mat.unitTT;
      }
    }
  }

  // Convert to expected refund fraction per near-success
  const refundFractions = new Map();
  for (const mat of validMaterials) {
    const totalRefunded = refundedUnits.get(mat.name) || 0;
    const expectedPerNearSuccess = totalRefunded / iterations;
    refundFractions.set(mat.name, expectedPerNearSuccess / mat.amount);
  }

  // Zero-cost materials get 100% refund
  for (const mat of materials) {
    if (mat.unitTT <= 0) {
      refundFractions.set(mat.name, 1);
    }
  }

  // Restore default RNG so non-simulation code (e.g. UUID) isn't affected
  _rng = Math.random;

  return refundFractions;
}

/**
 * Calculate per-material multipliers using pool-based refund simulation.
 *
 * @param {any[]} blueprintMaterials - Blueprint's materials array with Item and Amount properties
 * @param {number} nonFailChance - Non-fail chance % (0-100)
 * @param {number} rollChance - Per-material roll chance % (0-100)
 * @param {number} [conditionMult=1] - Condition multiplier: scales refund pool and per-material cap
 * @returns {Map<string, {multiplier: number, refundFraction: number}>} - materialName → multiplier data
 */
export function calculatePerMaterialMultipliers(blueprintMaterials, nonFailChance, rollChance, conditionMult = 1) {
  const { nearSuccessRate } = calculateSuccessRates(nonFailChance);

  // Prepare materials for simulation
  const materialsForSim = blueprintMaterials.map(mat => ({
    name: mat.Item?.Name || 'Unknown',
    amount: mat.Amount || 0,
    unitTT: mat.Item?.Properties?.Economy?.MaxTT || 0
  }));

  // Run simulation — condition scales refund pool and per-material cap
  const refundFractions = simulateRefundRates(materialsForSim, rollChance, SIMULATION_ITERATIONS, conditionMult);

  // Convert to multipliers
  const result = new Map();
  for (const mat of materialsForSim) {
    const refundFraction = refundFractions.get(mat.name) || 0;
    // Expected materials per attempt = 1 - (nearSuccessRate * refundFraction)
    const multiplier = 1 - (nearSuccessRate * refundFraction);
    result.set(mat.name, { multiplier, refundFraction });
  }

  return result;
}

/**
 * Check if a blueprint's product requires residue (has condition and is not limited)
 * @param {object} blueprint - Blueprint object
 * @returns {boolean}
 */
export function productNeedsResidue(blueprint) {
  if (!blueprint?.Product) return false;
  // Limited blueprints don't need residue (they're consumed)
  if (isLimitedBlueprint(blueprint)) return false;
  // Check if product type has condition
  return hasCondition({ Properties: { Type: blueprint.Product.Properties?.Type } });
}

/**
 * Calculate residue required per craft attempt
 * Residue = Product Max TT - Blueprint material cost (TT)
 * @param {object} blueprint - Blueprint object with Materials and Product
 * @returns {number} - Residue TT per click (0 if no residue needed)
 */
export function calculateResiduePerClick(blueprint) {
  if (!productNeedsResidue(blueprint)) return 0;

  const productTT = blueprint.Product?.Properties?.Economy?.MaxTT || 0;

  // Calculate total material TT cost per click
  let materialCostTT = 0;
  for (const mat of blueprint.Materials || []) {
    const matTT = mat.Item?.Properties?.Economy?.MaxTT || 0;
    materialCostTT += matTT * mat.Amount;
  }

  // Residue = Product TT - Material TT (max 0)
  return Math.max(0, productTT - materialCostTT);
}

/**
 * Build a crafting tree from target blueprints
 * @param {Array<{blueprintId: number, quantity: number}>} targets - Target blueprints with quantities
 * @param {object} ownershipMap - Map of blueprintId -> false (only stores not-owned)
 * @param {Map<number, object>} blueprintCache - Map of blueprintId -> full blueprint object
 * @param {object} [config] - Configuration options
 * @param {number} [config.rollChance] - Per-material roll success probability % (0-100)
 * @param {number} [config.certainty] - Confidence level % (50-99)
 * @param {object} [config.nonFailChances] - Map of blueprintId -> non-fail chance %
 * @param {object} [config.materialCraftConfig] - Map of materialName -> { craft: bool, preferLimited: bool }
 * @param {Record<number, number>} [config.conditionPercents] - Map of blueprintId -> condition % (0-20)
 * @returns {Array<CraftNode>} - Array of root crafting nodes
 */
export function buildCraftingTree(targets, ownershipMap, blueprintCache, config = {}) {
  const roots = [];
  const {
    rollChance = DEFAULT_CONFIG.rollChance,
    certainty = DEFAULT_CONFIG.certainty,
    nonFailChances = {},
    materialCraftConfig = {},
    conditionPercents = {}
  } = config;

  // Build product-to-blueprint map for material crafting lookup
  const productMap = buildProductToBlueprintMap(blueprintCache);

  for (const target of targets) {
    const blueprint = blueprintCache.get(target.blueprintId);
    if (!blueprint) continue;

    const owned = ownershipMap[target.blueprintId] !== false;
    const node = buildNode(blueprint, target.quantity, owned, ownershipMap, blueprintCache, 0, new Set(), rollChance, certainty, nonFailChances, productMap, materialCraftConfig, conditionPercents);
    roots.push(node);
  }

  return roots;
}

/**
 * Build a single crafting node (recursive)
 * @private
 * @param {Record<number, number>} [conditionPercents] - Map of blueprintId -> condition % (0-20)
 */
function buildNode(blueprint, quantityWanted, owned, ownershipMap, blueprintCache, depth, visited, rollChance, certainty, nonFailChances, productMap, materialCraftConfig, conditionPercents) {
  // Prevent infinite recursion (blueprint drops can be circular)
  if (visited.has(blueprint.Id)) {
    return {
      blueprint,
      quantityWanted,
      estimatedAttempts: 0,
      avgOutput: 1,
      avgOutputPerAttempt: 0,
      successRate: 0,
      nearSuccessRate: 0,
      failRate: 1,
      isLimited: isLimitedBlueprint(blueprint),
      isSiB: hasSiB(blueprint),
      owned,
      materials: [],
      materialChildren: [],
      depth,
      circular: true,
      residuePerClick: 0,
      totalResidue: 0,
      adjustedResidue: 0,
      nonFailChance: getMaxNonFailChance(blueprint),
      effectiveNonFailChance: getMaxNonFailChance(blueprint),
      materialMultiplier: 1,
      conditionPercent: 0,
      conditionMultiplier: 1
    };
  }
  visited.add(blueprint.Id);

  // Get non-fail chance and condition for this blueprint (from config or defaults)
  const configuredNonFail = nonFailChances[blueprint.Id];
  const userCondition = conditionPercents ? conditionPercents[blueprint.Id] : undefined;
  // Auto-compute optimal output condition if the user hasn't explicitly set one
  const conditionPercent = userCondition !== undefined
    ? userCondition
    : findOptimalOutputCondition(blueprint, configuredNonFail, certainty);
  const { estimatedAttempts, avgOutput, avgOutputPerAttempt, successRate, nearSuccessRate, failRate, nonFailChance, effectiveNonFailChance, conditionMultiplier } =
    calculateCraftAttempts(blueprint, quantityWanted, configuredNonFail, certainty, conditionPercent);

  const isLimited = isLimitedBlueprint(blueprint);
  const isSiB = hasSiB(blueprint);

  // Calculate per-material multipliers using pool-based simulation
  // Use effective non-fail chance (condition-adjusted) since that's the actual near-success rate
  // Pass conditionMultiplier so simulation uses the correct near-success hotspot set
  const perMaterialData = calculatePerMaterialMultipliers(
    blueprint.Materials || [],
    effectiveNonFailChance,
    rollChance,
    conditionMultiplier
  );

  // Collect materials with both raw and adjusted amounts
  // Also check if each material can be crafted
  const materials = (blueprint.Materials || []).map(mat => {
    const rawTotal = mat.Amount * estimatedAttempts;
    const materialName = mat.Item?.Name || 'Unknown';

    // Get per-material multiplier from simulation
    const matData = perMaterialData.get(materialName) || { multiplier: 1, refundFraction: 0 };
    const adjustedAmount = Math.ceil(rawTotal * matData.multiplier);

    // Check if this material has a craftable blueprint
    const craftableBlueprints = productMap?.get(materialName);
    const hasCraftableBlueprint = craftableBlueprints &&
      (craftableBlueprints.limited.length > 0 || craftableBlueprints.unlimited.length > 0);

    return {
      item: mat.Item,
      amountPerAttempt: mat.Amount,
      totalAmount: rawTotal,
      adjustedAmount,
      multiplier: matData.multiplier,
      refundFraction: matData.refundFraction,
      hasCraftableBlueprint,
      craftableVersions: hasCraftableBlueprint ? {
        hasLimited: craftableBlueprints.limited.length > 0,
        hasUnlimited: craftableBlueprints.unlimited.length > 0
      } : null
    };
  });

  // Calculate weighted average multiplier for backward compatibility
  let materialMultiplier = 1;
  let totalTTCost = 0;
  for (const m of materials) {
    const unitTT = m.item?.Properties?.Economy?.MaxTT || 0;
    totalTTCost += m.totalAmount * unitTT;
  }
  if (totalTTCost > 0) {
    let weightedSum = 0;
    for (const m of materials) {
      const unitTT = m.item?.Properties?.Economy?.MaxTT || 0;
      const matTTCost = m.totalAmount * unitTT;
      weightedSum += m.multiplier * (matTTCost / totalTTCost);
    }
    materialMultiplier = weightedSum;
  }

  // Calculate residue requirement (for products with condition)
  const residuePerClick = calculateResiduePerClick(blueprint);
  const totalResidue = residuePerClick * estimatedAttempts;
  // Residue is also subject to near-success refund
  const adjustedResidue = totalResidue * materialMultiplier;

  // Note: Blueprint "Drops" are bonus outputs that can randomly drop when crafting.
  // They are NOT requirements for crafting, so we don't include them in the tree.

  // Process craftable materials (only if we own this blueprint and material crafting is enabled)
  const materialChildren = [];
  if (owned && productMap && materialCraftConfig) {
    for (const mat of materials) {
      if (!mat.hasCraftableBlueprint) continue;

      const materialName = mat.item?.Name;
      const matBlueprint = getMaterialBlueprint(materialName, productMap, materialCraftConfig);

      if (matBlueprint) {
        const matOwned = ownershipMap[matBlueprint.Id] !== false;
        // Need adjustedAmount of this material
        const childNode = buildNode(
          matBlueprint, mat.adjustedAmount, matOwned,
          ownershipMap, blueprintCache, depth + 1, new Set(visited), rollChance, certainty, nonFailChances, productMap, materialCraftConfig, conditionPercents
        );
        childNode.isMaterialChild = true;
        childNode.parentMaterialName = materialName;
        materialChildren.push(childNode);
      }
    }
  }

  return {
    blueprint,
    quantityWanted,
    estimatedAttempts,
    avgOutput,
    avgOutputPerAttempt,
    successRate,
    nearSuccessRate,
    failRate,
    isLimited,
    isSiB,
    owned,
    materials,
    materialChildren,
    depth,
    residuePerClick,
    totalResidue,
    adjustedResidue,
    nonFailChance,
    effectiveNonFailChance,
    materialMultiplier,
    conditionPercent,
    conditionMultiplier
  };
}

/**
 * Generate ordered crafting steps (leaf-first / post-order traversal)
 * @param {Array<CraftNode>} roots - Root nodes from buildCraftingTree
 * @returns {Array<CraftStep>} - Ordered steps to craft
 */
export function generateCraftingSteps(roots) {
  const steps = [];
  const visited = new Set();

  function visit(node) {
    if (visited.has(node.blueprint.Id)) return;

    // Visit material children (craftable materials, depth-first post-order)
    for (const child of node.materialChildren || []) {
      visit(child);
    }

    visited.add(node.blueprint.Id);

    // Create step with both raw and adjusted values
    steps.push({
      blueprint: node.blueprint,
      quantityWanted: node.quantityWanted,
      estimatedAttempts: node.estimatedAttempts,
      avgOutput: node.avgOutput,
      avgOutputPerAttempt: node.avgOutputPerAttempt || 0,
      successRate: node.successRate || 0,
      nearSuccessRate: node.nearSuccessRate || 0,
      failRate: node.failRate || 1,
      isLimited: node.isLimited,
      isSiB: node.isSiB,
      owned: node.owned,
      materials: node.materials,
      materialChildren: node.materialChildren || [],
      action: node.owned ? 'craft' : 'buy_product',
      residuePerClick: node.residuePerClick || 0,
      totalResidue: node.totalResidue || 0,
      adjustedResidue: node.adjustedResidue || 0,
      nonFailChance: node.nonFailChance,
      effectiveNonFailChance: node.effectiveNonFailChance,
      materialMultiplier: node.materialMultiplier || 1,
      conditionPercent: node.conditionPercent || 0,
      conditionMultiplier: node.conditionMultiplier || 1,
      isMaterialChild: node.isMaterialChild || false,
      parentMaterialName: node.parentMaterialName || null
    });
  }

  for (const root of roots) {
    visit(root);
  }

  return steps;
}

/**
 * Generate shopping list - aggregated materials and products to buy
 * Uses adjusted amounts that account for near-success refunds
 * @param {Array<CraftNode>} roots - Root nodes from buildCraftingTree
 * @returns {{ materials: Array<ShoppingItem>, productsToBuy: Array<ShoppingItem>, limitedBlueprints: Array<ShoppingItem>, totalTT: number, totalResidue: number, adjustedTotalTT: number, adjustedTotalResidue: number }}
 */
export function generateShoppingList(roots) {
  const materialTotals = new Map(); // itemName -> { item, total, adjustedTotal }
  const productsToBuy = new Map(); // productName -> { item, quantity, blueprint }
  const limitedBPsToBuy = new Map(); // blueprintName -> { blueprint, quantity }
  const craftedMaterials = new Set(); // Materials being crafted (don't add to shopping list)
  let totalResidue = 0; // Total residue TT needed (raw)
  let adjustedTotalResidue = 0; // Total residue TT needed (adjusted for refunds)

  // First pass: collect all materials being crafted
  function collectCraftedMaterials(node) {
    if (!node.owned) return;

    for (const matChild of node.materialChildren || []) {
      if (matChild.parentMaterialName) {
        craftedMaterials.add(matChild.parentMaterialName);
      }
      collectCraftedMaterials(matChild);
    }
  }

  for (const root of roots) {
    collectCraftedMaterials(root);
  }

  function collectMaterials(node) {
    if (!node.owned) {
      if (node.isLimited && node.estimatedAttempts > 0) {
        // Limited blueprint not owned - add to limited BPs to buy
        const bpName = node.blueprint.Name;
        const existing = limitedBPsToBuy.get(bpName) || {
          blueprint: node.blueprint,
          quantity: 0
        };
        existing.quantity += node.estimatedAttempts;
        limitedBPsToBuy.set(bpName, existing);
      } else {
        // Unlimited blueprint not owned - add the final product to shopping list
        const productName = node.blueprint.Product?.Name || node.blueprint.Name;
        const existing = productsToBuy.get(productName) || {
          item: node.blueprint.Product || { Name: productName },
          quantity: 0,
          blueprint: node.blueprint
        };
        existing.quantity += node.quantityWanted;
        productsToBuy.set(productName, existing);
      }
      // Don't recurse into children - we're buying the product/BP instead
      return;
    }

    // Owned blueprints (both limited and unlimited) - user already has them
    // Just collect materials, residue, and recurse

    // Owned - add materials (both raw and adjusted)
    // Skip materials that are being crafted
    for (const mat of node.materials) {
      const key = mat.item.Name;

      // Skip if this material is being crafted
      if (craftedMaterials.has(key)) continue;

      const existing = materialTotals.get(key) || { item: mat.item, total: 0, adjustedTotal: 0 };
      existing.total += mat.totalAmount;
      existing.adjustedTotal += mat.adjustedAmount || mat.totalAmount;
      materialTotals.set(key, existing);
    }

    // Owned - add residue requirement (both raw and adjusted)
    if (node.totalResidue > 0) {
      totalResidue += node.totalResidue;
      adjustedTotalResidue += node.adjustedResidue || node.totalResidue;
    }

    // Recurse into material children
    for (const child of node.materialChildren || []) {
      collectMaterials(child);
    }
  }

  for (const root of roots) {
    collectMaterials(root);
  }

  // Convert to arrays and calculate TT values
  const materials = [];
  let totalTT = 0;
  let adjustedTotalTT = 0;

  for (const [name, { item, total, adjustedTotal }] of materialTotals) {
    const maxTT = item.Properties?.Economy?.MaxTT || 0;
    const ttValue = maxTT * total;
    const adjustedTTValue = maxTT * adjustedTotal;
    totalTT += ttValue;
    adjustedTotalTT += adjustedTTValue;
    materials.push({
      item,
      totalAmount: total,
      adjustedAmount: adjustedTotal,
      ttValue,
      adjustedTTValue,
      reason: 'material'
    });
  }

  // Sort by adjusted TT value descending
  materials.sort((a, b) => b.adjustedTTValue - a.adjustedTTValue);

  // Convert products to buy
  const productsArray = [];
  for (const [name, { item, quantity, blueprint }] of productsToBuy) {
    productsArray.push({
      item,
      totalAmount: quantity,
      ttValue: (item?.Properties?.Economy?.MaxTT || 0) * quantity,
      reason: 'unowned_bp_product',
      blueprintName: blueprint.Name
    });
  }

  // Convert limited blueprints to buy
  const limitedArray = [];
  for (const [name, { blueprint, quantity }] of limitedBPsToBuy) {
    limitedArray.push({
      blueprint,
      totalAmount: quantity,
      reason: 'limited_blueprint'
    });
  }

  return {
    materials,
    productsToBuy: productsArray,
    limitedBlueprints: limitedArray,
    totalTT,
    adjustedTotalTT,
    totalResidue,
    adjustedTotalResidue
  };
}

/**
 * Get all unique blueprints in a crafting tree (for ownership panel)
 * @param {Array<CraftNode>} roots - Root nodes from buildCraftingTree
 * @returns {Array<{ blueprint: object, owned: boolean, isLimited: boolean, isSiB: boolean, nonFailChance: number, maxNonFailChance: number, isMaterialChild: boolean }>}
 */
export function getAllBlueprintsInTree(roots) {
  const blueprints = new Map();

  function collect(node) {
    if (!blueprints.has(node.blueprint.Id)) {
      blueprints.set(node.blueprint.Id, {
        blueprint: node.blueprint,
        owned: node.owned,
        isLimited: node.isLimited,
        isSiB: node.isSiB,
        nonFailChance: node.nonFailChance,
        maxNonFailChance: getMaxNonFailChance(node.blueprint),
        isMaterialChild: node.isMaterialChild || false,
        parentMaterialName: node.parentMaterialName || null
      });
    }
    for (const child of node.materialChildren || []) {
      collect(child);
    }
  }

  for (const root of roots) {
    collect(root);
  }

  return Array.from(blueprints.values());
}

/**
 * Generate a UUID v4
 * @returns {string}
 */
function generateUUID() {
  // Use crypto.randomUUID if available, otherwise fallback
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  // Fallback UUID v4 generation
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * Create an empty crafting plan
 * @param {string} name - Plan name
 * @returns {object}
 */
export function createEmptyPlan(name = 'New Plan') {
  return {
    id: generateUUID(),
    name,
    data: {
      targets: []
    },
    created_at: new Date().toISOString(),
    last_update: new Date().toISOString()
  };
}

/**
 * Validate a crafting plan structure
 * @param {object} plan - Plan to validate
 * @returns {{ valid: boolean, error?: string }}
 */
export function validatePlan(plan) {
  if (!plan || typeof plan !== 'object') {
    return { valid: false, error: 'Invalid plan object' };
  }
  if (!plan.name || typeof plan.name !== 'string') {
    return { valid: false, error: 'Plan must have a name' };
  }
  if (!plan.data || typeof plan.data !== 'object') {
    return { valid: false, error: 'Plan must have data object' };
  }
  if (!Array.isArray(plan.data.targets)) {
    return { valid: false, error: 'Plan data must have targets array' };
  }
  for (const target of plan.data.targets) {
    if (typeof target.blueprintId !== 'number') {
      return { valid: false, error: 'Target must have blueprintId (number)' };
    }
    if (typeof target.quantity !== 'number' || target.quantity < 1) {
      return { valid: false, error: 'Target must have quantity >= 1' };
    }
  }
  return { valid: true };
}
