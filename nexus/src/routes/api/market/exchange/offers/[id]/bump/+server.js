//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getOfferById, bumpOffer } from '$lib/server/exchange.js';

/**
 * POST /api/market/exchange/offers/[id]/bump — Bump an offer
 */
export async function POST({ params, locals }) {
  const user = locals.session?.user;
  if (!user) return getResponse({ error: 'Authentication required' }, 401);
  if (!user.verified) return getResponse({ error: 'Verified account required' }, 403);

  const offerId = parseInt(params.id, 10);
  if (!Number.isFinite(offerId)) {
    return getResponse({ error: 'Invalid offer ID' }, 400);
  }

  const existing = await getOfferById(offerId);
  if (!existing) {
    return getResponse({ error: 'Offer not found' }, 404);
  }
  if (String(existing.user_id) !== String(user.id)) {
    return getResponse({ error: 'Not authorized' }, 403);
  }
  if (existing.state === 'closed') {
    return getResponse({ error: 'Cannot bump a closed offer' }, 400);
  }
  // Terminated offers (>30 days) must be re-created, not bumped
  if (existing.computed_state === 'terminated') {
    return getResponse({ error: 'This offer has expired. Please create a new offer.' }, 400);
  }

  try {
    const bumped = await bumpOffer(offerId);
    return getResponse(bumped, 200);
  } catch (err) {
    console.error('Error bumping offer:', err);
    return getResponse({ error: 'Failed to bump offer' }, 500);
  }
}
