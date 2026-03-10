// @ts-nocheck
/**
 * Globals rollup table maintenance.
 *
 * Maintains three pre-aggregated rollup tables at daily, weekly, monthly,
 * and quarterly granularities:
 *   - globals_rollup          (global-level: type × period)
 *   - globals_rollup_player   (player-level: player × type × period)
 *   - globals_rollup_target   (target-level: target × type × period)
 *
 * Endpoints select the appropriate granularity for the requested period,
 * reducing scanned rows from hundreds of thousands to hundreds.
 *
 * Rebuild strategy:
 *   - Daily: from raw ingested_globals (today + yesterday)
 *   - Weekly/monthly/quarterly: aggregated FROM daily rollup
 *   - Full rebuild on startup, incremental on ingestion events
 */
import { pool } from '$lib/server/db.js';

// --- Timing constants ---
const ROLLUP_REBUILD_INTERVAL_MS = 10 * 60_000;  // 10 min safety-net refresh
const ROLLUP_MIN_REBUILD_GAP_MS = 3 * 60_000;    // min 3 min between rebuilds

// --- State ---
let rollupReady = false;
let rollupRebuildPromise = null;
let rollupLastRebuiltAt = 0;

// --- Granularity config ---
const COARSE_GRANULARITIES = [
  { granularity: 'weekly', truncUnit: 'week' },
  { granularity: 'monthly', truncUnit: 'month' },
  { granularity: 'quarterly', truncUnit: 'quarter' },
];

// ------------------------------------------------------------------
// Daily rollup rebuild (from raw ingested_globals)
// ------------------------------------------------------------------

/**
 * Rebuild daily rollup rows for the given date range.
 * Runs DELETE + INSERT within a transaction for each table.
 */
async function rebuildDailyRange(startDate, endDate) {
  const client = await pool.connect();
  try {
    await client.query('SET statement_timeout = 120000'); // 2 min for heavy rebuild
    await client.query('BEGIN');

    // globals_rollup (global-level)
    await client.query(
      `DELETE FROM globals_rollup
       WHERE granularity = 'daily' AND period_start >= $1 AND period_start < $2`,
      [startDate, endDate]
    );
    await client.query(
      `INSERT INTO globals_rollup (granularity, period_start, global_type, event_count, sum_value, max_value, hof_count, ath_count)
       SELECT 'daily', date_trunc('day', event_timestamp), global_type,
              count(*), COALESCE(sum(value), 0), COALESCE(max(value), 0),
              count(*) FILTER (WHERE is_hof), count(*) FILTER (WHERE is_ath)
       FROM ingested_globals
       WHERE confirmed = true AND event_timestamp >= $1 AND event_timestamp < $2
       GROUP BY date_trunc('day', event_timestamp), global_type
       ON CONFLICT (granularity, period_start, global_type) DO UPDATE SET
         event_count = EXCLUDED.event_count, sum_value = EXCLUDED.sum_value,
         max_value = EXCLUDED.max_value, hof_count = EXCLUDED.hof_count, ath_count = EXCLUDED.ath_count`,
      [startDate, endDate]
    );

    // globals_rollup_player (per-player)
    await client.query(
      `DELETE FROM globals_rollup_player
       WHERE granularity = 'daily' AND period_start >= $1 AND period_start < $2`,
      [startDate, endDate]
    );
    await client.query(
      `INSERT INTO globals_rollup_player (granularity, period_start, player_name, global_type, event_count, sum_value, max_value, hof_count, ath_count)
       SELECT 'daily', date_trunc('day', event_timestamp), player_name, global_type,
              count(*), COALESCE(sum(value), 0), COALESCE(max(value), 0),
              count(*) FILTER (WHERE is_hof), count(*) FILTER (WHERE is_ath)
       FROM ingested_globals
       WHERE confirmed = true AND event_timestamp >= $1 AND event_timestamp < $2
       GROUP BY date_trunc('day', event_timestamp), player_name, global_type
       ON CONFLICT (granularity, period_start, player_name, global_type) DO UPDATE SET
         event_count = EXCLUDED.event_count, sum_value = EXCLUDED.sum_value,
         max_value = EXCLUDED.max_value, hof_count = EXCLUDED.hof_count, ath_count = EXCLUDED.ath_count`,
      [startDate, endDate]
    );

    // globals_rollup_target (per-target)
    await client.query(
      `DELETE FROM globals_rollup_target
       WHERE granularity = 'daily' AND period_start >= $1 AND period_start < $2`,
      [startDate, endDate]
    );
    await client.query(
      `INSERT INTO globals_rollup_target (granularity, period_start, target_name, mob_id, global_type, event_count, sum_value, max_value, hof_count, ath_count)
       SELECT 'daily', date_trunc('day', event_timestamp), target_name, MAX(mob_id), global_type,
              count(*), COALESCE(sum(value), 0), COALESCE(max(value), 0),
              count(*) FILTER (WHERE is_hof), count(*) FILTER (WHERE is_ath)
       FROM ingested_globals
       WHERE confirmed = true AND event_timestamp >= $1 AND event_timestamp < $2
         AND target_name IS NOT NULL
       GROUP BY date_trunc('day', event_timestamp), target_name, global_type
       ON CONFLICT (granularity, period_start, target_name, global_type) DO UPDATE SET
         mob_id = EXCLUDED.mob_id, event_count = EXCLUDED.event_count, sum_value = EXCLUDED.sum_value,
         max_value = EXCLUDED.max_value, hof_count = EXCLUDED.hof_count, ath_count = EXCLUDED.ath_count`,
      [startDate, endDate]
    );

    await client.query('COMMIT');
  } catch (e) {
    await client.query('ROLLBACK');
    throw e;
  } finally {
    await client.query('RESET statement_timeout').catch(() => {});
    client.release();
  }
}

// ------------------------------------------------------------------
// Coarse granularity rebuild (from daily rollup)
// ------------------------------------------------------------------

/**
 * Rebuild a coarser granularity by aggregating from the daily rollup.
 * If startDate/endDate provided, only rebuilds that range; otherwise full rebuild.
 */
async function rebuildCoarseGranularity(granularity, truncUnit, startDate, endDate) {
  const client = await pool.connect();
  try {
    await client.query('SET statement_timeout = 60000'); // 1 min for coarse rebuild
    await client.query('BEGIN');

    const rangeFilter = startDate && endDate
      ? ` AND period_start >= '${startDate.toISOString()}' AND period_start < '${endDate.toISOString()}'`
      : '';

    const coarseRangeFilter = startDate && endDate
      ? ` AND date_trunc('${truncUnit}', period_start) >= date_trunc('${truncUnit}', '${startDate.toISOString()}'::timestamptz)
          AND date_trunc('${truncUnit}', period_start) <= date_trunc('${truncUnit}', '${endDate.toISOString()}'::timestamptz)`
      : '';

    // globals_rollup
    await client.query(
      `DELETE FROM globals_rollup WHERE granularity = $1${startDate ? ` AND period_start >= date_trunc('${truncUnit}', $2::timestamptz) AND period_start <= date_trunc('${truncUnit}', $3::timestamptz)` : ''}`,
      startDate ? [granularity, startDate, endDate] : [granularity]
    );
    await client.query(
      `INSERT INTO globals_rollup (granularity, period_start, global_type, event_count, sum_value, max_value, hof_count, ath_count)
       SELECT $1, date_trunc('${truncUnit}', period_start), global_type,
              SUM(event_count), SUM(sum_value), MAX(max_value), SUM(hof_count), SUM(ath_count)
       FROM globals_rollup
       WHERE granularity = 'daily'${coarseRangeFilter}
       GROUP BY date_trunc('${truncUnit}', period_start), global_type
       ON CONFLICT (granularity, period_start, global_type) DO UPDATE SET
         event_count = EXCLUDED.event_count, sum_value = EXCLUDED.sum_value,
         max_value = EXCLUDED.max_value, hof_count = EXCLUDED.hof_count, ath_count = EXCLUDED.ath_count`,
      [granularity]
    );

    // globals_rollup_player
    await client.query(
      `DELETE FROM globals_rollup_player WHERE granularity = $1${startDate ? ` AND period_start >= date_trunc('${truncUnit}', $2::timestamptz) AND period_start <= date_trunc('${truncUnit}', $3::timestamptz)` : ''}`,
      startDate ? [granularity, startDate, endDate] : [granularity]
    );
    await client.query(
      `INSERT INTO globals_rollup_player (granularity, period_start, player_name, global_type, event_count, sum_value, max_value, hof_count, ath_count)
       SELECT $1, date_trunc('${truncUnit}', period_start), player_name, global_type,
              SUM(event_count), SUM(sum_value), MAX(max_value), SUM(hof_count), SUM(ath_count)
       FROM globals_rollup_player
       WHERE granularity = 'daily'${coarseRangeFilter}
       GROUP BY date_trunc('${truncUnit}', period_start), player_name, global_type
       ON CONFLICT (granularity, period_start, player_name, global_type) DO UPDATE SET
         event_count = EXCLUDED.event_count, sum_value = EXCLUDED.sum_value,
         max_value = EXCLUDED.max_value, hof_count = EXCLUDED.hof_count, ath_count = EXCLUDED.ath_count`,
      [granularity]
    );

    // globals_rollup_target
    await client.query(
      `DELETE FROM globals_rollup_target WHERE granularity = $1${startDate ? ` AND period_start >= date_trunc('${truncUnit}', $2::timestamptz) AND period_start <= date_trunc('${truncUnit}', $3::timestamptz)` : ''}`,
      startDate ? [granularity, startDate, endDate] : [granularity]
    );
    await client.query(
      `INSERT INTO globals_rollup_target (granularity, period_start, target_name, mob_id, global_type, event_count, sum_value, max_value, hof_count, ath_count)
       SELECT $1, date_trunc('${truncUnit}', period_start), target_name, MAX(mob_id), global_type,
              SUM(event_count), SUM(sum_value), MAX(max_value), SUM(hof_count), SUM(ath_count)
       FROM globals_rollup_target
       WHERE granularity = 'daily'${coarseRangeFilter}
       GROUP BY date_trunc('${truncUnit}', period_start), target_name, global_type
       ON CONFLICT (granularity, period_start, target_name, global_type) DO UPDATE SET
         mob_id = EXCLUDED.mob_id, event_count = EXCLUDED.event_count, sum_value = EXCLUDED.sum_value,
         max_value = EXCLUDED.max_value, hof_count = EXCLUDED.hof_count, ath_count = EXCLUDED.ath_count`,
      [granularity]
    );

    await client.query('COMMIT');
  } catch (e) {
    await client.query('ROLLBACK');
    throw e;
  } finally {
    await client.query('RESET statement_timeout').catch(() => {});
    client.release();
  }
}

// ------------------------------------------------------------------
// Full rebuild (startup)
// ------------------------------------------------------------------

async function fullRebuild() {
  // Check if tables exist
  const { rows } = await pool.query(
    `SELECT 1 FROM information_schema.tables WHERE table_name = 'globals_rollup' LIMIT 1`
  );
  if (rows.length === 0) return;

  // Find earliest confirmed global
  const { rows: minRows } = await pool.query(
    `SELECT MIN(event_timestamp) AS min_ts FROM ingested_globals WHERE confirmed = true`
  );
  if (!minRows[0]?.min_ts) return;

  const minDate = new Date(minRows[0].min_ts);
  minDate.setUTCHours(0, 0, 0, 0);

  const tomorrow = new Date();
  tomorrow.setUTCDate(tomorrow.getUTCDate() + 1);
  tomorrow.setUTCHours(0, 0, 0, 0);

  // Rebuild daily in 90-day chunks to avoid long-running queries that starve other connections
  const CHUNK_DAYS = 90;
  let chunkStart = new Date(minDate);
  while (chunkStart < tomorrow) {
    const chunkEnd = new Date(Math.min(
      chunkStart.getTime() + CHUNK_DAYS * 24 * 60 * 60 * 1000,
      tomorrow.getTime()
    ));
    await rebuildDailyRange(chunkStart, chunkEnd);
    chunkStart = chunkEnd;
  }

  // Rebuild coarse granularities from daily
  for (const { granularity, truncUnit } of COARSE_GRANULARITIES) {
    await rebuildCoarseGranularity(granularity, truncUnit);
  }

  // Refresh summary tables from rollup data
  await refreshSummaryTables();
}

// ------------------------------------------------------------------
// Incremental rebuild (on ingestion events)
// ------------------------------------------------------------------

async function incrementalRebuild(oldestEventTs) {
  // Check if tables exist
  const { rows } = await pool.query(
    `SELECT 1 FROM information_schema.tables WHERE table_name = 'globals_rollup' LIMIT 1`
  );
  if (rows.length === 0) return;

  // Default: rebuild today + yesterday. Extend if older events were ingested.
  const yesterday = new Date();
  yesterday.setUTCDate(yesterday.getUTCDate() - 1);
  yesterday.setUTCHours(0, 0, 0, 0);

  const startDate = new Date(Math.min(
    yesterday.getTime(),
    oldestEventTs ? new Date(oldestEventTs).setUTCHours(0, 0, 0, 0) : Infinity
  ));

  const tomorrow = new Date();
  tomorrow.setUTCDate(tomorrow.getUTCDate() + 1);
  tomorrow.setUTCHours(0, 0, 0, 0);

  await rebuildDailyRange(startDate, tomorrow);

  // Rebuild coarse granularities for the affected range
  for (const { granularity, truncUnit } of COARSE_GRANULARITIES) {
    await rebuildCoarseGranularity(granularity, truncUnit, startDate, tomorrow);
  }

  // Refresh summary tables from rollup data
  await refreshSummaryTables();
}

// ------------------------------------------------------------------
// Summary tables refresh (from rollup data)
// ------------------------------------------------------------------

const SUMMARY_PERIODS = [
  { period: 'all',  granularity: 'monthly', intervalSql: null },
  { period: '7d',   granularity: 'daily',   intervalSql: "interval '7 days'" },
  { period: '30d',  granularity: 'daily',   intervalSql: "interval '30 days'" },
  { period: '90d',  granularity: 'weekly',  intervalSql: "interval '90 days'" },
  { period: '1y',   granularity: 'weekly',  intervalSql: "interval '1 year'" },
];

/**
 * Refresh pre-computed summary tables (globals_player_agg, globals_target_agg)
 * from rollup data. Called after each rollup rebuild.
 */
async function refreshSummaryTables() {
  // Check if summary tables exist
  const { rows: tableCheck } = await pool.query(
    `SELECT 1 FROM information_schema.tables WHERE table_name = 'globals_player_agg' LIMIT 1`
  );
  if (tableCheck.length === 0) return;

  const client = await pool.connect();
  try {
    await client.query('SET statement_timeout = 120000');
    await client.query('BEGIN');

    await client.query('DELETE FROM globals_player_agg');
    await client.query('DELETE FROM globals_target_agg');

    for (const { period, granularity, intervalSql } of SUMMARY_PERIODS) {
      const periodFilter = intervalSql
        ? ` AND period_start >= date_trunc('day', now() - ${intervalSql})`
        : '';

      await client.query(
        `INSERT INTO globals_player_agg
           (period, player_name, event_count, sum_value, max_value, has_team, has_solo, has_profile)
         SELECT $1, player_name,
                SUM(event_count)::integer,
                SUM(sum_value),
                MAX(max_value),
                bool_or(global_type = 'team_kill'),
                bool_or(global_type != 'team_kill'),
                EXISTS(SELECT 1 FROM users u WHERE lower(u.eu_name) = lower(player_name) AND u.verified = true)
         FROM globals_rollup_player
         WHERE granularity = $2${periodFilter}
         GROUP BY player_name
         ON CONFLICT (period, player_name) DO UPDATE SET
           event_count = EXCLUDED.event_count,
           sum_value = EXCLUDED.sum_value,
           max_value = EXCLUDED.max_value,
           has_team = EXCLUDED.has_team,
           has_solo = EXCLUDED.has_solo,
           has_profile = EXCLUDED.has_profile`,
        [period, granularity]
      );

      await client.query(
        `INSERT INTO globals_target_agg
           (period, target_name, mob_id, event_count, sum_value, max_value, primary_type)
         SELECT $1, target_name,
                MAX(mob_id),
                SUM(event_count)::integer,
                SUM(sum_value),
                MAX(max_value),
                (SELECT r2.global_type FROM globals_rollup_target r2
                 WHERE r2.granularity = $2${periodFilter}
                   AND r2.target_name = globals_rollup_target.target_name
                 GROUP BY r2.global_type ORDER BY SUM(r2.event_count) DESC LIMIT 1)
         FROM globals_rollup_target
         WHERE granularity = $2${periodFilter}
         GROUP BY target_name
         ON CONFLICT (period, target_name) DO UPDATE SET
           mob_id = EXCLUDED.mob_id,
           event_count = EXCLUDED.event_count,
           sum_value = EXCLUDED.sum_value,
           max_value = EXCLUDED.max_value,
           primary_type = EXCLUDED.primary_type`,
        [period, granularity]
      );
    }

    await client.query('COMMIT');
    console.log('[globals-rollup] Summary tables refreshed');
  } catch (e) {
    await client.query('ROLLBACK').catch(() => {});
    console.error('[globals-rollup] Summary tables refresh error:', e);
  } finally {
    await client.query('RESET statement_timeout').catch(() => {});
    client.release();
  }
}

// ------------------------------------------------------------------
// Public API
// ------------------------------------------------------------------

/**
 * Whether rollup tables are populated and ready for use.
 */
export function isRollupReady() {
  return rollupReady;
}

/**
 * Trigger an incremental rollup rebuild (debounced externally by globals-cache.js).
 * @param {Date} [oldestEventTs] - Oldest event timestamp from the ingestion batch.
 *   If older than yesterday, the rebuild range extends to cover it.
 */
export async function rebuildRollups(oldestEventTs) {
  const now = Date.now();
  if (now - rollupLastRebuiltAt < ROLLUP_MIN_REBUILD_GAP_MS) return;
  if (rollupRebuildPromise) return rollupRebuildPromise;

  rollupRebuildPromise = (async () => {
    try {
      await incrementalRebuild(oldestEventTs);
      rollupLastRebuiltAt = Date.now();
      rollupReady = true;
    } catch (e) {
      console.error('[globals-rollup] Incremental rebuild error:', e);
    } finally {
      rollupRebuildPromise = null;
    }
  })();

  return rollupRebuildPromise;
}

/**
 * Initialize rollup tables on server start.
 * Performs a full rebuild from historical data.
 */
export async function initGlobalsRollups() {
  try {
    await fullRebuild();
    rollupReady = true;
    rollupLastRebuiltAt = Date.now();
    console.log('[globals-rollup] Full rebuild complete');
  } catch (e) {
    console.error('[globals-rollup] Full rebuild failed:', e);
  }

  // Scheduled safety-net refresh
  const scheduleRefresh = () => {
    const jitter = Math.floor(ROLLUP_REBUILD_INTERVAL_MS * (0.9 + Math.random() * 0.2));
    setTimeout(async () => {
      try {
        await rebuildRollups();
      } catch {}
      scheduleRefresh();
    }, jitter).unref();
  };
  scheduleRefresh();
}
