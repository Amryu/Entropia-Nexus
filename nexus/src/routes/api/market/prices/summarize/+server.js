//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { pool } from '$lib/server/db.js';

const VALID_PERIOD_TYPES = ['hour', 'day', 'week'];

/**
 * Truncate a timestamp to the start of its period bucket.
 */
function periodTruncSql(periodType) {
  switch (periodType) {
    case 'hour': return `date_trunc('hour', recorded_at)`;
    case 'day': return `date_trunc('day', recorded_at)`;
    case 'week': return `date_trunc('week', recorded_at)`;
    default: throw new Error(`Unknown period type: ${periodType}`);
  }
}

/**
 * Get the current period boundary (start of the current incomplete period).
 * We only summarize complete periods.
 */
function currentBoundarySql(periodType) {
  switch (periodType) {
    case 'hour': return `date_trunc('hour', now())`;
    case 'day': return `date_trunc('day', now())`;
    case 'week': return `date_trunc('week', now())`;
    default: throw new Error(`Unknown period type: ${periodType}`);
  }
}

async function computeSummaries(periodType) {
  // Read watermark
  const wmResult = await pool.query(
    'SELECT last_computed_until FROM item_price_summary_watermarks WHERE period_type = $1',
    [periodType]
  );
  const watermark = wmResult.rows[0]?.last_computed_until;

  // Get the boundary — only summarize complete periods
  const boundaryResult = await pool.query(`SELECT ${currentBoundarySql(periodType)} AS boundary`);
  const boundary = boundaryResult.rows[0].boundary;

  if (!boundary) return { period_type: periodType, processed: 0 };

  // If watermark exists and is at or beyond boundary, nothing to do
  if (watermark && new Date(watermark) >= new Date(boundary)) {
    return { period_type: periodType, processed: 0 };
  }

  const periodTrunc = periodTruncSql(periodType);

  // Build the aggregation query
  const conditions = ['recorded_at < $1'];
  const values = [boundary];
  let idx = 2;

  if (watermark) {
    conditions.push(`recorded_at >= $${idx}`);
    values.push(watermark);
    idx++;
  }

  const query = `
    INSERT INTO item_price_summaries (
      item_id, source, period_type, period_start,
      price_min, price_max, price_avg,
      price_p5, price_median, price_p95,
      price_wap, volume, sample_count, computed_at
    )
    SELECT
      item_id,
      source,
      '${periodType}'::price_period_type,
      ${periodTrunc} AS period_start,
      MIN(price_value),
      MAX(price_value),
      AVG(price_value),
      PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY price_value),
      PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_value),
      PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY price_value),
      SUM(price_value * quantity) / NULLIF(SUM(quantity), 0),
      SUM(quantity),
      COUNT(*),
      now()
    FROM item_prices
    WHERE ${conditions.join(' AND ')}
    GROUP BY item_id, source, ${periodTrunc}
    ON CONFLICT (item_id, COALESCE(source, ''), period_type, period_start)
    DO UPDATE SET
      price_min = EXCLUDED.price_min,
      price_max = EXCLUDED.price_max,
      price_avg = EXCLUDED.price_avg,
      price_p5 = EXCLUDED.price_p5,
      price_median = EXCLUDED.price_median,
      price_p95 = EXCLUDED.price_p95,
      price_wap = EXCLUDED.price_wap,
      volume = EXCLUDED.volume,
      sample_count = EXCLUDED.sample_count,
      computed_at = EXCLUDED.computed_at
  `;

  const result = await pool.query(query, values);

  // Update watermark
  await pool.query(
    `UPDATE item_price_summary_watermarks
     SET last_computed_until = $1, last_run_at = now()
     WHERE period_type = $2`,
    [boundary, periodType]
  );

  return { period_type: periodType, processed: result.rowCount };
}

export async function POST({ request, locals }) {
  const user = locals.session?.realUser || locals.session?.user;

  if (!user) {
    return getResponse({ error: 'Not authenticated' }, 401);
  }
  if (!user?.grants?.includes('admin.panel')) {
    return getResponse({ error: 'Only administrators can trigger summary computation' }, 403);
  }

  let body = {};
  try {
    body = await request.json();
  } catch {
    // Empty body is fine — compute all periods
  }

  const periodTypes = body?.period_type
    ? [body.period_type]
    : VALID_PERIOD_TYPES;

  for (const pt of periodTypes) {
    if (!VALID_PERIOD_TYPES.includes(pt)) {
      return getResponse({ error: `Invalid period_type: ${pt}. Must be one of: ${VALID_PERIOD_TYPES.join(', ')}` }, 400);
    }
  }

  try {
    const results = [];
    for (const pt of periodTypes) {
      results.push(await computeSummaries(pt));
    }
    return getResponse({ results }, 200);
  } catch (error) {
    console.error('Error computing price summaries:', error);
    return getResponse({ error: 'Failed to compute summaries' }, 500);
  }
}
