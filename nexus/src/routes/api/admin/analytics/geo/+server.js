// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth.js';
import { pool } from '$lib/server/db.js';

function periodConfig(period) {
  switch (period) {
    case '1h':     return { granularity: 'daily',   startSql: "now() - interval '1 hour'" };
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
 */
export async function GET({ locals, url }) {
  requireAdminAPI(locals);

  const period = url.searchParams.get('period') || '7d';
  const xBots = url.searchParams.get('excludeBots') === 'true';
  const xApi = url.searchParams.get('excludeApi') === 'true';
  const { granularity, startSql } = periodConfig(period);

  try {
    let rows;

    if (xBots || xApi) {
      // Geo rollup lacks bot/api breakdown — query raw data (bounded by 30-day retention)
      const rawWhere = startSql ? `AND visited_at >= ${startSql}` : '';
      const botFilter = xBots ? 'AND is_bot = false' : '';
      const apiFilter = xApi ? 'AND is_api = false' : '';
      ({ rows } = await pool.query(
        `SELECT country_code,
                count(*)::integer AS requests,
                count(DISTINCT ip_address)::integer AS unique_ips
         FROM route_visits
         WHERE country_code IS NOT NULL ${rawWhere} ${botFilter} ${apiFilter}
         GROUP BY country_code
         ORDER BY requests DESC`
      ));
    } else {
      const rollupWhere = startSql ? `AND period_start >= ${startSql}` : '';
      ({ rows } = await pool.query(
        `SELECT country_code,
                SUM(request_count)::integer AS requests,
                SUM(unique_ips)::integer AS unique_ips
         FROM route_analytics_geo_rollup
         WHERE granularity = $1 ${rollupWhere}
         GROUP BY country_code
         ORDER BY requests DESC`,
        [granularity]
      ));
    }

    return json({ countries: rows });
  } catch (e) {
    console.error('[analytics] Geo error:', e);
    return json({ error: 'Failed to fetch geographic data' }, { status: 500 });
  }
}
