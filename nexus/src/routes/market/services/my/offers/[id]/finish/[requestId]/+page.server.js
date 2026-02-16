// @ts-nocheck
import { apiCall } from '$lib/util';
import { redirect, error } from '@sveltejs/kit';
import { requireVerified } from '$lib/server/auth';

export async function load({ fetch, locals, params, url }) {
  // Require verified user to finish requests
  const user = requireVerified(locals, url.pathname);

  const serviceId = parseInt(params.id);
  const requestId = parseInt(params.requestId);

  if (isNaN(serviceId) || isNaN(requestId)) {
    throw error(400, 'Invalid ID');
  }

  // Fetch service and request details
  const [service, request] = await Promise.all([
    apiCall(fetch, `/api/services/${serviceId}`),
    apiCall(fetch, `/api/services/requests/${requestId}`)
  ]);

  if (!service) {
    throw error(404, 'Service not found');
  }

  if (!request) {
    throw error(404, 'Request not found');
  }

  // Verify ownership
  if (service.user_id !== user.id && service.owner_user_id !== user.id && !user?.grants?.includes('admin.panel')) {
    throw error(403, 'You can only finish requests for your own services');
  }

  // Verify request belongs to this service
  if (request.service_id !== serviceId) {
    throw error(400, 'Request does not belong to this service');
  }

  // Verify request is in progress
  if (request.status !== 'in_progress') {
    throw redirect(302, `/market/services/my/offers/${serviceId}`);
  }

  return {
    service,
    request
  };
}
