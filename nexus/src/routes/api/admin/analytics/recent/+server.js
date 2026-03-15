// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth.js';
import { pool } from '$lib/server/db.js';

/**
 * GET /api/admin/analytics/recent
 * Recent raw visits from route_visits table.
 */
export async function GET({ locals, url }) {
  requireAdminAPI(locals);

  const limit = Math.min(200, Math.max(1, parseInt(url.searchParams.get('limit') || '50', 10)));
  const category = url.searchParams.get('category') || null;
  const excludeBots = url.searchParams.get('excludeBots') === 'true';
  const excludeApi = url.searchParams.get('excludeApi') === 'true';

  const conditions = [];
  const params = [];
  let idx = 1;

  if (category) {
    conditions.push(`route_category = $${idx++}`);
    params.push(category);
  }
  if (excludeBots) {
    conditions.push('is_bot = false');
  }
  if (excludeApi) {
    conditions.push('is_api = false');
  }

  const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';

  try {
    const { rows } = await pool.query(
      `SELECT id, visited_at, ip_address::text, country_code, user_agent,
              route_category, route_pattern, route_path, method, status_code,
              referrer, is_bot, is_api, oauth_client_id, rate_limited, response_time_ms
       FROM route_visits
       ${where}
       ORDER BY visited_at DESC
       LIMIT ${limit}`,
      params
    );

    return json({ visits: rows });
  } catch (e) {
    console.error('[analytics] Recent visits error:', e);
    return json({ error: 'Failed to fetch recent visits' }, { status: 500 });
  }
}
