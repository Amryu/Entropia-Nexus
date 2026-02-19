//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getUserMarkups, upsertUserMarkups } from '$lib/server/inventory.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';

const MAX_MARKUP_VALUE = 100_000;

/**
 * GET /api/users/inventory/markups — Get user's markup configurations
 */
export async function GET({ locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  try {
    const markups = await getUserMarkups(user.id);
    return getResponse(markups, 200);
  } catch (err) {
    console.error('Error fetching markups:', err);
    return getResponse({ error: 'Failed to fetch markups' }, 500);
  }
}

/**
 * PUT /api/users/inventory/markups — Bulk upsert markup configurations
 * Body: { items: [{ item_id: number, markup: number }] }
 */
export async function PUT({ request, locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  // Rate limit: 60 per minute (generous for debounced typing)
  const rateCheck = checkRateLimit(`inv:markup:${user.id}`, 60, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many markup updates. Please slow down.' }, 429);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON' }, 400);
  }

  if (!Array.isArray(body.items) || body.items.length === 0) {
    return getResponse({ error: 'Body must contain a non-empty items array' }, 400);
  }

  if (body.items.length > 1000) {
    return getResponse({ error: 'Maximum 1000 markups per request' }, 400);
  }

  // Validate each entry
  const validated = [];
  for (let i = 0; i < body.items.length; i++) {
    const entry = body.items[i];

    const itemId = parseInt(entry.item_id, 10);
    if (!Number.isFinite(itemId) || itemId <= 0) {
      return getResponse({ error: `items[${i}].item_id must be a positive integer` }, 400);
    }

    const markup = parseFloat(entry.markup);
    if (!Number.isFinite(markup)) {
      return getResponse({ error: `items[${i}].markup must be a number` }, 400);
    }
    if (Math.abs(markup) > MAX_MARKUP_VALUE) {
      return getResponse({ error: `items[${i}].markup exceeds allowed range (-${MAX_MARKUP_VALUE} to ${MAX_MARKUP_VALUE})` }, 400);
    }

    validated.push({ item_id: itemId, markup });
  }

  try {
    const results = await upsertUserMarkups(user.id, validated);
    return getResponse(results, 200);
  } catch (err) {
    console.error('Error upserting markups:', err);
    return getResponse({ error: 'Failed to update markups' }, 500);
  }
}
