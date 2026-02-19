//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { deleteUserMarkup } from '$lib/server/inventory.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';

/**
 * DELETE /api/users/inventory/markups/[itemId] — Remove markup for an item
 */
export async function DELETE({ params, locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  // Share rate limit bucket with markup upserts
  const rateCheck = checkRateLimit(`inv:markup:${user.id}`, 60, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many markup updates. Please slow down.' }, 429);
  }

  const itemId = parseInt(params.itemId, 10);
  if (!Number.isFinite(itemId) || itemId <= 0) {
    return getResponse({ error: 'Invalid item ID' }, 400);
  }

  try {
    const deleted = await deleteUserMarkup(user.id, itemId);
    if (!deleted) {
      return getResponse({ error: 'Markup not found' }, 404);
    }
    return getResponse({ success: true }, 200);
  } catch (err) {
    console.error('Error deleting markup:', err);
    return getResponse({ error: 'Failed to delete markup' }, 500);
  }
}
