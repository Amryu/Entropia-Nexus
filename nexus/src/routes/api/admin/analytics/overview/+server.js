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
 * GET /api/admin/analytics/overview
 */
export async function GET({ locals, url }) {
  requireAdminAPI(locals);

  const period = url.searchParams.get('period') || '7d';
  const xBots = url.searchParams.get('excludeBots') === 'true';
  const xApi = url.searchParams.get('excludeApi') === 'true';
  const { granularity, startSql } = periodConfig(period);
  const rollupWhere = startSql ? `AND period_start >= ${startSql}` : '';
  const rawWhere = startSql ? `AND visited_at >= ${startSql}` : '';
  const apiFilter = xApi ? `AND route_category != 'api'` : '';

  // For requests: use rollup math (subtract bot_count when excluding bots)
  const reqExpr = xBots ? 'request_count - bot_count' : 'request_count';

  // Unique visitors always from raw for short periods; add bot/api filters
  const useRawForUniques = ['today', '7d', '30d'].includes(period);
  const rawBotFilter = xBots ? 'AND is_bot = false' : '';
  const rawApiFilter = xApi ? 'AND is_api = false' : '';

  // Geo/referrer rollups lack bot breakdown, so use raw data when filtering by bots
  const useRawForGeo = xBots;
  const useRawForReferrers = xBots;

  try {
    const [totals, uniqueResult, topRoutes, topCountries, topReferrers] = await Promise.all([
      // Totals from rollup
      pool.query(
        `SELECT COALESCE(SUM(${reqExpr}), 0)::integer AS total_requests,
                COALESCE(SUM(bot_count), 0)::integer AS bot_requests,
                COALESCE(SUM(rate_limited_count), 0)::integer AS rate_limited,
                COALESCE(SUM(error_count), 0)::integer AS errors,
                CASE WHEN SUM(${reqExpr}) > 0
                  THEN (SUM(COALESCE(avg_response_ms, 0)::bigint * ${reqExpr}) / NULLIF(SUM(CASE WHEN avg_response_ms IS NOT NULL THEN ${reqExpr} ELSE 0 END), 0))::integer
                  ELSE 0 END AS avg_response_ms
         FROM route_analytics_rollup
         WHERE granularity = $1 ${rollupWhere} ${apiFilter}`,
        [granularity]
      ),

      // Unique visitors
      useRawForUniques
        ? pool.query(
            `SELECT count(DISTINCT ip_address)::integer AS unique_visitors
             FROM route_visits
             WHERE true ${rawWhere} ${rawBotFilter} ${rawApiFilter}`
          )
        : pool.query(
            `SELECT COALESCE(SUM(unique_ips), 0)::integer AS unique_visitors
             FROM route_analytics_geo_rollup
             WHERE granularity = $1 ${rollupWhere}`,
            [granularity]
          ),

      // Top 10 routes from rollup
      pool.query(
        `SELECT route_category, route_pattern,
                SUM(${reqExpr})::integer AS requests,
                SUM(unique_ips)::integer AS unique_ips,
                SUM(bot_count)::integer AS bots,
                SUM(error_count)::integer AS errors
         FROM route_analytics_rollup
         WHERE granularity = $1 ${rollupWhere} ${apiFilter}
         GROUP BY route_category, route_pattern
         HAVING SUM(${reqExpr}) > 0
         ORDER BY requests DESC
         LIMIT 10`,
        [granularity]
      ),

      // Top 10 countries
      useRawForGeo
        ? pool.query(
            `SELECT country_code,
                    count(*)::integer AS requests,
                    count(DISTINCT ip_address)::integer AS unique_ips
             FROM route_visits
             WHERE country_code IS NOT NULL ${rawWhere} ${rawBotFilter} ${rawApiFilter}
             GROUP BY country_code
             ORDER BY requests DESC
             LIMIT 10`
          )
        : pool.query(
            `SELECT country_code,
                    SUM(request_count)::integer AS requests,
                    SUM(unique_ips)::integer AS unique_ips
             FROM route_analytics_geo_rollup
             WHERE granularity = $1 ${rollupWhere}
             GROUP BY country_code
             ORDER BY requests DESC
             LIMIT 10`,
            [granularity]
          ),

      // Top 10 referrers
      useRawForReferrers
        ? pool.query(
            `SELECT referrer AS referrer_domain,
                    count(*)::integer AS requests
             FROM route_visits
             WHERE referrer IS NOT NULL ${rawWhere} ${rawBotFilter} ${rawApiFilter}
             GROUP BY referrer
             ORDER BY requests DESC
             LIMIT 10`
          )
        : pool.query(
            `SELECT referrer_domain,
                    SUM(request_count)::integer AS requests
             FROM route_analytics_referrer_rollup
             WHERE granularity = $1 ${rollupWhere}
             GROUP BY referrer_domain
             ORDER BY requests DESC
             LIMIT 10`,
            [granularity]
          )
    ]);

    const t = totals.rows[0];
    const uv = uniqueResult.rows[0]?.unique_visitors || 0;
    // When bots are excluded, bot_requests reflects the excluded count for context
    const botReqs = xBots ? 0 : t.bot_requests;
    const totalReqs = t.total_requests;
    return json({
      totalRequests: totalReqs,
      uniqueVisitors: uv,
      botRequests: botReqs,
      rateLimited: t.rate_limited,
      errors: t.errors,
      avgResponseMs: t.avg_response_ms,
      botPercent: !xBots && totalReqs > 0 ? Math.round((t.bot_requests / (totalReqs + t.bot_requests)) * 100) : 0,
      topRoutes: topRoutes.rows,
      topCountries: topCountries.rows,
      topReferrers: topReferrers.rows,
      filtersActive: xBots || xApi
    });
  } catch (e) {
    console.error('[analytics] Overview error:', e);
    return json({ error: 'Failed to fetch analytics overview' }, { status: 500 });
  }
}
