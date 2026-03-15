// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth.js';
import { pool } from '$lib/server/db.js';

function periodStartSql(period) {
  switch (period) {
    case '1h':     return "now() - interval '1 hour'";
    case 'today':  return "date_trunc('day', now())";
    case '7d':     return "date_trunc('day', now() - interval '6 days')";
    case '30d':    return "date_trunc('day', now() - interval '29 days')";
    case '90d':    return "date_trunc('day', now() - interval '89 days')";
    case '1y':     return "date_trunc('day', now() - interval '1 year')";
    case 'all':    return null;
    default:       return "date_trunc('day', now() - interval '6 days')";
  }
}

/**
 * GET /api/admin/analytics/routes/detail
 * Actual paths (slug values) for a given route pattern.
 * Only useful for routes with parameterized segments.
 * Queries raw route_visits (bounded by 30-day retention).
 */
export async function GET({ locals, url }) {
  requireAdminAPI(locals);

  const pattern = url.searchParams.get('pattern');
  if (!pattern) return json({ error: 'pattern parameter required' }, { status: 400 });

  const period = url.searchParams.get('period') || '7d';
  const xBots = url.searchParams.get('excludeBots') === 'true';
  const startSql = periodStartSql(period);
  const whereClause = startSql ? `AND visited_at >= ${startSql}` : '';
  const botFilter = xBots ? 'AND is_bot = false' : '';

  try {
    const { rows } = await pool.query(
      `SELECT route_path,
              count(*)::integer AS requests,
              count(DISTINCT ip_address)::integer AS unique_ips
       FROM route_visits
       WHERE route_pattern = $1 ${whereClause} ${botFilter}
       GROUP BY route_path
       ORDER BY requests DESC
       LIMIT 50`,
      [pattern]
    );

    return json({ paths: rows });
  } catch (e) {
    console.error('[analytics] Route detail error:', e);
    return json({ error: 'Failed to fetch route detail' }, { status: 500 });
  }
}
