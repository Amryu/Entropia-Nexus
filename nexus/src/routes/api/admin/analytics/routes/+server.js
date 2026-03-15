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
 * GET /api/admin/analytics/routes
 */
export async function GET({ locals, url }) {
  requireAdminAPI(locals);

  const period = url.searchParams.get('period') || '7d';
  const category = url.searchParams.get('category') || null;
  const xBots = url.searchParams.get('excludeBots') === 'true';
  const xApi = url.searchParams.get('excludeApi') === 'true';
  const page = Math.max(1, parseInt(url.searchParams.get('page') || '1', 10));
  const limit = Math.min(100, Math.max(1, parseInt(url.searchParams.get('limit') || '50', 10)));
  const offset = (page - 1) * limit;

  const { granularity, startSql } = periodConfig(period);
  const whereClause = startSql ? `AND period_start >= ${startSql}` : '';
  const categoryFilter = category ? 'AND route_category = $2' : '';
  const apiFilter = !category && xApi ? `AND route_category != 'api'` : '';
  const params = category ? [granularity, category] : [granularity];
  const reqExpr = xBots ? 'request_count - bot_count' : 'request_count';

  try {
    const [routes, countResult, categories] = await Promise.all([
      pool.query(
        `SELECT route_category, route_pattern,
                SUM(${reqExpr})::integer AS requests,
                SUM(unique_ips)::integer AS unique_ips,
                SUM(bot_count)::integer AS bots,
                SUM(rate_limited_count)::integer AS rate_limited,
                SUM(error_count)::integer AS errors,
                CASE WHEN SUM(${reqExpr}) > 0
                  THEN (SUM(COALESCE(avg_response_ms, 0)::bigint * ${reqExpr}) / NULLIF(SUM(CASE WHEN avg_response_ms IS NOT NULL THEN ${reqExpr} ELSE 0 END), 0))::integer
                  ELSE 0 END AS avg_response_ms
         FROM route_analytics_rollup
         WHERE granularity = $1 ${whereClause} ${categoryFilter} ${apiFilter}
         GROUP BY route_category, route_pattern
         HAVING SUM(${reqExpr}) > 0
         ORDER BY requests DESC
         LIMIT ${limit} OFFSET ${offset}`,
        params
      ),
      pool.query(
        `SELECT count(*)::integer AS total FROM (
           SELECT 1 FROM route_analytics_rollup
           WHERE granularity = $1 ${whereClause} ${categoryFilter} ${apiFilter}
           GROUP BY route_category, route_pattern
           HAVING SUM(${reqExpr}) > 0
         ) sub`,
        params
      ),
      pool.query(
        `SELECT route_category,
                SUM(${reqExpr})::integer AS requests,
                SUM(unique_ips)::integer AS unique_ips,
                SUM(bot_count)::integer AS bots
         FROM route_analytics_rollup
         WHERE granularity = $1 ${whereClause} ${apiFilter}
         GROUP BY route_category
         HAVING SUM(${reqExpr}) > 0
         ORDER BY requests DESC`,
        [granularity]
      )
    ]);

    return json({
      routes: routes.rows,
      total: countResult.rows[0]?.total || 0,
      page,
      totalPages: Math.max(1, Math.ceil((countResult.rows[0]?.total || 0) / limit)),
      categories: categories.rows
    });
  } catch (e) {
    console.error('[analytics] Routes error:', e);
    return json({ error: 'Failed to fetch route analytics' }, { status: 500 });
  }
}
