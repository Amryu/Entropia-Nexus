//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getImportHistory } from '$lib/server/inventory.js';

/**
 * GET /api/users/inventory/imports — Get user's import history
 */
export async function GET({ url, locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  const limit = Math.min(parseInt(url.searchParams.get('limit') || '20', 10) || 20, 100);
  const offset = Math.max(parseInt(url.searchParams.get('offset') || '0', 10) || 0, 0);

  try {
    const imports = await getImportHistory(user.id, limit, offset);
    return getResponse(imports, 200);
  } catch (err) {
    console.error('Error fetching import history:', err);
    return getResponse({ error: 'Failed to fetch import history' }, 500);
  }
}
