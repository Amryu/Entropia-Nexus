//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getOfferById, updateOffer, closeOffer, PLANETS } from '$lib/server/exchange.js';

function getVerifiedUser(locals) {
  const user = locals.session?.user;
  if (!user) return { error: getResponse({ error: 'Authentication required' }, 401) };
  if (!user.verified) return { error: getResponse({ error: 'Verified account required' }, 403) };
  return { user };
}

/**
 * PUT /api/market/exchange/offers/[id] — Edit an offer
 */
export async function PUT({ params, request, locals }) {
  const { user, error } = getVerifiedUser(locals);
  if (error) return error;

  const offerId = parseInt(params.id, 10);
  if (!Number.isFinite(offerId)) {
    return getResponse({ error: 'Invalid offer ID' }, 400);
  }

  // Verify ownership
  const existing = await getOfferById(offerId);
  if (!existing) {
    return getResponse({ error: 'Offer not found' }, 404);
  }
  if (String(existing.user_id) !== String(user.id)) {
    return getResponse({ error: 'Not authorized' }, 403);
  }
  if (existing.state === 'closed') {
    return getResponse({ error: 'Cannot edit a closed offer' }, 400);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON' }, 400);
  }

  // Validate fields
  const quantity = parseInt(body.quantity, 10);
  if (!Number.isFinite(quantity) || quantity < 1) {
    return getResponse({ error: 'quantity must be at least 1' }, 400);
  }

  const markup = parseFloat(body.markup);
  if (!Number.isFinite(markup) || markup < 0) {
    return getResponse({ error: 'markup must be a non-negative number' }, 400);
  }

  const planet = body.planet || null;
  if (planet && !PLANETS.includes(planet)) {
    return getResponse({ error: `planet must be one of: ${PLANETS.join(', ')}` }, 400);
  }

  const minQuantity = body.min_quantity != null ? parseInt(body.min_quantity, 10) : null;
  const details = body.details || null;

  try {
    const updated = await updateOffer(offerId, { quantity, minQuantity, markup, planet, details });
    return getResponse(updated, 200);
  } catch (err) {
    console.error('Error updating offer:', err);
    return getResponse({ error: 'Failed to update offer' }, 500);
  }
}

/**
 * DELETE /api/market/exchange/offers/[id] — Close an offer
 */
export async function DELETE({ params, locals }) {
  const { user, error: authErr } = getVerifiedUser(locals);
  if (authErr) return authErr;

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
    return getResponse({ error: 'Offer is already closed' }, 400);
  }

  try {
    await closeOffer(offerId);
    return getResponse({ success: true }, 200);
  } catch (err) {
    console.error('Error closing offer:', err);
    return getResponse({ error: 'Failed to close offer' }, 500);
  }
}
