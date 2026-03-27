//@ts-nocheck
import { getPromoBookingById, updatePromoBooking, updatePromoBookingStatus } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';
import { requireVerifiedAPI } from '$lib/server/auth.js';

const MIN_WEEKS = 1;
const MAX_WEEKS = 52;

// GET booking detail (owner check)
export async function GET({ params, locals }) {
  const user = requireVerifiedAPI(locals);

  const bookingId = parseInt(params.id);
  if (isNaN(bookingId)) {
    return getResponse({ error: 'Invalid booking ID.' }, 400);
  }

  try {
    const booking = await getPromoBookingById(bookingId);
    if (!booking) {
      return getResponse({ error: 'Booking not found.' }, 404);
    }

    if (String(booking.user_id) !== String(user.id) && !user.grants?.includes('admin.panel')) {
      return getResponse({ error: 'You do not have permission to view this booking.' }, 403);
    }

    return getResponse(booking, 200);
  } catch (err) {
    console.error('Error fetching booking:', err);
    return getResponse({ error: 'Failed to fetch booking.' }, 500);
  }
}

// PUT update booking (owner check, only while status='pending')
export async function PUT({ params, request, locals }) {
  const user = requireVerifiedAPI(locals);

  const rateCheck = checkRateLimit(`promos:booking:update:${user.id}`, 20, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  const bookingId = parseInt(params.id);
  if (isNaN(bookingId)) {
    return getResponse({ error: 'Invalid booking ID.' }, 400);
  }

  const booking = await getPromoBookingById(bookingId);
  if (!booking) {
    return getResponse({ error: 'Booking not found.' }, 404);
  }

  if (String(booking.user_id) !== String(user.id) && !user.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You can only edit your own bookings.' }, 403);
  }

  if (booking.status !== 'pending') {
    return getResponse({ error: 'Only pending bookings can be updated.' }, 400);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  const fields = {};

  // Validate start_date if provided
  if (body.start_date !== undefined) {
    const parsedDate = new Date(body.start_date);
    if (isNaN(parsedDate.getTime())) {
      return getResponse({ error: 'Invalid start date format.' }, 400);
    }
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    if (parsedDate < today) {
      return getResponse({ error: 'Start date must be today or in the future.' }, 400);
    }
    fields.start_date = body.start_date;
  }

  // Validate weeks if provided
  if (body.weeks !== undefined) {
    const weeks = parseInt(body.weeks);
    if (isNaN(weeks) || weeks < MIN_WEEKS || weeks > MAX_WEEKS) {
      return getResponse({ error: `Weeks must be between ${MIN_WEEKS} and ${MAX_WEEKS}.` }, 400);
    }
    fields.weeks = weeks;
  }

  if (Object.keys(fields).length === 0) {
    return getResponse({ error: 'No valid fields to update.' }, 400);
  }

  try {
    const updated = await updatePromoBooking(bookingId, fields);
    return getResponse(updated, 200);
  } catch (err) {
    console.error('Error updating booking:', err);
    return getResponse({ error: 'Failed to update booking.' }, 500);
  }
}

// DELETE cancel booking (owner check, only pending or approved)
export async function DELETE({ params, locals }) {
  const user = requireVerifiedAPI(locals);

  const rateCheck = checkRateLimit(`promos:booking:cancel:${user.id}`, 10, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  const bookingId = parseInt(params.id);
  if (isNaN(bookingId)) {
    return getResponse({ error: 'Invalid booking ID.' }, 400);
  }

  const booking = await getPromoBookingById(bookingId);
  if (!booking) {
    return getResponse({ error: 'Booking not found.' }, 404);
  }

  if (String(booking.user_id) !== String(user.id) && !user.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You can only cancel your own bookings.' }, 403);
  }

  if (booking.status !== 'pending' && booking.status !== 'approved') {
    return getResponse({ error: 'Only pending or approved bookings can be cancelled.' }, 400);
  }

  try {
    const updated = await updatePromoBookingStatus(bookingId, 'cancelled');
    return getResponse(updated, 200);
  } catch (err) {
    console.error('Error cancelling booking:', err);
    return getResponse({ error: 'Failed to cancel booking.' }, 500);
  }
}
