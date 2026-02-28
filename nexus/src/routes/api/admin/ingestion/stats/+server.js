//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { requireAdminAPI } from '$lib/server/auth.js';
import { getIngestionStats } from '$lib/server/ingestion.js';

export async function GET({ locals }) {
  requireAdminAPI(locals);

  try {
    const stats = await getIngestionStats();
    return getResponse(stats, 200);
  } catch (e) {
    console.error('[admin/ingestion] Failed to get stats:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
