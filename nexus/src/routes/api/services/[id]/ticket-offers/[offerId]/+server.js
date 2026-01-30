//@ts-nocheck
import {
  getServiceById,
  getTicketOfferById,
  getServiceTicketOffers,
  updateTicketOffer,
  deleteTicketOffer
} from "$lib/server/db.js";
import { getResponse } from "$lib/util.js";

// GET single ticket offer
export async function GET({ params, locals }) {
  const offerId = parseInt(params.offerId);
  if (isNaN(offerId)) {
    return getResponse({ error: 'Invalid offer ID.' }, 400);
  }

  try {
    const offer = await getTicketOfferById(offerId);
    if (!offer) {
      return getResponse({ error: 'Ticket offer not found.' }, 404);
    }
    return getResponse(offer, 200);
  } catch (error) {
    console.error('Error fetching ticket offer:', error);
    return getResponse({ error: 'Failed to fetch ticket offer.' }, 500);
  }
}

// PUT update a ticket offer
export async function PUT({ params, request, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to update a ticket offer.' }, 401);
  }
  if (!user.verified) {
    return getResponse({ error: 'You must verify your account before updating ticket offers.' }, 403);
  }

  const serviceId = parseInt(params.id);
  const offerId = parseInt(params.offerId);

  if (isNaN(serviceId) || isNaN(offerId)) {
    return getResponse({ error: 'Invalid service or offer ID.' }, 400);
  }

  // Check service ownership
  const service = await getServiceById(serviceId);
  if (!service) {
    return getResponse({ error: 'Service not found.' }, 404);
  }

  if (service.user_id !== user.id && !user.administrator) {
    return getResponse({ error: 'You can only update ticket offers for your own services.' }, 403);
  }

  // Verify the offer belongs to this service
  const existingOffer = await getTicketOfferById(offerId);
  if (!existingOffer || existingOffer.service_id !== serviceId) {
    return getResponse({ error: 'Ticket offer not found for this service.' }, 404);
  }

  let body;
  try {
    body = await request.json();
  } catch (error) {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  // Validate if changing uses_count or validity_days
  const newUsesCount = body.uses_count !== undefined ? (body.uses_count > 0 ? parseInt(body.uses_count) : null) : existingOffer.uses_count;
  const newValidityDays = body.validity_days !== undefined ? (body.validity_days > 0 ? parseInt(body.validity_days) : null) : existingOffer.validity_days;

  // Must have either uses_count or validity_days
  if (newUsesCount == null && newValidityDays == null) {
    return getResponse({ error: 'Ticket offer must have either uses count or validity days.' }, 400);
  }

  if (newUsesCount != null && newValidityDays != null) {
    return getResponse({ error: 'Ticket offer cannot have both uses count and validity days.' }, 400);
  }

  try {
    // Check for duplicates if changing uses_count or validity_days
    const existingOffers = await getServiceTicketOffers(serviceId);

    if (newUsesCount != null && newUsesCount !== existingOffer.uses_count) {
      const duplicate = existingOffers.find(o => o.id !== offerId && o.uses_count === newUsesCount);
      if (duplicate) {
        return getResponse({ error: `A ticket offer with ${newUsesCount} uses already exists for this service.` }, 400);
      }
    }

    if (newValidityDays != null && newValidityDays !== existingOffer.validity_days) {
      const duplicate = existingOffers.find(o => o.id !== offerId && o.validity_days === newValidityDays);
      if (duplicate) {
        return getResponse({ error: `A ticket offer with ${newValidityDays} days validity already exists for this service.` }, 400);
      }
    }

    const offerData = {
      name: body.name?.trim() || existingOffer.name,
      uses_count: newUsesCount,
      validity_days: newValidityDays,
      price: body.price != null ? parseFloat(parseFloat(body.price).toFixed(4)) : existingOffer.price,
      waives_pickup_fee: body.waives_pickup_fee !== undefined ? body.waives_pickup_fee === true : existingOffer.waives_pickup_fee,
      description: body.description !== undefined ? (body.description?.trim() || null) : existingOffer.description,
      sort_order: body.sort_order != null ? parseInt(body.sort_order) : existingOffer.sort_order
    };

    const offer = await updateTicketOffer(offerId, offerData);
    return getResponse(offer, 200);
  } catch (error) {
    console.error('Error updating ticket offer:', error);
    return getResponse({ error: 'Failed to update ticket offer.' }, 500);
  }
}

// DELETE (soft delete) a ticket offer
export async function DELETE({ params, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to delete a ticket offer.' }, 401);
  }
  if (!user.verified) {
    return getResponse({ error: 'You must verify your account before deleting ticket offers.' }, 403);
  }

  const serviceId = parseInt(params.id);
  const offerId = parseInt(params.offerId);

  if (isNaN(serviceId) || isNaN(offerId)) {
    return getResponse({ error: 'Invalid service or offer ID.' }, 400);
  }

  // Check service ownership
  const service = await getServiceById(serviceId);
  if (!service) {
    return getResponse({ error: 'Service not found.' }, 404);
  }

  if (service.user_id !== user.id && !user.administrator) {
    return getResponse({ error: 'You can only delete ticket offers for your own services.' }, 403);
  }

  // Verify the offer belongs to this service
  const existingOffer = await getTicketOfferById(offerId);
  if (!existingOffer || existingOffer.service_id !== serviceId) {
    return getResponse({ error: 'Ticket offer not found for this service.' }, 404);
  }

  try {
    await deleteTicketOffer(offerId);
    return getResponse({ success: true, message: 'Ticket offer deleted successfully.' }, 200);
  } catch (error) {
    console.error('Error deleting ticket offer:', error);
    return getResponse({ error: 'Failed to delete ticket offer.' }, 500);
  }
}
