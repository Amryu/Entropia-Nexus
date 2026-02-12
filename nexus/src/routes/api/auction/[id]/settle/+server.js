// @ts-nocheck
/**
 * POST /api/auction/[id]/settle — Settle an ended auction (seller)
 */
import { getResponse } from '$lib/util.js';
import { checkRateLimitPeek, incrementRateLimit } from '$lib/server/rateLimiter.js';
import { settleAuction, RATE_LIMIT_SETTLE_PER_MIN } from '$lib/server/auction.js';

export async function POST({ params, locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  // Rate limit (peek-then-increment — only increment on success)
  const rateCheck = checkRateLimitPeek(`auction:settle:${user.id}`, RATE_LIMIT_SETTLE_PER_MIN, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.', retryAfter: Math.ceil(rateCheck.resetIn / 1000) }, 429);
  }

  try {
    const result = await settleAuction(params.id, user.id);
    if (result.error) {
      return getResponse({ error: result.error }, 400);
    }
    incrementRateLimit(`auction:settle:${user.id}`, RATE_LIMIT_SETTLE_PER_MIN, 60_000);
    return getResponse(result, 200);
  } catch (err) {
    console.error('Error settling auction:', err);
    return getResponse({ error: 'Failed to settle auction' }, 500);
  }
}
