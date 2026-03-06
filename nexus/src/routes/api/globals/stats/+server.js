// @ts-nocheck
/**
 * GET /api/globals/stats — Aggregated global event statistics.
 * Public endpoint, no auth required.
 */
import { pool } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import { buildGlobalsFilter, getActivityBucket, fillActivityGaps } from './filter-utils.js';

const MAX_ACTIVITY_BUCKETS = 2555;
const VALID_SORT_FIELDS = new Set(['count', 'value']);
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
  const { conditions, params, period, from, to } = buildGlobalsFilter(url);
  const { sqlUnit: bucketUnit, chartUnit } = getActivityBucket(period, from, to);
  const whereClause = `WHERE ${conditions.join(' AND ')}`;

  // Sort params for top players/targets charts
  const playersSortParam = url.searchParams.get('players_sort');
  const playersSortBy = VALID_SORT_FIELDS.has(playersSortParam) ? playersSortParam : 'value';
  const playersSortCol = playersSortBy === 'count' ? 'count(*)' : 'COALESCE(sum(value), 0)';

  const targetsSortParam = url.searchParams.get('targets_sort');
  const targetsSortBy = VALID_SORT_FIELDS.has(targetsSortParam) ? targetsSortParam : 'count';
  const targetsSortCol = targetsSortBy === 'count' ? 'count(*)' : 'COALESCE(sum(value), 0)';

  const targetsGroupParam = url.searchParams.get('targets_group');
  const targetsGroupBy = VALID_GROUP_FIELDS.has(targetsGroupParam) ? targetsGroupParam : 'maturity';
  const groupByMob = targetsGroupBy === 'mob';

  try {
    const [summaryResult, byTypeResult, topPlayersResult, topTargetsResult, activityResult] = await Promise.all([
      // Summary
      pool.query(
        `SELECT count(*) AS total_count,
                COALESCE(sum(value), 0) AS total_value,
                COALESCE(avg(value), 0) AS avg_value,
                COALESCE(max(value), 0) AS max_value,
                count(*) FILTER (WHERE is_hof) AS hof_count,
                count(*) FILTER (WHERE is_ath) AS ath_count,
                count(*) FILTER (WHERE global_type IN ('kill', 'team_kill')) AS hunting_count,
                COALESCE(sum(value) FILTER (WHERE global_type IN ('kill', 'team_kill')), 0) AS hunting_value,
                count(*) FILTER (WHERE global_type = 'deposit') AS mining_count,
                COALESCE(sum(value) FILTER (WHERE global_type = 'deposit'), 0) AS mining_value,
                count(*) FILTER (WHERE global_type = 'craft') AS crafting_count,
                COALESCE(sum(value) FILTER (WHERE global_type = 'craft'), 0) AS crafting_value
         FROM ingested_globals
         ${whereClause}`,
        params
      ),

      // By type
      pool.query(
        `SELECT global_type AS type, count(*) AS count, COALESCE(sum(value), 0) AS value
         FROM ingested_globals
         ${whereClause}
         GROUP BY global_type
         ORDER BY count DESC`,
        params
      ),

      // Top players
      pool.query(
        `SELECT player_name AS player, count(*) AS count, COALESCE(sum(value), 0) AS value,
                bool_or(global_type = 'team_kill') AS has_team,
                bool_or(global_type != 'team_kill') AS has_solo
         FROM ingested_globals
         ${whereClause}
         GROUP BY player_name
         ORDER BY ${playersSortCol} DESC
         LIMIT 10`,
        params
      ),

      // Top targets (kill/team_kill only)
      pool.query(
        groupByMob
          ? `SELECT min(target_name) AS target, mob_id, count(*) AS count, COALESCE(sum(value), 0) AS value
             FROM ingested_globals
             ${whereClause} AND global_type IN ('kill', 'team_kill')
             GROUP BY mob_id, CASE WHEN mob_id IS NULL THEN target_name END
             ORDER BY ${targetsSortCol} DESC
             LIMIT 10`
          : `SELECT target_name AS target, mob_id, count(*) AS count, COALESCE(sum(value), 0) AS value
             FROM ingested_globals
             ${whereClause} AND global_type IN ('kill', 'team_kill')
             GROUP BY target_name, mob_id
             ORDER BY ${targetsSortCol} DESC
             LIMIT 10`,
        params
      ),

      // Activity timeline (dynamic bucket aggregation)
      pool.query(
        `SELECT date_trunc('${bucketUnit}', event_timestamp) AS bucket, count(*) AS count
         FROM ingested_globals
         ${whereClause}
         GROUP BY bucket
         ORDER BY bucket
         LIMIT ${MAX_ACTIVITY_BUCKETS}`,
        params
      ),
    ]);

    const summary = summaryResult.rows[0];

    return new Response(JSON.stringify({
      summary: {
        total_count: parseInt(summary.total_count),
        total_value: parseFloat(summary.total_value),
        avg_value: parseFloat(summary.avg_value),
        max_value: parseFloat(summary.max_value),
        hof_count: parseInt(summary.hof_count),
        ath_count: parseInt(summary.ath_count),
        hunting: { count: parseInt(summary.hunting_count), value: parseFloat(summary.hunting_value) },
        mining: { count: parseInt(summary.mining_count), value: parseFloat(summary.mining_value) },
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
        activityResult.rows.map(r => ({ bucket: new Date(r.bucket).toISOString(), count: parseInt(r.count) })),
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
    console.error('[api/globals/stats] Error fetching stats:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
