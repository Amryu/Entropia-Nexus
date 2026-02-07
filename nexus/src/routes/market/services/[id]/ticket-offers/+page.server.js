// @ts-nocheck
import { apiCall } from '$lib/util';
import { error } from '@sveltejs/kit';
import { requireVerified } from '$lib/server/auth';

export async function load({ fetch, params, locals, url }) {
  // Require verified user to manage ticket offers
  const user = requireVerified(locals, url.pathname);

  const serviceId = parseInt(params.id);
  if (isNaN(serviceId)) {
    throw error(400, 'Invalid service ID');
  }

  // Fetch the service
  const service = await apiCall(fetch, `/api/services/${serviceId}`);
  if (!service || service.error) {
    throw error(404, 'Service not found');
  }

  // Check ownership
  if (service.user_id !== user.id && !user?.grants?.includes('admin.panel')) {
    throw error(403, 'You can only manage ticket offers for your own services');
  }

  // Only transportation services can have ticket offers
  if (service.type !== 'transportation') {
    throw error(400, 'Ticket offers are only available for transportation services');
  }

  // Fetch existing ticket offers
  const ticketOffers = await apiCall(fetch, `/api/services/${serviceId}/ticket-offers`);

  return {
    service,
    ticketOffers: ticketOffers || []
  };
}
