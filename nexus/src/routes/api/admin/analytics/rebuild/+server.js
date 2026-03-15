// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth.js';
import { rebuildRollups } from '$lib/server/route-analytics-rollup.js';
import { reevaluateBotFlags } from '$lib/server/route-analytics.js';

/**
 * POST /api/admin/analytics/rebuild
 * Manually trigger rollup rebuild and/or bot re-evaluation.
 * Query params:
 *   ?bots=true — re-evaluate is_bot on all existing rows first
 */
export async function POST({ locals, url }) {
  requireAdminAPI(locals);

  try {
    let botsUpdated = 0;

    // Re-evaluate bot flags if requested
    if (url.searchParams.get('bots') === 'true') {
      const result = await reevaluateBotFlags();
      botsUpdated = result.updated;
    }

    await rebuildRollups({ force: true });
    return json({ success: true, botsUpdated });
  } catch (e) {
    console.error('[analytics] Manual rebuild error:', e);
    return json({ error: 'Rebuild failed' }, { status: 500 });
  }
}
