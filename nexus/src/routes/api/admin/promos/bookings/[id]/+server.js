// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getPromoBookingById, updatePromoBooking } from '$lib/server/db.js';
import { requireAdminAPI } from '$lib/server/auth.js';

export async function GET({ params, locals }) {
  requireAdminAPI(locals);

  const booking = await getPromoBookingById(parseInt(params.id, 10));
  if (!booking) {
    return json({ error: 'Booking not found' }, { status: 404 });
  }

  return json(booking);
}

export async function PUT({ params, request, locals }) {
  requireAdminAPI(locals);

  const id = parseInt(params.id, 10);
  const existing = await getPromoBookingById(id);
  if (!existing) {
    return json({ error: 'Booking not found' }, { status: 404 });
  }

  const body = await request.json();

  const fields = {};
  if ('price' in body) {
    const price = Number(body.price);
    if (isNaN(price) || price < 0 || price > 999999.99) {
      return json({ error: 'Price must be a non-negative number no greater than 999999.99' }, { status: 400 });
    }
    fields.price = price;
  }
  if ('currency' in body) fields.currency = body.currency;
  if ('admin_note' in body) fields.admin_note = body.admin_note?.trim() || null;
  if ('start_date' in body) {
    const d = new Date(body.start_date);
    if (isNaN(d.getTime())) {
      return json({ error: 'start_date must be a valid date string' }, { status: 400 });
    }
    fields.start_date = body.start_date;
  }
  if ('weeks' in body) {
    const weeks = Number(body.weeks);
    if (!Number.isInteger(weeks) || weeks < 1 || weeks > 52) {
      return json({ error: 'Weeks must be an integer between 1 and 52' }, { status: 400 });
    }
    fields.weeks = weeks;
  }

  if (Object.keys(fields).length === 0) {
    return json({ error: 'No valid fields to update' }, { status: 400 });
  }

  const updated = await updatePromoBooking(id, fields);
  return json(updated);
}
