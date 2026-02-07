//@ts-nocheck
import {
  getServiceById,
  getTicketOfferById,
  createTicket
} from "$lib/server/db.js";
import { getResponse } from "$lib/util.js";

// POST purchase a ticket
export async function POST({ params, request, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to purchase a ticket.' }, 401);
  }
  if (!user.verified) {
    return getResponse({ error: 'You must verify your account before purchasing tickets.' }, 403);
  }

  const serviceId = parseInt(params.id);
  if (isNaN(serviceId)) {
    return getResponse({ error: 'Invalid service ID.' }, 400);
  }

  let body;
  try {
    body = await request.json();
  } catch (error) {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  if (!body.offer_id) {
    return getResponse({ error: 'Offer ID is required.' }, 400);
  }

  const offerId = parseInt(body.offer_id);
  if (isNaN(offerId)) {
    return getResponse({ error: 'Invalid offer ID.' }, 400);
  }

  try {
    // Verify the service exists
    const service = await getServiceById(serviceId);
    if (!service) {
      return getResponse({ error: 'Service not found.' }, 404);
    }

    // Cannot purchase tickets for your own service (unless admin for testing)
    if (service.user_id === user.id && !user?.grants?.includes('admin.panel')) {
      return getResponse({ error: 'You cannot purchase tickets for your own service.' }, 400);
    }

    // Verify the offer exists and belongs to this service
    const offer = await getTicketOfferById(offerId);
    if (!offer || offer.service_id !== serviceId) {
      return getResponse({ error: 'Ticket offer not found for this service.' }, 404);
    }

    if (!offer.is_active) {
      return getResponse({ error: 'This ticket offer is no longer available.' }, 400);
    }

    // Calculate uses_total and valid_until based on offer type
    let usesTotal;
    let validUntil = null;

    if (offer.uses_count) {
      // Uses-based ticket
      usesTotal = offer.uses_count;
    } else if (offer.validity_days) {
      // Duration-based ticket - unlimited uses until expiry
      usesTotal = 999999; // Effectively unlimited
      // valid_until will be set when the ticket is activated (first use)
    } else {
      return getResponse({ error: 'Invalid ticket offer configuration.' }, 500);
    }

    const ticketData = {
      offer_id: offerId,
      user_id: user.id,
      uses_total: usesTotal,
      valid_until: validUntil,
      price_paid: offer.price
    };

    const ticket = await createTicket(ticketData);

    return getResponse({
      ...ticket,
      offer_name: offer.name,
      service_title: service.title,
      message: 'Ticket purchased successfully. It will be activated when the provider accepts your first check-in.'
    }, 201);
  } catch (error) {
    console.error('Error purchasing ticket:', error);
    return getResponse({ error: 'Failed to purchase ticket.' }, 500);
  }
}
