//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';
import { getLatestMarketPrices, getLatestMarketPriceByName, getAllLatestMarketPrices } from '$lib/server/db.js';
import { resolveItemByName, resolveItemDataByItemId, resolveItemTypesByItemId } from '$lib/server/item-type-cache.js';
import { maybeRunMarketFinalization } from '$lib/server/ingestion.js';
import { TIERABLE_TYPES, isLimitedByName } from '$lib/common/itemTypes.js';

const RATE_LIMIT_WINDOW = 60_000; // 60 seconds
const PENDING_THRESHOLD_MS = 2 * 60 * 60 * 1000; // 2 hours

/** Build Cache-Control header — shorter TTL if any row is from a recent/pending hour. */
function cacheHeader(rows) {
  const arr = Array.isArray(rows) ? rows : (rows ? [rows] : []);
  const cutoff = Date.now() - PENDING_THRESHOLD_MS;
  const hasPending = arr.some(r => {
    const recAt = r.recorded_at ? new Date(r.recorded_at).getTime() : 0;
    return recAt > cutoff;
  });
  return hasPending ? 'public, max-age=60' : 'public, max-age=300';
}

// Per-mode rate limits
const RL_BULK_MAX = 20; // itemIds mode — heavier queries
const RL_ALL_MAX = 5;   // all=true — returns up to 10k rows
const RL_NAME_MAX = 30; // single name lookup — lightweight

const MAX_ITEM_IDS = 50;

/**
 * Parse and validate optional tier query param.
 * Returns { tier: number|null, error: string|null }.
 */
function parseTierParam(url) {
  const raw = url.searchParams.get('tier');
  if (raw == null) return { tier: null, error: null };
  const tier = parseInt(raw, 10);
  if (!Number.isInteger(tier) || tier < 0 || tier > 10) {
    return { tier: null, error: 'Invalid tier (must be 0-10)' };
  }
  return { tier, error: null };
}

/**
 * Check if an item is tierable by looking up its type.
 * Returns true if tierable, false if not (or if type can't be resolved).
 */
async function isItemTierable(itemId, itemName, fetch) {
  if (!itemId) return false;
  const types = await resolveItemTypesByItemId([itemId], fetch);
  const type = types[itemId]?.type;
  if (!type || !TIERABLE_TYPES.has(type)) return false;
  // Check (L) limited items — not tierable
  if (itemName && isLimitedByName(itemName)) return false;
  return true;
}

/**
 * Resolve effective tier for a request.
 * - If tier param is given on a non-tierable item → error
 * - If no tier param on tierable item → default to 0
 * - If no tier param on non-tierable item → null (no filter)
 */
async function resolveEffectiveTier(tierParam, itemId, itemName, fetch) {
  const tierable = await isItemTierable(itemId, itemName, fetch);

  if (tierParam != null && !tierable) {
    return { tier: null, error: 'Tier filter not supported for this item type' };
  }
  if (tierParam != null) {
    return { tier: tierParam, error: null };
  }
  // No tier param supplied
  if (tierable) {
    return { tier: 0, error: null }; // default to base tier
  }
  return { tier: null, error: null }; // non-tierable: no filter
}

/**
 * GET /api/market/prices/snapshots/latest — Latest market price snapshots.
 * Public (no auth required). Rate limited by IP.
 *
 * Query params:
 *   ?itemIds=1,2,3  — latest snapshot per item ID (max 50)
 *   ?name=...       — latest snapshot matching item name
 *   ?all=true       — all latest snapshots (one per item)
 *   ?tier=N         — filter by tier (0-10). Required for tierable items; rejected for non-tierable.
 *
 * Resolved entries (item_name IS NULL) are enriched with the item name
 * from the Item table so consumers always receive item_name in the response.
 */
export async function GET({ url, locals, request, fetch }) {
  const ip = locals.ip || request.headers.get('x-forwarded-for') || request.headers.get('cf-connecting-ip') || 'unknown';

  try {
    const { tier: tierParam, error: tierError } = parseTierParam(url);
    if (tierError) return getResponse({ error: tierError }, 400);

    const allParam = url.searchParams.get('all');
    if (allParam === 'true') {
      const rl = checkRateLimit(`mps-latest-all:${ip}`, RL_ALL_MAX, RATE_LIMIT_WINDOW);
      if (!rl.allowed) {
        return getResponse({ error: 'Rate limited', retryAfter: Math.ceil(rl.resetIn / 1000) }, 429);
      }
      // Tier filter not supported for bulk all endpoint
      if (tierParam != null) {
        return getResponse({ error: 'Tier filter not supported with all=true' }, 400);
      }
      const rows = await getAllLatestMarketPrices();
      await enrichItemNames(rows, fetch);
      return new Response(JSON.stringify(rows), {
        status: 200,
        headers: { 'Content-Type': 'application/json', 'Cache-Control': cacheHeader(rows) }
      });
    }

    const itemIdsParam = url.searchParams.get('itemIds');
    if (itemIdsParam) {
      const rl = checkRateLimit(`mps-latest-bulk:${ip}`, RL_BULK_MAX, RATE_LIMIT_WINDOW);
      if (!rl.allowed) {
        return getResponse({ error: 'Rate limited', retryAfter: Math.ceil(rl.resetIn / 1000) }, 429);
      }
      const itemIds = itemIdsParam.split(',')
        .map(s => parseInt(s.trim(), 10))
        .filter(n => Number.isInteger(n) && n > 0);
      if (itemIds.length === 0) {
        return getResponse({ error: 'Invalid itemIds' }, 400);
      }
      if (itemIds.length > MAX_ITEM_IDS) {
        return getResponse({ error: `Too many itemIds (max ${MAX_ITEM_IDS})` }, 400);
      }

      let effectiveTier;
      if (itemIds.length === 1) {
        // Single item: validate tierable, default to tier 0 for tierable
        const itemData = await resolveItemDataByItemId(itemIds, fetch);
        const name = itemData[itemIds[0]]?.item?.Name ?? null;
        const resolved = await resolveEffectiveTier(tierParam, itemIds[0], name, fetch);
        if (resolved.error) return getResponse({ error: resolved.error }, 400);
        effectiveTier = resolved.tier;
      } else {
        // Multi-item bulk: tier param not supported, always return tier 0
        if (tierParam != null) {
          return getResponse({ error: 'Tier filter not supported for bulk itemIds requests' }, 400);
        }
        effectiveTier = 0;
      }

      const rows = await getLatestMarketPrices(itemIds, effectiveTier);
      await enrichItemNames(rows, fetch);
      return new Response(JSON.stringify(rows), {
        status: 200,
        headers: { 'Content-Type': 'application/json', 'Cache-Control': cacheHeader(rows) }
      });
    }

    const name = url.searchParams.get('name');
    if (name) {
      const rl = checkRateLimit(`mps-latest-name:${ip}`, RL_NAME_MAX, RATE_LIMIT_WINDOW);
      if (!rl.allowed) {
        return getResponse({ error: 'Rate limited', retryAfter: Math.ceil(rl.resetIn / 1000) }, 429);
      }
      if (name.length > 200) {
        return getResponse({ error: 'Name too long' }, 400);
      }
      // Resolve name → item_id so we also find resolved (item_name IS NULL) entries
      const resolved = await resolveItemByName(name, fetch);
      const itemId = resolved?.itemId ?? null;

      // Resolve effective tier
      const { tier: effectiveTier, error: tierErr } = await resolveEffectiveTier(tierParam, itemId, name, fetch);
      if (tierErr) return getResponse({ error: tierErr }, 400);

      const row = await getLatestMarketPriceByName(name, itemId, effectiveTier);
      if (row) {
        await enrichItemNames([row], fetch);
        return new Response(JSON.stringify([row]), {
          status: 200,
          headers: { 'Content-Type': 'application/json', 'Cache-Control': cacheHeader([row]) }
        });
      }
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=300' }
      });
    }

    return getResponse({ error: 'Provide itemIds, name, or all=true' }, 400);
  } catch (e) {
    console.error('[market-prices] Failed to fetch latest snapshots:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  } finally {
    // Stale-while-revalidate: trigger background finalization so the next
    // request picks up any pending submissions. Uses global 1-min cooldown.
    maybeRunMarketFinalization();
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
