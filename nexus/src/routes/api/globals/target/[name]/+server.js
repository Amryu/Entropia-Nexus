// @ts-nocheck
/**
 * GET /api/globals/target/[name] — Target-specific global event statistics.
 * Public endpoint, no auth required.
 *
 * Returns summary stats, top players, activity timeline, recent globals,
 * available maturities, and wiki link (for mobs).
 *
 * Query params:
 *   maturities — comma-separated target names to filter by specific maturities
 */
import { pool } from '$lib/server/db.js';
import { getResponse, encodeURIComponentSafe, decodeURIComponentSafe } from '$lib/util.js';

const PERIOD_INTERVALS = {
  '24h': "interval '24 hours'",
  '7d': "interval '7 days'",
  '30d': "interval '30 days'",
};

/**
 * Extract the mob base name by stripping the maturity suffix.
 */
function extractMobName(targetName) {
  const parts = targetName.split(' ');
  if (parts.length < 2) return targetName;

  if (parts.length >= 4 && /^Gen$/i.test(parts[parts.length - 2]) && /^Elite$/i.test(parts[parts.length - 3])) {
    return parts.slice(0, -3).join(' ');
  }
  if (parts.length >= 3 && /^Gen$/i.test(parts[parts.length - 2])) {
    return parts.slice(0, -2).join(' ');
  }
  return parts.slice(0, -1).join(' ');
}

export async function GET({ params, url }) {
  const targetName = decodeURIComponentSafe(params.name);

  if (!targetName || targetName.length > 300) {
    return getResponse({ error: 'Invalid target name' }, 400);
  }

  // Maturity filter: comma-separated list of specific target_name variants
  const maturityParam = url.searchParams.get('maturities');
  const maturityFilter = maturityParam
    ? maturityParam.split(',').map(m => m.trim()).filter(Boolean).slice(0, 50)
    : null;

  // Period filter
  const period = url.searchParams.get('period') || 'all';
  const intervalSql = PERIOD_INTERVALS[period];
  const periodCond = intervalSql ? ` AND event_timestamp > now() - ${intervalSql}` : '';

  // Build the target name condition — exact match or maturity filter
  let targetCond;
  let targetParams;
  if (maturityFilter && maturityFilter.length > 0) {
    targetCond = 'lower(target_name) = ANY($1)';
    targetParams = [maturityFilter.map(m => m.toLowerCase())];
  } else {
    targetCond = 'lower(target_name) = lower($1)';
    targetParams = [targetName];
  }

  try {
    const [
      summaryResult,
      topPlayersResult,
      activityResult,
      recentResult,
      maturitiesResult,
    ] = await Promise.all([
      // Summary stats
      pool.query(
        `SELECT count(*) AS total_count,
                COALESCE(sum(value), 0) AS total_value,
                count(*) FILTER (WHERE is_hof) AS hof_count,
                count(*) FILTER (WHERE is_ath) AS ath_count,
                mode() WITHIN GROUP (ORDER BY global_type) AS primary_type,
                min(event_timestamp) AS first_seen,
                max(event_timestamp) AS last_seen,
                MAX(mob_id) AS mob_id
         FROM ingested_globals
         WHERE confirmed = true AND ${targetCond}${periodCond}`,
        targetParams
      ),

      // Top players by total value
      pool.query(
        `SELECT player_name AS player, count(*) AS count,
                COALESCE(sum(value), 0) AS value,
                COALESCE(max(value), 0) AS best_value,
                bool_or(global_type = 'team_kill') AS has_team,
                bool_or(global_type != 'team_kill') AS has_solo
         FROM ingested_globals
         WHERE confirmed = true AND ${targetCond}${periodCond}
         GROUP BY player_name
         ORDER BY sum(value) DESC
         LIMIT 10`,
        targetParams
      ),

      // Activity (daily buckets)
      pool.query(
        period === '24h'
          ? `SELECT date_trunc('hour', event_timestamp) AS bucket,
                  count(*) AS count
             FROM ingested_globals
             WHERE confirmed = true AND ${targetCond}${periodCond}
             GROUP BY 1
             ORDER BY 1
             LIMIT 2555`
          : `SELECT date_trunc('day', event_timestamp) AS bucket,
                  count(*) AS count
             FROM ingested_globals
             WHERE confirmed = true AND ${targetCond}${periodCond}
             GROUP BY 1
             ORDER BY 1
             LIMIT 2555`,
        targetParams
      ),

      // Recent globals (last 20)
      pool.query(
        `SELECT id, global_type, player_name, target_name, value, value_unit,
                location, is_hof, is_ath, event_timestamp,
                mob_id, maturity_id, extra
         FROM ingested_globals
         WHERE confirmed = true AND ${targetCond}${periodCond}
         ORDER BY event_timestamp DESC
         LIMIT 20`,
        targetParams
      ),

      // Available maturities for this target (find all variants sharing the same mob_id or base name)
      pool.query(
        `SELECT target_name, count(*) AS count, COALESCE(sum(value), 0) AS value
         FROM ingested_globals
         WHERE confirmed = true AND (
           mob_id = (SELECT MAX(mob_id) FROM ingested_globals WHERE confirmed = true AND lower(target_name) = lower($1) AND mob_id IS NOT NULL)
           OR lower(target_name) = lower($1)
         )
         GROUP BY target_name
         ORDER BY count(*) DESC`,
        [targetName]
      ),
    ]);

    const summary = summaryResult.rows[0];

    if (parseInt(summary.total_count) === 0) {
      return getResponse({ error: 'Target not found' }, 404);
    }

    // Derive wiki URL for mob targets (hunting types with mob_id)
    let wikiUrl = null;
    const mobId = summary.mob_id;
    const isHunting = summary.primary_type === 'kill' || summary.primary_type === 'team_kill';
    if (mobId && isHunting) {
      // Use the base mob name (strip maturity) for the wiki URL
      const mobName = maturitiesResult.rows.length > 1
        ? extractMobName(targetName)
        : targetName;
      wikiUrl = `/information/mobs/${encodeURIComponentSafe(mobName)}`;
    }

    // Build maturities list (only if there are multiple variants)
    const maturities = maturitiesResult.rows.length > 1
      ? maturitiesResult.rows.map(r => ({
          target: r.target_name,
          count: parseInt(r.count),
          value: parseFloat(r.value),
        }))
      : [];

    return new Response(JSON.stringify({
      target: targetName,
      primary_type: summary.primary_type,
      mob_id: mobId,
      wiki_url: wikiUrl,
      summary: {
        total_count: parseInt(summary.total_count),
        total_value: parseFloat(summary.total_value),
        hof_count: parseInt(summary.hof_count),
        ath_count: parseInt(summary.ath_count),
        first_seen: summary.first_seen,
        last_seen: summary.last_seen,
      },
      maturities,
      top_players: topPlayersResult.rows.map(r => ({
        player: r.player,
        count: parseInt(r.count),
        value: parseFloat(r.value),
        best_value: parseFloat(r.best_value),
        is_team: r.has_team && !r.has_solo,
      })),
      activity: activityResult.rows.map(r => ({
        bucket: r.bucket,
        count: parseInt(r.count),
      })),
      recent: recentResult.rows.map(r => ({
        id: r.id,
        type: r.global_type,
        player: r.player_name,
        target: r.target_name,
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
  } catch (e) {
    console.error('[api/globals/target] Error fetching target globals:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
