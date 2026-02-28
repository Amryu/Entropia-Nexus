// @ts-nocheck
/**
 * GET /api/globals/stats — Aggregated global event statistics.
 * Public endpoint, no auth required.
 */
import { pool } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import { buildGlobalsFilter } from './filter-utils.js';

const MAX_ACTIVITY_BUCKETS = 365;
const VALID_SORT_FIELDS = new Set(['count', 'value']);

export async function GET({ url }) {
  const period = url.searchParams.get('period') || 'all';
  const { conditions, params } = buildGlobalsFilter(url);
  const whereClause = `WHERE ${conditions.join(' AND ')}`;

  // Sort params for top players/targets charts
  const playersSortParam = url.searchParams.get('players_sort');
  const playersSortBy = VALID_SORT_FIELDS.has(playersSortParam) ? playersSortParam : 'value';
  const playersSortCol = playersSortBy === 'count' ? 'count(*)' : 'COALESCE(sum(value), 0)';

  const targetsSortParam = url.searchParams.get('targets_sort');
  const targetsSortBy = VALID_SORT_FIELDS.has(targetsSortParam) ? targetsSortParam : 'count';
  const targetsSortCol = targetsSortBy === 'count' ? 'count(*)' : 'COALESCE(sum(value), 0)';

  try {
    const [summaryResult, byTypeResult, topPlayersResult, topTargetsResult, activityResult] = await Promise.all([
      // Summary
      pool.query(
        `SELECT count(*) AS total_count,
                COALESCE(sum(value), 0) AS total_value,
                count(*) FILTER (WHERE is_hof) AS hof_count,
                count(*) FILTER (WHERE is_ath) AS ath_count
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
        `SELECT target_name AS target, mob_id, count(*) AS count, COALESCE(sum(value), 0) AS value
         FROM ingested_globals
         ${whereClause} AND global_type IN ('kill', 'team_kill')
         GROUP BY target_name, mob_id
         ORDER BY ${targetsSortCol} DESC
         LIMIT 10`,
        params
      ),

      // Activity timeline
      pool.query(
        period === '24h'
          ? `SELECT date_trunc('hour', event_timestamp) AS bucket, count(*) AS count
             FROM ingested_globals
             ${whereClause}
             GROUP BY bucket
             ORDER BY bucket
             LIMIT ${MAX_ACTIVITY_BUCKETS}`
          : `SELECT date_trunc('day', event_timestamp) AS bucket, count(*) AS count
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
        hof_count: parseInt(summary.hof_count),
        ath_count: parseInt(summary.ath_count),
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
        target: r.target,
        mob_id: r.mob_id,
        count: parseInt(r.count),
        value: parseFloat(r.value),
      })),
      activity: activityResult.rows.map(r => ({
        bucket: r.bucket,
        count: parseInt(r.count),
      })),
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
