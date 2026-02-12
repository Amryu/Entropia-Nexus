// @ts-nocheck
/**
 * POST /api/auction/[id]/admin/rollback — Rollback bids to a point (admin)
 */
import { getResponse } from '$lib/util.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';
import { requireAdmin } from '$lib/server/auth.js';
import { rollbackBids, RATE_LIMIT_ADMIN_PER_MIN } from '$lib/server/auction.js';

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

  // target_bid_id: null/undefined means rollback ALL bids
  const targetBidId = body.target_bid_id || null;

  try {
    const result = await rollbackBids(params.id, user.id, targetBidId, reason);
    if (result.error) return getResponse({ error: result.error }, 400);
    return getResponse(result, 200);
  } catch (err) {
    console.error('Error rolling back bids:', err);
    return getResponse({ error: 'Failed to rollback bids' }, 500);
  }
}
