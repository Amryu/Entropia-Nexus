// @ts-nocheck
import { apiCall } from '$lib/util';
import { error } from '@sveltejs/kit';
import { requireVerified } from '$lib/server/auth';

export async function load({ fetch, params, locals, url }) {
  // Require verified user to manage flights
  const user = requireVerified(locals, url.pathname);

  const serviceId = parseInt(params.id);
  if (isNaN(serviceId)) {
    throw error(400, 'Invalid service ID');
  }

  const service = await apiCall(fetch, `/api/services/${serviceId}`);
  if (!service || service.error) {
    throw error(404, 'Service not found');
  }

  if (service.user_id !== user.id && !user?.grants?.includes('admin.panel')) {
    throw error(403, 'You can only manage flights for your own services');
  }

  if (service.type !== 'transportation') {
    throw error(400, 'Flights are only available for transportation services');
  }

  // Fetch all planets for route selection
  const allPlanets = await apiCall(fetch, '/planets');
  const planets = (allPlanets || []).filter(p => p.Id > 0);

  // Fetch flights (include completed for history)
  const flights = await apiCall(fetch, `/api/services/${serviceId}/flights?include_completed=true`);

  return {
    service,
    planets,
    flights: flights || []
  };
}
