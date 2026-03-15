// @ts-nocheck
/**
 * Route analytics rollup engine.
 *
 * Maintains pre-aggregated rollup tables at daily, weekly, monthly, quarterly,
 * and yearly granularities (following the globals-rollup.js pattern).
 *
 * Rebuild strategy:
 *   - Daily:  from raw route_visits (today + yesterday)
 *   - Coarse: aggregated FROM daily rollup
 *   - Full rebuild on startup, incremental every 15 minutes
 */
import { pool } from '$lib/server/db.js';

// --- Timing ---
const ROLLUP_INTERVAL_MS = 15 * 60_000;    // 15 min safety-net refresh
const ROLLUP_MIN_GAP_MS = 5 * 60_000;      // min 5 min between rebuilds

// --- State ---
let rollupReady = false;
let rollupPromise = null;
let rollupLastRebuiltAt = 0;

// --- Granularity config ---
const COARSE_GRANULARITIES = [
  { granularity: 'weekly', truncUnit: 'week' },
  { granularity: 'monthly', truncUnit: 'month' },
  { granularity: 'quarterly', truncUnit: 'quarter' },
  { granularity: 'yearly', truncUnit: 'year' },
];

// ------------------------------------------------------------------
// Daily rollup (from raw route_visits)
// ------------------------------------------------------------------

async function rebuildDailyRange(startDate, endDate) {
  const client = await pool.connect();
  try {
    await client.query('SET statement_timeout = 120000');
    await client.query('BEGIN');

    // Route rollup
    await client.query(
      `DELETE FROM route_analytics_rollup
       WHERE granularity = 'daily' AND period_start >= $1 AND period_start < $2`,
      [startDate, endDate]
    );
    await client.query(
      `INSERT INTO route_analytics_rollup
         (granularity, period_start, route_category, route_pattern, request_count, unique_ips, bot_count, rate_limited_count, error_count, avg_response_ms)
       SELECT 'daily', date_trunc('day', visited_at), route_category, route_pattern,
              count(*),
              count(DISTINCT ip_address),
              count(*) FILTER (WHERE is_bot),
              count(*) FILTER (WHERE rate_limited),
              count(*) FILTER (WHERE status_code >= 400),
              avg(response_time_ms)::integer
       FROM route_visits
       WHERE visited_at >= $1 AND visited_at < $2
       GROUP BY date_trunc('day', visited_at), route_category, route_pattern
       ON CONFLICT (granularity, period_start, route_category, route_pattern) DO UPDATE SET
         request_count = EXCLUDED.request_count,
         unique_ips = EXCLUDED.unique_ips,
         bot_count = EXCLUDED.bot_count,
         rate_limited_count = EXCLUDED.rate_limited_count,
         error_count = EXCLUDED.error_count,
         avg_response_ms = EXCLUDED.avg_response_ms`,
      [startDate, endDate]
    );

    // Geo rollup
    await client.query(
      `DELETE FROM route_analytics_geo_rollup
       WHERE granularity = 'daily' AND period_start >= $1 AND period_start < $2`,
      [startDate, endDate]
    );
    await client.query(
      `INSERT INTO route_analytics_geo_rollup
         (granularity, period_start, country_code, request_count, unique_ips)
       SELECT 'daily', date_trunc('day', visited_at), country_code,
              count(*), count(DISTINCT ip_address)
       FROM route_visits
       WHERE visited_at >= $1 AND visited_at < $2 AND country_code IS NOT NULL
       GROUP BY date_trunc('day', visited_at), country_code
       ON CONFLICT (granularity, period_start, country_code) DO UPDATE SET
         request_count = EXCLUDED.request_count,
         unique_ips = EXCLUDED.unique_ips`,
      [startDate, endDate]
    );

    // OAuth rollup
    await client.query(
      `DELETE FROM route_analytics_oauth_rollup
       WHERE granularity = 'daily' AND period_start >= $1 AND period_start < $2`,
      [startDate, endDate]
    );
    await client.query(
      `INSERT INTO route_analytics_oauth_rollup
         (granularity, period_start, oauth_client_id, route_pattern, request_count, rate_limited_count)
       SELECT 'daily', date_trunc('day', visited_at), oauth_client_id, route_pattern,
              count(*),
              count(*) FILTER (WHERE rate_limited)
       FROM route_visits
       WHERE visited_at >= $1 AND visited_at < $2 AND oauth_client_id IS NOT NULL
       GROUP BY date_trunc('day', visited_at), oauth_client_id, route_pattern
       ON CONFLICT (granularity, period_start, oauth_client_id, route_pattern) DO UPDATE SET
         request_count = EXCLUDED.request_count,
         rate_limited_count = EXCLUDED.rate_limited_count`,
      [startDate, endDate]
    );

    // Referrer rollup
    await client.query(
      `DELETE FROM route_analytics_referrer_rollup
       WHERE granularity = 'daily' AND period_start >= $1 AND period_start < $2`,
      [startDate, endDate]
    );
    await client.query(
      `INSERT INTO route_analytics_referrer_rollup
         (granularity, period_start, referrer_domain, request_count)
       SELECT 'daily', date_trunc('day', visited_at), referrer,
              count(*)
       FROM route_visits
       WHERE visited_at >= $1 AND visited_at < $2 AND referrer IS NOT NULL
       GROUP BY date_trunc('day', visited_at), referrer
       ON CONFLICT (granularity, period_start, referrer_domain) DO UPDATE SET
         request_count = EXCLUDED.request_count`,
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

async function rebuildCoarseGranularity(granularity, truncUnit, startDate, endDate) {
  const client = await pool.connect();
  try {
    await client.query('SET statement_timeout = 60000');
    await client.query('BEGIN');

    const rangeFilter = startDate && endDate
      ? ` AND date_trunc('${truncUnit}', period_start) >= date_trunc('${truncUnit}', '${startDate.toISOString()}'::timestamptz)
          AND date_trunc('${truncUnit}', period_start) <= date_trunc('${truncUnit}', '${endDate.toISOString()}'::timestamptz)`
      : '';

    // Route rollup
    await client.query(
      `DELETE FROM route_analytics_rollup WHERE granularity = $1${startDate ? ` AND period_start >= date_trunc('${truncUnit}', $2::timestamptz) AND period_start <= date_trunc('${truncUnit}', $3::timestamptz)` : ''}`,
      startDate ? [granularity, startDate, endDate] : [granularity]
    );
    await client.query(
      `INSERT INTO route_analytics_rollup
         (granularity, period_start, route_category, route_pattern, request_count, unique_ips, bot_count, rate_limited_count, error_count, avg_response_ms)
       SELECT $1, date_trunc('${truncUnit}', period_start), route_category, route_pattern,
              SUM(request_count),
              SUM(unique_ips),   -- NOTE: approximate for coarse granularities (IPs across days are double-counted)
              SUM(bot_count), SUM(rate_limited_count), SUM(error_count),
              CASE WHEN SUM(request_count) > 0
                THEN (SUM(COALESCE(avg_response_ms, 0)::bigint * request_count) / NULLIF(SUM(CASE WHEN avg_response_ms IS NOT NULL THEN request_count ELSE 0 END), 0))::integer
              END
       FROM route_analytics_rollup
       WHERE granularity = 'daily'${rangeFilter}
       GROUP BY date_trunc('${truncUnit}', period_start), route_category, route_pattern
       ON CONFLICT (granularity, period_start, route_category, route_pattern) DO UPDATE SET
         request_count = EXCLUDED.request_count, unique_ips = EXCLUDED.unique_ips,
         bot_count = EXCLUDED.bot_count, rate_limited_count = EXCLUDED.rate_limited_count,
         error_count = EXCLUDED.error_count, avg_response_ms = EXCLUDED.avg_response_ms`,
      [granularity]
    );

    // Geo rollup
    await client.query(
      `DELETE FROM route_analytics_geo_rollup WHERE granularity = $1${startDate ? ` AND period_start >= date_trunc('${truncUnit}', $2::timestamptz) AND period_start <= date_trunc('${truncUnit}', $3::timestamptz)` : ''}`,
      startDate ? [granularity, startDate, endDate] : [granularity]
    );
    await client.query(
      `INSERT INTO route_analytics_geo_rollup
         (granularity, period_start, country_code, request_count, unique_ips)
       SELECT $1, date_trunc('${truncUnit}', period_start), country_code,
              SUM(request_count),
              SUM(unique_ips)   -- NOTE: approximate for coarse granularities
       FROM route_analytics_geo_rollup
       WHERE granularity = 'daily'${rangeFilter}
       GROUP BY date_trunc('${truncUnit}', period_start), country_code
       ON CONFLICT (granularity, period_start, country_code) DO UPDATE SET
         request_count = EXCLUDED.request_count, unique_ips = EXCLUDED.unique_ips`,
      [granularity]
    );

    // OAuth rollup
    await client.query(
      `DELETE FROM route_analytics_oauth_rollup WHERE granularity = $1${startDate ? ` AND period_start >= date_trunc('${truncUnit}', $2::timestamptz) AND period_start <= date_trunc('${truncUnit}', $3::timestamptz)` : ''}`,
      startDate ? [granularity, startDate, endDate] : [granularity]
    );
    await client.query(
      `INSERT INTO route_analytics_oauth_rollup
         (granularity, period_start, oauth_client_id, route_pattern, request_count, rate_limited_count)
       SELECT $1, date_trunc('${truncUnit}', period_start), oauth_client_id, route_pattern,
              SUM(request_count), SUM(rate_limited_count)
       FROM route_analytics_oauth_rollup
       WHERE granularity = 'daily'${rangeFilter}
       GROUP BY date_trunc('${truncUnit}', period_start), oauth_client_id, route_pattern
       ON CONFLICT (granularity, period_start, oauth_client_id, route_pattern) DO UPDATE SET
         request_count = EXCLUDED.request_count, rate_limited_count = EXCLUDED.rate_limited_count`,
      [granularity]
    );

    // Referrer rollup
    await client.query(
      `DELETE FROM route_analytics_referrer_rollup WHERE granularity = $1${startDate ? ` AND period_start >= date_trunc('${truncUnit}', $2::timestamptz) AND period_start <= date_trunc('${truncUnit}', $3::timestamptz)` : ''}`,
      startDate ? [granularity, startDate, endDate] : [granularity]
    );
    await client.query(
      `INSERT INTO route_analytics_referrer_rollup
         (granularity, period_start, referrer_domain, request_count)
       SELECT $1, date_trunc('${truncUnit}', period_start), referrer_domain,
              SUM(request_count)
       FROM route_analytics_referrer_rollup
       WHERE granularity = 'daily'${rangeFilter}
       GROUP BY date_trunc('${truncUnit}', period_start), referrer_domain
       ON CONFLICT (granularity, period_start, referrer_domain) DO UPDATE SET
         request_count = EXCLUDED.request_count`,
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
  const { rows } = await pool.query(
    `SELECT 1 FROM information_schema.tables WHERE table_name = 'route_visits' LIMIT 1`
  );
  if (rows.length === 0) return;

  // Find earliest visit
  const { rows: minRows } = await pool.query(
    `SELECT MIN(visited_at) AS min_ts FROM route_visits`
  );
  if (!minRows[0]?.min_ts) return; // no data yet

  const minDate = new Date(minRows[0].min_ts);
  minDate.setUTCHours(0, 0, 0, 0);

  const tomorrow = new Date();
  tomorrow.setUTCDate(tomorrow.getUTCDate() + 1);
  tomorrow.setUTCHours(0, 0, 0, 0);

  // Rebuild daily in 30-day chunks
  const CHUNK_DAYS = 30;
  let chunkStart = new Date(minDate);
  while (chunkStart < tomorrow) {
    const chunkEnd = new Date(Math.min(
      chunkStart.getTime() + CHUNK_DAYS * 24 * 60 * 60 * 1000,
      tomorrow.getTime()
    ));
    await rebuildDailyRange(chunkStart, chunkEnd);
    chunkStart = chunkEnd;
  }

  // Rebuild coarse from daily
  for (const { granularity, truncUnit } of COARSE_GRANULARITIES) {
    await rebuildCoarseGranularity(granularity, truncUnit);
  }
}

// ------------------------------------------------------------------
// Incremental rebuild
// ------------------------------------------------------------------

async function incrementalRebuild() {
  const { rows } = await pool.query(
    `SELECT 1 FROM information_schema.tables WHERE table_name = 'route_visits' LIMIT 1`
  );
  if (rows.length === 0) return;

  const yesterday = new Date();
  yesterday.setUTCDate(yesterday.getUTCDate() - 1);
  yesterday.setUTCHours(0, 0, 0, 0);

  const tomorrow = new Date();
  tomorrow.setUTCDate(tomorrow.getUTCDate() + 1);
  tomorrow.setUTCHours(0, 0, 0, 0);

  await rebuildDailyRange(yesterday, tomorrow);

  for (const { granularity, truncUnit } of COARSE_GRANULARITIES) {
    await rebuildCoarseGranularity(granularity, truncUnit, yesterday, tomorrow);
  }
}

// ------------------------------------------------------------------
// Public API
// ------------------------------------------------------------------

export function isRollupReady() {
  return rollupReady;
}

export async function rebuildRollups() {
  const now = Date.now();
  if (now - rollupLastRebuiltAt < ROLLUP_MIN_GAP_MS) return;
  if (rollupPromise) return rollupPromise;

  rollupPromise = (async () => {
    try {
      await incrementalRebuild();
      rollupLastRebuiltAt = Date.now();
      rollupReady = true;
    } catch (e) {
      console.error('[route-analytics-rollup] Incremental rebuild error:', e);
    } finally {
      rollupPromise = null;
    }
  })();

  return rollupPromise;
}

export async function initRouteAnalyticsRollups() {
  try {
    await fullRebuild();
    rollupReady = true;
    rollupLastRebuiltAt = Date.now();
    console.log('[route-analytics-rollup] Full rebuild complete');
  } catch (e) {
    console.error('[route-analytics-rollup] Full rebuild failed:', e);
  }

  // Scheduled refresh
  const scheduleRefresh = () => {
    const jitter = Math.floor(ROLLUP_INTERVAL_MS * (0.9 + Math.random() * 0.2));
    setTimeout(async () => {
      try {
        await rebuildRollups();
      } catch {}
      scheduleRefresh();
    }, jitter).unref();
  };
  scheduleRefresh();
}
