// @ts-nocheck
import { error } from '@sveltejs/kit';
import { requireVerified } from '$lib/server/auth.js';
import { getPromoBookingById, getPromoBookingMetrics, getPromoImages } from '$lib/server/db.js';

export async function load({ locals, params }) {
  const user = requireVerified(locals);

  const bookingId = parseInt(params.id);
  if (isNaN(bookingId)) {
    throw error(400, 'Invalid booking ID');
  }

  const booking = await getPromoBookingById(bookingId);
  if (!booking) {
    throw error(404, 'Booking not found');
  }

  if (String(booking.user_id) !== String(user.id)) {
    throw error(403, 'You can only view your own bookings');
  }

  const [metrics, images] = await Promise.all([
    getPromoBookingMetrics(bookingId),
    getPromoImages(booking.promo_id)
  ]);

  return {
    booking: {
      id: booking.id,
      promo_id: booking.promo_id,
      promo_name: booking.promo_name,
      promo_type: booking.promo_type,
      promo_title: booking.promo_title,
      promo_summary: booking.promo_summary,
      promo_link: booking.promo_link,
      slot_type: booking.slot_type,
      status: booking.status,
      start_date: booking.start_date?.toISOString?.() ?? booking.start_date,
      end_date: booking.end_date?.toISOString?.() ?? booking.end_date,
      weeks: booking.weeks,
      price: booking.price,
      currency: booking.currency,
      admin_note: booking.admin_note,
      created_at: booking.created_at?.toISOString?.() ?? booking.created_at
    },
    metrics: metrics.map(m => ({
      event_date: m.event_date?.toISOString?.() ?? m.event_date,
      views: Number(m.views) || 0,
      clicks: Number(m.clicks) || 0
    })),
    images: images.map(img => ({
      slot_variant: img.slot_variant,
      image_path: img.image_path,
      width: img.width,
      height: img.height
    }))
  };
}
