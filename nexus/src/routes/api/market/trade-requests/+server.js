//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { hasGrant } from '$lib/server/auth.js';
import { getOrCreateTradeRequest, getUserTradeRequests } from '$lib/server/trade-requests.js';

function getVerifiedUser(locals) {
  const user = locals.session?.user;
  if (!user) return { error: getResponse({ error: 'Authentication required' }, 401) };
  if (!user.verified) return { error: getResponse({ error: 'Verified account required' }, 403) };
  return { user };
}

/**
 * GET /api/market/trade-requests — Get current user's trade requests
 */
export async function GET({ locals }) {
  const { user, error } = getVerifiedUser(locals);
  if (error) return error;

  try {
    const requests = await getUserTradeRequests(user.id);
    return getResponse(requests, 200);
  } catch (err) {
    console.error('Error fetching trade requests:', err);
    return getResponse({ error: 'Failed to fetch trade requests' }, 500);
  }
}

/**
 * POST /api/market/trade-requests — Create or add to a trade request
 * Requires market.trade grant.
 */
export async function POST({ request, locals }) {
  const { user, error } = getVerifiedUser(locals);
  if (error) return error;

  if (!hasGrant(locals, 'market.trade')) {
    return getResponse({ error: 'You do not have permission to create trade requests' }, 403);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON' }, 400);
  }

  // Validate target_id
  const targetId = parseInt(body.target_id, 10);
  if (!Number.isFinite(targetId) || targetId <= 0) {
    return getResponse({ error: 'target_id must be a positive integer' }, 400);
  }
  if (targetId === user.id) {
    return getResponse({ error: 'Cannot create a trade request with yourself' }, 400);
  }

  // Validate items
  const items = body.items;
  if (!Array.isArray(items) || items.length === 0) {
    return getResponse({ error: 'items must be a non-empty array' }, 400);
  }
  if (items.length > 50) {
    return getResponse({ error: 'Maximum 50 items per request' }, 400);
  }

  for (const item of items) {
    if (!item.item_id || !item.item_name || !item.side) {
      return getResponse({ error: 'Each item must have item_id, item_name, and side' }, 400);
    }
    if (!['BUY', 'SELL'].includes(item.side)) {
      return getResponse({ error: 'Item side must be BUY or SELL' }, 400);
    }
  }

  const planet = body.planet || null;

  try {
    const result = await getOrCreateTradeRequest(user.id, targetId, planet, items);
    return getResponse(result, result.isNew ? 201 : 200);
  } catch (err) {
    // Unique constraint violation = open request already exists (race condition)
    if (err.code === '23505') {
      return getResponse({ error: 'An open trade request already exists between you and this user' }, 409);
    }
    console.error('Error creating trade request:', err);
    return getResponse({ error: 'Failed to create trade request' }, 500);
  }
}
