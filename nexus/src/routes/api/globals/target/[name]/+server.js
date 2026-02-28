// @ts-nocheck
/**
 * GET /api/globals/target/[name] — Target-specific global event statistics.
 * Public endpoint, no auth required.
 *
 * Returns summary stats, top players, activity timeline, and recent globals
 * for a specific target (mob, resource, crafted item, etc.).
 */
import { pool } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';

export async function GET({ params }) {
  const targetName = decodeURIComponent(params.name);

  if (!targetName || targetName.length > 300) {
    return getResponse({ error: 'Invalid target name' }, 400);
  }

  try {
    const [
      summaryResult,
      topPlayersResult,
      activityResult,
      recentResult,
    ] = await Promise.all([
      // Summary stats
      pool.query(
        `SELECT count(*) AS total_count,
                COALESCE(sum(value), 0) AS total_value,
                count(*) FILTER (WHERE is_hof) AS hof_count,
                count(*) FILTER (WHERE is_ath) AS ath_count,
                mode() WITHIN GROUP (ORDER BY global_type) AS primary_type,
                min(event_timestamp) AS first_seen,
                max(event_timestamp) AS last_seen
         FROM ingested_globals
         WHERE confirmed = true AND lower(target_name) = lower($1)`,
        [targetName]
      ),

      // Top players by total value
      pool.query(
        `SELECT player_name AS player, count(*) AS count,
                COALESCE(sum(value), 0) AS value,
                COALESCE(max(value), 0) AS best_value
         FROM ingested_globals
         WHERE confirmed = true AND lower(target_name) = lower($1)
         GROUP BY player_name
         ORDER BY sum(value) DESC
         LIMIT 10`,
        [targetName]
      ),

      // Activity (daily buckets)
      pool.query(
        `SELECT date_trunc('day', event_timestamp) AS bucket,
                count(*) AS count
         FROM ingested_globals
         WHERE confirmed = true AND lower(target_name) = lower($1)
         GROUP BY 1
         ORDER BY 1
         LIMIT 2555`,
        [targetName]
      ),

      // Recent globals (last 20)
      pool.query(
        `SELECT id, global_type, player_name, value, value_unit,
                location, is_hof, is_ath, event_timestamp,
                mob_id, maturity_id, extra
         FROM ingested_globals
         WHERE confirmed = true AND lower(target_name) = lower($1)
         ORDER BY event_timestamp DESC
         LIMIT 20`,
        [targetName]
      ),
    ]);

    const summary = summaryResult.rows[0];

    if (parseInt(summary.total_count) === 0) {
      return getResponse({ error: 'Target not found' }, 404);
    }

    const response = new Response(JSON.stringify({
      target: targetName,
      primary_type: summary.primary_type,
      summary: {
        total_count: parseInt(summary.total_count),
        total_value: parseFloat(summary.total_value),
        hof_count: parseInt(summary.hof_count),
        ath_count: parseInt(summary.ath_count),
        first_seen: summary.first_seen,
        last_seen: summary.last_seen,
      },
      top_players: topPlayersResult.rows.map(r => ({
        player: r.player,
        count: parseInt(r.count),
        value: parseFloat(r.value),
        best_value: parseFloat(r.best_value),
      })),
      activity: activityResult.rows.map(r => ({
        bucket: r.bucket,
        count: parseInt(r.count),
      })),
      recent: recentResult.rows.map(r => ({
        id: r.id,
        type: r.global_type,
        player: r.player_name,
        value: parseFloat(r.value),
        unit: r.value_unit,
        location: r.location,
        hof: r.is_hof,
        ath: r.is_ath,
        timestamp: r.event_timestamp,
        mob_id: r.mob_id,
        maturity_id: r.maturity_id,
        extra: r.extra,
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
    console.error('[api/globals/target] Error fetching target globals:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
