//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { requireAdminAPI } from '$lib/server/auth.js';
import { banUser, unbanUser } from '$lib/server/ingestion.js';

/**
 * POST /api/admin/ingestion/ban — Ban a user from ingestion.
 * Body: { userId, reason }
 */
export async function POST({ request, locals }) {
  const admin = requireAdminAPI(locals);

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid request body' }, 400);
  }

  const { userId, reason } = body;
  if (!userId) return getResponse({ error: 'Missing userId' }, 400);
  if (!reason || typeof reason !== 'string' || !reason.trim()) {
    return getResponse({ error: 'Missing or empty reason' }, 400);
  }

  try {
    await banUser(userId, reason.trim(), admin.id);
    return getResponse({ success: true }, 200);
  } catch (e) {
    console.error('[admin/ingestion] Failed to ban user:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}

/**
 * DELETE /api/admin/ingestion/ban — Unban a user from ingestion.
 * Body: { userId }
 */
export async function DELETE({ request, locals }) {
  requireAdminAPI(locals);

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid request body' }, 400);
  }

  if (!body.userId) return getResponse({ error: 'Missing userId' }, 400);

  try {
    await unbanUser(body.userId);
    return getResponse({ success: true }, 200);
  } catch (e) {
    console.error('[admin/ingestion] Failed to unban user:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
