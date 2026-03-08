//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';
import { getMarketPriceSnapshots } from '$lib/server/db.js';
import { resolveItemDataByItemId } from '$lib/server/item-type-cache.js';

const RATE_LIMIT_MAX = 30;
const RATE_LIMIT_WINDOW = 60_000; // 30 requests per 60 seconds
const MAX_LIMIT = 750; // 30d * 24h = 720 possible hourly snapshots
const MAX_TIMESPAN_MS = 30 * 24 * 60 * 60 * 1000; // 30 days

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

  const itemId = parseInt(params.itemId, 10);
  if (!Number.isInteger(itemId) || itemId <= 0) {
    return getResponse({ error: 'Invalid itemId' }, 400);
  }

  const fromParam = url.searchParams.get('from');
  const toParam = url.searchParams.get('to');
  const limitParam = parseInt(url.searchParams.get('limit') || '100', 10);
  const limit = Math.min(Math.max(1, limitParam || 100), MAX_LIMIT);

  // Validate date params
  let from, to;
  if (fromParam) {
    from = new Date(fromParam);
    if (isNaN(from.getTime())) return getResponse({ error: 'Invalid from date' }, 400);
  }
  if (toParam) {
    to = new Date(toParam);
    if (isNaN(to.getTime())) return getResponse({ error: 'Invalid to date' }, 400);
  }

  // Enforce max 30-day timespan
  const effectiveFrom = from || new Date(Date.now() - MAX_TIMESPAN_MS);
  const effectiveTo = to || new Date();
  if (effectiveTo.getTime() - effectiveFrom.getTime() > MAX_TIMESPAN_MS) {
    return getResponse({ error: 'Maximum timespan is 30 days' }, 400);
  }

  try {
    const rows = await getMarketPriceSnapshots(itemId, {
      from: from?.toISOString(),
      to: to?.toISOString(),
      limit
    });

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

    // Shorter cache for results containing recent/pending data
    const hasPending = rows.some(r => {
      const recAt = r.recorded_at ? new Date(r.recorded_at).getTime() : 0;
      return recAt > Date.now() - 2 * 60 * 60 * 1000;
    });

    return new Response(JSON.stringify(rows), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': hasPending ? 'public, max-age=60' : 'public, max-age=300'
      }
    });
  } catch (e) {
    console.error('[market-prices] Failed to fetch snapshots:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
