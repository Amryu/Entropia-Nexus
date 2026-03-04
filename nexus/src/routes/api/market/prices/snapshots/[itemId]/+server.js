//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';
import { getMarketPriceSnapshots } from '$lib/server/db.js';
import { resolveItemDataByItemId } from '$lib/server/item-type-cache.js';

const RATE_LIMIT_MAX = 30;
const RATE_LIMIT_WINDOW = 60_000; // 30 requests per 60 seconds

/**
 * GET /api/market/prices/snapshots/[itemId] — History of market price snapshots for an item.
 * Public (no auth required). Rate limited by IP.
 */
export async function GET({ params, url, locals, request, fetch }) {
  const ip = locals.ip || request.headers.get('x-forwarded-for') || request.headers.get('cf-connecting-ip') || 'unknown';
  const rl = checkRateLimit(`mps-history:${ip}`, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW);
  if (!rl.allowed) {
    return getResponse({ error: 'Rate limited', retryAfter: Math.ceil(rl.resetIn / 1000) }, 429);
  }

  const itemId = parseInt(params.itemId);
  if (!Number.isInteger(itemId) || itemId <= 0) {
    return getResponse({ error: 'Invalid itemId' }, 400);
  }

  const from = url.searchParams.get('from') || undefined;
  const to = url.searchParams.get('to') || undefined;
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '100') || 100, 1000);

  // Validate date params if provided
  if (from && isNaN(new Date(from).getTime())) {
    return getResponse({ error: 'Invalid from date' }, 400);
  }
  if (to && isNaN(new Date(to).getTime())) {
    return getResponse({ error: 'Invalid to date' }, 400);
  }

  try {
    const rows = await getMarketPriceSnapshots(itemId, { from, to, limit });

    // Enrich resolved rows (item_name IS NULL) with name from Item table
    if (rows.length > 0 && rows.some(r => !r.item_name)) {
      const itemData = await resolveItemDataByItemId([itemId], fetch);
      const name = itemData[itemId]?.item?.Name;
      if (name) {
        for (const row of rows) {
          if (!row.item_name) row.item_name = name;
        }
      }
    }

    return getResponse(rows, 200);
  } catch (e) {
    console.error('[market-prices] Failed to fetch snapshots:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
