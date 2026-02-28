//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { requireAdminAPI } from '$lib/server/auth.js';
import { getIngestionUsers } from '$lib/server/ingestion.js';

export async function GET({ url, locals }) {
  requireAdminAPI(locals);

  const page = parseInt(url.searchParams.get('page') || '1');
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '50'), 100);

  try {
    const rows = await getIngestionUsers(page, limit);
    return getResponse(rows, 200);
  } catch (e) {
    console.error('[admin/ingestion] Failed to get users:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
