//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getExchangePrices } from '$lib/server/exchange.js';

/**
 * GET /api/market/prices/exchange/[itemId] — Get exchange-derived price data
 * Public endpoint.
 */
export async function GET({ params }) {
  const itemId = parseInt(params.itemId, 10);
  if (!Number.isFinite(itemId) || itemId <= 0) {
    return getResponse({ error: 'Invalid item ID' }, 400);
  }

  try {
    const prices = await getExchangePrices(itemId);
    return getResponse(prices, 200);
  } catch (err) {
    console.error('Error fetching exchange prices:', err);
    return getResponse({ error: 'Failed to fetch exchange prices' }, 500);
  }
}
