//@ts-nocheck
import { getPromoBookingById, getPromoBookingMetrics } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';
import { requireVerifiedAPI } from '$lib/server/auth.js';

// GET daily metrics for a booking (owner check)
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
      return getResponse({ error: 'You do not have permission to view these metrics.' }, 403);
    }

    const metrics = await getPromoBookingMetrics(bookingId);
    return getResponse(metrics, 200);
  } catch (err) {
    console.error('Error fetching booking metrics:', err);
    return getResponse({ error: 'Failed to fetch booking metrics.' }, 500);
  }
}
