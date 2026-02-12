// @ts-nocheck
/**
 * GET  /api/auction — List auctions (public)
 * POST /api/auction — Create draft auction (verified)
 */
import { getResponse } from '$lib/util.js';
import { checkRateLimitPeek, incrementRateLimit } from '$lib/server/rateLimiter.js';
import {
  listAuctions, createAuction, countUserActiveAuctions, validateAuctionInput,
  insertAuditLog, hasAcceptedDisclaimer,
  MAX_AUCTIONS_PER_USER, RATE_LIMIT_CREATE_PER_HOUR
} from '$lib/server/auction.js';
import { pool } from '$lib/server/db.js';

// Allowed statuses for public listing (drafts are private)
const PUBLIC_STATUSES = ['active', 'ended', 'settled', 'cancelled'];

export async function GET({ url }) {
  const rawStatus = url.searchParams.get('status') || 'active';
  const status = PUBLIC_STATUSES.includes(rawStatus) ? rawStatus : 'active';
  const search = url.searchParams.get('search') || undefined;
  const sort = url.searchParams.get('sort') || 'ends_at';
  const order = url.searchParams.get('order') || 'asc';
  const limit = parseInt(url.searchParams.get('limit'), 10) || 24;
  const offset = parseInt(url.searchParams.get('offset'), 10) || 0;

  try {
    const result = await listAuctions({ status, search, sort, order, limit, offset });
    return getResponse(result, 200);
  } catch (err) {
    console.error('Error listing auctions:', err);
    return getResponse({ error: 'Failed to fetch auctions' }, 500);
  }
}

export async function POST({ request, locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  // Rate limit (peek-then-increment — only increment on success)
  const rateCheck = checkRateLimitPeek(`auction:create:${user.id}`, RATE_LIMIT_CREATE_PER_HOUR, 3_600_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many auction creations. Please try again later.', retryAfter: Math.ceil(rateCheck.resetIn / 1000) }, 429);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON' }, 400);
  }

  // Validate input
  const validation = validateAuctionInput(body);
  if (validation.error) return getResponse({ error: validation.error }, 400);

  try {
    // Check seller disclaimer
    const hasDisclaimer = await hasAcceptedDisclaimer(user.id, 'seller');
    if (!hasDisclaimer) {
      return getResponse({ error: 'You must accept the seller disclaimer first' }, 403);
    }

    // Check auction count limit
    const count = await countUserActiveAuctions(user.id);
    if (count >= MAX_AUCTIONS_PER_USER) {
      return getResponse({ error: `Maximum ${MAX_AUCTIONS_PER_USER} active auctions allowed` }, 400);
    }

    // Verify item set belongs to user
    const { rows: sets } = await pool.query(
      `SELECT id FROM item_sets WHERE id = $1 AND user_id = $2`,
      [validation.data.item_set_id, user.id]
    );
    if (sets.length === 0) {
      return getResponse({ error: 'Item set not found or not yours' }, 400);
    }

    const auction = await createAuction(user.id, validation.data);
    await insertAuditLog(null, auction.id, user.id, 'created', {
      title: validation.data.title,
      starting_bid: validation.data.starting_bid,
      buyout_price: validation.data.buyout_price,
      duration_days: validation.data.duration_days
    });

    incrementRateLimit(`auction:create:${user.id}`, RATE_LIMIT_CREATE_PER_HOUR, 3_600_000);
    return getResponse(auction, 201);
  } catch (err) {
    console.error('Error creating auction:', err);
    return getResponse({ error: 'Failed to create auction' }, 500);
  }
}
