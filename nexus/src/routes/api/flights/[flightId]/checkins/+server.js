//@ts-nocheck
import {
  getFlightInstance,
  getServiceById,
  getFlightCheckins,
  canManageService
} from "$lib/server/db.js";
import { getResponse } from "$lib/util.js";

// GET list check-ins for a flight (provider or pilots)
export async function GET({ params, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  const flightId = parseInt(params.flightId);
  if (isNaN(flightId)) {
    return getResponse({ error: 'Invalid flight ID.' }, 400);
  }

  try {
    const flight = await getFlightInstance(flightId);
    if (!flight) {
      return getResponse({ error: 'Flight not found.' }, 404);
    }

    // Provider or pilots can view check-ins
    const canManage = await canManageService(flight.service_id, user.id, user.administrator);
    if (!canManage) {
      return getResponse({ error: 'Only the provider or pilots can view check-ins.' }, 403);
    }

    const checkins = await getFlightCheckins(flightId);
    return getResponse(checkins, 200);
  } catch (error) {
    console.error('Error fetching check-ins:', error);
    return getResponse({ error: 'Failed to fetch check-ins.' }, 500);
  }
}
