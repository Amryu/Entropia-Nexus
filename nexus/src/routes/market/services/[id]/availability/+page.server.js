// @ts-nocheck
import { apiCall } from '$lib/util';
import { redirect, error } from '@sveltejs/kit';
import { requireVerified } from '$lib/server/auth';

export async function load({ fetch, params, locals, url }) {
  // Require verified user to manage availability
  const user = requireVerified(locals, url.pathname);

  const serviceId = parseInt(params.id);
  if (isNaN(serviceId)) {
    throw redirect(302, '/market/services');
  }

  // Fetch service details
  const service = await apiCall(fetch, `/api/services/${serviceId}`);

  if (!service || service.error) {
    throw redirect(302, '/market/services');
  }

  // Check ownership
  if (service.user_id !== user.id && !user?.grants?.includes('admin.panel')) {
    throw redirect(302, `/market/services/${serviceId}`);
  }

  // Fetch current availability
  const availability = await apiCall(fetch, `/api/services/${serviceId}/availability`);

  return {
    service,
    availability: Array.isArray(availability) ? availability : []
  };
}
