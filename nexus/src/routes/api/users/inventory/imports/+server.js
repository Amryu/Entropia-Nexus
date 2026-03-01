//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getImportHistory } from '$lib/server/inventory.js';
import { requireGrantAPI } from '$lib/server/auth.js';

/**
 * GET /api/users/inventory/imports — Get user's import history
 */
export async function GET({ url, locals }) {
  const user = requireGrantAPI(locals, 'inventory.read');

  const limit = Math.min(parseInt(url.searchParams.get('limit') || '20', 10) || 20, 100);
  const offset = Math.max(parseInt(url.searchParams.get('offset') || '0', 10) || 0, 0);
  const sinceParam = url.searchParams.get('since');
  const since = sinceParam ? new Date(sinceParam) : null;
  if (since && isNaN(since.getTime())) return getResponse({ error: 'Invalid since date' }, 400);

  try {
    const imports = await getImportHistory(user.id, limit, offset, since);
    return getResponse(imports, 200);
  } catch (err) {
    console.error('Error fetching import history:', err);
    return getResponse({ error: 'Failed to fetch import history' }, 500);
  }
}
