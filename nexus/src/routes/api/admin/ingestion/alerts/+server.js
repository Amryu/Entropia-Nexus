//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { requireAdminAPI } from '$lib/server/auth.js';
import { getAlerts } from '$lib/server/ingestion.js';

export async function GET({ url, locals }) {
  requireAdminAPI(locals);

  const page = parseInt(url.searchParams.get('page') || '1');
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '20'), 100);

  try {
    const result = await getAlerts(page, limit);
    return getResponse(result, 200);
  } catch (e) {
    console.error('[admin/ingestion] Failed to get alerts:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
