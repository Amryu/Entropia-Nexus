//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { bumpAllOrders, formatRetryTime, RATE_LIMIT_BUMP_ALL_PER_MIN } from '$lib/server/exchange.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';
import { verifyTurnstile } from '$lib/server/turnstile.js';

/**
 * POST /api/market/exchange/orders/bump-all — Bump all eligible orders for the current user
 */
export async function POST({ request, locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  // Verify Turnstile
  let body = {};
  try { body = await request.json(); } catch {}
  const turnstileToken = body.turnstile_token;
  if (!turnstileToken) return getResponse({ error: 'Captcha verification required' }, 400);
  const ip = locals.ip || request.headers.get('x-forwarded-for') || request.headers.get('cf-connecting-ip');
  if (!await verifyTurnstile(turnstileToken, ip)) return getResponse({ error: 'Captcha verification failed. Please try again.' }, 400);

  const bumpCheck = checkRateLimit(`order:bump-all:${user.id}`, RATE_LIMIT_BUMP_ALL_PER_MIN, 60_000);
  if (!bumpCheck.allowed) {
    const retryAfter = Math.ceil(bumpCheck.resetIn / 1000);
    return getResponse({
      error: `You can only bump all orders once per minute. Try again in ${formatRetryTime(retryAfter)}.`,
      retryAfter
    }, 429);
  }

  try {
    const orders = await bumpAllOrders(user.id);
    return getResponse({ orders, count: orders.length }, 200);
  } catch (err) {
    console.error('Error bumping all orders:', err);
    return getResponse({ error: 'Failed to bump orders' }, 500);
  }
}
