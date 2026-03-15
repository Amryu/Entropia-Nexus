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
 * GET /api/admin/analytics/referrers
 */
export async function GET({ locals, url }) {
  requireAdminAPI(locals);

  const period = url.searchParams.get('period') || '7d';
  const xBots = url.searchParams.get('excludeBots') === 'true';
  const xApi = url.searchParams.get('excludeApi') === 'true';
  const { granularity, startSql } = periodConfig(period);

  try {
    let rows;

    if (period === '1h' || xBots || xApi) {
      // Raw query: 1h has no rollup row; bot/api filters need row-level access
      const rawWhere = startSql ? `AND visited_at >= ${startSql}` : '';
      const botFilter = xBots ? 'AND is_bot = false' : '';
      const apiFilter = xApi ? 'AND is_api = false' : '';
      ({ rows } = await pool.query(
        `SELECT referrer AS referrer_domain,
                count(*)::integer AS requests
         FROM route_visits
         WHERE referrer IS NOT NULL ${rawWhere} ${botFilter} ${apiFilter}
         GROUP BY referrer
         ORDER BY requests DESC
         LIMIT 50`
      ));
    } else {
      const rollupWhere = startSql ? `AND period_start >= ${startSql}` : '';
      ({ rows } = await pool.query(
        `SELECT referrer_domain,
                SUM(request_count)::integer AS requests
         FROM route_analytics_referrer_rollup
         WHERE granularity = $1 ${rollupWhere}
         GROUP BY referrer_domain
         ORDER BY requests DESC
         LIMIT 50`,
        [granularity]
      ));
    }

    return json({ referrers: rows });
  } catch (e) {
    console.error('[analytics] Referrers error:', e);
    return json({ error: 'Failed to fetch referrer data' }, { status: 500 });
  }
}
