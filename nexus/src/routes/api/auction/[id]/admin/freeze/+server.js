// @ts-nocheck
/**
 * POST /api/auction/[id]/admin/freeze — Freeze or unfreeze an auction (admin)
 */
import { getResponse } from '$lib/util.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';
import { requireAdmin } from '$lib/server/auth.js';
import { freezeAuction, unfreezeAuction, getAuction, RATE_LIMIT_ADMIN_PER_MIN } from '$lib/server/auction.js';

export async function POST({ params, request, locals }) {
  let user;
  try {
    user = requireAdmin(locals);
  } catch (err) {
    return getResponse({ error: err.body?.message || 'Admin access required' }, err.status || 403);
  }

  // Rate limit
  const rateCheck = checkRateLimit(`auction:admin:${user.id}`, RATE_LIMIT_ADMIN_PER_MIN, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests' }, 429);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON' }, 400);
  }

  const reason = (typeof body.reason === 'string' ? body.reason.trim() : '').slice(0, 500);
  if (!reason) {
    return getResponse({ error: 'Reason is required' }, 400);
  }

  try {
    const auction = await getAuction(params.id);
    if (!auction) return getResponse({ error: 'Auction not found' }, 404);

    let result;
    if (auction.status === 'frozen') {
      // Unfreeze
      result = await unfreezeAuction(params.id, user.id, reason);
    } else {
      // Freeze
      result = await freezeAuction(params.id, user.id, reason);
    }

    if (result.error) return getResponse({ error: result.error }, 400);
    return getResponse(result, 200);
  } catch (err) {
    console.error('Error freezing/unfreezing auction:', err);
    return getResponse({ error: 'Failed to freeze/unfreeze auction' }, 500);
  }
}
