// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth.js';
import { pool } from '$lib/server/db.js';

/**
 * GET /api/admin/analytics/errors
 * Recent errors grouped by route and status code.
 */
export async function GET({ locals, url }) {
  requireAdminAPI(locals);

  const statusFilter = url.searchParams.get('status') || null; // e.g. '404', '500', '4xx', '5xx'
  const route = url.searchParams.get('route') || null;

  const conditions = [];
  const params = [];
  let idx = 1;

  if (statusFilter === '4xx') {
    conditions.push('status_code >= 400 AND status_code < 500');
  } else if (statusFilter === '5xx') {
    conditions.push('status_code >= 500');
  } else if (statusFilter) {
    const code = parseInt(statusFilter, 10);
    if (!isNaN(code)) {
      conditions.push(`status_code = $${idx++}`);
      params.push(code);
    }
  }

  if (route) {
    conditions.push(`route_pattern = $${idx++}`);
    params.push(route);
  }

  const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';

  try {
    // Summary: count per route+status
    const { rows: summary } = await pool.query(
      `SELECT route_pattern, status_code, count(*)::integer AS count,
              max(created_at) AS last_seen
       FROM error_log
       ${where}
       GROUP BY route_pattern, status_code
       ORDER BY last_seen DESC`
      + (params.length > 0 ? '' : ''),
      params
    );

    // Detail: all errors (already capped at 10 per group by pruning)
    const { rows: errors } = await pool.query(
      `SELECT id, created_at, route_pattern, route_path, method, status_code,
              ip_address::text, country_code, user_agent, request_headers,
              response_body, error_message, response_time_ms
       FROM error_log
       ${where}
       ORDER BY created_at DESC
       LIMIT 200`,
      params
    );

    return json({ summary, errors });
  } catch (e) {
    console.error('[analytics] Errors endpoint error:', e);
    return json({ error: 'Failed to fetch error log' }, { status: 500 });
  }
}

/**
 * DELETE /api/admin/analytics/errors
 * Clear all error log entries (or filtered by route/status).
 */
export async function DELETE({ locals, url }) {
  requireAdminAPI(locals);

  const route = url.searchParams.get('route') || null;
  const status = url.searchParams.get('status') || null;

  const conditions = [];
  const params = [];
  let idx = 1;

  if (route) { conditions.push(`route_pattern = $${idx++}`); params.push(route); }
  if (status) {
    const code = parseInt(status, 10);
    if (!isNaN(code)) { conditions.push(`status_code = $${idx++}`); params.push(code); }
  }

  const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';

  try {
    const { rowCount } = await pool.query(`DELETE FROM error_log ${where}`, params);
    return json({ deleted: rowCount });
  } catch (e) {
    console.error('[analytics] Error log clear error:', e);
    return json({ error: 'Failed to clear errors' }, { status: 500 });
  }
}
