//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getImportDeltas } from '$lib/server/inventory.js';
import { requireGrantAPI } from '$lib/server/auth.js';

/**
 * GET /api/users/inventory/imports/[id]/deltas — Get deltas for a specific import
 */
export async function GET({ params, locals }) {
  const user = requireGrantAPI(locals, 'inventory.read');

  const importId = parseInt(params.id, 10);
  if (!Number.isFinite(importId) || importId <= 0) {
    return getResponse({ error: 'Invalid import ID' }, 400);
  }

  try {
    const deltas = await getImportDeltas(importId, user.id);
    if (deltas === null) {
      return getResponse({ error: 'Import not found' }, 404);
    }
    return getResponse(deltas, 200);
  } catch (err) {
    console.error('Error fetching import deltas:', err);
    return getResponse({ error: 'Failed to fetch import deltas' }, 500);
  }
}
