// @ts-nocheck
/**
 * GET /api/globals/stats/targets — Paginated ranked list of targets by globals.
 * Public endpoint, no auth required.
 *
 * Unlike the main stats endpoint, this shows ALL target types (not just hunting)
 * unless a type filter is explicitly set.
 */
import { pool } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import { buildGlobalsFilter } from '../filter-utils.js';

const DEFAULT_LIMIT = 50;
const MAX_LIMIT = 100;
const VALID_SORT_FIELDS = new Set(['count', 'value', 'avg', 'best']);
const VALID_GROUP_FIELDS = new Set(['maturity', 'mob']);

/** Strip maturity suffix from a target name to get the base mob name. */
function extractMobName(targetName) {
  const parts = targetName.split(' ');
  if (parts.length < 2) return targetName;
  if (parts.length >= 3 && /^Gen$/i.test(parts[parts.length - 2])) {
    return parts.slice(0, -2).join(' ');
  }
  if (parts.length >= 4 && /^Gen$/i.test(parts[parts.length - 2]) && /^Elite$/i.test(parts[parts.length - 3])) {
    return parts.slice(0, -3).join(' ');
  }
  return parts.slice(0, -1).join(' ');
}

export async function GET({ url }) {
  const { conditions, params, paramIdx: nextIdx } = buildGlobalsFilter(url);

  // Exclude globals without a target name
  conditions.push('target_name IS NOT NULL');

  const whereClause = `WHERE ${conditions.join(' AND ')}`;

  const sortParam = url.searchParams.get('sort');
  const sortBy = VALID_SORT_FIELDS.has(sortParam) ? sortParam : 'count';
  const SORT_COLS = { count: 'count(*)', value: 'COALESCE(sum(value), 0)', avg: 'COALESCE(avg(value), 0)', best: 'COALESCE(max(value), 0)' };
  const sortCol = SORT_COLS[sortBy];

  const groupParam = url.searchParams.get('group');
  const groupByMob = VALID_GROUP_FIELDS.has(groupParam) ? groupParam === 'mob' : false;

  const groupByClause = groupByMob
    ? 'GROUP BY mob_id, CASE WHEN mob_id IS NULL THEN target_name END'
    : 'GROUP BY target_name, mob_id';
  const selectTarget = groupByMob ? 'min(target_name)' : 'target_name';

  const pageNum = Math.max(1, parseInt(url.searchParams.get('page')) || 1);
  const limit = Math.min(Math.max(1, parseInt(url.searchParams.get('limit')) || DEFAULT_LIMIT), MAX_LIMIT);
  const offset = (pageNum - 1) * limit;

  let paramIdx = nextIdx;
  const limitParams = [...params, limit, offset];

  try {
    const [dataResult, countResult] = await Promise.all([
      pool.query(
        `SELECT ${selectTarget} AS target, mob_id, count(*) AS count,
                COALESCE(sum(value), 0) AS value,
                COALESCE(avg(value), 0) AS avg_value, COALESCE(max(value), 0) AS best_value,
                mode() WITHIN GROUP (ORDER BY global_type) AS primary_type
         FROM ingested_globals
         ${whereClause}
         ${groupByClause}
         ORDER BY ${sortCol} DESC
         LIMIT $${paramIdx} OFFSET $${paramIdx + 1}`,
        limitParams
      ),
      pool.query(
        `SELECT count(*) AS total FROM (
           SELECT 1 FROM ingested_globals
           ${whereClause}
           ${groupByClause}
         ) sub`,
        params
      ),
    ]);

    const total = parseInt(countResult.rows[0].total);
    const pages = Math.ceil(total / limit);

    return new Response(JSON.stringify({
      targets: dataResult.rows.map(r => ({
        target: groupByMob && r.mob_id ? extractMobName(r.target) : r.target,
        mob_id: r.mob_id,
        count: parseInt(r.count),
        value: parseFloat(r.value),
        avg_value: parseFloat(r.avg_value),
        best_value: parseFloat(r.best_value),
        primary_type: r.primary_type,
      })),
      total,
      page: pageNum,
      pages,
    }), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'public, max-age=60',
      },
    });
  } catch (e) {
    console.error('[api/globals/stats/targets] Error:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
