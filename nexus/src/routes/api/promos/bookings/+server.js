//@ts-nocheck
import { getPromoBookingsByUser, createPromoBooking, getPromoById } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';
import { requireVerifiedAPI } from '$lib/server/auth.js';

const VALID_SLOT_TYPES = ['left', 'right', 'featured_post'];
const MIN_WEEKS = 1;
const MAX_WEEKS = 52;

// Map promo_type to valid slot types
const PROMO_TYPE_SLOTS = {
  placement: ['left', 'right'],
  featured_post: ['featured_post']
};

// GET list user's bookings
export async function GET({ locals }) {
  const user = requireVerifiedAPI(locals);

  try {
    const bookings = await getPromoBookingsByUser(user.id);
    return getResponse(bookings, 200);
  } catch (err) {
    console.error('Error fetching bookings:', err);
    return getResponse({ error: 'Failed to fetch bookings.' }, 500);
  }
}

// POST create booking
export async function POST({ request, locals }) {
  const user = requireVerifiedAPI(locals);

  const rateCheck = checkRateLimit(`promos:booking:create:${user.id}`, 10, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  // Validate promo_id
  const promoId = parseInt(body.promo_id);
  if (isNaN(promoId)) {
    return getResponse({ error: 'Valid promo_id is required.' }, 400);
  }

  // Validate ownership of promo
  const promo = await getPromoById(promoId);
  if (!promo) {
    return getResponse({ error: 'Promo not found.' }, 404);
  }
  if (String(promo.owner_id) !== String(user.id)) {
    return getResponse({ error: 'You can only create bookings for your own promos.' }, 403);
  }

  // Validate slot_type
  const slotType = body.slot_type;
  if (!slotType || !VALID_SLOT_TYPES.includes(slotType)) {
    return getResponse({ error: `Invalid slot type. Must be one of: ${VALID_SLOT_TYPES.join(', ')}.` }, 400);
  }

  // Validate promo type matches slot type
  const allowedSlots = PROMO_TYPE_SLOTS[promo.promo_type];
  if (!allowedSlots || !allowedSlots.includes(slotType)) {
    return getResponse({ error: `Slot type '${slotType}' is not valid for promo type '${promo.promo_type}'. Allowed: ${allowedSlots?.join(', ') || 'none'}.` }, 400);
  }

  // Validate start_date
  const startDate = body.start_date;
  if (!startDate) {
    return getResponse({ error: 'Start date is required.' }, 400);
  }
  const parsedDate = new Date(startDate);
  if (isNaN(parsedDate.getTime())) {
    return getResponse({ error: 'Invalid start date format.' }, 400);
  }
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  if (parsedDate < today) {
    return getResponse({ error: 'Start date must be today or in the future.' }, 400);
  }

  // Validate weeks
  const weeks = parseInt(body.weeks);
  if (isNaN(weeks) || weeks < MIN_WEEKS || weeks > MAX_WEEKS) {
    return getResponse({ error: `Weeks must be between ${MIN_WEEKS} and ${MAX_WEEKS}.` }, 400);
  }

  try {
    const booking = await createPromoBooking({
      promoId,
      userId: user.id,
      slotType,
      startDate: startDate,
      weeks
    });
    return getResponse(booking, 201);
  } catch (err) {
    console.error('Error creating booking:', err);
    return getResponse({ error: 'Failed to create booking.' }, 500);
  }
}
