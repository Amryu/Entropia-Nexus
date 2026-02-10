//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getUserPublicOrders } from '$lib/server/trade-requests.js';

/**
 * GET /api/market/exchange/orders/user/[userId] — Get all active orders by a user
 * Public endpoint (no auth required).
 */
export async function GET({ params }) {
  const userId = params.userId;
  if (!userId || !/^\d+$/.test(userId)) {
    return getResponse({ error: 'Invalid user ID' }, 400);
  }

  try {
    const orders = await getUserPublicOrders(userId);
    return getResponse(orders, 200);
  } catch (err) {
    console.error('Error fetching user orders:', err);
    return getResponse({ error: 'Failed to fetch user orders' }, 500);
  }
}
