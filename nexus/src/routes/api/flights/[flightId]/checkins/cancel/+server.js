// @ts-nocheck
import {
  getFlightInstance,
  getUserCheckinForFlight,
  cancelCheckin,
  restoreTicketUseForCheckin
} from "$lib/server/db.js";
import { getResponse } from "$lib/util.js";
import { pool } from "$lib/server/db.js";

export async function POST({ params, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  const flightId = parseInt(params.flightId);
  if (isNaN(flightId)) {
    return getResponse({ error: 'Invalid flight ID.' }, 400);
  }

  try {
    // Get flight
    const flight = await getFlightInstance(flightId);
    if (!flight) {
      return getResponse({ error: 'Flight not found.' }, 404);
    }

    // Can't cancel if flight has entered warp
    if (flight.status === 'running' && flight.current_state && flight.current_state.startsWith('warp_to_')) {
      return getResponse({ error: 'Cannot cancel check-in after flight has entered warp.' }, 400);
    }

    if (flight.status === 'completed' || flight.status === 'cancelled') {
      return getResponse({ error: 'Cannot cancel check-in for a completed or cancelled flight.' }, 400);
    }

    // Get user's check-in
    const checkin = await getUserCheckinForFlight(user.id, flightId);
    if (!checkin) {
      return getResponse({ error: 'No check-in found for this flight.' }, 404);
    }

    // Restore ticket use (use is reserved at check-in time)
    if (checkin.status === 'pending' || checkin.status === 'accepted') {
      await restoreTicketUseForCheckin(checkin.id);
    }

    // Cancel the check-in
    await cancelCheckin(checkin.id);

    return getResponse({ message: 'Check-in cancelled successfully. Your ticket use has been restored.' }, 200);
  } catch (error) {
    console.error('Error cancelling check-in:', error);
    return getResponse({ error: 'Failed to cancel check-in.' }, 500);
  }
}
