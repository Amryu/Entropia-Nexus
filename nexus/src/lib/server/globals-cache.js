// @ts-nocheck
/**
 * In-memory cache for globals API endpoints.
 *
 * Caches the unfiltered, default-sorted, all-time responses for:
 *   - /api/globals/stats  (5 aggregation queries)
 *   - /api/globals/stats/players  (page 1, sort by value)
 *   - /api/globals/stats/targets  (page 1, sort by count)
 *
 * Also maintains a pre-aggregated ATH leaderboard table
 * (`globals_ath_leaderboard`) to replace the 4 expensive CTE
 * ranking queries in /api/globals/player/[name].
 *
 * Follows the SWR pattern from market/cache.js:
 *   - Event-driven invalidation (debounced) from ingestion pipeline
 *   - Scheduled refresh as safety net
 *   - Concurrent-request locking
 *   - ETag support
 */
import { pool } from '$lib/server/db.js';
import { createHash } from 'node:crypto';
import { getActivityBucket, fillActivityGaps } from '../../routes/api/globals/stats/filter-utils.js';
import { rebuildRollups } from './globals-rollup.js';

// --- Timing constants ---
const REFRESH_INTERVAL_MS = 5 * 60_000;         // 5 min scheduled refresh
const STALE_MAX_MS = 30 * 60_000;               // 30 min max staleness before blocking
const INVALIDATE_DEBOUNCE_MS = 2_000;            // 2s debounce on confirmation events
const ATH_REBUILD_INTERVAL_MS = 15 * 60_000;    // 15 min ATH leaderboard rebuild
const ATH_MIN_REBUILD_GAP_MS = 5 * 60_000;      // min 5 min between ATH rebuilds

// --- Cache state ---
let cache = {
  stats: { json: null, etag: null, builtAt: 0 },
  playersPage1: { json: null, etag: null, builtAt: 0 },
  targetsPage1: { json: null, etag: null, builtAt: 0 },
};
let rebuildPromise = null;
let athRebuildPromise = null;
let athLastRebuiltAt = 0;
let athLastCutoff = null;               // confirmed_at cutoff for incremental rebuilds
const ATH_FULL_REBUILD_INTERVAL_MS = 24 * 60 * 60_000; // full rebuild every 24h as safety net
let athLastFullRebuildAt = 0;
let invalidateTimer = null;

// --- Helpers ---

function computeEtag(json) {
  return createHash('md5').update(json).digest('hex');
}

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

// ------------------------------------------------------------------
// Stats cache (replaces 5 parallel queries in /api/globals/stats)
// ------------------------------------------------------------------

async function buildStatsCache() {
  const { sqlUnit: bucketUnit, chartUnit } = getActivityBucket('all', null, null);

  const [summaryResult, byTypeResult, topPlayersResult, topTargetsResult, activityResult] = await Promise.all([
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
       WHERE confirmed = true`
    ),
    pool.query(
      `SELECT global_type AS type, count(*) AS count, COALESCE(sum(value), 0) AS value
       FROM ingested_globals
       WHERE confirmed = true
       GROUP BY global_type
       ORDER BY count DESC`
    ),
    // Top players from pre-computed agg table (default sort: by value)
    pool.query(
      `SELECT player_name AS player, event_count AS count, sum_value AS value,
              has_team, has_solo
       FROM globals_player_agg
       WHERE period = 'all'
       ORDER BY sum_value DESC
       LIMIT 10`
    ),
    // Top targets from pre-computed agg table (default sort: by count, hunting only)
    pool.query(
      `SELECT target_name AS target, mob_id, event_count AS count, sum_value AS value
       FROM globals_target_agg
       WHERE period = 'all' AND primary_type IN ('kill', 'team_kill')
       ORDER BY event_count DESC
       LIMIT 10`
    ),
    pool.query(
      `SELECT date_trunc('${bucketUnit}', event_timestamp) AS bucket, count(*) AS count
       FROM ingested_globals
       WHERE confirmed = true
       GROUP BY bucket
       ORDER BY bucket
       LIMIT 2555`
    ),
  ]);

  const summary = summaryResult.rows[0];
  const data = {
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
      target: r.target,
      mob_id: r.mob_id,
      count: parseInt(r.count),
      value: parseFloat(r.value),
    })),
    bucket_unit: chartUnit,
    activity: fillActivityGaps(
      activityResult.rows.map(r => ({ bucket: new Date(r.bucket).toISOString(), count: parseInt(r.count) })),
      bucketUnit, null, null, 'all'
    ),
  };

  const json = JSON.stringify(data);
  cache.stats = { json, etag: computeEtag(json), builtAt: Date.now() };
}

// ------------------------------------------------------------------
// Players page 1 cache (default sort: value)
// ------------------------------------------------------------------

const PLAYERS_PAGE_SIZE = 50;

async function buildPlayersPage1Cache() {
  const [dataResult, countResult] = await Promise.all([
    pool.query(
      `SELECT player_name AS player, event_count AS count, sum_value AS value,
              sum_value / NULLIF(event_count, 0) AS avg_value,
              max_value AS best_value, has_team, has_solo, has_profile
       FROM globals_player_agg
       WHERE period = 'all'
       ORDER BY sum_value DESC
       LIMIT $1`,
      [PLAYERS_PAGE_SIZE]
    ),
    pool.query(
      `SELECT count(*) AS total FROM globals_player_agg WHERE period = 'all'`
    ),
  ]);

  const total = parseInt(countResult.rows[0].total);
  const data = {
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
    page: 1,
    pages: Math.ceil(total / PLAYERS_PAGE_SIZE),
  };

  const json = JSON.stringify(data);
  cache.playersPage1 = { json, etag: computeEtag(json), builtAt: Date.now() };
}

// ------------------------------------------------------------------
// Targets page 1 cache (default sort: count, group: maturity)
// ------------------------------------------------------------------

const TARGETS_PAGE_SIZE = 50;

async function buildTargetsPage1Cache() {
  const [dataResult, countResult] = await Promise.all([
    pool.query(
      `SELECT target_name AS target, mob_id, event_count AS count,
              sum_value AS value,
              sum_value / NULLIF(event_count, 0) AS avg_value,
              max_value AS best_value, primary_type
       FROM globals_target_agg
       WHERE period = 'all'
       ORDER BY event_count DESC
       LIMIT $1`,
      [TARGETS_PAGE_SIZE]
    ),
    pool.query(
      `SELECT count(*) AS total FROM globals_target_agg WHERE period = 'all'`
    ),
  ]);

  const total = parseInt(countResult.rows[0].total);
  const data = {
    targets: dataResult.rows.map(r => ({
      target: r.target,
      mob_id: r.mob_id,
      count: parseInt(r.count),
      value: parseFloat(r.value),
      avg_value: parseFloat(r.avg_value),
      best_value: parseFloat(r.best_value),
      primary_type: r.primary_type,
    })),
    total,
    page: 1,
    pages: Math.ceil(total / TARGETS_PAGE_SIZE),
  };

  const json = JSON.stringify(data);
  cache.targetsPage1 = { json, etag: computeEtag(json), builtAt: Date.now() };
}

// ------------------------------------------------------------------
// ATH leaderboard rebuild
// ------------------------------------------------------------------

const ATH_CATEGORIES = [
  { category: 'hunting', typeFilter: "global_type IN ('kill', 'team_kill')", useMobKey: true },
  { category: 'mining', typeFilter: "global_type = 'deposit'", useMobKey: false },
  { category: 'crafting', typeFilter: "global_type = 'craft'", useMobKey: false },
  { category: 'pvp', typeFilter: "global_type = 'pvp'", useMobKey: false },
];

async function rebuildAthLeaderboard() {
  const now = Date.now();
  if (now - athLastRebuiltAt < ATH_MIN_REBUILD_GAP_MS) return;
  if (athRebuildPromise) return athRebuildPromise;

  athRebuildPromise = (async () => {
    let client;
    try {
      client = await pool.connect();
      // Check if leaderboard table exists
      const { rows: tableCheck } = await client.query(
        `SELECT 1 FROM information_schema.tables WHERE table_name = 'globals_ath_leaderboard' LIMIT 1`
      );
      if (tableCheck.length === 0) return; // table not yet created

      // Determine rebuild mode: incremental (delta) vs full
      let cutoff = athLastCutoff;

      // On cold start, recover cutoff from the leaderboard table
      if (!cutoff) {
        const { rows } = await client.query(
          `SELECT MAX(updated_at) AS last_updated FROM globals_ath_leaderboard`
        );
        if (rows[0]?.last_updated) {
          cutoff = rows[0].last_updated;
        }
      }

      // Force full rebuild periodically as safety net to correct any drift
      // (only after we've been running long enough, not on cold start)
      const forceFullRebuild = athLastFullRebuildAt > 0
        && (now - athLastFullRebuildAt > ATH_FULL_REBUILD_INTERVAL_MS);
      const isIncremental = !!cutoff && !forceFullRebuild;

      if (!isIncremental) {
        // Full rebuild needs a generous timeout (2M+ rows to aggregate)
        await client.query('SET statement_timeout = 120000'); // 2 min
      } else {
        await client.query('SET statement_timeout = 30000'); // 30s for incremental
      }

      for (const { category, typeFilter, useMobKey } of ATH_CATEGORIES) {
        const targetKeyExpr = useMobKey
          ? "COALESCE(mob_id::text, target_name)"
          : "target_name";
        const bestTargetExpr = useMobKey
          ? "(array_agg(target_name ORDER BY value DESC))[1]"
          : "MAX(target_name)";
        const mobIdExpr = useMobKey ? "MAX(mob_id)" : "NULL::integer";

        const cutoffFilter = isIncremental ? ` AND confirmed_at > $2` : '';
        const params = isIncremental ? [category, cutoff] : [category];

        if (isIncremental) {
          // Delta upsert: add new values to existing totals
          const { rowCount } = await client.query(
            `INSERT INTO globals_ath_leaderboard
               (category, target_key, player_name, total_value, best_value, count, mob_id, best_target_name, total_rank, best_rank, updated_at)
             SELECT $1, ${targetKeyExpr}, player_name,
                    COALESCE(sum(value), 0), COALESCE(max(value), 0), count(*),
                    ${mobIdExpr}, ${bestTargetExpr},
                    0, 0, now()
             FROM ingested_globals
             WHERE confirmed = true AND ${typeFilter}${cutoffFilter}
             GROUP BY player_name, ${targetKeyExpr}
             ON CONFLICT (category, target_key, player_name)
             DO UPDATE SET
               total_value = globals_ath_leaderboard.total_value + EXCLUDED.total_value,
               best_value = GREATEST(globals_ath_leaderboard.best_value, EXCLUDED.best_value),
               count = globals_ath_leaderboard.count + EXCLUDED.count,
               mob_id = COALESCE(EXCLUDED.mob_id, globals_ath_leaderboard.mob_id),
               best_target_name = CASE
                 WHEN EXCLUDED.best_value > globals_ath_leaderboard.best_value THEN EXCLUDED.best_target_name
                 ELSE globals_ath_leaderboard.best_target_name
               END,
               updated_at = now()`,
            params
          );

          // Only recompute ranks if there were changes
          if (rowCount === 0) continue;
        } else {
          // Full rebuild: replace totals entirely
          await client.query(
            `INSERT INTO globals_ath_leaderboard
               (category, target_key, player_name, total_value, best_value, count, mob_id, best_target_name, total_rank, best_rank, updated_at)
             SELECT $1, ${targetKeyExpr}, player_name,
                    COALESCE(sum(value), 0), COALESCE(max(value), 0), count(*),
                    ${mobIdExpr}, ${bestTargetExpr},
                    0, 0, now()
             FROM ingested_globals
             WHERE confirmed = true AND ${typeFilter}
             GROUP BY player_name, ${targetKeyExpr}
             ON CONFLICT (category, target_key, player_name)
             DO UPDATE SET
               total_value = EXCLUDED.total_value,
               best_value = EXCLUDED.best_value,
               count = EXCLUDED.count,
               mob_id = EXCLUDED.mob_id,
               best_target_name = EXCLUDED.best_target_name,
               updated_at = now()`,
            [category]
          );
        }

        // Compute ranks
        await client.query(
          `UPDATE globals_ath_leaderboard a
           SET total_rank = sub.total_rank, best_rank = sub.best_rank
           FROM (
             SELECT target_key, player_name,
                    RANK() OVER (PARTITION BY target_key ORDER BY total_value DESC) AS total_rank,
                    RANK() OVER (PARTITION BY target_key ORDER BY best_value DESC) AS best_rank
             FROM globals_ath_leaderboard
             WHERE category = $1
           ) sub
           WHERE a.category = $1 AND a.target_key = sub.target_key AND a.player_name = sub.player_name`,
          [category]
        );
      }

      athLastCutoff = new Date();
      athLastRebuiltAt = Date.now();
      // Start/reset the 24h full-rebuild safety-net timer
      if (!isIncremental || athLastFullRebuildAt === 0) athLastFullRebuildAt = Date.now();
      console.log(`[globals-cache] ATH leaderboard rebuilt successfully (${isIncremental ? 'incremental' : 'full'})`);
    } catch (e) {
      console.error('[globals-cache] ATH leaderboard rebuild error:', e);
    } finally {
      if (client) {
        await client.query('RESET statement_timeout').catch(() => {});
        client.release();
      }
      athRebuildPromise = null;
    }
  })();

  return athRebuildPromise;
}

// ------------------------------------------------------------------
// Main rebuild (all in-memory caches)
// ------------------------------------------------------------------

async function rebuildAll() {
  if (rebuildPromise) return rebuildPromise;
  rebuildPromise = (async () => {
    try {
      await Promise.all([
        buildStatsCache(),
        buildPlayersPage1Cache(),
        buildTargetsPage1Cache(),
      ]);
      console.log('[globals-cache] Cache rebuilt successfully');
    } catch (e) {
      console.error('[globals-cache] Rebuild error:', e);
    } finally {
      rebuildPromise = null;
    }
  })();
  return rebuildPromise;
}

// ------------------------------------------------------------------
// Public API
// ------------------------------------------------------------------

/**
 * Get cached stats for the unfiltered all-time request.
 * Returns { json, etag } or null if no cache is available.
 */
export function getCachedStats() {
  return cache.stats.json ? cache.stats : null;
}

/**
 * Get cached players page 1 for unfiltered, default-sorted request.
 * Returns { json, etag } or null if no cache is available.
 */
export function getCachedPlayersPage1() {
  return cache.playersPage1.json ? cache.playersPage1 : null;
}

/**
 * Get cached targets page 1 for unfiltered, default-sorted request.
 * Returns { json, etag } or null if no cache is available.
 */
export function getCachedTargetsPage1() {
  return cache.targetsPage1.json ? cache.targetsPage1 : null;
}

/**
 * Check if the ATH leaderboard table is populated and usable.
 * Returns true if we've successfully rebuilt at least once.
 */
export function isAthLeaderboardReady() {
  return athLastRebuiltAt > 0;
}

/**
 * Debounced invalidation — call when a global becomes confirmed.
 * @param {Date} [oldestEventTs] - Oldest event timestamp from ingestion batch,
 *   used to extend rollup rebuild range beyond the default today+yesterday window.
 */
let pendingOldestTs = null;
export function invalidateGlobalsCache(oldestEventTs) {
  if (oldestEventTs && (!pendingOldestTs || oldestEventTs < pendingOldestTs)) {
    pendingOldestTs = oldestEventTs;
  }
  if (invalidateTimer) clearTimeout(invalidateTimer);
  invalidateTimer = setTimeout(async () => {
    invalidateTimer = null;
    const oldestTs = pendingOldestTs;
    pendingOldestTs = null;
    try {
      // Rebuild rollups first (updates rollup + agg tables), then cache reads from fresh agg data
      await rebuildRollups(oldestTs);
      await rebuildAll();
      rebuildAthLeaderboard().catch(() => {});
    } catch {}
  }, INVALIDATE_DEBOUNCE_MS);
}

/**
 * Initialize the cache on server start. Called from hooks.server.js.
 */
export async function initGlobalsCache() {
  try {
    await rebuildAll();
    console.log('[globals-cache] Initial build complete');
  } catch (e) {
    console.error('[globals-cache] Initial build failed:', e);
  }

  // Start ATH leaderboard rebuild in background
  rebuildAthLeaderboard().catch(() => {});

  // Scheduled refresh (safety net)
  const scheduleRefresh = () => {
    const jitter = Math.floor(REFRESH_INTERVAL_MS * (0.9 + Math.random() * 0.2));
    setTimeout(async () => {
      try {
        await rebuildAll();
      } catch {}
      scheduleRefresh();
    }, jitter).unref();
  };
  scheduleRefresh();

  // ATH leaderboard on its own schedule
  const scheduleAth = () => {
    const jitter = Math.floor(ATH_REBUILD_INTERVAL_MS * (0.9 + Math.random() * 0.2));
    setTimeout(async () => {
      try {
        await rebuildAthLeaderboard();
      } catch {}
      scheduleAth();
    }, jitter).unref();
  };
  scheduleAth();
}
