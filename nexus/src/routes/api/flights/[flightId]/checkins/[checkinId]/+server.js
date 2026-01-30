//@ts-nocheck
import {
  getFlightInstance,
  getServiceById,
  getCheckinById,
  updateCheckinStatus,
  activateTicket,
  logTicketUsage,
  getTicketById,
  canManageService
} from "$lib/server/db.js";
import { getResponse } from "$lib/util.js";

// PUT accept or deny a check-in
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
  } catch (error) {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  const { status } = body;
  if (!status || !['accepted', 'denied'].includes(status)) {
    return getResponse({ error: 'Status must be "accepted" or "denied".' }, 400);
  }

  try {
    // Verify flight and ownership
    const flight = await getFlightInstance(flightId);
    if (!flight) {
      return getResponse({ error: 'Flight not found.' }, 404);
    }

    const service = await getServiceById(flight.service_id);
    const canManage = await canManageService(flight.service_id, user.id, user.administrator);
    if (!canManage) {
      return getResponse({ error: 'Only the provider or pilots can manage check-ins.' }, 403);
    }

    // Verify check-in exists
    const checkin = await getCheckinById(checkinId);
    if (!checkin || checkin.flight_id !== flightId) {
      return getResponse({ error: 'Check-in not found for this flight.' }, 404);
    }

    if (checkin.status !== 'pending') {
      return getResponse({ error: `Check-in is already '${checkin.status}'.` }, 400);
    }

    // Update check-in status
    const updatedCheckin = await updateCheckinStatus(checkinId, status);

    // If accepted, handle ticket activation and log usage
    // Note: Ticket use was already reserved at check-in time, so we don't decrement again here
    if (status === 'accepted' && checkin.ticket_id) {
      const ticket = await getTicketById(checkin.ticket_id);
      if (ticket) {
        if (ticket.status === 'pending') {
          // First acceptance - activate the ticket
          await activateTicket(ticket.id);
        }

        // Log the usage (ticket use was already reserved at check-in creation)
        await logTicketUsage(ticket.id, {
          departure_date: new Date().toISOString().split('T')[0],
          notes: `Flight #${flightId} check-in accepted`
        });
      }
    }

    return getResponse({
      ...updatedCheckin,
      message: status === 'accepted' ? 'Check-in accepted.' : 'Check-in denied.'
    }, 200);
  } catch (error) {
    console.error('Error updating check-in:', error);
    return getResponse({ error: 'Failed to update check-in.' }, 500);
  }
}
