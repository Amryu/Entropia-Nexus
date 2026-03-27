// @ts-nocheck
/**
 * GET /api/globals/stats — Aggregated global event statistics.
 * Public endpoint, no auth required.
 */
import { pool } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import { buildGlobalsFilter, getActivityBucket, fillActivityGaps, chooseRollupGranularity, buildRollupPeriodFilter, VALUE_PED } from './filter-utils.js';
import { getCachedStats } from '$lib/server/globals-cache.js';
import { isRollupReady } from '$lib/server/globals-rollup.js';

const MAX_ACTIVITY_BUCKETS = 2555;
const VALID_SORT_FIELDS = new Set(['count', 'value']);
const VALID_GROUP_FIELDS = new Set(['maturity', 'mob']);
const AGG_PERIODS = new Set(['all', '7d', '30d', '90d', '1y']);

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
  const { conditions, params, period, from, to } = buildGlobalsFilter(url);

  // Sort params for top players/targets charts
  const playersSortParam = url.searchParams.get('players_sort');
  const playersSortBy = VALID_SORT_FIELDS.has(playersSortParam) ? playersSortParam : 'value';
  const playersSortCol = playersSortBy === 'count' ? 'count(*)' : `COALESCE(sum(${VALUE_PED}), 0)`;

  const targetsSortParam = url.searchParams.get('targets_sort');
  const targetsSortBy = VALID_SORT_FIELDS.has(targetsSortParam) ? targetsSortParam : 'count';
  const targetsSortCol = targetsSortBy === 'count' ? 'count(*)' : `COALESCE(sum(${VALUE_PED}), 0)`;

  const targetsGroupParam = url.searchParams.get('targets_group');
  const targetsGroupBy = VALID_GROUP_FIELDS.has(targetsGroupParam) ? targetsGroupParam : 'maturity';
  const groupByMob = targetsGroupBy === 'mob';

  // Fast path: serve from in-memory cache for unfiltered default request
  const isDefault = conditions.length === 1 && playersSortBy === 'value'
    && targetsSortBy === 'count' && !groupByMob;
  if (isDefault) {
    const cached = getCachedStats();
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

  const { sqlUnit: bucketUnit, chartUnit } = getActivityBucket(period, from, to);

  // Rollup fast path: period-filtered requests without incompatible filters
  const rollupGranularity = chooseRollupGranularity(period, from, to);
  const playerFilter = url.searchParams.get('player');
  const targetFilter = url.searchParams.get('target');
  const locationFilter = url.searchParams.get('location');
  const minValueFilter = url.searchParams.get('min_value');
  const hofFilter = url.searchParams.get('hof');
  const typeFilter = url.searchParams.get('type');
  const canUseRollup = rollupGranularity && isRollupReady()
    && !playerFilter && !targetFilter && !locationFilter && !minValueFilter && !hofFilter;

  if (canUseRollup) {
    try {
      const { periodWhere, periodParams } = buildRollupPeriodFilter(rollupGranularity, period, from, to, 2);
      const typeFilterArr = typeFilter
        ? typeFilter.split(',').map(t => t.trim()).filter(t => ['kill','team_kill','deposit','craft','rare_item','discovery','tier','examine','pvp'].includes(t))
        : null;
      const typeCond = typeFilterArr ? ` AND global_type = ANY($${periodParams.length + 2})` : '';
      const typeParams = typeFilterArr ? [typeFilterArr] : [];

      const baseParams = [rollupGranularity, ...periodParams, ...typeParams];

      // Use pre-computed agg tables for top players/targets when no type filter and standard period
      const useAggTables = !typeFilterArr && AGG_PERIODS.has(period) && !from && !to;

      const playersSortAgg = playersSortBy === 'count' ? 'event_count' : 'sum_value';
      const targetsSortAgg = targetsSortBy === 'count' ? 'event_count' : 'sum_value';

      // Space mining filter condition for rollup_target
      const spaceFilter = url.searchParams.get('space');
      const smPeriodParams = [rollupGranularity, ...periodParams];

      const [summaryResult, byTypeResult, topPlayersResult, topTargetsResult, activityResult, spaceMiningResult] = await Promise.all([
        // Summary
        pool.query(
          `SELECT SUM(event_count) AS total_count,
                  SUM(sum_value) AS total_value,
                  SUM(sum_value) / NULLIF(SUM(event_count), 0) AS avg_value,
                  MAX(max_value) AS max_value,
                  SUM(hof_count) AS hof_count,
                  SUM(ath_count) AS ath_count,
                  SUM(event_count) FILTER (WHERE global_type IN ('kill', 'team_kill', 'examine')) AS hunting_count,
                  SUM(sum_value) FILTER (WHERE global_type IN ('kill', 'team_kill', 'examine')) AS hunting_value,
                  SUM(event_count) FILTER (WHERE global_type = 'deposit') AS mining_count,
                  SUM(sum_value) FILTER (WHERE global_type = 'deposit') AS mining_value,
                  SUM(event_count) FILTER (WHERE global_type = 'craft') AS crafting_count,
                  SUM(sum_value) FILTER (WHERE global_type = 'craft') AS crafting_value
           FROM globals_rollup
           WHERE granularity = $1${periodWhere}${typeCond}`,
          baseParams
        ),
        // By type
        pool.query(
          `SELECT global_type AS type, SUM(event_count) AS count, SUM(sum_value) AS value
           FROM globals_rollup
           WHERE granularity = $1${periodWhere}${typeCond}
           GROUP BY global_type
           ORDER BY SUM(event_count) DESC`,
          baseParams
        ),
        // Top players (from agg table or rollup)
        useAggTables
          ? pool.query(
              `SELECT player_name AS player, event_count AS count, sum_value AS value,
                      has_team, has_solo
               FROM globals_player_agg
               WHERE period = $1
               ORDER BY ${playersSortAgg} DESC
               LIMIT 10`,
              [period]
            )
          : pool.query(
              `SELECT player_name AS player, SUM(event_count) AS count, SUM(sum_value) AS value,
                      bool_or(global_type = 'team_kill') AS has_team,
                      bool_or(global_type != 'team_kill') AS has_solo
               FROM globals_rollup_player
               WHERE granularity = $1${periodWhere}${typeCond}
               GROUP BY player_name
               ORDER BY ${playersSortBy === 'count' ? 'SUM(event_count)' : 'SUM(sum_value)'} DESC
               LIMIT 10`,
              baseParams
            ),
        // Top targets (from agg table or rollup, respects type filter)
        useAggTables
          ? pool.query(
              groupByMob
                ? `SELECT min(target_name) AS target, mob_id, SUM(event_count) AS count, SUM(sum_value) AS value
                   FROM globals_target_agg
                   WHERE period = $1
                   GROUP BY mob_id, CASE WHEN mob_id IS NULL THEN target_name END
                   ORDER BY ${targetsSortAgg === 'event_count' ? 'SUM(event_count)' : 'SUM(sum_value)'} DESC
                   LIMIT 10`
                : `SELECT target_name AS target, mob_id, event_count AS count, sum_value AS value
                   FROM globals_target_agg
                   WHERE period = $1
                   ORDER BY ${targetsSortAgg} DESC
                   LIMIT 10`,
              [period]
            )
          : pool.query(
              groupByMob
                ? `SELECT min(target_name) AS target, mob_id, SUM(event_count) AS count, SUM(sum_value) AS value
                   FROM globals_rollup_target
                   WHERE granularity = $1${periodWhere}${typeCond}
                   GROUP BY mob_id, CASE WHEN mob_id IS NULL THEN target_name END
                   ORDER BY ${targetsSortBy === 'count' ? 'SUM(event_count)' : 'SUM(sum_value)'} DESC
                   LIMIT 10`
                : `SELECT target_name AS target, MAX(mob_id) AS mob_id, SUM(event_count) AS count, SUM(sum_value) AS value
                   FROM globals_rollup_target
                   WHERE granularity = $1${periodWhere}${typeCond}
                   GROUP BY target_name
                   ORDER BY ${targetsSortBy === 'count' ? 'SUM(event_count)' : 'SUM(sum_value)'} DESC
                   LIMIT 10`,
              baseParams
            ),
        // Activity timeline
        pool.query(
          `SELECT period_start AS bucket, SUM(event_count) AS count,
                  COALESCE(SUM(sum_value), 0) AS total_value
           FROM globals_rollup
           WHERE granularity = $1${periodWhere}${typeCond}
           GROUP BY period_start
           ORDER BY period_start
           LIMIT ${MAX_ACTIVITY_BUCKETS}`,
          baseParams
        ),
        // Space mining stats from rollup_target (has target_name)
        pool.query(
          `SELECT COALESCE(SUM(event_count), 0) AS count,
                  COALESCE(SUM(sum_value), 0) AS value
           FROM globals_rollup_target
           WHERE granularity = $1${periodWhere} AND global_type = 'deposit' AND target_name ~* 'asteroid'`,
          smPeriodParams
        ),
      ]);

      const summary = summaryResult.rows[0];
      const smRow = spaceMiningResult.rows[0];
      const smCount = parseInt(smRow?.count) || 0;
      const smValue = parseFloat(smRow?.value) || 0;

      return new Response(JSON.stringify({
        summary: {
          total_count: parseInt(summary.total_count) || 0,
          total_value: parseFloat(summary.total_value) || 0,
          avg_value: parseFloat(summary.avg_value) || 0,
          max_value: parseFloat(summary.max_value) || 0,
          hof_count: parseInt(summary.hof_count) || 0,
          ath_count: parseInt(summary.ath_count) || 0,
          hunting: { count: parseInt(summary.hunting_count) || 0, value: parseFloat(summary.hunting_value) || 0 },
          mining: { count: (parseInt(summary.mining_count) || 0) - smCount, value: (parseFloat(summary.mining_value) || 0) - smValue },
          space_mining: { count: smCount, value: smValue },
          crafting: { count: parseInt(summary.crafting_count) || 0, value: parseFloat(summary.crafting_value) || 0 },
        },
        by_type: byTypeResult.rows.map(r => ({
          type: r.type,
          count: parseInt(r.count),
          value: parseFloat(r.value),
        })),
        top_players: topPlayersResult.rows.map(r => ({
          player: r.player,
          count: parseInt(r.count),
          value: parseFloat(r.value),
          is_team: r.has_team && !r.has_solo,
        })),
        top_targets: topTargetsResult.rows.map(r => ({
          target: groupByMob && r.mob_id ? extractMobName(r.target) : r.target,
          mob_id: r.mob_id,
          count: parseInt(r.count),
          value: parseFloat(r.value),
        })),
        bucket_unit: chartUnit,
        activity: fillActivityGaps(
          activityResult.rows.map(r => ({ bucket: new Date(r.bucket).toISOString(), count: parseInt(r.count), value: parseFloat(r.total_value || 0) })),
          bucketUnit, from, to, period
        ),
      }), {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'public, max-age=60',
        },
      });
    } catch (e) {
      console.error('[api/globals/stats] Rollup query error, falling back to raw:', e);
      // Fall through to raw table query
    }
  }

  const whereClause = `WHERE ${conditions.join(' AND ')}`;

  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await client.query('SET LOCAL statement_timeout = 10000');

    const [summaryResult, byTypeResult, topPlayersResult, topTargetsResult, activityResult] = await Promise.all([
      // Summary
      client.query(
        `SELECT count(*) AS total_count,
                COALESCE(sum(${VALUE_PED}), 0) AS total_value,
                COALESCE(avg(${VALUE_PED}), 0) AS avg_value,
                COALESCE(max(${VALUE_PED}), 0) AS max_value,
                count(*) FILTER (WHERE is_hof) AS hof_count,
                count(*) FILTER (WHERE is_ath) AS ath_count,
                count(*) FILTER (WHERE global_type IN ('kill', 'team_kill', 'examine')) AS hunting_count,
                COALESCE(sum(${VALUE_PED}) FILTER (WHERE global_type IN ('kill', 'team_kill', 'examine')), 0) AS hunting_value,
                count(*) FILTER (WHERE global_type = 'deposit') AS mining_count,
                COALESCE(sum(${VALUE_PED}) FILTER (WHERE global_type = 'deposit'), 0) AS mining_value,
                count(*) FILTER (WHERE global_type = 'deposit' AND target_name ~* 'asteroid') AS space_mining_count,
                COALESCE(sum(${VALUE_PED}) FILTER (WHERE global_type = 'deposit' AND target_name ~* 'asteroid'), 0) AS space_mining_value,
                count(*) FILTER (WHERE global_type = 'craft') AS crafting_count,
                COALESCE(sum(${VALUE_PED}) FILTER (WHERE global_type = 'craft'), 0) AS crafting_value
         FROM ingested_globals
         ${whereClause}`,
        params
      ),

      // By type
      client.query(
        `SELECT global_type AS type, count(*) AS count, COALESCE(sum(${VALUE_PED}), 0) AS value
         FROM ingested_globals
         ${whereClause}
         GROUP BY global_type
         ORDER BY count DESC`,
        params
      ),

      // Top players
      client.query(
        `SELECT player_name AS player, count(*) AS count, COALESCE(sum(${VALUE_PED}), 0) AS value,
                bool_or(global_type = 'team_kill') AS has_team,
                bool_or(global_type != 'team_kill') AS has_solo
         FROM ingested_globals
         ${whereClause}
         GROUP BY player_name
         ORDER BY ${playersSortCol} DESC
         LIMIT 10`,
        params
      ),

      // Top targets (respects type filter)
      client.query(
        groupByMob
          ? `SELECT min(target_name) AS target, mob_id, count(*) AS count, COALESCE(sum(${VALUE_PED}), 0) AS value
             FROM ingested_globals
             ${whereClause}
             GROUP BY mob_id, CASE WHEN mob_id IS NULL THEN target_name END
             ORDER BY ${targetsSortCol} DESC
             LIMIT 10`
          : `SELECT target_name AS target, mob_id, count(*) AS count, COALESCE(sum(${VALUE_PED}), 0) AS value
             FROM ingested_globals
             ${whereClause}
             GROUP BY target_name, mob_id
             ORDER BY ${targetsSortCol} DESC
             LIMIT 10`,
        params
      ),

      // Activity timeline (dynamic bucket aggregation)
      client.query(
        `SELECT date_trunc('${bucketUnit}', event_timestamp) AS bucket, count(*) AS count,
                COALESCE(sum(${VALUE_PED}), 0) AS total_value
         FROM ingested_globals
         ${whereClause}
         GROUP BY bucket
         ORDER BY bucket
         LIMIT ${MAX_ACTIVITY_BUCKETS}`,
        params
      ),
    ]);

    await client.query('COMMIT');

    const summary = summaryResult.rows[0];
    const rawSmCount = parseInt(summary.space_mining_count) || 0;
    const rawSmValue = parseFloat(summary.space_mining_value) || 0;

    return new Response(JSON.stringify({
      summary: {
        total_count: parseInt(summary.total_count),
        total_value: parseFloat(summary.total_value),
        avg_value: parseFloat(summary.avg_value),
        max_value: parseFloat(summary.max_value),
        hof_count: parseInt(summary.hof_count),
        ath_count: parseInt(summary.ath_count),
        hunting: { count: parseInt(summary.hunting_count), value: parseFloat(summary.hunting_value) },
        mining: { count: (parseInt(summary.mining_count) || 0) - rawSmCount, value: (parseFloat(summary.mining_value) || 0) - rawSmValue },
        space_mining: { count: rawSmCount, value: rawSmValue },
        crafting: { count: parseInt(summary.crafting_count), value: parseFloat(summary.crafting_value) },
      },
      by_type: byTypeResult.rows.map(r => ({
        type: r.type,
        count: parseInt(r.count),
        value: parseFloat(r.value),
      })),
      top_players: topPlayersResult.rows.map(r => ({
        player: r.player,
        count: parseInt(r.count),
        value: parseFloat(r.value),
        is_team: r.has_team && !r.has_solo,
      })),
      top_targets: topTargetsResult.rows.map(r => ({
        target: groupByMob && r.mob_id ? extractMobName(r.target) : r.target,
        mob_id: r.mob_id,
        count: parseInt(r.count),
        value: parseFloat(r.value),
      })),
      bucket_unit: chartUnit,
      activity: fillActivityGaps(
        activityResult.rows.map(r => ({ bucket: new Date(r.bucket).toISOString(), count: parseInt(r.count), value: parseFloat(r.total_value || 0) })),
        bucketUnit, from, to, period
      ),
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
      console.warn('[api/globals/stats] Raw query timed out');
      return getResponse({ error: 'Query too complex, try a narrower filter' }, 503);
    }
    console.error('[api/globals/stats] Error fetching stats:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  } finally {
    client.release();
  }
}
