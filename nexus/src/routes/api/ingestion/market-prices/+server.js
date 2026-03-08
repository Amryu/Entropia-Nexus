//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { requireVerifiedAPI } from '$lib/server/auth.js';
import { checkRateLimit, checkConcurrentUploads, startUpload, endUpload } from '$lib/server/rateLimiter.js';
import {
  isIngestionAllowed,
  isIngestionBanned,
  validateMarketPrice,
  ingestMarketPrices,
  parseRequestBody,
} from '$lib/server/ingestion.js';
import { resolveItemByName, resolveItemByPrefix, resolveItemByFuzzy } from '$lib/server/item-type-cache.js';

const MAX_BATCH_SIZE = 50;
const RATE_LIMIT_MAX = 20;
const RATE_LIMIT_WINDOW = 60_000; // 20 requests per 60 seconds

/**
 * POST /api/ingestion/market-prices — Submit market price snapshots.
 * OAuth required, must be verified and not ingestion-banned.
 */
export async function POST({ request, locals, fetch }) {
  const user = requireVerifiedAPI(locals);

  // Rate limit (admins bypass)
  const isAdmin = user.grants?.includes('admin.panel');
  if (!isAdmin) {
    const rl = checkRateLimit(`ingest-market-prices:${user.id}`, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW);
    if (!rl.allowed) {
      return getResponse(
        { error: 'Rate limited', retryAfter: Math.ceil(rl.resetIn / 1000) },
        429
      );
    }
  }

  // Concurrent upload guard (1 per user per endpoint)
  const uploadKey = `ingest-market-prices:${user.id}`;
  if (!checkConcurrentUploads(uploadKey, 1)) {
    return getResponse({ error: 'Concurrent ingestion in progress' }, 409);
  }
  startUpload(uploadKey);

  try {
    // Require OAuth client — browser sessions cannot submit market prices
    if (!locals.oauthClientId) {
      return getResponse({ error: 'Market price ingestion requires an authorized client application' }, 403);
    }
    // Allowlist check (OAuth client application must be approved)
    if (!(await isIngestionAllowed(locals.oauthClientId))) {
      return getResponse({ error: 'This application is not authorized for ingestion' }, 403);
    }
    if (await isIngestionBanned(user.id)) {
      return getResponse({ error: 'Ingestion access revoked' }, 403);
    }

    // Parse body (supports gzip)
    let body;
    try {
      body = await parseRequestBody(request);
    } catch (e) {
      return getResponse({ error: 'Invalid request body' }, 400);
    }

    const prices = body?.prices;
    if (!Array.isArray(prices) || prices.length === 0) {
      return getResponse({ error: 'Missing or empty prices array' }, 400);
    }
    if (prices.length > MAX_BATCH_SIZE) {
      return getResponse({ error: `Batch too large (max ${MAX_BATCH_SIZE})` }, 400);
    }

    // Validate each entry
    const validPrices = [];
    const errors = [];
    for (let i = 0; i < prices.length; i++) {
      const err = validateMarketPrice(prices[i]);
      if (err) {
        errors.push({ index: i, error: err });
      } else {
        validPrices.push(prices[i]);
      }
    }

    if (validPrices.length === 0) {
      return getResponse({ error: 'No valid entries in batch', details: errors }, 400);
    }

    // Resolve item names → item_id via /items data API cache.
    // Tries: exact → case-insensitive → raw OCR variant → prefix match.
    // Game displays names in ALL CAPS so all matching is case-insensitive.
    const resolveItem = async (name, rawName) => {
      const match = await resolveItemByName(name, fetch);
      if (match) return match.itemId;
      if (rawName && rawName !== name) {
        const rawMatch = await resolveItemByName(rawName, fetch);
        if (rawMatch) return rawMatch.itemId;
      }
      const prefix = await resolveItemByPrefix(name, fetch);
      if (prefix) return prefix.itemId;
      const fuzzy = await resolveItemByFuzzy(name, fetch);
      return fuzzy?.itemId ?? null;
    };
    const result = await ingestMarketPrices(user.id, validPrices, resolveItem);

    const response = {
      ...result,
      total: prices.length,
      invalid: errors.length,
    };
    if (errors.length > 0) response.errors = errors;
    return getResponse(response, 200);
  } catch (e) {
    console.error('[ingestion] Failed to ingest market prices:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  } finally {
    endUpload(uploadKey);
  }
}
