// @ts-nocheck
/**
 * GET /api/globals/target/[name]/leaderboard — Paginated player leaderboard for a target.
 * Public endpoint, no auth required.
 *
 * Query params:
 *   sort       — 'count' | 'value' | 'best' (default: 'value')
 *   page       — page number (default: 1)
 *   maturities — comma-separated target names to filter by specific maturities
 *   period     — time period filter
 *   from, to   — custom date range
 */
import { pool } from '$lib/server/db.js';
import { getResponse, decodeURIComponentSafe } from '$lib/util.js';
import { PERIOD_INTERVALS } from '../../../stats/filter-utils.js';

const PAGE_SIZE = 20;
const VALID_SORTS = { count: 'count', value: 'total_value', best: 'best_value' };

export async function GET({ params, url }) {
  const targetName = decodeURIComponentSafe(params.name);

  if (!targetName || targetName.length > 300) {
    return getResponse({ error: 'Invalid target name' }, 400);
  }

  const sort = VALID_SORTS[url.searchParams.get('sort')] || 'total_value';
  const page = Math.max(1, Math.min(parseInt(url.searchParams.get('page')) || 1, 1000));

  // Maturity filter
  const maturityParam = url.searchParams.get('maturities');
  const maturityFilter = maturityParam
    ? maturityParam.split(',').map(m => m.trim()).filter(Boolean).slice(0, 50)
    : null;

  // Period filter
  const period = url.searchParams.get('period') || 'all';
  const from = url.searchParams.get('from');
  const to = url.searchParams.get('to');

  // Resolve mob: find all maturity target names sharing the same mob_id
  let resolvedTargets = null;
  if (!maturityFilter) {
    const mobLookup = await pool.query(
      `SELECT DISTINCT lower(target_name) AS name FROM ingested_globals
       WHERE confirmed = true AND mob_id IS NOT NULL
         AND mob_id = (
           SELECT mob_id FROM ingested_globals
           WHERE confirmed = true AND mob_id IS NOT NULL
             AND (lower(target_name) = lower($1) OR lower(target_name) LIKE lower($1) || ' %')
           LIMIT 1
         )`,
      [targetName]
    );
    if (mobLookup.rows.length > 0) {
      resolvedTargets = mobLookup.rows.map(r => r.name);
    }
  }

  // Build target condition
  let targetCond;
  let queryParams;
  if (maturityFilter && maturityFilter.length > 0) {
    targetCond = 'lower(target_name) = ANY($1)';
    queryParams = [maturityFilter.map(m => m.toLowerCase())];
  } else if (resolvedTargets) {
    targetCond = 'lower(target_name) = ANY($1)';
    queryParams = [resolvedTargets];
  } else {
    targetCond = 'lower(target_name) = lower($1)';
    queryParams = [targetName];
  }

  // Period condition
  let periodCond = '';
  if (from && to) {
    periodCond = ` AND event_timestamp >= $2 AND event_timestamp < $3`;
    queryParams.push(new Date(from), new Date(to + 'T23:59:59.999Z'));
  } else {
    const intervalSql = PERIOD_INTERVALS[period];
    if (intervalSql) {
      periodCond = ` AND event_timestamp > now() - ${intervalSql}`;
    }
  }

  const offset = (page - 1) * PAGE_SIZE;
  const nextParam = queryParams.length + 1;

  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await client.query('SET LOCAL statement_timeout = 10000');

    const [dataResult, countResult] = await Promise.all([
      client.query(
        `SELECT player_name AS player, count(*) AS count,
                COALESCE(sum(value), 0) AS total_value,
                COALESCE(max(value), 0) AS best_value,
                bool_or(global_type = 'team_kill') AS has_team,
                bool_or(global_type != 'team_kill') AS has_solo
         FROM ingested_globals
         WHERE confirmed = true AND ${targetCond}${periodCond}
         GROUP BY player_name
         ORDER BY ${sort} DESC
         LIMIT ${PAGE_SIZE} OFFSET $${nextParam}`,
        [...queryParams, offset]
      ),
      client.query(
        `SELECT count(DISTINCT player_name) AS total
         FROM ingested_globals
         WHERE confirmed = true AND ${targetCond}${periodCond}`,
        queryParams
      ),
    ]);

    await client.query('COMMIT');

    const total = parseInt(countResult.rows[0].total);

    return new Response(JSON.stringify({
      players: dataResult.rows.map(r => ({
        player: r.player,
        count: parseInt(r.count),
        value: parseFloat(r.total_value),
        best_value: parseFloat(r.best_value),
        is_team: r.has_team && !r.has_solo,
      })),
      page,
      pages: Math.max(1, Math.ceil(total / PAGE_SIZE)),
      total,
    }), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'public, max-age=60',
      },
    });
  } catch (e) {
    await client.query('ROLLBACK').catch(() => {});
    if (e.message?.includes('statement timeout')) {
      console.warn('[api/globals/target/leaderboard] Query timed out for:', targetName);
      return getResponse({ error: 'Query too complex, try a narrower filter' }, 503);
    }
    console.error('[api/globals/target/leaderboard] Error:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  } finally {
    client.release();
  }
}
