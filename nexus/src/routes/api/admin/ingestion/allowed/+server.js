//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { requireAdminAPI } from '$lib/server/auth.js';
import { getAllowedClients, addAllowedClient, removeAllowedClient } from '$lib/server/ingestion.js';

/**
 * GET /api/admin/ingestion/allowed — List allowed OAuth client applications.
 */
export async function GET({ url, locals }) {
  requireAdminAPI(locals);

  const page = parseInt(url.searchParams.get('page') || '1');
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '50'), 100);

  try {
    const result = await getAllowedClients(page, limit);
    return getResponse(result, 200);
  } catch (e) {
    console.error('[admin/ingestion] Failed to fetch allowed clients:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}

/**
 * POST /api/admin/ingestion/allowed — Add an OAuth client application to the ingestion allowlist.
 * Body: { clientId, notes? }
 */
export async function POST({ request, locals }) {
  const admin = requireAdminAPI(locals);

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid request body' }, 400);
  }

  if (!body.clientId || typeof body.clientId !== 'string') {
    return getResponse({ error: 'Missing clientId' }, 400);
  }

  try {
    const added = await addAllowedClient(body.clientId, admin.id, body.notes || null);
    if (!added) {
      return getResponse({ error: 'Application is already on the allowlist' }, 409);
    }
    return getResponse({ success: true }, 200);
  } catch (e) {
    if (e.code === '23503') { // foreign key violation — invalid client_id
      return getResponse({ error: 'OAuth client not found' }, 404);
    }
    console.error('[admin/ingestion] Failed to add allowed client:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}

/**
 * DELETE /api/admin/ingestion/allowed — Remove an OAuth client application from the allowlist.
 * Body: { clientId }
 */
export async function DELETE({ request, locals }) {
  requireAdminAPI(locals);

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid request body' }, 400);
  }

  if (!body.clientId) return getResponse({ error: 'Missing clientId' }, 400);

  try {
    const removed = await removeAllowedClient(body.clientId);
    if (!removed) {
      return getResponse({ error: 'Application not found on allowlist' }, 404);
    }
    return getResponse({ success: true }, 200);
  } catch (e) {
    console.error('[admin/ingestion] Failed to remove allowed client:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
