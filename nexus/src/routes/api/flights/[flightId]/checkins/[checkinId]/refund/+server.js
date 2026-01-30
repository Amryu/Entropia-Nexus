// @ts-nocheck
import {
  getFlightInstance,
  getServiceById,
  getCheckinById,
  refundCheckin,
  restoreTicketUse,
  canManageService
} from "$lib/server/db.js";
import { getResponse } from "$lib/util.js";

export async function POST({ params, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  const flightId = parseInt(params.flightId);
  const checkinId = parseInt(params.checkinId);

  if (isNaN(flightId) || isNaN(checkinId)) {
    return getResponse({ error: 'Invalid flight or check-in ID.' }, 400);
  }

  try {
    // Get flight
    const flight = await getFlightInstance(flightId);
    if (!flight) {
      return getResponse({ error: 'Flight not found.' }, 404);
    }

    // Check if user can manage this service
    const service = await getServiceById(flight.service_id);
    if (!service) {
      return getResponse({ error: 'Service not found.' }, 404);
    }

    const canManage = await canManageService(flight.service_id, user.id, user.administrator);
    if (!canManage) {
      return getResponse({ error: 'You do not have permission to refund check-ins for this service.' }, 403);
    }

    // Get check-in
    const checkin = await getCheckinById(checkinId);
    if (!checkin || checkin.flight_id !== flightId) {
      return getResponse({ error: 'Check-in not found for this flight.' }, 404);
    }

    // Can only refund accepted check-ins
    if (checkin.status !== 'accepted') {
      return getResponse({ error: 'Can only refund accepted check-ins.' }, 400);
    }

    // Check if flight completed more than 1 hour ago
    if (flight.status === 'completed' && flight.completed_at) {
      const completedAt = new Date(flight.completed_at);
      const now = new Date();
      const hoursSinceCompletion = (now - completedAt) / (1000 * 60 * 60);

      if (hoursSinceCompletion > 1) {
        return getResponse({
          error: 'Cannot refund after 1 hour from flight completion.'
        }, 400);
      }
    }

    // Restore the ticket use
    await restoreTicketUse(checkin.ticket_id);

    // Mark checkin as refunded
    await refundCheckin(checkinId);

    return getResponse({ message: 'Check-in refunded successfully. Ticket use has been restored.' }, 200);
  } catch (error) {
    console.error('Error refunding check-in:', error);
    return getResponse({ error: 'Failed to refund check-in.' }, 500);
  }
}
