//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getExchangePrices, getExchangePriceSummary, getExchangePriceHistory } from '$lib/server/exchange.js';

/**
 * GET /api/market/prices/exchange/[itemId] — Get exchange-derived price data
 * Public endpoint.
 * Optional query params:
 *   period - price history period (24h, 7d, 30d, 3m, 6m, 1y, 5y, all)
 *   history - if "1", also return time series data for charting
 */
export async function GET({ params, url }) {
  const itemId = parseInt(params.itemId, 10);
  if (!Number.isFinite(itemId) || itemId <= 0) {
    return getResponse({ error: 'Invalid item ID' }, 400);
  }

  const period = url.searchParams.get('period') || '7d';
  const includeHistory = url.searchParams.get('history') === '1';

  try {
    const [prices, summary] = await Promise.all([
      getExchangePrices(itemId),
      getExchangePriceSummary(itemId, period),
    ]);

    const result = { ...prices, ...summary };

    if (includeHistory) {
      result.history = await getExchangePriceHistory(itemId, period);
    }

    return getResponse(result, 200);
  } catch (err) {
    console.error('Error fetching exchange prices:', err);
    return getResponse({ error: 'Failed to fetch exchange prices' }, 500);
  }
}
