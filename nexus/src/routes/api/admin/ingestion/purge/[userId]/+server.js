//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { requireAdminAPI } from '$lib/server/auth.js';
import { purgeUserData } from '$lib/server/ingestion.js';

/**
 * POST /api/admin/ingestion/purge/:userId — Purge all ingested data from a user.
 * Recalculates confirmation counts and removes orphaned entries.
 */
export async function POST({ params, locals }) {
  const admin = requireAdminAPI(locals);

  const userId = params.userId;
  if (!userId) {
    return getResponse({ error: 'Missing userId' }, 400);
  }

  try {
    const result = await purgeUserData(userId, admin.id);
    return getResponse({ success: true, ...result }, 200);
  } catch (e) {
    console.error('[admin/ingestion] Failed to purge user data:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
