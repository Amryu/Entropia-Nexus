//@ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth.js';
import { resolveUnknownItem } from '$lib/server/inventory.js';

/**
 * PATCH /api/admin/unknown-items/[id] — Mark unknown item as resolved
 */
export async function PATCH({ params, request, locals }) {
  requireAdminAPI(locals);

  const id = parseInt(params.id, 10);
  if (!Number.isFinite(id) || id <= 0) {
    return json({ error: 'Invalid ID' }, { status: 400 });
  }

  let body = {};
  try {
    body = await request.json();
  } catch {
    // Body is optional — just marking resolved without mapping to item
  }

  const resolvedItemId = body.resolved_item_id ? parseInt(body.resolved_item_id, 10) : null;

  try {
    const result = await resolveUnknownItem(id, resolvedItemId);
    if (!result) {
      return json({ error: 'Unknown item not found' }, { status: 404 });
    }
    return json(result);
  } catch (err) {
    console.error('Error resolving unknown item:', err);
    return json({ error: 'Failed to resolve unknown item' }, { status: 500 });
  }
}
