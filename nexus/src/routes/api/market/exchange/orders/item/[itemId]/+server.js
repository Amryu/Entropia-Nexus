//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getOrderBook } from '$lib/server/exchange.js';

/**
 * GET /api/market/exchange/orders/item/[itemId] — Get order book for an item
 * Public endpoint, no auth required.
 */
export async function GET({ params }) {
  const itemId = parseInt(params.itemId, 10);
  if (!Number.isFinite(itemId) || itemId <= 0) {
    return getResponse({ error: 'Invalid item ID' }, 400);
  }

  try {
    const orders = await getOrderBook(itemId);

    // Split into buy and sell
    const buy = orders.filter(o => o.type === 'BUY');
    const sell = orders.filter(o => o.type === 'SELL');

    return getResponse({ buy, sell }, 200);
  } catch (err) {
    console.error('Error fetching order book:', err);
    return getResponse({ error: 'Failed to fetch order book' }, 500);
  }
}
