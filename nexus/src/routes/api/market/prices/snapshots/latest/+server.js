//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';
import { getLatestMarketPrices, getLatestMarketPriceByName, getAllLatestMarketPrices } from '$lib/server/db.js';
import { resolveItemByName, resolveItemDataByItemId } from '$lib/server/item-type-cache.js';

const RATE_LIMIT_MAX = 30;
const RATE_LIMIT_WINDOW = 60_000; // 30 requests per 60 seconds
const MAX_ITEM_IDS = 500;

/**
 * GET /api/market/prices/snapshots/latest — Latest market price snapshots.
 * Public (no auth required). Rate limited by IP.
 *
 * Query params:
 *   ?itemIds=1,2,3  — latest snapshot per item ID
 *   ?name=...       — latest snapshot matching item name (ILIKE)
 *   ?all=true       — all latest snapshots (one per item)
 *
 * Resolved entries (item_name IS NULL) are enriched with the item name
 * from the Item table so consumers always receive item_name in the response.
 */
export async function GET({ url, locals, request, fetch }) {
  const ip = locals.ip || request.headers.get('x-forwarded-for') || request.headers.get('cf-connecting-ip') || 'unknown';
  const rl = checkRateLimit(`mps-latest:${ip}`, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW);
  if (!rl.allowed) {
    return getResponse({ error: 'Rate limited', retryAfter: Math.ceil(rl.resetIn / 1000) }, 429);
  }

  try {
    const allParam = url.searchParams.get('all');
    if (allParam === 'true') {
      const rows = await getAllLatestMarketPrices();
      await enrichItemNames(rows, fetch);
      return getResponse(rows, 200);
    }

    const itemIdsParam = url.searchParams.get('itemIds');
    if (itemIdsParam) {
      const itemIds = itemIdsParam.split(',')
        .map(s => parseInt(s.trim()))
        .filter(n => Number.isInteger(n) && n > 0);
      if (itemIds.length === 0) {
        return getResponse({ error: 'Invalid itemIds' }, 400);
      }
      if (itemIds.length > MAX_ITEM_IDS) {
        return getResponse({ error: `Too many itemIds (max ${MAX_ITEM_IDS})` }, 400);
      }
      const rows = await getLatestMarketPrices(itemIds);
      await enrichItemNames(rows, fetch);
      return getResponse(rows, 200);
    }

    const name = url.searchParams.get('name');
    if (name) {
      if (name.length > 200) {
        return getResponse({ error: 'Name too long' }, 400);
      }
      // Resolve name → item_id so we also find resolved (item_name IS NULL) entries
      const resolved = await resolveItemByName(name, fetch);
      const row = await getLatestMarketPriceByName(name, resolved?.itemId ?? null);
      if (row) {
        await enrichItemNames([row], fetch);
        return getResponse([row], 200);
      }
      return getResponse([], 200);
    }

    return getResponse({ error: 'Provide itemIds, name, or all=true' }, 400);
  } catch (e) {
    console.error('[market-prices] Failed to fetch latest snapshots:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}

/**
 * Fill in item_name from the Item table for resolved entries where item_name IS NULL.
 */
async function enrichItemNames(rows, fetch) {
  const needNames = rows.filter(r => !r.item_name && r.item_id);
  if (needNames.length === 0) return;

  const itemIds = [...new Set(needNames.map(r => r.item_id))];
  const itemData = await resolveItemDataByItemId(itemIds, fetch);

  for (const row of needNames) {
    const data = itemData[row.item_id];
    if (data?.item?.Name) row.item_name = data.item.Name;
  }
}
