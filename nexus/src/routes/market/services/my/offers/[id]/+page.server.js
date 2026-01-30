// @ts-nocheck
import { apiCall } from '$lib/util';
import { error } from '@sveltejs/kit';
import { requireVerified } from '$lib/server/auth';

export async function load({ fetch, locals, params, url }) {
  // Require verified user to manage offers
  const user = requireVerified(locals, url.pathname);

  const serviceId = parseInt(params.id);
  if (isNaN(serviceId)) {
    throw error(400, 'Invalid service ID');
  }

  const statusFilter = url.searchParams.get('status') || null;

  // Fetch service details and requests
  const [service, requests] = await Promise.all([
    apiCall(fetch, `/api/services/${serviceId}`),
    apiCall(fetch, `/api/services/my/requests?serviceId=${serviceId}${statusFilter ? `&status=${statusFilter}` : ''}`)
  ]);

  if (!service) {
    throw error(404, 'Service not found');
  }

  // Verify ownership
  if (service.user_id !== user.id && !user.administrator) {
    throw error(403, 'You can only view your own services');
  }

  return {
    service,
    requests: requests || [],
    statusFilter
  };
}
