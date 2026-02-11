//@ts-nocheck
import { getRentalOfferById, getRentalRequests, createRentalRequest, checkRentalDateConflict } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';
import { validateDateRange, sanitizeNote } from '$lib/server/rentalUtils.js';
import { calculateRentalPrice, countDays } from '$lib/utils/rentalPricing.js';

// GET /api/rental/[id]/requests — List requests for this offer (owner only)
export async function GET({ params, locals }) {
  const user = locals.session?.user;
  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  const offerId = parseInt(params.id);
  if (isNaN(offerId)) {
    return getResponse({ error: 'Invalid offer ID.' }, 400);
  }

  const offer = await getRentalOfferById(offerId);
  if (!offer) {
    return getResponse({ error: 'Rental offer not found.' }, 404);
  }
  if (offer.user_id !== user.id && !user.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You can only view requests for your own offers.' }, 403);
  }

  try {
    const requests = await getRentalRequests(offerId);
    return getResponse(requests, 200);
  } catch (error) {
    console.error('Error fetching rental requests:', error);
    return getResponse({ error: 'Failed to fetch requests.' }, 500);
  }
}

// POST /api/rental/[id]/requests — Create rental request
export async function POST({ params, request, locals }) {
  const user = locals.session?.user;
  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }
  if (!user.verified) {
    return getResponse({ error: 'You must verify your account before making rental requests.' }, 403);
  }

  const offerId = parseInt(params.id);
  if (isNaN(offerId)) {
    return getResponse({ error: 'Invalid offer ID.' }, 400);
  }

  // Rate limit
  const rateCheck = checkRateLimit(`rental:request:${user.id}`, 10, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  const offer = await getRentalOfferById(offerId);
  if (!offer) {
    return getResponse({ error: 'Rental offer not found.' }, 404);
  }
  if (offer.status !== 'available') {
    return getResponse({ error: 'This offer is not currently available for rental.' }, 400);
  }
  if (offer.user_id === user.id) {
    return getResponse({ error: 'You cannot rent your own items.' }, 400);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  // Validate date range
  const dateValidation = validateDateRange(body.start_date, body.end_date);
  if (!dateValidation.valid) {
    return getResponse({ error: dateValidation.error }, 400);
  }

  // Check for date conflicts
  try {
    const hasConflict = await checkRentalDateConflict(offerId, body.start_date, body.end_date);
    if (hasConflict) {
      return getResponse({ error: 'The requested dates overlap with an existing booking or blocked period.' }, 409);
    }

    // Calculate pricing
    const totalDays = countDays(body.start_date, body.end_date);
    const pricing = calculateRentalPrice(
      parseFloat(offer.price_per_day),
      offer.discounts || [],
      totalDays
    );

    const rentalRequest = await createRentalRequest({
      offer_id: offerId,
      requester_id: user.id,
      start_date: body.start_date,
      end_date: body.end_date,
      total_days: pricing.totalDays,
      price_per_day: pricing.pricePerDay,
      discount_pct: pricing.discountPct,
      total_price: pricing.totalPrice,
      deposit: parseFloat(offer.deposit) || 0,
      requester_note: sanitizeNote(body.note)
    });

    // Atomic conflict check returned null — dates were taken between check and insert
    if (!rentalRequest) {
      return getResponse({ error: 'The requested dates overlap with an existing booking or blocked period.' }, 409);
    }

    return getResponse(rentalRequest, 201);
  } catch (error) {
    console.error('Error creating rental request:', error);
    return getResponse({ error: 'Failed to create rental request.' }, 500);
  }
}
