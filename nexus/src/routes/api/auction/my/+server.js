// @ts-nocheck
/**
 * GET /api/auction/my — Get user's auctions and bids (verified)
 */
import { getResponse } from '$lib/util.js';
import { requireGrantAPI } from '$lib/server/auth.js';
import { getUserAuctions, getUserBids, endExpiredAuctions } from '$lib/server/auction.js';

export async function GET({ locals }) {
  const user = requireGrantAPI(locals, 'auction.read');

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
