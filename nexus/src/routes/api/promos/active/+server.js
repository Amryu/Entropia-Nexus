// @ts-nocheck
/**
 * GET /api/promos/active — Returns active promos grouped by slot type.
 * Public endpoint, no auth required.
 */
import { getActivePromos } from '$lib/server/promo-cache.js';

export async function GET() {
  const data = await getActivePromos();

  return new Response(JSON.stringify(data), {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'public, max-age=60'
    }
  });
}
