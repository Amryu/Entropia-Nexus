// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth.js';
import { pool } from '$lib/server/db.js';

function periodConfig(period) {
  switch (period) {
    case 'today':  return { granularity: 'daily',   startSql: "date_trunc('day', now())" };
    case '7d':     return { granularity: 'daily',   startSql: "date_trunc('day', now() - interval '6 days')" };
    case '30d':    return { granularity: 'daily',   startSql: "date_trunc('day', now() - interval '29 days')" };
    case '90d':    return { granularity: 'weekly',  startSql: "date_trunc('day', now() - interval '89 days')" };
    case '1y':     return { granularity: 'monthly', startSql: "date_trunc('day', now() - interval '1 year')" };
    case 'all':    return { granularity: 'monthly', startSql: null };
    default:       return { granularity: 'daily',   startSql: "date_trunc('day', now() - interval '6 days')" };
  }
}

/**
 * GET /api/admin/analytics/timeseries
 * Time-series data points for charting.
 */
export async function GET({ locals, url }) {
  requireAdminAPI(locals);

  const period = url.searchParams.get('period') || '7d';
  const category = url.searchParams.get('category') || null;
  const { granularity, startSql } = periodConfig(period);
  const whereClause = startSql ? `AND period_start >= ${startSql}` : '';
  const categoryFilter = category ? `AND route_category = $2` : '';
  const params = category ? [granularity, category] : [granularity];

  try {
    const { rows } = await pool.query(
      `SELECT period_start AS date,
              SUM(request_count)::integer AS requests,
              SUM(unique_ips)::integer AS unique_ips,
              SUM(bot_count)::integer AS bots,
              SUM(error_count)::integer AS errors,
              CASE WHEN SUM(request_count) > 0
                THEN (SUM(COALESCE(avg_response_ms, 0)::bigint * request_count) / NULLIF(SUM(CASE WHEN avg_response_ms IS NOT NULL THEN request_count ELSE 0 END), 0))::integer
                ELSE 0 END AS avg_response_ms
       FROM route_analytics_rollup
       WHERE granularity = $1 ${whereClause} ${categoryFilter}
       GROUP BY period_start
       ORDER BY period_start ASC`,
      params
    );

    return json({ points: rows, granularity });
  } catch (e) {
    console.error('[analytics] Timeseries error:', e);
    return json({ error: 'Failed to fetch timeseries data' }, { status: 500 });
  }
}
