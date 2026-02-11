//@ts-nocheck
import { getUserRentalOffers, getUserRentalRequests } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';

// GET /api/rental/my — User's own offers or requests
export async function GET({ url, locals }) {
  const user = locals.session?.user;
  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  const type = url.searchParams.get('type') || 'offers';

  try {
    if (type === 'requests') {
      const requests = await getUserRentalRequests(user.id);
      return getResponse(requests, 200);
    }

    // Default: offers
    const offers = await getUserRentalOffers(user.id);
    return getResponse(offers, 200);
  } catch (error) {
    console.error('Error fetching user rental data:', error);
    return getResponse({ error: 'Failed to fetch rental data.' }, 500);
  }
}
