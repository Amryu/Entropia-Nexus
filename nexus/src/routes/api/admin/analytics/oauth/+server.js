// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth.js';
import { pool } from '$lib/server/db.js';

function periodConfig(period) {
  switch (period) {
    case '1h':     return { granularity: 'raw',     startSql: "now() - interval '1 hour'" };
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
 */
export async function GET({ locals, url }) {
  requireAdminAPI(locals);

  const period = url.searchParams.get('period') || '7d';
  const { granularity, startSql } = periodConfig(period);
  const useRaw = granularity === 'raw';

  try {
    let clients, details;

    if (useRaw) {
      const rawWhere = `AND visited_at >= ${startSql}`;
      ({ rows: clients } = await pool.query(
        `SELECT v.oauth_client_id,
                c.name AS client_name,
                count(*)::integer AS requests,
                count(*) FILTER (WHERE v.rate_limited)::integer AS rate_limited,
                count(DISTINCT v.route_pattern)::integer AS routes_used
         FROM route_visits v
         LEFT JOIN oauth_clients c ON c.id::text = v.oauth_client_id
         WHERE v.oauth_client_id IS NOT NULL ${rawWhere}
         GROUP BY v.oauth_client_id, c.name
         ORDER BY requests DESC`
      ));
      ({ rows: details } = await pool.query(
        `SELECT v.oauth_client_id,
                c.name AS client_name,
                v.route_pattern,
                count(*)::integer AS requests,
                count(*) FILTER (WHERE v.rate_limited)::integer AS rate_limited
         FROM route_visits v
         LEFT JOIN oauth_clients c ON c.id::text = v.oauth_client_id
         WHERE v.oauth_client_id IS NOT NULL ${rawWhere}
         GROUP BY v.oauth_client_id, c.name, v.route_pattern
         ORDER BY requests DESC
         LIMIT 50`
      ));
    } else {
      const rollupWhere = startSql ? `AND r.period_start >= ${startSql}` : '';
      ({ rows: clients } = await pool.query(
        `SELECT r.oauth_client_id,
                c.name AS client_name,
                SUM(r.request_count)::integer AS requests,
                SUM(r.rate_limited_count)::integer AS rate_limited,
                count(DISTINCT r.route_pattern)::integer AS routes_used
         FROM route_analytics_oauth_rollup r
         LEFT JOIN oauth_clients c ON c.id::text = r.oauth_client_id
         WHERE r.granularity = $1 ${rollupWhere}
         GROUP BY r.oauth_client_id, c.name
         ORDER BY requests DESC`,
        [granularity]
      ));
      ({ rows: details } = await pool.query(
        `SELECT r.oauth_client_id,
                c.name AS client_name,
                r.route_pattern,
                SUM(r.request_count)::integer AS requests,
                SUM(r.rate_limited_count)::integer AS rate_limited
         FROM route_analytics_oauth_rollup r
         LEFT JOIN oauth_clients c ON c.id::text = r.oauth_client_id
         WHERE r.granularity = $1 ${rollupWhere}
         GROUP BY r.oauth_client_id, c.name, r.route_pattern
         ORDER BY requests DESC
         LIMIT 50`,
        [granularity]
      ));
    }

    return json({ clients, details });
  } catch (e) {
    console.error('[analytics] OAuth error:', e);
    return json({ error: 'Failed to fetch OAuth analytics' }, { status: 500 });
  }
}
