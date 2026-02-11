//@ts-nocheck
import {
  getRentalRequestById, updateRentalRequest, updateRentalOffer,
  updateRentalRequestWithOfferStatus,
  checkRentalDateConflict, createRentalExtension, getRentalExtensions,
  createNotification
} from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';
import { sanitizeNote, validateDate, MAX_PRICE_PER_DAY } from '$lib/server/rentalUtils.js';
import { calculateExtensionPrice, countDays } from '$lib/utils/rentalPricing.js';

// Valid status transitions per role
const OWNER_TRANSITIONS = {
  open: ['accepted', 'rejected'],
  accepted: ['in_progress'],
  in_progress: ['completed']
};
const REQUESTER_TRANSITIONS = {
  open: ['cancelled']
};

// GET /api/rental/requests/[requestId] — Get request details
export async function GET({ params, locals }) {
  const user = locals.session?.user;
  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  const requestId = parseInt(params.requestId);
  if (isNaN(requestId)) {
    return getResponse({ error: 'Invalid request ID.' }, 400);
  }

  try {
    const req = await getRentalRequestById(requestId);
    if (!req) {
      return getResponse({ error: 'Rental request not found.' }, 404);
    }

    // Must be owner or requester
    if (req.requester_id !== user.id && req.offer_owner_id !== user.id && !user.grants?.includes('admin.panel')) {
      return getResponse({ error: 'Access denied.' }, 403);
    }

    // Include extensions
    const extensions = await getRentalExtensions(requestId);
    req.extensions = extensions;

    return getResponse(req, 200);
  } catch (error) {
    console.error('Error fetching rental request:', error);
    return getResponse({ error: 'Failed to fetch request.' }, 500);
  }
}

// PUT /api/rental/requests/[requestId] — Status transitions and extensions
export async function PUT({ params, request, locals }) {
  const user = locals.session?.user;
  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  const requestId = parseInt(params.requestId);
  if (isNaN(requestId)) {
    return getResponse({ error: 'Invalid request ID.' }, 400);
  }

  const req = await getRentalRequestById(requestId);
  if (!req) {
    return getResponse({ error: 'Rental request not found.' }, 404);
  }

  const isOwner = req.offer_owner_id === user.id || user.grants?.includes('admin.panel');
  const isRequester = req.requester_id === user.id;

  if (!isOwner && !isRequester) {
    return getResponse({ error: 'Access denied.' }, 403);
  }

  // Rate limit
  const rateCheck = checkRateLimit(`rental:requpdate:${user.id}`, 20, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  // Handle extension action
  if (body.action === 'extend') {
    return handleExtension(req, body, isOwner);
  }

  // Handle status transition
  if (!body.status) {
    return getResponse({ error: 'Status is required.' }, 400);
  }

  const transitions = isOwner ? OWNER_TRANSITIONS : REQUESTER_TRANSITIONS;
  const allowed = transitions[req.status];
  if (!allowed || !allowed.includes(body.status)) {
    return getResponse({ error: `Cannot change status from '${req.status}' to '${body.status}'.` }, 400);
  }

  try {
    const updateData = { status: body.status };

    // Owner-specific fields
    if (isOwner) {
      if (body.owner_note !== undefined) {
        updateData.owner_note = sanitizeNote(body.owner_note);
      }
      if (body.status === 'completed' && body.actual_return_date) {
        const validated = validateDate(body.actual_return_date);
        if (validated) {
          updateData.actual_return_date = validated;
        }
      }
    }

    // Determine if offer status needs to change
    let newOfferStatus = null;
    if (body.status === 'in_progress') {
      newOfferStatus = 'rented';
    } else if (body.status === 'completed') {
      newOfferStatus = 'available'; // The DB function checks for other active requests first
    }

    // Atomic update: request + offer status in a single transaction
    const updated = await updateRentalRequestWithOfferStatus(
      requestId, updateData, req.offer_id, req.offer_owner_id, newOfferStatus
    );

    // Notify the requester when their request is accepted
    if (body.status === 'accepted') {
      try {
        await createNotification(
          req.requester_id,
          'Rental',
          `Your rental request for "${req.offer_title}" was accepted!`
        );
      } catch { /* don't block response on notification failure */ }
    }

    return getResponse(updated, 200);
  } catch (error) {
    console.error('Error updating rental request:', error);
    return getResponse({ error: 'Failed to update request.' }, 500);
  }
}

async function handleExtension(req, body, isOwner) {
  if (!isOwner) {
    return getResponse({ error: 'Only the offer owner can extend rentals.' }, 403);
  }

  if (!['accepted', 'in_progress'].includes(req.status)) {
    return getResponse({ error: 'Can only extend accepted or in-progress rentals.' }, 400);
  }

  const newEndDate = validateDate(body.new_end_date);
  if (!newEndDate) {
    return getResponse({ error: 'Invalid new end date.' }, 400);
  }

  const currentEnd = typeof req.end_date === 'string' ? req.end_date : req.end_date.toISOString().split('T')[0];
  if (new Date(newEndDate) <= new Date(currentEnd)) {
    return getResponse({ error: 'New end date must be after the current end date.' }, 400);
  }

  const extraDays = countDays(currentEnd, newEndDate) - 1; // Don't count the current end date again
  if (extraDays <= 0) {
    return getResponse({ error: 'Extension must add at least 1 day.' }, 400);
  }
  if (extraDays > 365) {
    return getResponse({ error: 'Extension cannot exceed 365 days.' }, 400);
  }

  // Check date conflicts for the extension period (day after current end through new end)
  const extensionStart = new Date(currentEnd + 'T00:00:00Z');
  extensionStart.setUTCDate(extensionStart.getUTCDate() + 1);
  const extensionStartStr = extensionStart.toISOString().split('T')[0];

  try {
    const hasConflict = await checkRentalDateConflict(req.offer_id, extensionStartStr, newEndDate, req.id);
    if (hasConflict) {
      return getResponse({ error: 'Extension period overlaps with a blocked date or existing booking.' }, 409);
    }

    const retroactive = !!body.retroactive;
    let customPrice = null;
    if (body.custom_price_per_day != null) {
      customPrice = parseFloat(body.custom_price_per_day);
      if (!Number.isFinite(customPrice) || customPrice <= 0 || customPrice > MAX_PRICE_PER_DAY) {
        return getResponse({ error: 'Custom price per day is invalid.' }, 400);
      }
    }

    const extensionPricing = calculateExtensionPrice(
      parseFloat(req.offer_price_per_day),
      req.offer_discounts || [],
      parseFloat(req.total_price),
      parseInt(req.total_days),
      extraDays,
      retroactive,
      customPrice
    );

    // Create extension record
    const extension = await createRentalExtension({
      request_id: req.id,
      previous_end: currentEnd,
      new_end: newEndDate,
      extra_days: extraDays,
      retroactive,
      price_per_day: extensionPricing.pricePerDay,
      discount_pct: extensionPricing.discountPct,
      extra_price: extensionPricing.extraPrice,
      new_total_price: extensionPricing.newTotalPrice,
      note: sanitizeNote(body.note)
    });

    // Update request dates and pricing
    const newTotalDays = parseInt(req.total_days) + extraDays;
    await updateRentalRequest(req.id, {
      end_date: newEndDate,
      total_days: newTotalDays,
      total_price: extensionPricing.newTotalPrice,
      // Update price_per_day if retroactive (new blended rate)
      ...(retroactive ? { price_per_day: extensionPricing.pricePerDay, discount_pct: extensionPricing.discountPct } : {})
    });

    return getResponse(extension, 200);
  } catch (error) {
    console.error('Error extending rental:', error);
    return getResponse({ error: 'Failed to extend rental.' }, 500);
  }
}
