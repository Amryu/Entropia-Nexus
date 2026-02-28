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
const VALID_SORT_FIELDS = new Set(['count', 'value']);

export async function GET({ url }) {
  const { conditions, params, paramIdx: nextIdx } = buildGlobalsFilter(url);

  // Exclude globals without a target name
  conditions.push('target_name IS NOT NULL');

  const whereClause = `WHERE ${conditions.join(' AND ')}`;

  const sortParam = url.searchParams.get('sort');
  const sortBy = VALID_SORT_FIELDS.has(sortParam) ? sortParam : 'count';
  const sortCol = sortBy === 'count' ? 'count(*)' : 'COALESCE(sum(value), 0)';

  const pageNum = Math.max(1, parseInt(url.searchParams.get('page')) || 1);
  const limit = Math.min(Math.max(1, parseInt(url.searchParams.get('limit')) || DEFAULT_LIMIT), MAX_LIMIT);
  const offset = (pageNum - 1) * limit;

  let paramIdx = nextIdx;
  const limitParams = [...params, limit, offset];

  try {
    const [dataResult, countResult] = await Promise.all([
      pool.query(
        `SELECT target_name AS target, mob_id, count(*) AS count,
                COALESCE(sum(value), 0) AS value,
                mode() WITHIN GROUP (ORDER BY global_type) AS primary_type
         FROM ingested_globals
         ${whereClause}
         GROUP BY target_name, mob_id
         ORDER BY ${sortCol} DESC
         LIMIT $${paramIdx} OFFSET $${paramIdx + 1}`,
        limitParams
      ),
      pool.query(
        `SELECT count(*) AS total FROM (
           SELECT 1 FROM ingested_globals
           ${whereClause}
           GROUP BY target_name, mob_id
         ) sub`,
        params
      ),
    ]);

    const total = parseInt(countResult.rows[0].total);
    const pages = Math.ceil(total / limit);

    return new Response(JSON.stringify({
      targets: dataResult.rows.map(r => ({
        target: r.target,
        mob_id: r.mob_id,
        count: parseInt(r.count),
        value: parseFloat(r.value),
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
