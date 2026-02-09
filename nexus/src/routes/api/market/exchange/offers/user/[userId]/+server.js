//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getUserPublicOffers } from '$lib/server/trade-requests.js';

/**
 * GET /api/market/exchange/offers/user/[userId] — Get all active offers by a user
 * Public endpoint (no auth required).
 */
export async function GET({ params }) {
  const userId = params.userId;
  if (!userId || !/^\d+$/.test(userId)) {
    return getResponse({ error: 'Invalid user ID' }, 400);
  }

  try {
    const offers = await getUserPublicOffers(userId);
    return getResponse(offers, 200);
  } catch (err) {
    console.error('Error fetching user offers:', err);
    return getResponse({ error: 'Failed to fetch user offers' }, 500);
  }
}
