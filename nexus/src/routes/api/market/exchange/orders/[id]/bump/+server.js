//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getOrderById, bumpOrder, formatRetryTime, RATE_LIMIT_BUMP_PER_MIN } from '$lib/server/exchange.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';

/**
 * POST /api/market/exchange/orders/[id]/bump — Bump an order
 */
export async function POST({ params, locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  // Bump rate limit
  const bumpCheck = checkRateLimit(`order:bump:${user.id}`, RATE_LIMIT_BUMP_PER_MIN, 60_000);
  if (!bumpCheck.allowed) {
    const retryAfter = Math.ceil(bumpCheck.resetIn / 1000);
    return getResponse({
      error: `Bump rate limit exceeded. Try again in ${formatRetryTime(retryAfter)}.`,
      retryAfter
    }, 429);
  }

  const orderId = parseInt(params.id, 10);
  if (!Number.isFinite(orderId)) {
    return getResponse({ error: 'Invalid order ID' }, 400);
  }

  const existing = await getOrderById(orderId);
  if (!existing) {
    return getResponse({ error: 'Order not found' }, 404);
  }
  if (String(existing.user_id) !== String(user.id)) {
    return getResponse({ error: 'Not authorized' }, 403);
  }
  if (existing.state === 'closed') {
    return getResponse({ error: 'Cannot bump a closed order' }, 400);
  }
  // Terminated orders (>30 days) must be re-created, not bumped
  if (existing.computed_state === 'terminated') {
    return getResponse({ error: 'This order has expired. Please create a new order.' }, 400);
  }

  try {
    const bumped = await bumpOrder(orderId);
    return getResponse(bumped, 200);
  } catch (err) {
    console.error('Error bumping order:', err);
    return getResponse({ error: 'Failed to bump order' }, 500);
  }
}
