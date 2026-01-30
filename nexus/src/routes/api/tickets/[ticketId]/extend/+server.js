// @ts-nocheck
import {
  getTicketById,
  getServiceById,
  extendTicketUses,
  extendTicketValidity,
  reactivateExpiredTicket,
  canManageService
} from "$lib/server/db.js";
import { getResponse } from "$lib/util.js";

export async function POST({ params, request, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  const ticketId = parseInt(params.ticketId);
  if (isNaN(ticketId)) {
    return getResponse({ error: 'Invalid ticket ID.' }, 400);
  }

  let body;
  try {
    body = await request.json();
  } catch (error) {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  try {
    // Get ticket with service info
    const ticket = await getTicketById(ticketId);
    if (!ticket) {
      return getResponse({ error: 'Ticket not found.' }, 404);
    }

    // Get service to verify ownership
    const service = await getServiceById(ticket.service_id);
    if (!service) {
      return getResponse({ error: 'Service not found.' }, 404);
    }

    // Check if user can manage this service
    const canManage = await canManageService(ticket.service_id, user.id, user.administrator);
    if (!canManage) {
      return getResponse({ error: 'You do not have permission to manage tickets for this service.' }, 403);
    }

    const { action, additionalUses, additionalDays } = body;

    switch (action) {
      case 'extend_uses': {
        if (!additionalUses || additionalUses < 1) {
          return getResponse({ error: 'Please specify additional uses (minimum 1).' }, 400);
        }

        const updatedTicket = await extendTicketUses(ticketId, additionalUses);
        return getResponse({
          ...updatedTicket,
          message: `Added ${additionalUses} uses to ticket.`
        }, 200);
      }

      case 'extend_validity': {
        if (!additionalDays || additionalDays < 1) {
          return getResponse({ error: 'Please specify additional days (minimum 1).' }, 400);
        }

        const updatedTicket = await extendTicketValidity(ticketId, additionalDays);
        return getResponse({
          ...updatedTicket,
          message: `Extended ticket validity by ${additionalDays} days.`
        }, 200);
      }

      case 'reactivate': {
        // Only allow reactivating expired tickets
        if (ticket.status !== 'expired' && ticket.status !== 'used') {
          // Check if valid_until has passed
          if (ticket.valid_until && new Date(ticket.valid_until) >= new Date()) {
            return getResponse({ error: 'This ticket is not expired.' }, 400);
          }
        }

        if (!additionalDays || additionalDays < 1) {
          return getResponse({ error: 'Please specify validity days for reactivation (minimum 1).' }, 400);
        }

        const updatedTicket = await reactivateExpiredTicket(ticketId, additionalDays, additionalUses || 0);
        return getResponse({
          ...updatedTicket,
          message: `Ticket reactivated with ${additionalDays} days validity${additionalUses ? ` and ${additionalUses} additional uses` : ''}.`
        }, 200);
      }

      default:
        return getResponse({ error: 'Invalid action. Valid actions: extend_uses, extend_validity, reactivate' }, 400);
    }
  } catch (error) {
    console.error('Error extending ticket:', error);
    return getResponse({ error: 'Failed to extend ticket.' }, 500);
  }
}
