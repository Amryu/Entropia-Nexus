// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getAllPromoBookings } from '$lib/server/db.js';
import { requireAdminAPI } from '$lib/server/auth.js';

export async function GET({ url, locals }) {
  requireAdminAPI(locals);

  const status = url.searchParams.get('status') || null;
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '50', 10), 100);
  const offset = Math.max(0, parseInt(url.searchParams.get('offset') || '0', 10));

  const bookings = await getAllPromoBookings({ status, limit, offset });
  return json(bookings);
}
