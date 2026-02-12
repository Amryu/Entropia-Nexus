// @ts-nocheck
/**
 * POST /api/auction/[id]/buyout — Buy out an auction (verified, requires Turnstile)
 */
import { getResponse } from '$lib/util.js';
import { checkRateLimitPeek, incrementRateLimit } from '$lib/server/rateLimiter.js';
import { verifyTurnstile } from '$lib/server/turnstile.js';
import { buyoutAuction, hasAcceptedDisclaimer, RATE_LIMIT_BUYOUT_PER_MIN } from '$lib/server/auction.js';

export async function POST({ params, request, locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  // Rate limit
  const rateKey = `auction:buyout:${user.id}`;
  const rateCheck = checkRateLimitPeek(rateKey, RATE_LIMIT_BUYOUT_PER_MIN, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({
      error: 'Too many buyout attempts. Please slow down.',
      retryAfter: Math.ceil(rateCheck.resetIn / 1000)
    }, 429);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON' }, 400);
  }

  // Verify Turnstile token
  const turnstileToken = body.turnstile_token;
  if (!turnstileToken) {
    return getResponse({ error: 'Captcha verification required' }, 400);
  }

  const ip = locals.ip || request.headers.get('x-forwarded-for') || request.headers.get('cf-connecting-ip');
  const turnstileValid = await verifyTurnstile(turnstileToken, ip);
  if (!turnstileValid) {
    return getResponse({ error: 'Captcha verification failed. Please try again.' }, 400);
  }

  // Check bidder disclaimer (buyout counts as bidding)
  const hasDisclaimer = await hasAcceptedDisclaimer(user.id, 'bidder');
  if (!hasDisclaimer) {
    return getResponse({ error: 'You must accept the bidder disclaimer first' }, 403);
  }

  try {
    const result = await buyoutAuction(params.id, user.id);
    if (result.error) {
      return getResponse({ error: result.error }, 400);
    }

    incrementRateLimit(rateKey, 60_000);

    return getResponse({ auction: result.auction }, 200);
  } catch (err) {
    console.error('Error buying out auction:', err);
    return getResponse({ error: 'Failed to buy out auction' }, 500);
  }
}
