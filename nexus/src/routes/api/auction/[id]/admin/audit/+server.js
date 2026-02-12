// @ts-nocheck
/**
 * GET /api/auction/[id]/admin/audit — Get audit log for an auction (admin)
 */
import { getResponse } from '$lib/util.js';
import { requireAdmin } from '$lib/server/auth.js';
import { getAuditLog } from '$lib/server/auction.js';

export async function GET({ params, locals }) {
  try {
    requireAdmin(locals);
  } catch (err) {
    return getResponse({ error: err.body?.message || 'Admin access required' }, err.status || 403);
  }

  try {
    const log = await getAuditLog(params.id);
    return getResponse(log, 200);
  } catch (err) {
    console.error('Error fetching audit log:', err);
    return getResponse({ error: 'Failed to fetch audit log' }, 500);
  }
}
