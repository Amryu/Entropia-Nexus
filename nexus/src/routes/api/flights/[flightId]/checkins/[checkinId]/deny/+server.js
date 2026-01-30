// @ts-nocheck
import {
  getFlightInstance,
  getServiceById,
  updateCheckin,
  canManageService
} from "$lib/server/db.js";
import { getResponse } from "$lib/util.js";

export async function PUT({ params, request, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  const flightId = parseInt(params.flightId);
  const checkinId = parseInt(params.checkinId);

  if (isNaN(flightId) || isNaN(checkinId)) {
    return getResponse({ error: 'Invalid flight or check-in ID.' }, 400);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    body = {};
  }

  try {
    // Get flight and verify ownership
    const flight = await getFlightInstance(flightId);
    if (!flight) {
      return getResponse({ error: 'Flight not found.' }, 404);
    }

    const service = await getServiceById(flight.service_id);
    if (!service) {
      return getResponse({ error: 'Service not found.' }, 404);
    }

    const canManage = await canManageService(flight.service_id, user.id, user.administrator);
    if (!canManage) {
      return getResponse({ error: 'You do not have permission to manage check-ins for this flight.' }, 403);
    }

    // Get the check-in
    const { getCheckinById } = await import('$lib/server/db.js');
    const checkin = await getCheckinById(checkinId);

    if (!checkin || checkin.flight_id !== flightId) {
      return getResponse({ error: 'Check-in not found.' }, 404);
    }

    if (checkin.status !== 'pending') {
      return getResponse({ error: 'Check-in is not pending.' }, 400);
    }

    // Deny the check-in
    const updatedCheckin = await updateCheckin(checkinId, {
      status: 'denied',
      denial_reason: body.reason || null
    });

    return getResponse(updatedCheckin, 200);
  } catch (error) {
    console.error('Error denying check-in:', error);
    return getResponse({ error: 'Failed to deny check-in.' }, 500);
  }
}
