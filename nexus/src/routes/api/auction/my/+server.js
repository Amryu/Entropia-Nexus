// @ts-nocheck
/**
 * GET /api/auction/my — Get user's auctions and bids (verified)
 */
import { getResponse } from '$lib/util.js';
import { getUserAuctions, getUserBids, endExpiredAuctions } from '$lib/server/auction.js';

export async function GET({ locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  try {
    // End any expired auctions
    await endExpiredAuctions();

    const [auctions, bids] = await Promise.all([
      getUserAuctions(user.id),
      getUserBids(user.id)
    ]);

    return getResponse({ auctions, bids }, 200);
  } catch (err) {
    console.error('Error fetching user auction data:', err);
    return getResponse({ error: 'Failed to fetch your auction data' }, 500);
  }
}
