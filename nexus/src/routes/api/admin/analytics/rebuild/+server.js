// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth.js';
import { rebuildRollups } from '$lib/server/route-analytics-rollup.js';

/**
 * POST /api/admin/analytics/rebuild
 * Manually trigger an incremental rollup rebuild.
 */
export async function POST({ locals }) {
  requireAdminAPI(locals);

  try {
    await rebuildRollups({ force: true });
    return json({ success: true });
  } catch (e) {
    console.error('[analytics] Manual rebuild error:', e);
    return json({ error: 'Rebuild failed' }, { status: 500 });
  }
}
