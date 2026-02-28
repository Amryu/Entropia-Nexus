//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { requireAdminAPI } from '$lib/server/auth.js';
import { resolveAlert } from '$lib/server/ingestion.js';

export async function PATCH({ params, request, locals }) {
  const user = requireAdminAPI(locals);

  const alertId = parseInt(params.id);
  if (isNaN(alertId)) {
    return getResponse({ error: 'Invalid alert ID' }, 400);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid request body' }, 400);
  }

  if (!body.resolved) {
    return getResponse({ error: 'Missing resolved field' }, 400);
  }

  try {
    await resolveAlert(alertId, user.id, body.notes || null);
    return getResponse({ success: true }, 200);
  } catch (e) {
    console.error('[admin/ingestion] Failed to resolve alert:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
