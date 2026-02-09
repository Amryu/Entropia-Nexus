//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getUserInventory, upsertInventory } from '$lib/server/inventory.js';

const MAX_IMPORT_ITEMS = 500;

/**
 * GET /api/users/inventory — Get user's server inventory
 */
export async function GET({ locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  try {
    const items = await getUserInventory(user.id);
    return getResponse(items, 200);
  } catch (err) {
    console.error('Error fetching inventory:', err);
    return getResponse({ error: 'Failed to fetch inventory' }, 500);
  }
}

/**
 * PUT /api/users/inventory — Bulk upsert inventory (import)
 */
export async function PUT({ request, locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON' }, 400);
  }

  if (!Array.isArray(body.items) || body.items.length === 0) {
    return getResponse({ error: 'Body must contain a non-empty items array' }, 400);
  }
  if (body.items.length > MAX_IMPORT_ITEMS) {
    return getResponse({ error: `Maximum ${MAX_IMPORT_ITEMS} items per import` }, 400);
  }

  // Validate each item
  const validated = [];
  for (let i = 0; i < body.items.length; i++) {
    const item = body.items[i];

    const itemId = parseInt(item.item_id, 10);
    if (!Number.isFinite(itemId) || itemId <= 0) {
      return getResponse({ error: `items[${i}].item_id must be a positive integer` }, 400);
    }

    const itemName = typeof item.item_name === 'string' ? item.item_name.trim() : '';
    if (!itemName) {
      return getResponse({ error: `items[${i}].item_name is required` }, 400);
    }

    const quantity = item.quantity != null ? parseInt(item.quantity, 10) : 0;
    if (!Number.isFinite(quantity) || quantity < 0) {
      return getResponse({ error: `items[${i}].quantity must be a non-negative integer` }, 400);
    }

    const instanceKey = item.instance_key || null;
    const details = item.details || null;

    const value = item.value != null ? parseFloat(item.value) : null;
    if (value != null && !Number.isFinite(value)) {
      return getResponse({ error: `items[${i}].value must be a number` }, 400);
    }

    const container = typeof item.container === 'string' ? item.container.trim() || null : null;

    validated.push({ item_id: itemId, item_name: itemName, quantity, instance_key: instanceKey, details, value, container });
  }

  try {
    const results = await upsertInventory(user.id, validated);
    return getResponse({ imported: results.length, items: results }, 200);
  } catch (err) {
    console.error('Error importing inventory:', err);
    return getResponse({ error: 'Failed to import inventory' }, 500);
  }
}
