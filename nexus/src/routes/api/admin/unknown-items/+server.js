//@ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth.js';
import { getUnknownItems } from '$lib/server/inventory.js';

/**
 * GET /api/admin/unknown-items — List unknown items
 */
export async function GET({ url, locals }) {
  requireAdminAPI(locals);

  const resolved = url.searchParams.get('resolved') === 'true';
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '50', 10) || 50, 200);
  const offset = Math.max(parseInt(url.searchParams.get('offset') || '0', 10) || 0, 0);

  try {
    const items = await getUnknownItems({ resolved, limit, offset });
    return json(items);
  } catch (err) {
    console.error('Error fetching unknown items:', err);
    return json({ error: 'Failed to fetch unknown items' }, { status: 500 });
  }
}
