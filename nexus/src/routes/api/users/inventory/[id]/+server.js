//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { deleteInventoryItem, updateInventoryItem } from '$lib/server/inventory.js';

/**
 * Validate and sanitize inventory item details.
 * Only allows known metadata keys with correct types.
 */
function validateDetails(details) {
  if (details === null || details === undefined) return null;
  if (typeof details !== 'object' || Array.isArray(details)) return null;

  const clean = {};

  if (details.Tier != null) {
    const tier = parseFloat(details.Tier);
    if (Number.isFinite(tier) && tier >= 0 && tier <= 10) clean.Tier = tier;
  }
  if (details.TierIncreaseRate != null) {
    const tir = parseInt(details.TierIncreaseRate, 10);
    if (Number.isFinite(tir) && tir >= 1 && tir <= 4000) clean.TierIncreaseRate = tir;
  }
  if (details.QualityRating != null) {
    const qr = parseFloat(details.QualityRating);
    if (Number.isFinite(qr) && qr >= 0 && qr <= 100) clean.QualityRating = qr;
  }

  return Object.keys(clean).length > 0 ? clean : null;
}

/**
 * PATCH /api/users/inventory/[id] — Update an inventory item
 */
export async function PATCH({ params, request, locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  const itemRowId = parseInt(params.id, 10);
  if (!Number.isFinite(itemRowId)) {
    return getResponse({ error: 'Invalid item ID' }, 400);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON' }, 400);
  }

  const updates = {};

  if (body.quantity !== undefined) {
    const qty = parseInt(body.quantity, 10);
    if (!Number.isFinite(qty) || qty < 0) {
      return getResponse({ error: 'quantity must be a non-negative integer' }, 400);
    }
    updates.quantity = qty;
  }

  if (body.value !== undefined) {
    if (body.value === null) {
      updates.value = null;
    } else {
      const val = parseFloat(body.value);
      if (!Number.isFinite(val) || val < 0) {
        return getResponse({ error: 'value must be a non-negative number' }, 400);
      }
      updates.value = val;
    }
  }

  if (body.details !== undefined) {
    updates.details = validateDetails(body.details);
  }

  if (Object.keys(updates).length === 0) {
    return getResponse({ error: 'No valid fields to update' }, 400);
  }

  try {
    const updated = await updateInventoryItem(itemRowId, user.id, updates);
    if (!updated) {
      return getResponse({ error: 'Item not found or not owned by you' }, 404);
    }
    return getResponse(updated, 200);
  } catch (err) {
    console.error('Error updating inventory item:', err);
    return getResponse({ error: 'Failed to update inventory item' }, 500);
  }
}

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
