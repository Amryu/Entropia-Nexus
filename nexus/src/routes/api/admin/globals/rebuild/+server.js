// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdmin } from '$lib/server/auth.js';
import { rebuildTargeted } from '$lib/server/globals-rollup.js';
import { forceAthRebuild, forceRefreshCaches } from '$lib/server/globals-cache.js';

export async function POST({ request, locals }) {
  requireAdmin(locals);
  const body = await request.json();
  const { mode, player, target, mobId } = body;

  try {
    const start = Date.now();

    if (mode === 'player' && player) {
      await rebuildTargeted({ player });
    } else if (mode === 'target' && target) {
      await rebuildTargeted({ target });
    } else if (mode === 'mob' && mobId) {
      await rebuildTargeted({ mobId: parseInt(mobId, 10) });
    } else if (mode === 'all') {
      await rebuildTargeted();
    } else {
      return json({ error: 'Invalid mode or missing filter value' }, { status: 400 });
    }

    // Rebuild ATH leaderboard and refresh in-memory caches
    await forceAthRebuild();
    await forceRefreshCaches();

    const elapsed = ((Date.now() - start) / 1000).toFixed(1);
    return json({ success: true, elapsed: `${elapsed}s` });
  } catch (err) {
    console.error('[admin/globals/rebuild] Error:', err);
    return json({ error: err.message || 'Rebuild failed' }, { status: 500 });
  }
}
