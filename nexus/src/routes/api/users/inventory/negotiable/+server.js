//@ts-nocheck
import { getResponse } from '$lib/util.js';
import {
  getUserNegotiableConfig,
  upsertNegotiableConfig,
  deleteNegotiableConfig,
  deleteAllNegotiableOffers,
  validateNegotiableConfig,
  syncNegotiableListings,
} from '$lib/server/exchange.js';
import { getSlimItemLookup } from '$lib/market/cache.js';
import { invalidateOfferCounts } from '$lib/market/cache';
import { checkRateLimit } from '$lib/server/rateLimiter.js';

/**
 * GET /api/users/inventory/negotiable — Get user's negotiable listing config
 */
export async function GET({ locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  try {
    const config = await getUserNegotiableConfig(user.id);
    return getResponse(config?.config || null, 200);
  } catch (err) {
    console.error('Error fetching negotiable config:', err);
    return getResponse({ error: 'Failed to fetch config' }, 500);
  }
}

/**
 * PUT /api/users/inventory/negotiable — Save config and sync listings
 * Body: { nodes: [...] }
 */
export async function PUT({ request, locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);
  if (!user.grants?.includes('exchange.manage')) return getResponse({ error: 'Permission denied' }, 403);

  const rateCheck = checkRateLimit(`neg:save:${user.id}`, 5, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many updates. Please slow down.' }, 429);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON' }, 400);
  }

  // Validate and sanitize config
  let sanitized;
  try {
    sanitized = validateNegotiableConfig(body);
  } catch (err) {
    return getResponse({ error: err.message }, 400);
  }

  try {
    // Save config
    await upsertNegotiableConfig(user.id, sanitized);

    // Sync listings (best-effort — config is saved even if sync fails)
    let syncResult = { created: 0, closed: 0, skipped: 0 };
    try {
      const slimLookup = getSlimItemLookup();
      syncResult = await syncNegotiableListings(user.id, { slimLookup });
      invalidateOfferCounts();
    } catch (syncErr) {
      console.error('Error syncing negotiable listings:', syncErr);
    }

    return getResponse({
      saved: true,
      ...syncResult
    }, 200);
  } catch (err) {
    console.error('Error saving negotiable config:', err);
    return getResponse({ error: 'Failed to save config' }, 500);
  }
}

/**
 * DELETE /api/users/inventory/negotiable — Remove config and close all negotiable offers
 */
export async function DELETE({ locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);
  if (!user.grants?.includes('exchange.manage')) return getResponse({ error: 'Permission denied' }, 403);

  const rateCheck = checkRateLimit(`neg:del:${user.id}`, 60, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please slow down.' }, 429);
  }

  try {
    const deleted = await deleteNegotiableConfig(user.id);
    const closed = await deleteAllNegotiableOffers(user.id);
    if (closed > 0) invalidateOfferCounts();

    return getResponse({ deleted, closed }, deleted ? 200 : 404);
  } catch (err) {
    console.error('Error deleting negotiable config:', err);
    return getResponse({ error: 'Failed to delete config' }, 500);
  }
}
