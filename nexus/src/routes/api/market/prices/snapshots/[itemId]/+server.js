//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';
import { getMarketPriceSnapshots } from '$lib/server/db.js';
import { resolveItemDataByItemId, resolveItemTypesByItemId } from '$lib/server/item-type-cache.js';
import { TIERABLE_TYPES } from '$lib/common/itemTypes.js';

const RATE_LIMIT_MAX = 30;
const RATE_LIMIT_WINDOW = 60_000; // 30 requests per 60 seconds
const MAX_LIMIT = 750; // 30d * 24h = 720 possible hourly snapshots
const MAX_TIMESPAN_MS = 30 * 24 * 60 * 60 * 1000; // 30 days

/**
 * GET /api/market/prices/snapshots/[itemId] — History of market price snapshots for an item.
 * Public (no auth required). Rate limited by IP.
 *
 * Query params:
 *   ?tier=N   — filter by tier (0-10). Defaults to 0 for tierable items.
 *   ?from=    — start date (ISO8601)
 *   ?to=      — end date (ISO8601)
 *   ?limit=   — max rows (default 100, max 750)
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

  // Parse tier param
  const tierRaw = url.searchParams.get('tier');
  let tierParam = null;
  if (tierRaw != null) {
    tierParam = parseInt(tierRaw, 10);
    if (!Number.isInteger(tierParam) || tierParam < 0 || tierParam > 10) {
      return getResponse({ error: 'Invalid tier (must be 0-10)' }, 400);
    }
  }

  // Resolve item type to validate tier usage
  const itemData = await resolveItemDataByItemId([itemId], fetch);
  const itemName = itemData[itemId]?.item?.Name ?? null;
  const types = await resolveItemTypesByItemId([itemId], fetch);
  const itemType = types[itemId]?.type ?? null;
  const tierable = itemType && TIERABLE_TYPES.has(itemType);

  if (tierParam != null && !tierable) {
    return getResponse({ error: 'Tier filter not supported for this item type' }, 400);
  }

  // Default to tier 0 for tierable items when no tier is specified
  const effectiveTier = tierParam != null ? tierParam : (tierable ? 0 : null);

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
      tier: effectiveTier,
      from: from?.toISOString(),
      to: to?.toISOString(),
      limit
    });

    // Enrich resolved rows (item_name IS NULL) with name from Item table
    if (rows.length > 0 && rows.some(r => !r.item_name)) {
      const name = itemName || itemData[itemId]?.item?.Name;
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
