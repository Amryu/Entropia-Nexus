//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { requireAdminAPI } from '$lib/server/auth.js';
import { getUserSubmissions } from '$lib/server/ingestion.js';

export async function GET({ params, url, locals }) {
  requireAdminAPI(locals);

  const userId = params.id;
  if (!userId) {
    return getResponse({ error: 'Missing user ID' }, 400);
  }

  const type = url.searchParams.get('type') || 'global';
  if (type !== 'global' && type !== 'trade' && type !== 'market_price') {
    return getResponse({ error: 'Invalid type (must be global, trade, or market_price)' }, 400);
  }

  const page = parseInt(url.searchParams.get('page') || '1');
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '50'), 100);

  try {
    const rows = await getUserSubmissions(userId, type, page, limit);
    return getResponse(rows, 200);
  } catch (e) {
    console.error('[admin/ingestion] Failed to get submissions:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
