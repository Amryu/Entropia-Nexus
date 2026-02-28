//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { requireAdminAPI } from '$lib/server/auth.js';
import { getConflicts } from '$lib/server/ingestion.js';

export async function GET({ url, locals }) {
  requireAdminAPI(locals);

  const page = parseInt(url.searchParams.get('page') || '1');
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '50'), 100);
  const userId = url.searchParams.get('userId') || null;

  try {
    const rows = await getConflicts(page, limit, userId);
    return getResponse(rows, 200);
  } catch (e) {
    console.error('[admin/ingestion] Failed to get conflicts:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
