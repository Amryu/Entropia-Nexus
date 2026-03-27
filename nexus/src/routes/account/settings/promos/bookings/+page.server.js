// @ts-nocheck
import { requireVerified } from '$lib/server/auth.js';
import { getPromoBookingsByUser } from '$lib/server/db.js';

export async function load({ locals }) {
  const user = requireVerified(locals);

  const bookings = await getPromoBookingsByUser(user.id);

  return {
    bookings: bookings.map(b => ({
      id: b.id,
      promo_id: b.promo_id,
      promo_name: b.promo_name,
      promo_type: b.promo_type,
      slot_type: b.slot_type,
      status: b.status,
      start_date: b.start_date?.toISOString?.() ?? b.start_date,
      end_date: b.end_date?.toISOString?.() ?? b.end_date,
      weeks: b.weeks,
      total_views: Number(b.total_views) || 0,
      total_clicks: Number(b.total_clicks) || 0,
      created_at: b.created_at?.toISOString?.() ?? b.created_at
    }))
  };
}
