// @ts-nocheck
/**
 * Shared filter-building utilities for globals stats endpoints.
 */

export const PERIOD_INTERVALS = {
  '24h': "interval '24 hours'",
  '7d': "interval '7 days'",
  '30d': "interval '30 days'",
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
 * @returns {{ conditions: string[], params: any[], paramIdx: number }}
 */
export function buildGlobalsFilter(url) {
  const conditions = ['confirmed = true'];
  const params = [];
  let paramIdx = 1;

  // Period
  const period = url.searchParams.get('period') || 'all';
  const intervalSql = PERIOD_INTERVALS[period];
  if (intervalSql) {
    conditions.push(`event_timestamp > now() - ${intervalSql}`);
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

  return { conditions, params, paramIdx };
}
