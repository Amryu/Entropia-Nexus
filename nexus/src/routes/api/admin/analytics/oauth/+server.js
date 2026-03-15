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
 * GET /api/admin/analytics/oauth
 * OAuth client usage breakdown.
 */
export async function GET({ locals, url }) {
  requireAdminAPI(locals);

  const period = url.searchParams.get('period') || '7d';
  const { granularity, startSql } = periodConfig(period);
  const whereClause = startSql ? `AND r.period_start >= ${startSql}` : '';

  try {
    // Per-client summary
    const { rows: clients } = await pool.query(
      `SELECT r.oauth_client_id,
              c.name AS client_name,
              SUM(r.request_count)::integer AS requests,
              SUM(r.rate_limited_count)::integer AS rate_limited,
              count(DISTINCT r.route_pattern)::integer AS routes_used
       FROM route_analytics_oauth_rollup r
       LEFT JOIN oauth_clients c ON c.id::text = r.oauth_client_id
       WHERE r.granularity = $1 ${whereClause}
       GROUP BY r.oauth_client_id, c.name
       ORDER BY requests DESC`,
      [granularity]
    );

    // Per-client per-route breakdown (top 50)
    const { rows: details } = await pool.query(
      `SELECT r.oauth_client_id,
              c.name AS client_name,
              r.route_pattern,
              SUM(r.request_count)::integer AS requests,
              SUM(r.rate_limited_count)::integer AS rate_limited
       FROM route_analytics_oauth_rollup r
       LEFT JOIN oauth_clients c ON c.id::text = r.oauth_client_id
       WHERE r.granularity = $1 ${whereClause}
       GROUP BY r.oauth_client_id, c.name, r.route_pattern
       ORDER BY requests DESC
       LIMIT 50`,
      [granularity]
    );

    return json({ clients, details });
  } catch (e) {
    console.error('[analytics] OAuth error:', e);
    return json({ error: 'Failed to fetch OAuth analytics' }, { status: 500 });
  }
}
