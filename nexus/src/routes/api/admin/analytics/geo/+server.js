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
 * GET /api/admin/analytics/geo
 * Geographic breakdown by country.
 */
export async function GET({ locals, url }) {
  requireAdminAPI(locals);

  const period = url.searchParams.get('period') || '7d';
  const { granularity, startSql } = periodConfig(period);
  const whereClause = startSql ? `AND period_start >= ${startSql}` : '';

  try {
    const { rows } = await pool.query(
      `SELECT country_code,
              SUM(request_count)::integer AS requests,
              SUM(unique_ips)::integer AS unique_ips
       FROM route_analytics_geo_rollup
       WHERE granularity = $1 ${whereClause}
       GROUP BY country_code
       ORDER BY requests DESC`,
      [granularity]
    );

    return json({ countries: rows });
  } catch (e) {
    console.error('[analytics] Geo error:', e);
    return json({ error: 'Failed to fetch geographic data' }, { status: 500 });
  }
}
