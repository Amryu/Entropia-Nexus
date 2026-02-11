//@ts-nocheck
import { getRentalOfferById, getRentalAvailability } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';

// GET /api/rental/[id]/availability — Get availability calendar data
export async function GET({ params, url }) {
  const id = parseInt(params.id);
  if (isNaN(id)) {
    return getResponse({ error: 'Invalid offer ID.' }, 400);
  }

  const offer = await getRentalOfferById(id);
  if (!offer) {
    return getResponse({ error: 'Rental offer not found.' }, 404);
  }

  // Determine date range (default 3 months, max 12 months)
  const months = Math.min(Math.max(parseInt(url.searchParams.get('months')) || 3, 1), 12);

  const startDate = new Date();
  startDate.setUTCHours(0, 0, 0, 0);
  const startStr = startDate.toISOString().split('T')[0];

  const endDate = new Date(startDate);
  endDate.setUTCMonth(endDate.getUTCMonth() + months);
  const endStr = endDate.toISOString().split('T')[0];

  try {
    const availability = await getRentalAvailability(id, startStr, endStr);
    return getResponse(availability, 200);
  } catch (error) {
    console.error('Error fetching rental availability:', error);
    return getResponse({ error: 'Failed to fetch availability.' }, 500);
  }
}
