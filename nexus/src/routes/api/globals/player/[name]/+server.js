// @ts-nocheck
/**
 * GET /api/globals/player/[name] — Player-specific global event statistics.
 * Public endpoint, no auth required.
 *
 * Returns summary stats + breakdowns by hunting (per-mob with maturities),
 * mining (per-resource), crafting (per-item), and activity timeline.
 */
import { pool } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';

export async function GET({ params }) {
  const playerName = decodeURIComponent(params.name);

  if (!playerName || playerName.length > 200) {
    return getResponse({ error: 'Invalid player name' }, 400);
  }

  try {
    // Run all queries in parallel
    const [
      summaryResult,
      huntingResult,
      miningResult,
      craftingResult,
      activityResult,
      recentResult,
      discoveryResult,
    ] = await Promise.all([
      // Summary stats
      pool.query(
        `SELECT count(*) AS total_count,
                COALESCE(sum(value), 0) AS total_value,
                count(*) FILTER (WHERE is_hof) AS hof_count,
                count(*) FILTER (WHERE is_ath) AS ath_count,
                count(*) FILTER (WHERE global_type = 'kill') AS kill_count,
                count(*) FILTER (WHERE global_type = 'team_kill') AS team_kill_count,
                count(*) FILTER (WHERE global_type = 'deposit') AS deposit_count,
                count(*) FILTER (WHERE global_type = 'craft') AS craft_count,
                count(*) FILTER (WHERE global_type = 'rare_item') AS rare_count,
                count(*) FILTER (WHERE global_type = 'discovery') AS discovery_count,
                count(*) FILTER (WHERE global_type = 'tier') AS tier_count
         FROM ingested_globals
         WHERE confirmed = true AND lower(player_name) = lower($1)`,
        [playerName]
      ),

      // Hunting: per-mob breakdown with maturity details
      pool.query(
        `SELECT target_name, mob_id, maturity_id,
                count(*) AS kills, COALESCE(sum(value), 0) AS total_value,
                COALESCE(avg(value), 0) AS avg_value, COALESCE(max(value), 0) AS best_value
         FROM ingested_globals
         WHERE confirmed = true AND lower(player_name) = lower($1)
           AND global_type IN ('kill', 'team_kill')
         GROUP BY target_name, mob_id, maturity_id
         ORDER BY total_value DESC`,
        [playerName]
      ),

      // Mining: per-resource breakdown
      pool.query(
        `SELECT target_name AS target, count(*) AS finds,
                COALESCE(sum(value), 0) AS total_value,
                COALESCE(avg(value), 0) AS avg_value, COALESCE(max(value), 0) AS best_value
         FROM ingested_globals
         WHERE confirmed = true AND lower(player_name) = lower($1)
           AND global_type = 'deposit'
         GROUP BY target_name
         ORDER BY total_value DESC`,
        [playerName]
      ),

      // Crafting: per-item breakdown
      pool.query(
        `SELECT target_name AS target, count(*) AS crafts,
                COALESCE(sum(value), 0) AS total_value,
                COALESCE(avg(value), 0) AS avg_value, COALESCE(max(value), 0) AS best_value
         FROM ingested_globals
         WHERE confirmed = true AND lower(player_name) = lower($1)
           AND global_type = 'craft'
         GROUP BY target_name
         ORDER BY total_value DESC`,
        [playerName]
      ),

      // Activity (daily buckets, last 365 days max)
      pool.query(
        `SELECT date_trunc('day', event_timestamp) AS bucket,
                global_type AS type, count(*) AS count
         FROM ingested_globals
         WHERE confirmed = true AND lower(player_name) = lower($1)
         GROUP BY bucket, global_type
         ORDER BY bucket
         LIMIT 2555`,
        [playerName]
      ),

      // Recent globals (last 20)
      pool.query(
        `SELECT id, global_type, target_name, value, value_unit,
                location, is_hof, is_ath, event_timestamp,
                mob_id, maturity_id, extra
         FROM ingested_globals
         WHERE confirmed = true AND lower(player_name) = lower($1)
         ORDER BY event_timestamp DESC
         LIMIT 20`,
        [playerName]
      ),

      // Discovery + tier achievements
      pool.query(
        `SELECT global_type, target_name, value, extra, event_timestamp, is_hof, is_ath
         FROM ingested_globals
         WHERE confirmed = true AND lower(player_name) = lower($1)
           AND global_type IN ('discovery', 'tier')
         ORDER BY event_timestamp DESC`,
        [playerName]
      ),
    ]);

    const summary = summaryResult.rows[0];

    // Group hunting results by mob (aggregate maturities under each mob)
    const mobMap = new Map();
    for (const row of huntingResult.rows) {
      // Extract mob name from target_name by removing maturity suffix
      // If mob_id is available, group by that; otherwise group by target_name
      const key = row.mob_id ?? row.target_name;
      if (!mobMap.has(key)) {
        mobMap.set(key, {
          mob_id: row.mob_id,
          target: row.target_name, // Will be overridden with mob-only name if we have mob_id
          kills: 0,
          total_value: 0,
          best_value: 0,
          maturities: [],
        });
      }
      const mob = mobMap.get(key);
      mob.kills += parseInt(row.kills);
      mob.total_value += parseFloat(row.total_value);
      mob.best_value = Math.max(mob.best_value, parseFloat(row.best_value));
      mob.maturities.push({
        target: row.target_name,
        maturity_id: row.maturity_id,
        kills: parseInt(row.kills),
        total_value: parseFloat(row.total_value),
        avg_value: parseFloat(row.avg_value),
        best_value: parseFloat(row.best_value),
      });
    }

    const hunting = [...mobMap.values()].map(m => ({
      ...m,
      avg_value: m.kills > 0 ? m.total_value / m.kills : 0,
      maturities: m.maturities.sort((a, b) => b.total_value - a.total_value),
    }));

    const response = new Response(JSON.stringify({
      player: playerName,
      summary: {
        total_count: parseInt(summary.total_count),
        total_value: parseFloat(summary.total_value),
        hof_count: parseInt(summary.hof_count),
        ath_count: parseInt(summary.ath_count),
        kill_count: parseInt(summary.kill_count),
        team_kill_count: parseInt(summary.team_kill_count),
        deposit_count: parseInt(summary.deposit_count),
        craft_count: parseInt(summary.craft_count),
        rare_count: parseInt(summary.rare_count),
        discovery_count: parseInt(summary.discovery_count),
        tier_count: parseInt(summary.tier_count),
      },
      hunting,
      mining: {
        resources: miningResult.rows.map(r => ({
          target: r.target,
          finds: parseInt(r.finds),
          total_value: parseFloat(r.total_value),
          avg_value: parseFloat(r.avg_value),
          best_value: parseFloat(r.best_value),
        })),
      },
      crafting: {
        items: craftingResult.rows.map(r => ({
          target: r.target,
          crafts: parseInt(r.crafts),
          total_value: parseFloat(r.total_value),
          avg_value: parseFloat(r.avg_value),
          best_value: parseFloat(r.best_value),
        })),
      },
      activity: activityResult.rows.map(r => ({
        bucket: r.bucket,
        type: r.type,
        count: parseInt(r.count),
      })),
      recent: recentResult.rows.map(r => ({
        id: r.id,
        type: r.global_type,
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
      achievements: discoveryResult.rows.map(r => ({
        type: r.global_type,
        target: r.target_name,
        value: parseFloat(r.value),
        extra: r.extra,
        timestamp: r.event_timestamp,
        hof: r.is_hof,
        ath: r.is_ath,
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
    console.error('[api/globals/player] Error fetching player globals:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
