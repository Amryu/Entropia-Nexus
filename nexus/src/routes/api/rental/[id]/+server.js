//@ts-nocheck
import { getRentalOfferById, updateRentalOffer, softDeleteRentalOffer, getRentalRequests, getUserItemSetById } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';
import { sanitizeRentalOfferData, validateItemSetForRental } from '$lib/server/rentalUtils.js';

// Valid status transitions
const VALID_TRANSITIONS = {
  draft: ['available'],
  available: ['draft', 'unlisted', 'deleted'],
  rented: ['unlisted', 'deleted'],
  unlisted: ['available', 'deleted']
};

// GET /api/rental/[id] — Get single rental offer with item set data
export async function GET({ params, locals }) {
  const id = parseInt(params.id);
  if (isNaN(id)) {
    return getResponse({ error: 'Invalid offer ID.' }, 400);
  }

  try {
    const offer = await getRentalOfferById(id);
    if (!offer) {
      return getResponse({ error: 'Rental offer not found.' }, 404);
    }

    // Draft offers only visible to owner or admin
    if (offer.status === 'draft') {
      const user = locals.session?.user;
      if (!user || (offer.user_id !== user.id && !user.grants?.includes('admin.panel'))) {
        return getResponse({ error: 'Rental offer not found.' }, 404);
      }
    }

    return getResponse(offer, 200);
  } catch (error) {
    console.error('Error fetching rental offer:', error);
    return getResponse({ error: 'Failed to fetch rental offer.' }, 500);
  }
}

// PUT /api/rental/[id] — Update rental offer
export async function PUT({ params, request, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }
  if (!user.verified) {
    return getResponse({ error: 'You must verify your account.' }, 403);
  }

  const id = parseInt(params.id);
  if (isNaN(id)) {
    return getResponse({ error: 'Invalid offer ID.' }, 400);
  }

  // Rate limit
  const rateCheck = checkRateLimit(`rental:update:${user.id}`, 20, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  // Check ownership
  const existing = await getRentalOfferById(id);
  if (!existing) {
    return getResponse({ error: 'Rental offer not found.' }, 404);
  }
  if (existing.user_id !== user.id && !user.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You can only edit your own offers.' }, 403);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  // Sanitize
  const { data, error } = sanitizeRentalOfferData(body, true);
  if (error) {
    return getResponse({ error }, 400);
  }

  // Validate status transition
  if (data.status && data.status !== existing.status) {
    const allowed = VALID_TRANSITIONS[existing.status];
    if (!allowed || !allowed.includes(data.status)) {
      return getResponse({ error: `Cannot change status from '${existing.status}' to '${data.status}'.` }, 400);
    }

    // Check for active requests before certain transitions
    if (data.status === 'draft' || data.status === 'deleted') {
      const requests = await getRentalRequests(id);
      const activeRequests = requests.filter(r => ['accepted', 'in_progress'].includes(r.status));

      if (activeRequests.length > 0) {
        return getResponse({
          error: `Cannot ${data.status === 'deleted' ? 'delete' : 'revert to draft'} with ${activeRequests.length} active request(s). Complete or cancel them first.`,
          activeRequests: activeRequests.length
        }, 400);
      }
    }
  }

  // Block item set, pricing, and field changes when not in draft
  if (existing.status !== 'draft') {
    const draftOnlyFields = ['item_set_id', 'price_per_day', 'discounts', 'deposit', 'title', 'description', 'planet_id', 'location'];
    const blockedFields = draftOnlyFields.filter(f => data[f] !== undefined);
    if (blockedFields.length > 0) {
      return getResponse({ error: 'Offer details can only be edited in draft status.' }, 400);
    }
  }

  // If item_set_id is changing, validate the new set's contents
  if (data.item_set_id && data.item_set_id !== existing.item_set_id) {
    const itemSet = await getUserItemSetById(existing.user_id, data.item_set_id);
    if (!itemSet) {
      return getResponse({ error: 'Item set not found or does not belong to you.' }, 404);
    }
    const validation = validateItemSetForRental(itemSet.data);
    if (!validation.valid) {
      return getResponse({ error: validation.error }, 400);
    }
  }

  try {
    // Use offer owner's ID for the DB query (admin may be acting on behalf of owner)
    const updated = await updateRentalOffer(id, existing.user_id, data, existing.status);
    if (!updated) {
      return getResponse({ error: 'Failed to update offer. It may have been modified concurrently.' }, 409);
    }
    return getResponse(updated, 200);
  } catch (error) {
    console.error('Error updating rental offer:', error);
    return getResponse({ error: 'Failed to update rental offer.' }, 500);
  }
}

// DELETE /api/rental/[id] — Soft delete rental offer
export async function DELETE({ params, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }
  if (!user.verified) {
    return getResponse({ error: 'You must verify your account.' }, 403);
  }

  const id = parseInt(params.id);
  if (isNaN(id)) {
    return getResponse({ error: 'Invalid offer ID.' }, 400);
  }

  // Rate limit
  const rateCheck = checkRateLimit(`rental:delete:${user.id}`, 10, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  const existing = await getRentalOfferById(id);
  if (!existing) {
    return getResponse({ error: 'Rental offer not found.' }, 404);
  }
  if (existing.user_id !== user.id && !user.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You can only delete your own offers.' }, 403);
  }

  // Check for active requests
  const requests = await getRentalRequests(id);
  const activeRequests = requests.filter(r => ['accepted', 'in_progress'].includes(r.status));
  if (activeRequests.length > 0) {
    return getResponse({
      error: `Cannot delete offer with ${activeRequests.length} active request(s). Complete or cancel them first.`,
      activeRequests: activeRequests.length
    }, 409);
  }

  try {
    const result = await softDeleteRentalOffer(id, existing.user_id);
    if (!result) {
      return getResponse({ error: 'Failed to delete offer.' }, 500);
    }
    return getResponse({ success: true }, 200);
  } catch (error) {
    console.error('Error deleting rental offer:', error);
    return getResponse({ error: 'Failed to delete rental offer.' }, 500);
  }
}
