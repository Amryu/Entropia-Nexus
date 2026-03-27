// @ts-nocheck
import { requireAdmin } from '$lib/server/auth.js';
import { getPromoBookingById, getPromoImages, getPromoBookingMetrics } from '$lib/server/db.js';
import { error } from '@sveltejs/kit';

export async function load({ locals, params }) {
  requireAdmin(locals);

  const id = parseInt(params.id, 10);
  if (!id || isNaN(id)) throw error(400, 'Invalid booking ID');

  const booking = await getPromoBookingById(id);
  if (!booking) throw error(404, 'Booking not found');

  const [images, metrics] = await Promise.all([
    getPromoImages(booking.promo_id),
    getPromoBookingMetrics(id)
  ]);

  return { booking, images, metrics };
}
