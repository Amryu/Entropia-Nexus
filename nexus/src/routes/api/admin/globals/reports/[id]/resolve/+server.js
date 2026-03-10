// @ts-nocheck
/**
 * POST /api/admin/globals/reports/[id]/resolve — Mark a media report as resolved.
 */
import { pool } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import { requireAdminAPI } from '$lib/server/auth.js';

/** @type {import('./$types').RequestHandler} */
export async function POST({ params, locals }) {
  const user = requireAdminAPI(locals);

  const reportId = parseInt(params.id);
  if (isNaN(reportId)) {
    return getResponse({ error: 'Invalid report ID.' }, 400);
  }

  const userId = String(user.Id || user.id);

  const { rowCount } = await pool.query(
    `UPDATE globals_media_reports
     SET resolved_by = $1, resolved_at = NOW()
     WHERE id = $2 AND resolved_at IS NULL`,
    [userId, reportId]
  );

  if (rowCount === 0) {
    return getResponse({ error: 'Report not found or already resolved.' }, 404);
  }

  return getResponse({ success: true });
}
