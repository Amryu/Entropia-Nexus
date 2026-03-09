// @ts-nocheck
/**
 * Shared filter-building utilities for globals stats endpoints.
 */

export const PERIOD_INTERVALS = {
  '24h': "interval '24 hours'",
  '7d': "interval '7 days'",
  '30d': "interval '30 days'",
  '90d': "interval '90 days'",
  '1y': "interval '1 year'",
};

export const VALID_GLOBAL_TYPES = new Set([
  'kill', 'team_kill', 'deposit', 'craft', 'rare_item',
  'discovery', 'tier', 'examine', 'pvp',
]);

export function escapeLike(str) {
  return str.replace(/[%_\\]/g, '\\$&');
}

/**
 * Parse common globals filter query params and build WHERE conditions.
 * Supports both preset periods and custom date ranges (from/to).
 * @returns {{ conditions: string[], params: any[], paramIdx: number, period: string, from: string|null, to: string|null }}
 */
export function buildGlobalsFilter(url) {
  const conditions = ['confirmed = true'];
  const params = [];
  let paramIdx = 1;

  // Custom date range (takes precedence over period presets)
  const from = url.searchParams.get('from');
  const to = url.searchParams.get('to');
  const period = url.searchParams.get('period') || 'all';

  if (from && to && isValidDate(from) && isValidDate(to)) {
    conditions.push(`event_timestamp >= $${paramIdx}`);
    params.push(new Date(from));
    paramIdx++;
    // to is end of day inclusive
    conditions.push(`event_timestamp < $${paramIdx}`);
    params.push(new Date(to + 'T23:59:59.999Z'));
    paramIdx++;
  } else {
    const intervalSql = PERIOD_INTERVALS[period];
    if (intervalSql) {
      conditions.push(`event_timestamp > now() - ${intervalSql}`);
    }
  }

  // Player
  const playerFilter = url.searchParams.get('player');
  if (playerFilter) {
    conditions.push(`player_name ILIKE $${paramIdx}`);
    params.push(`%${escapeLike(playerFilter)}%`);
    paramIdx++;
  }

  // Type
  const typeFilter = url.searchParams.get('type');
  if (typeFilter) {
    const types = typeFilter.split(',').map(t => t.trim()).filter(t => VALID_GLOBAL_TYPES.has(t));
    if (types.length > 0) {
      conditions.push(`global_type = ANY($${paramIdx})`);
      params.push(types);
      paramIdx++;
    }
  }

  // Target
  const targetFilter = url.searchParams.get('target');
  if (targetFilter) {
    conditions.push(`target_name ILIKE $${paramIdx}`);
    params.push(`%${escapeLike(targetFilter)}%`);
    paramIdx++;
  }

  // Location
  const locationFilter = url.searchParams.get('location');
  if (locationFilter) {
    conditions.push(`location = $${paramIdx}`);
    params.push(locationFilter);
    paramIdx++;
  }

  // Min value
  const minValueParam = url.searchParams.get('min_value');
  if (minValueParam) {
    const minVal = parseFloat(minValueParam);
    if (!isNaN(minVal) && minVal > 0) {
      conditions.push(`value >= $${paramIdx}`);
      params.push(minVal);
      paramIdx++;
    }
  }

  // HoF only
  if (url.searchParams.get('hof') === 'true') {
    conditions.push('is_hof = true');
  }

  return { conditions, params, paramIdx, period, from: from || null, to: to || null };
}

/**
 * Determine the appropriate date_trunc bucket unit based on period/date range.
 * Returns a PostgreSQL date_trunc unit string and a Chart.js time unit.
 */
export function getActivityBucket(period, from, to) {
  if (from && to) {
    const diffMs = new Date(to).getTime() - new Date(from).getTime();
    const diffDays = diffMs / (1000 * 60 * 60 * 24);
    if (diffDays <= 2) return { sqlUnit: 'hour', chartUnit: 'hour' };
    if (diffDays <= 90) return { sqlUnit: 'day', chartUnit: 'day' };
    if (diffDays <= 365) return { sqlUnit: 'week', chartUnit: 'week' };
    return { sqlUnit: 'month', chartUnit: 'month' };
  }
  switch (period) {
    case '24h': return { sqlUnit: 'hour', chartUnit: 'hour' };
    case '7d':
    case '30d': return { sqlUnit: 'day', chartUnit: 'day' };
    case '90d': return { sqlUnit: 'week', chartUnit: 'week' };
    case '1y': return { sqlUnit: 'week', chartUnit: 'week' };
    default: return { sqlUnit: 'month', chartUnit: 'month' };
  }
}

/**
 * Fill gaps in activity data so zero-count buckets are explicit.
 * @param {Array<{bucket: string, count: number}>} rows - Activity data from DB
 * @param {string} sqlUnit - The date_trunc unit used ('hour', 'day', 'week', 'month')
 * @param {string|null} from - Custom range start (ISO date string)
 * @param {string|null} to - Custom range end (ISO date string)
 * @param {string} period - Period preset
 * @returns {Array<{bucket: string, count: number}>}
 */
export function fillActivityGaps(rows, sqlUnit, from, to, period) {
  if (!rows || rows.length === 0) return rows;

  // Determine the range boundaries
  let rangeStart, rangeEnd;
  if (from && to) {
    rangeStart = new Date(from);
    rangeEnd = new Date(to + 'T23:59:59.999Z');
  } else if (PERIOD_INTERVALS[period]) {
    rangeEnd = new Date();
    const ms = periodToMs(period);
    rangeStart = new Date(rangeEnd.getTime() - ms);
  } else {
    // 'all' - use the data range
    rangeStart = new Date(rows[0].bucket);
    rangeEnd = new Date(rows[rows.length - 1].bucket);
  }

  // Build a map of existing buckets (supports optional value field for dual-series)
  const bucketMap = new Map();
  for (const row of rows) {
    const key = truncateDate(new Date(row.bucket), sqlUnit).toISOString();
    const existing = bucketMap.get(key) || { count: 0, value: 0 };
    existing.count += row.count;
    existing.value += (row.value || 0);
    bucketMap.set(key, existing);
  }

  // Generate all buckets in the range
  const result = [];
  let current = truncateDate(rangeStart, sqlUnit);
  const end = truncateDate(rangeEnd, sqlUnit);

  const maxBuckets = 2555;
  let i = 0;
  while (current <= end && i < maxBuckets) {
    const key = current.toISOString();
    const entry = bucketMap.get(key) || { count: 0, value: 0 };
    result.push({ bucket: key, count: entry.count, value: entry.value });
    current = advanceBucket(current, sqlUnit);
    i++;
  }

  return result;
}

function isValidDate(str) {
  if (!str || typeof str !== 'string') return false;
  const d = new Date(str);
  return !isNaN(d.getTime());
}

function periodToMs(period) {
  const hours = {
    '24h': 24,
    '7d': 7 * 24,
    '30d': 30 * 24,
    '90d': 90 * 24,
    '1y': 365 * 24,
  };
  return (hours[period] || 30 * 24) * 60 * 60 * 1000;
}

function truncateDate(date, unit) {
  const d = new Date(date);
  switch (unit) {
    case 'hour':
      d.setMinutes(0, 0, 0);
      return d;
    case 'day':
      d.setHours(0, 0, 0, 0);
      return d;
    case 'week': {
      d.setHours(0, 0, 0, 0);
      const day = d.getDay();
      d.setDate(d.getDate() - ((day + 6) % 7)); // Monday-based
      return d;
    }
    case 'month':
      d.setHours(0, 0, 0, 0);
      d.setDate(1);
      return d;
    default:
      return d;
  }
}

/**
 * Choose the best rollup granularity for a given period/date range.
 * Returns null if the raw table should be queried (e.g. 24h needs hourly).
 */
export function chooseRollupGranularity(period, from, to) {
  if (from && to) {
    const diffMs = new Date(to).getTime() - new Date(from).getTime();
    const diffDays = diffMs / (1000 * 60 * 60 * 24);
    if (diffDays <= 2) return null;
    if (diffDays <= 90) return 'daily';
    if (diffDays <= 365) return 'weekly';
    return 'monthly';
  }
  switch (period) {
    case '24h': return null;
    case '7d':
    case '30d': return 'daily';
    case '90d':
    case '1y': return 'weekly';
    case 'all': return 'monthly';
    default: return null;
  }
}

/**
 * Build a period_start range condition for rollup queries.
 * Returns { periodWhere, periodParams, nextIdx } or null if no period filter.
 */
export function buildRollupPeriodFilter(granularity, period, from, to, startIdx = 2) {
  let periodWhere = '';
  const periodParams = [];
  let nextIdx = startIdx;

  if (from && to) {
    periodWhere = ` AND period_start >= $${nextIdx} AND period_start < $${nextIdx + 1}`;
    periodParams.push(new Date(from), new Date(to + 'T23:59:59.999Z'));
    nextIdx += 2;
  } else {
    const intervalSql = PERIOD_INTERVALS[period];
    if (intervalSql) {
      periodWhere = ` AND period_start >= date_trunc('day', now() - ${intervalSql})`;
    }
    // 'all' → no period filter needed
  }

  return { periodWhere, periodParams, nextIdx };
}

function advanceBucket(date, unit) {
  const d = new Date(date);
  switch (unit) {
    case 'hour':
      d.setHours(d.getHours() + 1);
      return d;
    case 'day':
      d.setDate(d.getDate() + 1);
      return d;
    case 'week':
      d.setDate(d.getDate() + 7);
      return d;
    case 'month':
      d.setMonth(d.getMonth() + 1);
      return d;
    default:
      return d;
  }
}
