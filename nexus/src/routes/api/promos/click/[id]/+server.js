//@ts-nocheck
import { getPromoBookingById, incrementPromoMetrics } from '$lib/server/db.js';
import { redirect } from '@sveltejs/kit';
import { getResponse } from '$lib/util.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';
import { isBot, getClientIp } from '$lib/server/route-analytics.js';

const CLICK_WINDOW_MS = 5 * 60 * 1000; // 5 minutes

// GET click tracking - redirects to promo link
export async function GET(event) {
  const { params } = event;

  const bookingId = parseInt(params.id);
  if (isNaN(bookingId)) {
    return getResponse({ error: 'Invalid booking ID.' }, 400);
  }

  let booking;
  try {
    booking = await getPromoBookingById(bookingId);
  } catch (err) {
    console.error('Error fetching booking for click:', err);
    return getResponse({ error: 'Failed to process click.' }, 500);
  }

  if (!booking || !booking.promo_link) {
    return getResponse({ error: 'Promo not found or has no link.' }, 404);
  }

  // Validate URL protocol to prevent open redirect attacks
  try {
    const parsedUrl = new URL(booking.promo_link);
    if (parsedUrl.protocol !== 'http:' && parsedUrl.protocol !== 'https:') {
      return getResponse({ error: 'Invalid link protocol.' }, 400);
    }
  } catch {
    return getResponse({ error: 'Invalid link URL.' }, 400);
  }

  // Bot detection - only count clicks from real users
  const userAgent = event.request.headers.get('user-agent') || '';
  const isBotRequest = isBot(userAgent, event.request.method);

  if (!isBotRequest) {
    const ip = getClientIp(event);
    const rateLimitKey = `promo:click:${bookingId}:${ip}`;
    const rateCheck = checkRateLimit(rateLimitKey, 1, CLICK_WINDOW_MS);

    if (rateCheck.allowed) {
      const today = new Date().toISOString().split('T')[0];
      try {
        await incrementPromoMetrics(bookingId, today, 0, 1);
      } catch (err) {
        // Don't block the redirect if metrics fail
        console.error('Error incrementing click metric:', err);
      }
    }
  }

  throw redirect(302, booking.promo_link);
}
