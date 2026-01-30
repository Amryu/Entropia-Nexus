//@ts-nocheck
import {
  getTicketById,
  getTicketUsageHistory,
  cancelTicket
} from "$lib/server/db.js";
import { getResponse } from "$lib/util.js";

// GET single ticket with usage history
export async function GET({ params, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to view your tickets.' }, 401);
  }

  const ticketId = parseInt(params.ticketId);
  if (isNaN(ticketId)) {
    return getResponse({ error: 'Invalid ticket ID.' }, 400);
  }

  try {
    const ticket = await getTicketById(ticketId);
    if (!ticket) {
      return getResponse({ error: 'Ticket not found.' }, 404);
    }

    // Verify ownership
    if (ticket.user_id !== user.id && !user.administrator) {
      return getResponse({ error: 'You can only view your own tickets.' }, 403);
    }

    // Get usage history
    const usageHistory = await getTicketUsageHistory(ticketId);

    return getResponse({
      ...ticket,
      usage_history: usageHistory
    }, 200);
  } catch (error) {
    console.error('Error fetching ticket:', error);
    return getResponse({ error: 'Failed to fetch ticket.' }, 500);
  }
}

// DELETE (cancel) a ticket
export async function DELETE({ params, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to cancel a ticket.' }, 401);
  }

  const ticketId = parseInt(params.ticketId);
  if (isNaN(ticketId)) {
    return getResponse({ error: 'Invalid ticket ID.' }, 400);
  }

  try {
    const ticket = await getTicketById(ticketId);
    if (!ticket) {
      return getResponse({ error: 'Ticket not found.' }, 404);
    }

    // Verify ownership
    if (ticket.user_id !== user.id && !user.administrator) {
      return getResponse({ error: 'You can only cancel your own tickets.' }, 403);
    }

    // Can only cancel pending tickets
    if (ticket.status !== 'pending') {
      return getResponse({ error: 'Only pending tickets can be cancelled. Contact the provider for refunds on active tickets.' }, 400);
    }

    const cancelledTicket = await cancelTicket(ticketId);
    return getResponse({
      ...cancelledTicket,
      message: 'Ticket cancelled successfully.'
    }, 200);
  } catch (error) {
    console.error('Error cancelling ticket:', error);
    return getResponse({ error: 'Failed to cancel ticket.' }, 500);
  }
}
