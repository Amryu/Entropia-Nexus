// @ts-nocheck
/**
 * GET /api/globals/stats/players — Paginated ranked list of players by globals.
 * Public endpoint, no auth required.
 */
import { pool } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import { buildGlobalsFilter } from '../filter-utils.js';

const DEFAULT_LIMIT = 50;
const MAX_LIMIT = 100;
const VALID_SORT_FIELDS = new Set(['count', 'value', 'avg', 'best']);

export async function GET({ url }) {
  const { conditions, params, paramIdx: nextIdx } = buildGlobalsFilter(url);
  const whereClause = `WHERE ${conditions.join(' AND ')}`;

  const sortParam = url.searchParams.get('sort');
  const sortBy = VALID_SORT_FIELDS.has(sortParam) ? sortParam : 'value';
  const SORT_COLS = { count: 'count(*)', value: 'COALESCE(sum(value), 0)', avg: 'COALESCE(avg(value), 0)', best: 'COALESCE(max(value), 0)' };
  const sortCol = SORT_COLS[sortBy];

  const pageNum = Math.max(1, parseInt(url.searchParams.get('page')) || 1);
  const limit = Math.min(Math.max(1, parseInt(url.searchParams.get('limit')) || DEFAULT_LIMIT), MAX_LIMIT);
  const offset = (pageNum - 1) * limit;

  let paramIdx = nextIdx;
  const limitParams = [...params, limit, offset];

  try {
    const [dataResult, countResult] = await Promise.all([
      pool.query(
        `SELECT player_name AS player, count(*) AS count, COALESCE(sum(value), 0) AS value,
                COALESCE(avg(value), 0) AS avg_value, COALESCE(max(value), 0) AS best_value,
                bool_or(global_type = 'team_kill') AS has_team,
                bool_or(global_type != 'team_kill') AS has_solo,
                EXISTS(SELECT 1 FROM users u WHERE lower(u.eu_name) = lower(player_name) AND u.verified = true) AS has_profile
         FROM ingested_globals
         ${whereClause}
         GROUP BY player_name
         ORDER BY ${sortCol} DESC
         LIMIT $${paramIdx} OFFSET $${paramIdx + 1}`,
        limitParams
      ),
      pool.query(
        `SELECT count(DISTINCT player_name) AS total
         FROM ingested_globals
         ${whereClause}`,
        params
      ),
    ]);

    const total = parseInt(countResult.rows[0].total);
    const pages = Math.ceil(total / limit);

    return new Response(JSON.stringify({
      players: dataResult.rows.map(r => ({
        player: r.player,
        count: parseInt(r.count),
        value: parseFloat(r.value),
        avg_value: parseFloat(r.avg_value),
        best_value: parseFloat(r.best_value),
        is_team: r.has_team && !r.has_solo,
        has_profile: r.has_profile,
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
    console.error('[api/globals/stats/players] Error:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
