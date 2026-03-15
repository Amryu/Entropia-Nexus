// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth.js';
import { pool } from '$lib/server/db.js';

/**
 * Map period param to rollup granularity and SQL interval.
 */
function periodConfig(period) {
  switch (period) {
    case 'today':  return { granularity: 'daily',   interval: "interval '1 day'",   startSql: "date_trunc('day', now())" };
    case '7d':     return { granularity: 'daily',   interval: "interval '7 days'",  startSql: "date_trunc('day', now() - interval '6 days')" };
    case '30d':    return { granularity: 'daily',   interval: "interval '30 days'", startSql: "date_trunc('day', now() - interval '29 days')" };
    case '90d':    return { granularity: 'weekly',  interval: "interval '90 days'", startSql: "date_trunc('day', now() - interval '89 days')" };
    case '1y':     return { granularity: 'monthly', interval: "interval '1 year'",  startSql: "date_trunc('day', now() - interval '1 year')" };
    case 'all':    return { granularity: 'monthly', interval: null,                 startSql: null };
    default:       return { granularity: 'daily',   interval: "interval '7 days'",  startSql: "date_trunc('day', now() - interval '6 days')" };
  }
}

/**
 * GET /api/admin/analytics/overview
 * Summary stats for the selected period.
 */
export async function GET({ locals, url }) {
  requireAdminAPI(locals);

  const period = url.searchParams.get('period') || '7d';
  const { granularity, startSql } = periodConfig(period);
  const whereClause = startSql ? `AND period_start >= ${startSql}` : '';

  // For unique visitors we need a true distinct count — the rollup's unique_ips
  // is per-route and not additive across routes.  Query raw table for short periods,
  // fall back to geo rollup (per-country unique_ips is closer) for long ones.
  const useRawForUniques = ['today', '7d', '30d'].includes(period);
  const rawWhereClause = startSql ? `AND visited_at >= ${startSql}` : '';

  try {
    const [totals, uniqueResult, topRoutes, topCountries, topReferrers] = await Promise.all([
      // Aggregate totals from rollup
      pool.query(
        `SELECT COALESCE(SUM(request_count), 0)::integer AS total_requests,
                COALESCE(SUM(bot_count), 0)::integer AS bot_requests,
                COALESCE(SUM(rate_limited_count), 0)::integer AS rate_limited,
                COALESCE(SUM(error_count), 0)::integer AS errors,
                CASE WHEN SUM(request_count) > 0
                  THEN (SUM(COALESCE(avg_response_ms, 0)::bigint * request_count) / NULLIF(SUM(CASE WHEN avg_response_ms IS NOT NULL THEN request_count ELSE 0 END), 0))::integer
                  ELSE 0 END AS avg_response_ms
         FROM route_analytics_rollup
         WHERE granularity = $1 ${whereClause}`,
        [granularity]
      ),
      // True unique visitor count (from raw table for short periods;
      // bounded by 30-day retention so at most ~3M rows scanned)
      useRawForUniques
        ? pool.query(
            `SELECT count(DISTINCT ip_address)::integer AS unique_visitors
             FROM route_visits
             WHERE true ${rawWhereClause}`
          )
        : pool.query(
            `SELECT COALESCE(SUM(unique_ips), 0)::integer AS unique_visitors
             FROM route_analytics_geo_rollup
             WHERE granularity = $1 ${whereClause}`,
            [granularity]
          ),
      // Top 10 routes
      pool.query(
        `SELECT route_category, route_pattern,
                SUM(request_count)::integer AS requests,
                SUM(unique_ips)::integer AS unique_ips,
                SUM(bot_count)::integer AS bots,
                SUM(error_count)::integer AS errors
         FROM route_analytics_rollup
         WHERE granularity = $1 ${whereClause}
         GROUP BY route_category, route_pattern
         ORDER BY requests DESC
         LIMIT 10`,
        [granularity]
      ),
      // Top 10 countries
      pool.query(
        `SELECT country_code,
                SUM(request_count)::integer AS requests,
                SUM(unique_ips)::integer AS unique_ips
         FROM route_analytics_geo_rollup
         WHERE granularity = $1 ${whereClause}
         GROUP BY country_code
         ORDER BY requests DESC
         LIMIT 10`,
        [granularity]
      ),
      // Top 10 referrers
      pool.query(
        `SELECT referrer_domain,
                SUM(request_count)::integer AS requests
         FROM route_analytics_referrer_rollup
         WHERE granularity = $1 ${whereClause}
         GROUP BY referrer_domain
         ORDER BY requests DESC
         LIMIT 10`,
        [granularity]
      )
    ]);

    const t = totals.rows[0];
    const uv = uniqueResult.rows[0]?.unique_visitors || 0;
    return json({
      totalRequests: t.total_requests,
      uniqueVisitors: uv,
      botRequests: t.bot_requests,
      rateLimited: t.rate_limited,
      errors: t.errors,
      avgResponseMs: t.avg_response_ms,
      botPercent: t.total_requests > 0 ? Math.round((t.bot_requests / t.total_requests) * 100) : 0,
      topRoutes: topRoutes.rows,
      topCountries: topCountries.rows,
      topReferrers: topReferrers.rows
    });
  } catch (e) {
    console.error('[analytics] Overview error:', e);
    return json({ error: 'Failed to fetch analytics overview' }, { status: 500 });
  }
}
