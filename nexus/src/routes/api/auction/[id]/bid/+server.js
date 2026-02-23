// @ts-nocheck
/**
 * POST /api/auction/[id]/bid — Place a bid (verified, requires Turnstile)
 */
import { getResponse } from '$lib/util.js';
import { checkRateLimitPeek, incrementRateLimit } from '$lib/server/rateLimiter.js';
import { verifyTurnstile } from '$lib/server/turnstile.js';
import { isOAuthRequest } from '$lib/server/auth.js';
import { placeBid, hasAcceptedDisclaimer, RATE_LIMIT_BID_PER_MIN } from '$lib/server/auction.js';

export async function POST({ params, request, locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  // Rate limit (peek first, increment on success)
  const rateKey = `auction:bid:${user.id}`;
  const rateCheck = checkRateLimitPeek(rateKey, RATE_LIMIT_BID_PER_MIN, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({
      error: 'Too many bid attempts. Please slow down.',
      retryAfter: Math.ceil(rateCheck.resetIn / 1000)
    }, 429);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON' }, 400);
  }

  // Verify Turnstile token (skipped for OAuth-authenticated requests)
  if (!isOAuthRequest(locals)) {
    const turnstileToken = body.turnstile_token;
    if (!turnstileToken) {
      return getResponse({ error: 'Captcha verification required' }, 400);
    }

    const ip = locals.ip || request.headers.get('x-forwarded-for') || request.headers.get('cf-connecting-ip');
    const turnstileValid = await verifyTurnstile(turnstileToken, ip);
    if (!turnstileValid) {
      return getResponse({ error: 'Captcha verification failed. Please try again.' }, 400);
    }
  }

  // Check bidder disclaimer
  const hasDisclaimer = await hasAcceptedDisclaimer(user.id, 'bidder');
  if (!hasDisclaimer) {
    return getResponse({ error: 'You must accept the bidder disclaimer first' }, 403);
  }

  // Validate amount
  const amount = parseFloat(body.amount);
  if (!Number.isFinite(amount) || amount <= 0) {
    return getResponse({ error: 'Invalid bid amount' }, 400);
  }

  try {
    const result = await placeBid(params.id, user.id, amount);
    if (result.error) {
      return getResponse({ error: result.error }, 400);
    }

    // Increment rate limit on success
    incrementRateLimit(rateKey, 60_000);

    return getResponse({
      bid: result.bid,
      auction: {
        current_bid: result.auction.current_bid,
        bid_count: result.auction.bid_count,
        ends_at: result.auction.ends_at
      }
    }, 200);
  } catch (err) {
    console.error('Error placing bid:', err);
    return getResponse({ error: 'Failed to place bid' }, 500);
  }
}
