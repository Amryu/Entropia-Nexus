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
import { buildGlobalsFilter, chooseRollupGranularity, buildRollupPeriodFilter } from '../filter-utils.js';
import { getCachedTargetsPage1 } from '$lib/server/globals-cache.js';
import { isRollupReady } from '$lib/server/globals-rollup.js';

const DEFAULT_LIMIT = 50;
const MAX_LIMIT = 100;
const VALID_SORT_FIELDS = new Set(['count', 'value', 'avg', 'best']);
const VALID_GROUP_FIELDS = new Set(['maturity', 'mob']);
const AGG_PERIODS = new Set(['all', '7d', '30d', '90d', '1y']);
const AGG_SORT_COLS = { count: 'event_count', value: 'sum_value', avg: 'sum_value / NULLIF(event_count, 0)', best: 'max_value' };

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

export async function GET({ url, request }) {
  const { conditions, params, paramIdx: nextIdx, period, from, to } = buildGlobalsFilter(url);
  const isUnfiltered = conditions.length === 1; // only 'confirmed = true'

  const sortParam = url.searchParams.get('sort');
  const sortBy = VALID_SORT_FIELDS.has(sortParam) ? sortParam : 'count';

  const groupParam = url.searchParams.get('group');
  const groupByMob = VALID_GROUP_FIELDS.has(groupParam) ? groupParam === 'mob' : false;

  const pageNum = Math.max(1, parseInt(url.searchParams.get('page')) || 1);
  const limit = Math.min(Math.max(1, parseInt(url.searchParams.get('limit')) || DEFAULT_LIMIT), MAX_LIMIT);
  const offset = (pageNum - 1) * limit;

  // Fast path: serve from in-memory cache for unfiltered default request (page 1, sort by count, group by maturity)
  if (isUnfiltered && sortBy === 'count' && !groupByMob && pageNum === 1) {
    const cached = getCachedTargetsPage1();
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
    && !url.searchParams.get('hof') && !url.searchParams.get('type') && !from && !to;
  if (hasNoExtraFilters && AGG_PERIODS.has(period)) {
    try {
      const aggSortCol = groupByMob
        ? ({ count: 'SUM(event_count)', value: 'SUM(sum_value)', avg: 'SUM(sum_value) / NULLIF(SUM(event_count), 0)', best: 'MAX(max_value)' })[sortBy]
        : AGG_SORT_COLS[sortBy];

      const [dataResult, countResult] = groupByMob
        ? await Promise.all([
            pool.query(
              `SELECT min(target_name) AS target, mob_id,
                      SUM(event_count) AS count, SUM(sum_value) AS value,
                      SUM(sum_value) / NULLIF(SUM(event_count), 0) AS avg_value,
                      MAX(max_value) AS best_value,
                      (array_agg(primary_type ORDER BY event_count DESC))[1] AS primary_type
               FROM globals_target_agg
               WHERE period = $1
               GROUP BY mob_id, CASE WHEN mob_id IS NULL THEN target_name END
               ORDER BY ${aggSortCol} DESC
               LIMIT $2 OFFSET $3`,
              [period, limit, offset]
            ),
            pool.query(
              `SELECT count(*) AS total FROM (
                 SELECT 1 FROM globals_target_agg WHERE period = $1
                 GROUP BY mob_id, CASE WHEN mob_id IS NULL THEN target_name END
               ) sub`,
              [period]
            ),
          ])
        : await Promise.all([
            pool.query(
              `SELECT target_name AS target, mob_id, event_count AS count, sum_value AS value,
                      sum_value / NULLIF(event_count, 0) AS avg_value,
                      max_value AS best_value, primary_type
               FROM globals_target_agg
               WHERE period = $1
               ORDER BY ${aggSortCol} DESC
               LIMIT $2 OFFSET $3`,
              [period, limit, offset]
            ),
            pool.query(
              `SELECT count(*) AS total FROM globals_target_agg WHERE period = $1`,
              [period]
            ),
          ]);

      if (dataResult.rows.length > 0 || offset === 0) {
        const total = parseInt(countResult.rows[0].total);
        const pages = Math.max(1, Math.ceil(total / limit));

        return new Response(JSON.stringify({
          targets: dataResult.rows.map(r => ({
            target: groupByMob && r.mob_id ? extractMobName(r.target) : r.target,
            mob_id: r.mob_id,
            count: parseInt(r.count),
            value: parseFloat(r.value),
            avg_value: parseFloat(r.avg_value) || 0,
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
      }
      // Table empty (not yet populated) — fall through
    } catch (e) {
      console.error('[api/globals/stats/targets] Agg table error, falling back:', e);
    }
  }

  // Rollup fast path: period-filtered without incompatible filters
  const rollupGranularity = chooseRollupGranularity(period, from, to);
  const canUseRollup = rollupGranularity && isRollupReady()
    && !url.searchParams.get('player') && !url.searchParams.get('target')
    && !url.searchParams.get('location') && !url.searchParams.get('min_value')
    && !url.searchParams.get('hof');

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

      const rollupGroupBy = groupByMob
        ? 'GROUP BY mob_id, CASE WHEN mob_id IS NULL THEN target_name END'
        : 'GROUP BY target_name';
      const rollupSelectTarget = groupByMob ? 'min(target_name)' : 'target_name';
      const rollupSelectMobId = groupByMob ? 'mob_id' : 'MAX(mob_id) AS mob_id';

      const [dataResult, countResult] = await Promise.all([
        pool.query(
          `SELECT ${rollupSelectTarget} AS target, ${rollupSelectMobId},
                  SUM(event_count) AS count, SUM(sum_value) AS value,
                  SUM(sum_value) / NULLIF(SUM(event_count), 0) AS avg_value,
                  MAX(max_value) AS best_value,
                  (SELECT global_type FROM globals_rollup_target r2
                   WHERE r2.granularity = $1${periodWhere}
                     AND r2.target_name = globals_rollup_target.target_name
                   GROUP BY global_type ORDER BY SUM(event_count) DESC LIMIT 1
                  ) AS primary_type
           FROM globals_rollup_target
           WHERE granularity = $1${periodWhere}${typeCond}
           ${rollupGroupBy}
           ORDER BY ${rollupSortCol} DESC
           LIMIT $${limitIdx} OFFSET $${limitIdx + 1}`,
          [...baseParams, limit, offset]
        ),
        pool.query(
          `SELECT count(*) AS total FROM (
             SELECT 1 FROM globals_rollup_target
             WHERE granularity = $1${periodWhere}${typeCond}
             ${rollupGroupBy}
           ) sub`,
          baseParams
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
          avg_value: parseFloat(r.avg_value) || 0,
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
      console.error('[api/globals/stats/targets] Rollup error, falling back to raw:', e);
    }
  }

  // Raw table path
  // Exclude globals without a target name
  conditions.push('target_name IS NOT NULL');

  const whereClause = `WHERE ${conditions.join(' AND ')}`;

  const SORT_COLS = { count: 'count(*)', value: 'COALESCE(sum(value), 0)', avg: 'COALESCE(avg(value), 0)', best: 'COALESCE(max(value), 0)' };
  const sortCol = SORT_COLS[sortBy];

  const groupByClause = groupByMob
    ? 'GROUP BY mob_id, CASE WHEN mob_id IS NULL THEN target_name END'
    : 'GROUP BY target_name, mob_id';
  const selectTarget = groupByMob ? 'min(target_name)' : 'target_name';

  let paramIdx = nextIdx;
  const limitParams = [...params, limit, offset];

  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await client.query('SET LOCAL statement_timeout = 10000');

    const [dataResult, countResult] = await Promise.all([
      client.query(
        `SELECT ${selectTarget} AS target, mob_id, count(*) AS count,
                COALESCE(sum(value), 0) AS value,
                COALESCE(avg(value), 0) AS avg_value, COALESCE(max(value), 0) AS best_value,
                MIN(global_type) AS primary_type
         FROM ingested_globals
         ${whereClause}
         ${groupByClause}
         ORDER BY ${sortCol} DESC
         LIMIT $${paramIdx} OFFSET $${paramIdx + 1}`,
        limitParams
      ),
      client.query(
        `SELECT count(*) AS total FROM (
           SELECT 1 FROM ingested_globals
           ${whereClause}
           ${groupByClause}
         ) sub`,
        params
      ),
    ]);

    await client.query('COMMIT');

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
    await client.query('ROLLBACK').catch(() => {});
    if (e.message?.includes('statement timeout')) {
      console.warn('[api/globals/stats/targets] Raw query timed out');
      return getResponse({ error: 'Query too complex, try a narrower filter' }, 503);
    }
    console.error('[api/globals/stats/targets] Error:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  } finally {
    client.release();
  }
}
