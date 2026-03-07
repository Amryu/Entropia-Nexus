// @ts-nocheck
/**
 * GET /api/globals/player/[name] — Player-specific global event statistics.
 * Public endpoint, no auth required.
 *
 * Returns summary stats + breakdowns by hunting (per-mob with maturities),
 * mining (per-resource), crafting (per-item), activity timeline,
 * top individual loots per category, and per-target ATH stats.
 */
import { pool } from '$lib/server/db.js';
import { getResponse, decodeURIComponentSafe } from '$lib/util.js';
import { initMobResolver, resolveMob } from '$lib/server/mobResolver.js';
import { PERIOD_INTERVALS, getActivityBucket, fillActivityGaps } from '../../stats/filter-utils.js';
import { isAthLeaderboardReady } from '$lib/server/globals-cache.js';

const TOP_LOOTS_LIMIT = 100;
const OVERVIEW_TOP_LIMIT = 3;
const ATH_RANK_CUTOFF = 10;

export async function GET({ params, url }) {
  const playerName = decodeURIComponentSafe(params.name);

  if (!playerName || playerName.length > 200) {
    return getResponse({ error: 'Invalid player name' }, 400);
  }

  // Period / custom date range filter
  const period = url.searchParams.get('period') || 'all';
  const from = url.searchParams.get('from');
  const to = url.searchParams.get('to');

  let periodCond = '';
  const extraParams = [];
  let extraParamOffset = 1; // $1 is playerName

  if (from && to) {
    periodCond = ` AND event_timestamp >= $2 AND event_timestamp < $3`;
    extraParams.push(new Date(from), new Date(to + 'T23:59:59.999Z'));
    extraParamOffset = 3;
  } else {
    const intervalSql = PERIOD_INTERVALS[period];
    if (intervalSql) {
      periodCond = ` AND event_timestamp > now() - ${intervalSql}`;
    }
  }

  const { sqlUnit: bucketUnit } = getActivityBucket(period, from, to);

  // Helper for top individual loots query per category
  function topLootsQuery(typeCondition) {
    return pool.query(
      `SELECT target_name, value, mob_id, is_hof, is_ath, event_timestamp
       FROM ingested_globals
       WHERE confirmed = true AND lower(player_name) = lower($1)${periodCond}
         AND ${typeCondition}
       ORDER BY value DESC
       LIMIT ${TOP_LOOTS_LIMIT}`,
      [playerName, ...extraParams]
    );
  }

  // Use pre-aggregated leaderboard table for all-time requests (no period/date filter)
  const useLeaderboard = isAthLeaderboardReady() && !periodCond;

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
      rareItemsResult,
      pvpResult,
      topHuntingResult,
      topMiningResult,
      topCraftingResult,
      athHuntingResult,
      athMiningResult,
      athCraftingResult,
      athPvpResult,
    ] = await Promise.all([
      // Summary stats
      pool.query(
        `SELECT count(*) AS total_count,
                COALESCE(sum(value), 0) AS total_value,
                COALESCE(avg(value), 0) AS avg_value,
                COALESCE(max(value), 0) AS max_value,
                count(*) FILTER (WHERE is_hof) AS hof_count,
                count(*) FILTER (WHERE is_ath) AS ath_count,
                count(*) FILTER (WHERE global_type = 'kill') AS kill_count,
                count(*) FILTER (WHERE global_type = 'team_kill') AS team_kill_count,
                COALESCE(sum(value) FILTER (WHERE global_type IN ('kill', 'team_kill')), 0) AS hunting_value,
                count(*) FILTER (WHERE global_type = 'deposit') AS deposit_count,
                COALESCE(sum(value) FILTER (WHERE global_type = 'deposit'), 0) AS mining_value,
                count(*) FILTER (WHERE global_type = 'craft') AS craft_count,
                COALESCE(sum(value) FILTER (WHERE global_type = 'craft'), 0) AS crafting_value,
                count(*) FILTER (WHERE global_type = 'rare_item') AS rare_count,
                count(*) FILTER (WHERE global_type = 'discovery') AS discovery_count,
                count(*) FILTER (WHERE global_type = 'tier') AS tier_count,
                count(*) FILTER (WHERE global_type = 'pvp') AS pvp_count,
                COALESCE(sum(value) FILTER (WHERE global_type = 'pvp'), 0) AS pvp_value
         FROM ingested_globals
         WHERE confirmed = true AND lower(player_name) = lower($1)${periodCond}`,
        [playerName, ...extraParams]
      ),

      // Hunting: per-mob breakdown
      pool.query(
        `SELECT target_name,
                MAX(mob_id) AS mob_id, MAX(maturity_id) AS maturity_id,
                count(*) AS kills, COALESCE(sum(value), 0) AS total_value,
                COALESCE(avg(value), 0) AS avg_value, COALESCE(max(value), 0) AS best_value
         FROM ingested_globals
         WHERE confirmed = true AND lower(player_name) = lower($1)${periodCond}
           AND global_type IN ('kill', 'team_kill')
         GROUP BY target_name
         ORDER BY total_value DESC`,
        [playerName, ...extraParams]
      ),

      // Mining: per-resource breakdown
      pool.query(
        `SELECT target_name AS target, count(*) AS finds,
                COALESCE(sum(value), 0) AS total_value,
                COALESCE(avg(value), 0) AS avg_value, COALESCE(max(value), 0) AS best_value
         FROM ingested_globals
         WHERE confirmed = true AND lower(player_name) = lower($1)${periodCond}
           AND global_type = 'deposit'
         GROUP BY target_name
         ORDER BY total_value DESC`,
        [playerName, ...extraParams]
      ),

      // Crafting: per-item breakdown
      pool.query(
        `SELECT target_name AS target, count(*) AS crafts,
                COALESCE(sum(value), 0) AS total_value,
                COALESCE(avg(value), 0) AS avg_value, COALESCE(max(value), 0) AS best_value
         FROM ingested_globals
         WHERE confirmed = true AND lower(player_name) = lower($1)${periodCond}
           AND global_type = 'craft'
         GROUP BY target_name
         ORDER BY total_value DESC`,
        [playerName, ...extraParams]
      ),

      // Activity (dynamic bucket aggregation)
      pool.query(
        `SELECT date_trunc('${bucketUnit}', event_timestamp) AS bucket,
                global_type AS type, count(*) AS count
         FROM ingested_globals
         WHERE confirmed = true AND lower(player_name) = lower($1)${periodCond}
         GROUP BY bucket, global_type
         ORDER BY bucket
         LIMIT 2555`,
        [playerName, ...extraParams]
      ),

      // Recent globals (last 20)
      pool.query(
        `SELECT id, global_type, target_name, value, value_unit,
                location, is_hof, is_ath, event_timestamp,
                mob_id, maturity_id, extra
         FROM ingested_globals
         WHERE confirmed = true AND lower(player_name) = lower($1)${periodCond}
         ORDER BY event_timestamp DESC
         LIMIT 20`,
        [playerName, ...extraParams]
      ),

      // Discovery + tier achievements
      pool.query(
        `SELECT global_type, target_name, value, extra, event_timestamp, is_hof, is_ath
         FROM ingested_globals
         WHERE confirmed = true AND lower(player_name) = lower($1)${periodCond}
           AND global_type IN ('discovery', 'tier')
         ORDER BY event_timestamp DESC`,
        [playerName, ...extraParams]
      ),

      // Rare items
      pool.query(
        `SELECT target_name, value, event_timestamp, is_hof, is_ath
         FROM ingested_globals
         WHERE confirmed = true AND lower(player_name) = lower($1)${periodCond}
           AND global_type = 'rare_item'
         ORDER BY event_timestamp DESC`,
        [playerName, ...extraParams]
      ),

      // PvP events
      pool.query(
        `SELECT value, event_timestamp, is_hof, is_ath
         FROM ingested_globals
         WHERE confirmed = true AND lower(player_name) = lower($1)${periodCond}
           AND global_type = 'pvp'
         ORDER BY value DESC`,
        [playerName, ...extraParams]
      ),

      // Top individual hunting loots
      topLootsQuery("global_type IN ('kill', 'team_kill')"),

      // Top individual mining loots
      topLootsQuery("global_type = 'deposit'"),

      // Top individual crafting loots
      topLootsQuery("global_type = 'craft'"),

      // ATH rankings — use pre-aggregated leaderboard for all-time, fall back to live CTEs for period filters
      ...(useLeaderboard ? [
        // Hunting ATH from leaderboard
        pool.query(
          `SELECT target_key, total_value, best_value, count, mob_id,
                  best_target_name, total_rank, best_rank
           FROM globals_ath_leaderboard
           WHERE lower(player_name) = lower($1) AND category = 'hunting'
             AND (total_rank <= ${ATH_RANK_CUTOFF} OR best_rank <= ${ATH_RANK_CUTOFF})
           ORDER BY LEAST(total_rank, best_rank), total_value DESC`,
          [playerName]
        ),
        // Mining ATH from leaderboard
        pool.query(
          `SELECT target_key AS target_name, total_value, best_value, count, total_rank, best_rank
           FROM globals_ath_leaderboard
           WHERE lower(player_name) = lower($1) AND category = 'mining'
             AND (total_rank <= ${ATH_RANK_CUTOFF} OR best_rank <= ${ATH_RANK_CUTOFF})
           ORDER BY LEAST(total_rank, best_rank), total_value DESC`,
          [playerName]
        ),
        // Crafting ATH from leaderboard
        pool.query(
          `SELECT target_key AS target_name, total_value, best_value, count, total_rank, best_rank
           FROM globals_ath_leaderboard
           WHERE lower(player_name) = lower($1) AND category = 'crafting'
             AND (total_rank <= ${ATH_RANK_CUTOFF} OR best_rank <= ${ATH_RANK_CUTOFF})
           ORDER BY LEAST(total_rank, best_rank), total_value DESC`,
          [playerName]
        ),
        // PvP ATH from leaderboard (note: PvP leaderboard stores per-target aggregates, not individual events)
        pool.query(
          `SELECT total_value AS value, total_rank AS rank
           FROM globals_ath_leaderboard
           WHERE lower(player_name) = lower($1) AND category = 'pvp'
             AND (total_rank <= ${ATH_RANK_CUTOFF} OR best_rank <= ${ATH_RANK_CUTOFF})
           ORDER BY LEAST(total_rank, best_rank), total_value DESC`,
          [playerName]
        ),
      ] : [
        // Fallback: live CTE queries for period-filtered requests
        pool.query(
          `WITH target_totals AS (
             SELECT player_name, COALESCE(mob_id::text, target_name) AS mob_key,
                    MAX(target_name) AS target_name,
                    (array_agg(target_name ORDER BY value DESC))[1] AS best_target_name,
                    sum(value) AS total_value, max(value) AS best_value,
                    count(*) AS count, MAX(mob_id) AS mob_id
             FROM ingested_globals
             WHERE confirmed = true AND global_type IN ('kill', 'team_kill')${periodCond}
               AND COALESCE(mob_id::text, target_name) IN (
                 SELECT DISTINCT COALESCE(mob_id::text, target_name) FROM ingested_globals
                 WHERE confirmed = true AND lower(player_name) = lower($1)
                   AND global_type IN ('kill', 'team_kill')${periodCond}
               )
             GROUP BY player_name, mob_key
           ),
           ranked AS (
             SELECT *,
                    RANK() OVER (PARTITION BY mob_key ORDER BY total_value DESC) AS total_rank,
                    RANK() OVER (PARTITION BY mob_key ORDER BY best_value DESC) AS best_rank
             FROM target_totals
           )
           SELECT target_name, best_target_name, total_value, best_value, count, mob_id, total_rank, best_rank
           FROM ranked
           WHERE lower(player_name) = lower($1) AND (total_rank <= ${ATH_RANK_CUTOFF} OR best_rank <= ${ATH_RANK_CUTOFF})
           ORDER BY LEAST(total_rank, best_rank), total_value DESC`,
          [playerName, ...extraParams]
        ),
        pool.query(
          `WITH target_totals AS (
             SELECT player_name, target_name,
                    sum(value) AS total_value, max(value) AS best_value,
                    count(*) AS count
             FROM ingested_globals
             WHERE confirmed = true AND global_type = 'deposit'${periodCond}
               AND target_name IN (
                 SELECT DISTINCT target_name FROM ingested_globals
                 WHERE confirmed = true AND lower(player_name) = lower($1)
                   AND global_type = 'deposit'${periodCond}
               )
             GROUP BY player_name, target_name
           ),
           ranked AS (
             SELECT *,
                    RANK() OVER (PARTITION BY target_name ORDER BY total_value DESC) AS total_rank,
                    RANK() OVER (PARTITION BY target_name ORDER BY best_value DESC) AS best_rank
             FROM target_totals
           )
           SELECT target_name, total_value, best_value, count, total_rank, best_rank
           FROM ranked
           WHERE lower(player_name) = lower($1) AND (total_rank <= ${ATH_RANK_CUTOFF} OR best_rank <= ${ATH_RANK_CUTOFF})
           ORDER BY LEAST(total_rank, best_rank), total_value DESC`,
          [playerName, ...extraParams]
        ),
        pool.query(
          `WITH target_totals AS (
             SELECT player_name, target_name,
                    sum(value) AS total_value, max(value) AS best_value,
                    count(*) AS count
             FROM ingested_globals
             WHERE confirmed = true AND global_type = 'craft'${periodCond}
               AND target_name IN (
                 SELECT DISTINCT target_name FROM ingested_globals
                 WHERE confirmed = true AND lower(player_name) = lower($1)
                   AND global_type = 'craft'${periodCond}
               )
             GROUP BY player_name, target_name
           ),
           ranked AS (
             SELECT *,
                    RANK() OVER (PARTITION BY target_name ORDER BY total_value DESC) AS total_rank,
                    RANK() OVER (PARTITION BY target_name ORDER BY best_value DESC) AS best_rank
             FROM target_totals
           )
           SELECT target_name, total_value, best_value, count, total_rank, best_rank
           FROM ranked
           WHERE lower(player_name) = lower($1) AND (total_rank <= ${ATH_RANK_CUTOFF} OR best_rank <= ${ATH_RANK_CUTOFF})
           ORDER BY LEAST(total_rank, best_rank), total_value DESC`,
          [playerName, ...extraParams]
        ),
        pool.query(
          `WITH pvp_ranked AS (
             SELECT player_name, value, event_timestamp, is_hof, is_ath,
                    RANK() OVER (ORDER BY value DESC) AS rank
             FROM ingested_globals
             WHERE confirmed = true AND global_type = 'pvp'${periodCond}
           )
           SELECT value, event_timestamp, is_hof, is_ath, rank
           FROM pvp_ranked
           WHERE lower(player_name) = lower($1) AND rank <= ${ATH_RANK_CUTOFF}
           ORDER BY rank`,
          [playerName, ...extraParams]
        ),
      ]),
    ]);

    const summary = summaryResult.rows[0];

    if (parseInt(summary.total_count) === 0) {
      return getResponse({ error: 'Player not found' }, 404);
    }

    // Ensure mob resolver is loaded for proper name splitting
    await initMobResolver();

    // Group hunting results by mob (aggregate maturities under each mob)
    const mobMap = new Map();
    for (const row of huntingResult.rows) {
      const resolved = resolveMob(row.target_name);
      const mobName = resolved?.mobName || row.target_name;
      const key = row.mob_id ?? row.target_name;
      if (!mobMap.has(key)) {
        mobMap.set(key, {
          mob_id: row.mob_id,
          target: mobName,
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

    function mapLootRows(rows) {
      return rows.map(r => ({
        target: r.target_name,
        value: parseFloat(r.value),
        mob_id: r.mob_id,
        hof: r.is_hof,
        ath: r.is_ath,
        timestamp: r.event_timestamp,
      }));
    }

    function mapRankingRows(rows) {
      return rows.map(r => ({
        target: r.target_name,
        count: parseInt(r.count),
        total_value: parseFloat(r.total_value),
        best_value: parseFloat(r.best_value),
        total_rank: parseInt(r.total_rank),
        best_rank: parseInt(r.best_rank),
        mob_id: r.mob_id || null,
      }));
    }

    const response = new Response(JSON.stringify({
      player: playerName,
      summary: {
        total_count: parseInt(summary.total_count),
        total_value: parseFloat(summary.total_value),
        avg_value: parseFloat(summary.avg_value),
        max_value: parseFloat(summary.max_value),
        hof_count: parseInt(summary.hof_count),
        ath_count: parseInt(summary.ath_count),
        kill_count: parseInt(summary.kill_count),
        team_kill_count: parseInt(summary.team_kill_count),
        hunting_value: parseFloat(summary.hunting_value),
        deposit_count: parseInt(summary.deposit_count),
        mining_value: parseFloat(summary.mining_value),
        craft_count: parseInt(summary.craft_count),
        crafting_value: parseFloat(summary.crafting_value),
        rare_count: parseInt(summary.rare_count),
        discovery_count: parseInt(summary.discovery_count),
        tier_count: parseInt(summary.tier_count),
        pvp_count: parseInt(summary.pvp_count),
        pvp_value: parseFloat(summary.pvp_value),
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
      bucket_unit: bucketUnit,
      activity: fillActivityGaps(
        (() => {
          const bucketMap = new Map();
          for (const r of activityResult.rows) {
            const key = new Date(r.bucket).toISOString();
            bucketMap.set(key, (bucketMap.get(key) || 0) + parseInt(r.count));
          }
          return [...bucketMap.entries()]
            .sort((a, b) => a[0].localeCompare(b[0]))
            .map(([bucket, count]) => ({ bucket, count }));
        })(),
        bucketUnit, from, to, period
      ),
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
      rare_items: rareItemsResult.rows.map(r => ({
        target: r.target_name,
        value: parseFloat(r.value),
        timestamp: r.event_timestamp,
        hof: r.is_hof,
        ath: r.is_ath,
      })),
      pvp_events: pvpResult.rows.map(r => ({
        value: parseFloat(r.value),
        timestamp: r.event_timestamp,
        hof: r.is_hof,
        ath: r.is_ath,
      })),
      top_loots: {
        hunting: mapLootRows(topHuntingResult.rows),
        mining: mapLootRows(topMiningResult.rows),
        crafting: mapLootRows(topCraftingResult.rows),
      },
      ath_rankings: {
        hunting: athHuntingResult.rows.map(r => {
          const targetName = r.target_name || r.best_target_name || r.target_key || '';
          const resolved = resolveMob(targetName);
          return {
            target: resolved?.mobName || targetName,
            best_target: r.best_target_name || targetName,
            count: parseInt(r.count),
            total_value: parseFloat(r.total_value),
            best_value: parseFloat(r.best_value),
            total_rank: parseInt(r.total_rank),
            best_rank: parseInt(r.best_rank),
            mob_id: r.mob_id || null,
          };
        }),
        mining: mapRankingRows(athMiningResult.rows),
        crafting: mapRankingRows(athCraftingResult.rows),
        pvp: useLeaderboard
          ? athPvpResult.rows.map(r => ({
              value: parseFloat(r.value),
              rank: parseInt(r.rank),
            }))
          : athPvpResult.rows.map(r => ({
              value: parseFloat(r.value),
              rank: parseInt(r.rank),
              hof: r.is_hof,
              ath: r.is_ath,
              timestamp: r.event_timestamp,
            })),
      },
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
