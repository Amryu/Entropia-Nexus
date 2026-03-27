// @ts-nocheck
import { getPromosByOwner, getPromoBookingsByUser } from '$lib/server/db.js';

export async function load({ locals }) {
  const user = locals.session.user;

  const [promos, bookings] = await Promise.all([
    getPromosByOwner(user.id),
    getPromoBookingsByUser(user.id)
  ]);

  const activeBookings = bookings.filter(b => b.status === 'active');
  const pendingBookings = bookings.filter(b => b.status === 'pending');

  return {
    totalPromos: promos.length,
    activeBookings: activeBookings.length,
    pendingBookings: pendingBookings.length,
    totalViews: activeBookings.reduce((sum, b) => sum + (Number(b.total_views) || 0), 0),
    totalClicks: activeBookings.reduce((sum, b) => sum + (Number(b.total_clicks) || 0), 0)
  };
}
