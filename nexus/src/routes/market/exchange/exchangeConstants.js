export const STALENESS_THRESHOLDS = {
  STALE_DAYS: 3,
  EXPIRED_DAYS: 7,
  TERMINATED_DAYS: 30,
};

export const MAX_SELL_ORDERS = 1000;
export const MAX_BUY_ORDERS = 50;

export const PLANETS = [
  'Calypso',
  'Arkadia',
  'Cyrene',
  'Rocktropia',
  'Next Island',
  'Monria',
  'Toulan',
  'Howling Mine (Space)',
];

// 2% relative undercut system
const UNDERCUT_PERCENT = 0.02;
const MIN_UNDERCUT = 0.01;

/** Default min_quantity as fraction of total quantity */
export const DEFAULT_PARTIAL_RATIO = 0.2;

/**
 * Compute display state from bumped_at timestamp.
 * @param {Date|string|number} bumpedAt
 * @returns {'active'|'stale'|'expired'|'terminated'}
 */
export function computeState(bumpedAt) {
  if (!bumpedAt) return 'terminated';
  const ts = typeof bumpedAt === 'string' || typeof bumpedAt === 'number'
    ? new Date(bumpedAt)
    : bumpedAt;
  const dayMs = 24 * 60 * 60 * 1000;
  const age = Date.now() - ts.getTime();
  if (age < STALENESS_THRESHOLDS.STALE_DAYS * dayMs) return 'active';
  if (age < STALENESS_THRESHOLDS.EXPIRED_DAYS * dayMs) return 'stale';
  if (age < STALENESS_THRESHOLDS.TERMINATED_DAYS * dayMs) return 'expired';
  return 'terminated';
}

/**
 * Calculate undercut amount for percent-markup items.
 * Formula: 2% × (markup - 100), floored at MIN_UNDERCUT.
 * @param {number} markup - Current best markup percentage (e.g. 150 = 150%)
 * @returns {number} Undercut amount in percentage points
 */
export function getPercentUndercutAmount(markup) {
  const base = Math.max(0, markup - 100);
  return Math.max(MIN_UNDERCUT, Math.round(UNDERCUT_PERCENT * base * 100) / 100);
}

/**
 * Calculate undercut amount for absolute-markup items (+PED).
 * Formula: 2% × markup, floored at MIN_UNDERCUT.
 * @param {number} markup - Current best markup in PED
 * @returns {number} Undercut amount in PED
 */
export function getAbsoluteUndercutAmount(markup) {
  return Math.max(MIN_UNDERCUT, Math.round(UNDERCUT_PERCENT * markup * 100) / 100);
}
