//@ts-nocheck
import {
  getServiceById,
  getServiceTicketOffers,
  getTicketOfferById,
  createTicketOffer,
  updateTicketOffer,
  deleteTicketOffer
} from "$lib/server/db.js";
import { getResponse } from "$lib/util.js";

// GET all ticket offers for a service
export async function GET({ params, locals }) {
  const serviceId = parseInt(params.id);
  if (isNaN(serviceId)) {
    return getResponse({ error: 'Invalid service ID.' }, 400);
  }

  try {
    const offers = await getServiceTicketOffers(serviceId);
    return getResponse(offers, 200);
  } catch (error) {
    console.error('Error fetching ticket offers:', error);
    return getResponse({ error: 'Failed to fetch ticket offers.' }, 500);
  }
}

// POST create a new ticket offer
export async function POST({ params, request, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to create a ticket offer.' }, 401);
  }
  if (!user.verified) {
    return getResponse({ error: 'You must verify your account before creating ticket offers.' }, 403);
  }

  const serviceId = parseInt(params.id);
  if (isNaN(serviceId)) {
    return getResponse({ error: 'Invalid service ID.' }, 400);
  }

  // Check ownership
  const service = await getServiceById(serviceId);
  if (!service) {
    return getResponse({ error: 'Service not found.' }, 404);
  }

  if (service.user_id !== user.id && !user?.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You can only create ticket offers for your own services.' }, 403);
  }

  // Only transportation services can have ticket offers
  if (service.type !== 'transportation') {
    return getResponse({ error: 'Ticket offers are only available for transportation services.' }, 400);
  }

  let body;
  try {
    body = await request.json();
  } catch (error) {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  // Validate required fields
  if (!body.name || typeof body.name !== 'string' || body.name.trim().length === 0) {
    return getResponse({ error: 'Ticket offer name is required.' }, 400);
  }

  if (body.price == null || isNaN(parseFloat(body.price)) || parseFloat(body.price) < 0) {
    return getResponse({ error: 'Valid price is required.' }, 400);
  }

  // Must have either uses_count or validity_days, but not both
  const hasUses = body.uses_count != null && body.uses_count > 0;
  const hasValidity = body.validity_days != null && body.validity_days > 0;

  if (!hasUses && !hasValidity) {
    return getResponse({ error: 'Ticket offer must have either uses count or validity days.' }, 400);
  }

  if (hasUses && hasValidity) {
    return getResponse({ error: 'Ticket offer cannot have both uses count and validity days.' }, 400);
  }

  try {
    // Check for duplicates (same uses_count or validity_days for this service)
    const existingOffers = await getServiceTicketOffers(serviceId);

    if (hasUses) {
      const duplicate = existingOffers.find(o => o.uses_count === body.uses_count);
      if (duplicate) {
        return getResponse({ error: `A ticket offer with ${body.uses_count} uses already exists for this service.` }, 400);
      }
    }

    if (hasValidity) {
      const duplicate = existingOffers.find(o => o.validity_days === body.validity_days);
      if (duplicate) {
        return getResponse({ error: `A ticket offer with ${body.validity_days} days validity already exists for this service.` }, 400);
      }
    }

    const offerData = {
      name: body.name.trim(),
      uses_count: hasUses ? parseInt(body.uses_count) : null,
      validity_days: hasValidity ? parseInt(body.validity_days) : null,
      price: parseFloat(parseFloat(body.price).toFixed(4)),
      waives_pickup_fee: body.waives_pickup_fee === true,
      description: body.description?.trim() || null,
      sort_order: body.sort_order != null ? parseInt(body.sort_order) : 0
    };

    const offer = await createTicketOffer(serviceId, offerData);
    return getResponse(offer, 201);
  } catch (error) {
    console.error('Error creating ticket offer:', error);
    return getResponse({ error: 'Failed to create ticket offer.' }, 500);
  }
}
