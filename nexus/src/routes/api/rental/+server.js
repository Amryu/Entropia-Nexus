//@ts-nocheck
import { getRentalOffers, createRentalOffer, countUserRentalOffers, getUserItemSetById } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';
import { sanitizeRentalOfferData, validateItemSetForRental, MAX_RENTAL_OFFERS_PER_USER } from '$lib/server/rentalUtils.js';
import { requireGrantAPI } from '$lib/server/auth.js';

// GET /api/rental — List available rental offers
export async function GET({ url }) {
  const filters = {};

  const planetId = url.searchParams.get('planet_id');
  if (planetId) filters.planet_id = parseInt(planetId);

  const limit = Math.min(parseInt(url.searchParams.get('limit')) || 50, 100);
  const page = Math.max(parseInt(url.searchParams.get('page')) || 1, 1);
  filters.limit = limit;
  filters.offset = (page - 1) * limit;

  try {
    const offers = await getRentalOffers(filters);
    return getResponse(offers, 200);
  } catch (error) {
    console.error('Error fetching rental offers:', error);
    return getResponse({ error: 'Failed to fetch rental offers.' }, 500);
  }
}

// POST /api/rental — Create new rental offer
export async function POST({ request, locals }) {
  const user = requireGrantAPI(locals, 'rental.manage');

  // Rate limit
  const rateCheck = checkRateLimit(`rental:create:${user.id}`, 5, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  // Sanitize
  const { data, error } = sanitizeRentalOfferData(body, false);
  if (error) {
    return getResponse({ error }, 400);
  }

  try {
    // Check offer count limit
    const count = await countUserRentalOffers(user.id);
    if (count >= MAX_RENTAL_OFFERS_PER_USER) {
      return getResponse({ error: `You can have at most ${MAX_RENTAL_OFFERS_PER_USER} rental offers.` }, 400);
    }

    // Verify the item set belongs to the user
    const itemSet = await getUserItemSetById(user.id, data.item_set_id);
    if (!itemSet) {
      return getResponse({ error: 'Item set not found or does not belong to you.' }, 404);
    }

    // Validate item set contents are rental-compatible
    const validation = validateItemSetForRental(itemSet.data);
    if (!validation.valid) {
      return getResponse({ error: validation.error }, 400);
    }

    const offer = await createRentalOffer({
      user_id: user.id,
      ...data
    });

    return getResponse(offer, 201);
  } catch (error) {
    console.error('Error creating rental offer:', error);
    return getResponse({ error: 'Failed to create rental offer.' }, 500);
  }
}
