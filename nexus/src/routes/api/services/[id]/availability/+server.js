//@ts-nocheck
import {
  getServiceById,
  getServiceAvailability,
  setServiceAvailability
} from "$lib/server/db.js";
import { getResponse } from "$lib/util.js";

// GET service availability
export async function GET({ params }) {
  const serviceId = parseInt(params.id);
  if (isNaN(serviceId)) {
    return getResponse({ error: 'Invalid service ID.' }, 400);
  }

  try {
    const availability = await getServiceAvailability(serviceId);
    return getResponse(availability, 200);
  } catch (error) {
    console.error('Error fetching availability:', error);
    return getResponse({ error: 'Failed to fetch availability.' }, 500);
  }
}

// PUT update availability
export async function PUT({ params, request, locals }) {
  console.log('[API] PUT request received for service', params.id);
  const user = locals.session?.user;

  if (!user) {
    console.log('[API] No user session');
    return getResponse({ error: 'You must be logged in.' }, 401);
  }
  if (!user.verified) {
    console.log('[API] User not verified');
    return getResponse({ error: 'You must verify your account.' }, 403);
  }

  const serviceId = parseInt(params.id);
  if (isNaN(serviceId)) {
    console.log('[API] Invalid service ID');
    return getResponse({ error: 'Invalid service ID.' }, 400);
  }

  console.log('[API] Checking service ownership');
  // Check ownership
  const service = await getServiceById(serviceId);
  if (!service) {
    console.log('[API] Service not found');
    return getResponse({ error: 'Service not found.' }, 404);
  }
  if (service.user_id !== user.id && !user?.grants?.includes('admin.panel')) {
    console.log('[API] User not authorized');
    return getResponse({ error: 'You can only edit your own services.' }, 403);
  }

  console.log('[API] Parsing request body');
  let body;
  try {
    body = await request.json();
  } catch (error) {
    console.log('[API] Invalid JSON');
    return getResponse({ error: 'Invalid JSON.' }, 400);
  }

  if (!Array.isArray(body.slots)) {
    console.log('[API] Slots not an array');
    return getResponse({ error: 'slots must be an array.' }, 400);
  }

  console.log('[API] Validating', body.slots.length, 'slots');
  // Validate slots
  for (const slot of body.slots) {
    if (slot.day_of_week < 0 || slot.day_of_week > 6) {
      return getResponse({ error: 'day_of_week must be between 0 and 6.' }, 400);
    }
    if (!slot.start_time || !slot.end_time) {
      return getResponse({ error: 'start_time and end_time are required.' }, 400);
    }
  }

  console.log('[API] Calling setServiceAvailability');
  try {
    const availability = await setServiceAvailability(serviceId, body.slots);
    console.log('[API] setServiceAvailability returned', availability.length, 'slots');
    console.log('[API] Sending response');
    return getResponse(availability, 200);
  } catch (error) {
    console.error('[API] Error updating availability:', error);
    return getResponse({ error: 'Failed to update availability.' }, 500);
  }
}

