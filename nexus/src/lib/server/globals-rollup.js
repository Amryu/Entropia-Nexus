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
       GROUP BY date_trunc('day', event_timestamp), global_type`,
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
       GROUP BY date_trunc('day', event_timestamp), player_name, global_type`,
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
       GROUP BY date_trunc('day', event_timestamp), target_name, global_type`,
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
      `DELETE FROM globals_rollup WHERE granularity = $1${startDate ? ` AND period_start >= date_trunc('${truncUnit}', $2) AND period_start <= date_trunc('${truncUnit}', $3)` : ''}`,
      startDate ? [granularity, startDate, endDate] : [granularity]
    );
    await client.query(
      `INSERT INTO globals_rollup (granularity, period_start, global_type, event_count, sum_value, max_value, hof_count, ath_count)
       SELECT $1, date_trunc('${truncUnit}', period_start), global_type,
              SUM(event_count), SUM(sum_value), MAX(max_value), SUM(hof_count), SUM(ath_count)
       FROM globals_rollup
       WHERE granularity = 'daily'${coarseRangeFilter}
       GROUP BY date_trunc('${truncUnit}', period_start), global_type`,
      [granularity]
    );

    // globals_rollup_player
    await client.query(
      `DELETE FROM globals_rollup_player WHERE granularity = $1${startDate ? ` AND period_start >= date_trunc('${truncUnit}', $2) AND period_start <= date_trunc('${truncUnit}', $3)` : ''}`,
      startDate ? [granularity, startDate, endDate] : [granularity]
    );
    await client.query(
      `INSERT INTO globals_rollup_player (granularity, period_start, player_name, global_type, event_count, sum_value, max_value, hof_count, ath_count)
       SELECT $1, date_trunc('${truncUnit}', period_start), player_name, global_type,
              SUM(event_count), SUM(sum_value), MAX(max_value), SUM(hof_count), SUM(ath_count)
       FROM globals_rollup_player
       WHERE granularity = 'daily'${coarseRangeFilter}
       GROUP BY date_trunc('${truncUnit}', period_start), player_name, global_type`,
      [granularity]
    );

    // globals_rollup_target
    await client.query(
      `DELETE FROM globals_rollup_target WHERE granularity = $1${startDate ? ` AND period_start >= date_trunc('${truncUnit}', $2) AND period_start <= date_trunc('${truncUnit}', $3)` : ''}`,
      startDate ? [granularity, startDate, endDate] : [granularity]
    );
    await client.query(
      `INSERT INTO globals_rollup_target (granularity, period_start, target_name, mob_id, global_type, event_count, sum_value, max_value, hof_count, ath_count)
       SELECT $1, date_trunc('${truncUnit}', period_start), target_name, MAX(mob_id), global_type,
              SUM(event_count), SUM(sum_value), MAX(max_value), SUM(hof_count), SUM(ath_count)
       FROM globals_rollup_target
       WHERE granularity = 'daily'${coarseRangeFilter}
       GROUP BY date_trunc('${truncUnit}', period_start), target_name, global_type`,
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
  // Delay full rebuild to avoid starving concurrent queries during server startup
  setTimeout(async () => {
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
  }, 10_000).unref(); // 10s delay for server to stabilize
}
