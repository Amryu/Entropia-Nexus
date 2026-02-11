// @ts-nocheck
import { getResponse } from '$lib/util';
import { checkRateLimit } from '$lib/server/rateLimiter.js';
import { syncServiceAvailability, setServiceAvailability, getUserServices } from '$lib/server/db';

export async function POST({ request, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to sync availability.' }, 401);
  }

  if (!user.verified) {
    return getResponse({ error: 'You must verify your account to modify services.' }, 403);
  }

  const rateCheck = checkRateLimit(`services:sync-avail:${user.id}`, 5, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  try {
    const body = await request.json();
    const { sourceServiceId, targetServiceIds, slots } = body;

    // Validate input
    if (!targetServiceIds || !Array.isArray(targetServiceIds) || targetServiceIds.length === 0) {
      return getResponse({ error: 'Target service IDs are required.' }, 400);
    }

    // Verify ownership of all target services
    const userServices = await getUserServices(user.id);
    const userServiceIds = new Set(userServices.map(s => s.id));

    for (const targetId of targetServiceIds) {
      if (!userServiceIds.has(targetId)) {
        return getResponse({ error: 'You can only sync availability for your own services.' }, 403);
      }
    }

    if (sourceServiceId) {
      // Copy from source service
      if (!userServiceIds.has(sourceServiceId)) {
        return getResponse({ error: 'Source service must be your own service.' }, 403);
      }

      await syncServiceAvailability(sourceServiceId, targetServiceIds, user.id);
    } else if (slots && Array.isArray(slots)) {
      // Set new availability for all target services
      for (const targetId of targetServiceIds) {
        await setServiceAvailability(targetId, slots);
      }
    } else {
      return getResponse({ error: 'Either sourceServiceId or slots must be provided.' }, 400);
    }

    return getResponse({ success: true, message: 'Availability synced successfully.' }, 200);
  } catch (error) {
    console.error('Error syncing availability:', error);
    return getResponse({ error: 'Failed to sync availability.' }, 500);
  }
}
