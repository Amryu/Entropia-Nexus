// @ts-nocheck
/**
 * GET /api/globals/stats — Aggregated global event statistics.
 * Public endpoint, no auth required.
 */
import { pool } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';

const PERIOD_INTERVALS = {
  '24h': "interval '24 hours'",
  '7d': "interval '7 days'",
  '30d': "interval '30 days'",
};
const VALID_GLOBAL_TYPES = new Set(['kill', 'team_kill', 'deposit', 'craft', 'rare_item', 'discovery', 'tier']);
const MAX_ACTIVITY_BUCKETS = 365;

function escapeLike(str) {
  return str.replace(/[%_\\]/g, '\\$&');
}

export async function GET({ url }) {
  const period = url.searchParams.get('period') || 'all';
  const playerFilter = url.searchParams.get('player');
  const typeFilter = url.searchParams.get('type');

  const conditions = ['confirmed = true'];
  const params = [];
  let paramIdx = 1;

  // Period filter
  const intervalSql = PERIOD_INTERVALS[period];
  if (intervalSql) {
    conditions.push(`event_timestamp > now() - ${intervalSql}`);
  }

  // Player filter
  if (playerFilter) {
    conditions.push(`player_name ILIKE $${paramIdx}`);
    params.push(`%${escapeLike(playerFilter)}%`);
    paramIdx++;
  }

  // Type filter (validated against known types)
  if (typeFilter) {
    const types = typeFilter.split(',').map(t => t.trim()).filter(t => VALID_GLOBAL_TYPES.has(t));
    if (types.length > 0) {
      conditions.push(`global_type = ANY($${paramIdx})`);
      params.push(types);
      paramIdx++;
    }
  }

  // Target filter
  const targetFilter = url.searchParams.get('target');
  if (targetFilter) {
    conditions.push(`target_name ILIKE $${paramIdx}`);
    params.push(`%${escapeLike(targetFilter)}%`);
    paramIdx++;
  }

  // Min value filter
  const minValueParam = url.searchParams.get('min_value');
  if (minValueParam) {
    const minVal = parseFloat(minValueParam);
    if (!isNaN(minVal) && minVal > 0) {
      conditions.push(`value >= $${paramIdx}`);
      params.push(minVal);
      paramIdx++;
    }
  }

  // HoF only filter
  if (url.searchParams.get('hof') === 'true') {
    conditions.push('is_hof = true');
  }

  const whereClause = `WHERE ${conditions.join(' AND ')}`;

  try {
    // Run all stats queries in parallel
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

      // Top players (by total value)
      pool.query(
        `SELECT player_name AS player, count(*) AS count, COALESCE(sum(value), 0) AS value
         FROM ingested_globals
         ${whereClause}
         GROUP BY player_name
         ORDER BY value DESC
         LIMIT 10`,
        params
      ),

      // Top targets (by count, for kill/team_kill with mob resolution)
      pool.query(
        `SELECT target_name AS target, mob_id, count(*) AS count, COALESCE(sum(value), 0) AS value
         FROM ingested_globals
         ${whereClause} AND global_type IN ('kill', 'team_kill')
         GROUP BY target_name, mob_id
         ORDER BY count DESC
         LIMIT 10`,
        params
      ),

      // Activity (hourly buckets for last 7 days, daily for longer periods)
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

    const response = new Response(JSON.stringify({
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
    return response;
  } catch (e) {
    console.error('[api/globals/stats] Error fetching stats:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
