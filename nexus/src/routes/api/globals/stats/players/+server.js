// @ts-nocheck
/**
 * GET /api/globals/stats/players — Paginated ranked list of players by globals.
 * Public endpoint, no auth required.
 */
import { pool } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import { buildGlobalsFilter, chooseRollupGranularity, buildRollupPeriodFilter, VALUE_PED } from '../filter-utils.js';
import { getCachedPlayersPage1 } from '$lib/server/globals-cache.js';
import { isRollupReady } from '$lib/server/globals-rollup.js';

const DEFAULT_LIMIT = 50;
const MAX_LIMIT = 100;
const VALID_SORT_FIELDS = new Set(['count', 'value', 'avg', 'best']);
const AGG_PERIODS = new Set(['all', '7d', '30d', '90d', '1y']);
const AGG_SORT_COLS = { count: 'event_count', value: 'sum_value', avg: 'sum_value / NULLIF(event_count, 0)', best: 'max_value' };

export async function GET({ url, request }) {
  const { conditions, params, paramIdx: nextIdx, period, from, to } = buildGlobalsFilter(url);

  const sortParam = url.searchParams.get('sort');
  const sortBy = VALID_SORT_FIELDS.has(sortParam) ? sortParam : 'value';
  const pageNum = Math.max(1, parseInt(url.searchParams.get('page')) || 1);
  const limit = Math.min(Math.max(1, parseInt(url.searchParams.get('limit')) || DEFAULT_LIMIT), MAX_LIMIT);
  const offset = (pageNum - 1) * limit;

  // Fast path: serve from in-memory cache for unfiltered default request (page 1, sort by value)
  if (conditions.length === 1 && sortBy === 'value' && pageNum === 1) {
    const cached = getCachedPlayersPage1();
    if (cached) {
      const ifNoneMatch = request.headers.get('if-none-match');
      if (ifNoneMatch === cached.etag) {
        return new Response(null, { status: 304, headers: { 'ETag': cached.etag } });
      }
      return new Response(cached.json, {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'public, max-age=60',
          'ETag': cached.etag,
        },
      });
    }
  }

  // Pre-computed aggregate table: standard periods without type or incompatible filters
  const hasNoExtraFilters = !url.searchParams.get('player') && !url.searchParams.get('target')
    && !url.searchParams.get('location') && !url.searchParams.get('min_value')
    && !url.searchParams.get('hof') && !url.searchParams.get('type') && !url.searchParams.get('space') && !from && !to;
  if (hasNoExtraFilters && AGG_PERIODS.has(period)) {
    try {
      const aggSortCol = AGG_SORT_COLS[sortBy];
      const [dataResult, countResult] = await Promise.all([
        pool.query(
          `SELECT player_name AS player, event_count AS count, sum_value AS value,
                  sum_value / NULLIF(event_count, 0) AS avg_value,
                  max_value AS best_value, has_team, has_solo, has_profile
           FROM globals_player_agg
           WHERE period = $1
           ORDER BY ${aggSortCol} DESC
           LIMIT $2 OFFSET $3`,
          [period, limit, offset]
        ),
        pool.query(
          `SELECT count(*) AS total FROM globals_player_agg WHERE period = $1`,
          [period]
        ),
      ]);

      if (dataResult.rows.length > 0 || offset === 0) {
        const total = parseInt(countResult.rows[0].total);
        const pages = Math.max(1, Math.ceil(total / limit));

        return new Response(JSON.stringify({
          players: dataResult.rows.map(r => ({
            player: r.player,
            count: parseInt(r.count),
            value: parseFloat(r.value),
            avg_value: parseFloat(r.avg_value) || 0,
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
      }
      // Table empty (not yet populated) — fall through to rollup/raw
    } catch (e) {
      console.error('[api/globals/stats/players] Agg table error, falling back:', e);
    }
  }

  // Rollup fast path: period-filtered without incompatible filters
  const rollupGranularity = chooseRollupGranularity(period, from, to);
  const canUseRollup = rollupGranularity && isRollupReady()
    && !url.searchParams.get('player') && !url.searchParams.get('target')
    && !url.searchParams.get('location') && !url.searchParams.get('min_value')
    && !url.searchParams.get('hof') && !url.searchParams.get('space');

  if (canUseRollup) {
    try {
      const { periodWhere, periodParams } = buildRollupPeriodFilter(rollupGranularity, period, from, to, 2);
      const typeFilter = url.searchParams.get('type');
      const typeFilterArr = typeFilter
        ? typeFilter.split(',').map(t => t.trim()).filter(t => ['kill','team_kill','deposit','craft','rare_item','discovery','tier','examine','pvp'].includes(t))
        : null;
      const typeCond = typeFilterArr ? ` AND global_type = ANY($${periodParams.length + 2})` : '';
      const typeParams = typeFilterArr ? [typeFilterArr] : [];

      const baseParams = [rollupGranularity, ...periodParams, ...typeParams];

      const ROLLUP_SORT_COLS = { count: 'SUM(event_count)', value: 'SUM(sum_value)', avg: 'SUM(sum_value) / NULLIF(SUM(event_count), 0)', best: 'MAX(max_value)' };
      const rollupSortCol = ROLLUP_SORT_COLS[sortBy];
      const limitIdx = baseParams.length + 1;

      const [dataResult, countResult] = await Promise.all([
        pool.query(
          `SELECT player_name AS player, SUM(event_count) AS count, SUM(sum_value) AS value,
                  SUM(sum_value) / NULLIF(SUM(event_count), 0) AS avg_value,
                  MAX(max_value) AS best_value,
                  bool_or(global_type = 'team_kill') AS has_team,
                  bool_or(global_type != 'team_kill') AS has_solo,
                  EXISTS(SELECT 1 FROM users u WHERE lower(u.eu_name) = lower(player_name) AND u.verified = true) AS has_profile
           FROM globals_rollup_player
           WHERE granularity = $1${periodWhere}${typeCond}
           GROUP BY player_name
           ORDER BY ${rollupSortCol} DESC
           LIMIT $${limitIdx} OFFSET $${limitIdx + 1}`,
          [...baseParams, limit, offset]
        ),
        pool.query(
          `SELECT count(DISTINCT player_name) AS total
           FROM globals_rollup_player
           WHERE granularity = $1${periodWhere}${typeCond}`,
          baseParams
        ),
      ]);

      const total = parseInt(countResult.rows[0].total);
      const pages = Math.ceil(total / limit);

      return new Response(JSON.stringify({
        players: dataResult.rows.map(r => ({
          player: r.player,
          count: parseInt(r.count),
          value: parseFloat(r.value),
          avg_value: parseFloat(r.avg_value) || 0,
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
      console.error('[api/globals/stats/players] Rollup error, falling back to raw:', e);
    }
  }

  // Raw table path
  const whereClause = `WHERE ${conditions.join(' AND ')}`;
  const SORT_COLS = { count: 'count(*)', value: `COALESCE(sum(${VALUE_PED}), 0)`, avg: `COALESCE(avg(${VALUE_PED}), 0)`, best: `COALESCE(max(${VALUE_PED}), 0)` };
  const sortCol = SORT_COLS[sortBy];

  let paramIdx = nextIdx;
  const limitParams = [...params, limit, offset];

  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await client.query('SET LOCAL statement_timeout = 10000');

    const [dataResult, countResult] = await Promise.all([
      client.query(
        `SELECT player_name AS player, count(*) AS count, COALESCE(sum(${VALUE_PED}), 0) AS value,
                COALESCE(avg(${VALUE_PED}), 0) AS avg_value, COALESCE(max(${VALUE_PED}), 0) AS best_value,
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
      client.query(
        `SELECT count(DISTINCT player_name) AS total
         FROM ingested_globals
         ${whereClause}`,
        params
      ),
    ]);

    await client.query('COMMIT');

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
    await client.query('ROLLBACK').catch(() => {});
    if (e.message?.includes('statement timeout')) {
      console.warn('[api/globals/stats/players] Raw query timed out');
      return getResponse({ error: 'Query too complex, try a narrower filter' }, 503);
    }
    console.error('[api/globals/stats/players] Error:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  } finally {
    client.release();
  }
}
