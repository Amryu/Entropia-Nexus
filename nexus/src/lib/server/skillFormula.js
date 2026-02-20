/**
 * Server-only skill value conversion.
 * DO NOT import from client-side code — SvelteKit enforces this via $lib/server/.
 */

// Coefficients stored in arrays to avoid revealing formula structure
const _C = [250, 2.465937, 0.00027699, 1.125];                    // pre-BP
const _P = [36 / 85, 1 / 4, 712.0, -125 / 84, -139 / 86, 4878.0]; // trend decay
const _W = [0.30, 2264.4, 500];                                    // modulation
const _K = 200 / 9;                                                 // scale

/**
 * Marginal cost at skill level x (micro-PED drops per skill point).
 * @param {number} x
 * @returns {number}
 */
function _cost(x) {
  if (x < _C[0]) {
    return _C[1] + _C[2] * Math.pow(Math.max(x, 0), _C[3]);
  }
  const t = x - _C[0];
  const f = _P[1] + (_P[0] - _P[1]) * Math.exp(-t / _P[2]);
  const g = _P[3] + (_P[4] - _P[3]) * Math.exp(-t / _P[5]);
  const a = _W[0] * (1 - Math.exp(-t / _W[1]));
  const poisson = Math.sqrt(1 - a * a) / (1 - a * Math.cos(2 * Math.PI * x / _W[2]));
  return _K * (f * Math.pow(x, 0.25) + g) * poisson;
}

/**
 * Cumulative PED value for a given number of skill points.
 * Integrates cost(x) from 0 to S via trapezoidal rule, divides by 1,000,000.
 * @param {number} skillPoints
 * @returns {number} PED value
 */
export function skillPointsToPED(skillPoints) {
  if (skillPoints <= 0) return 0;

  const steps = Math.min(Math.max(Math.ceil(skillPoints * 4), 200), 50000);
  const dx = skillPoints / steps;
  let sum = 0;

  for (let i = 0; i < steps; i++) {
    const x0 = i * dx;
    const x1 = (i + 1) * dx;
    sum += (_cost(x0) + _cost(x1)) / 2 * dx;
  }

  return sum / 1_000_000;
}

/**
 * Inverse: PED value to skill points via binary search.
 * @param {number} ped
 * @returns {number} skill points
 */
export function pedToSkillPoints(ped) {
  if (ped <= 0) return 0;

  let lo = 0;
  let hi = 100000;
  while (skillPointsToPED(hi) < ped) hi *= 2;

  for (let i = 0; i < 60; i++) {
    const mid = (lo + hi) / 2;
    if (skillPointsToPED(mid) < ped) lo = mid;
    else hi = mid;
  }
  return (lo + hi) / 2;
}

/**
 * Batch convert skill points → PED.
 * @param {number[]} arr
 * @returns {number[]}
 */
export function batchSkillPointsToPED(arr) {
  return arr.map(sp => skillPointsToPED(sp));
}

/**
 * Batch convert PED → skill points.
 * @param {number[]} arr
 * @returns {number[]}
 */
export function batchPedToSkillPoints(arr) {
  return arr.map(p => pedToSkillPoints(p));
}
