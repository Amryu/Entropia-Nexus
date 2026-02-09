//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { deleteInventoryItem } from '$lib/server/inventory.js';

/**
 * DELETE /api/users/inventory/[id] — Remove an inventory item
 */
export async function DELETE({ params, locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  const itemRowId = parseInt(params.id, 10);
  if (!Number.isFinite(itemRowId)) {
    return getResponse({ error: 'Invalid item ID' }, 400);
  }

  try {
    const deleted = await deleteInventoryItem(itemRowId, user.id);
    if (!deleted) {
      return getResponse({ error: 'Item not found or not owned by you' }, 404);
    }
    return getResponse({ success: true }, 200);
  } catch (err) {
    console.error('Error deleting inventory item:', err);
    return getResponse({ error: 'Failed to delete inventory item' }, 500);
  }
}
