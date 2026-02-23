//@ts-nocheck
import { getRentalOfferById, getRentalBlockedDates, addRentalBlockedDate, deleteRentalBlockedDate, countRentalBlockedDates } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';
import { requireGrantAPI } from '$lib/server/auth.js';
import { validateDate, MAX_BLOCKED_RANGES } from '$lib/server/rentalUtils.js';

// GET /api/rental/[id]/blocked-dates — List blocked date ranges
export async function GET({ params, locals }) {
  const user = requireGrantAPI(locals, 'rental.manage');

  const id = parseInt(params.id);
  if (isNaN(id)) {
    return getResponse({ error: 'Invalid offer ID.' }, 400);
  }

  const offer = await getRentalOfferById(id);
  if (!offer) {
    return getResponse({ error: 'Rental offer not found.' }, 404);
  }
  if (offer.user_id !== user.id && !user.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You can only manage your own offers.' }, 403);
  }

  try {
    const dates = await getRentalBlockedDates(id);
    return getResponse(dates, 200);
  } catch (error) {
    console.error('Error fetching blocked dates:', error);
    return getResponse({ error: 'Failed to fetch blocked dates.' }, 500);
  }
}

// POST /api/rental/[id]/blocked-dates — Add blocked date range
export async function POST({ params, request, locals }) {
  const user = requireGrantAPI(locals, 'rental.manage');

  const id = parseInt(params.id);
  if (isNaN(id)) {
    return getResponse({ error: 'Invalid offer ID.' }, 400);
  }

  // Rate limit
  const rateCheck = checkRateLimit(`rental:blocked:${user.id}`, 20, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  const offer = await getRentalOfferById(id);
  if (!offer) {
    return getResponse({ error: 'Rental offer not found.' }, 404);
  }
  if (offer.user_id !== user.id && !user.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You can only manage your own offers.' }, 403);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  const startDate = validateDate(body.start_date);
  const endDate = validateDate(body.end_date);

  if (!startDate || !endDate) {
    return getResponse({ error: 'Invalid date format. Use YYYY-MM-DD.' }, 400);
  }
  if (new Date(endDate) < new Date(startDate)) {
    return getResponse({ error: 'End date must be on or after start date.' }, 400);
  }

  // Bounds check: not in the past, not more than 2 years ahead
  const today = new Date();
  today.setUTCHours(0, 0, 0, 0);
  if (new Date(startDate + 'T00:00:00Z') < today) {
    return getResponse({ error: 'Cannot block dates in the past.' }, 400);
  }
  const maxFuture = new Date(today);
  maxFuture.setUTCFullYear(maxFuture.getUTCFullYear() + 2);
  if (new Date(endDate + 'T00:00:00Z') > maxFuture) {
    return getResponse({ error: 'Cannot block dates more than 2 years in the future.' }, 400);
  }

  try {
    const count = await countRentalBlockedDates(id);
    if (count >= MAX_BLOCKED_RANGES) {
      return getResponse({ error: `Maximum ${MAX_BLOCKED_RANGES} blocked date ranges allowed.` }, 400);
    }

    const reason = typeof body.reason === 'string' ? body.reason.trim().slice(0, 200) || null : null;
    const result = await addRentalBlockedDate(id, startDate, endDate, reason);
    return getResponse(result, 201);
  } catch (error) {
    console.error('Error adding blocked date:', error);
    return getResponse({ error: 'Failed to add blocked date.' }, 500);
  }
}

// DELETE /api/rental/[id]/blocked-dates — Remove blocked date range
export async function DELETE({ params, request, locals }) {
  const user = requireGrantAPI(locals, 'rental.manage');

  const offerId = parseInt(params.id);
  if (isNaN(offerId)) {
    return getResponse({ error: 'Invalid offer ID.' }, 400);
  }

  // Rate limit
  const rateCheck = checkRateLimit(`rental:blocked:${user.id}`, 20, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  const offer = await getRentalOfferById(offerId);
  if (!offer) {
    return getResponse({ error: 'Rental offer not found.' }, 404);
  }
  if (offer.user_id !== user.id && !user.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You can only manage your own offers.' }, 403);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  const blockedId = parseInt(body.id);
  if (isNaN(blockedId)) {
    return getResponse({ error: 'Invalid blocked date ID.' }, 400);
  }

  try {
    const result = await deleteRentalBlockedDate(blockedId, offerId);
    if (!result) {
      return getResponse({ error: 'Blocked date not found.' }, 404);
    }
    return getResponse({ success: true }, 200);
  } catch (error) {
    console.error('Error deleting blocked date:', error);
    return getResponse({ error: 'Failed to delete blocked date.' }, 500);
  }
}
