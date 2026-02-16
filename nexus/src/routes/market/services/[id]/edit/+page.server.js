// @ts-nocheck
import { apiCall } from '$lib/util';
import { error } from '@sveltejs/kit';
import { requireVerified } from '$lib/server/auth';

// Helper to determine if a planet is a main planet (not a moon or sub-area)
function isMainPlanet(planetName) {
  const subPlanets = [
    'Asteroid F.O.M.A.',
    'Crystal Palace',
    'Space',
    'Setesh',
    'ARIS',
    'Arkadia Moon',
    'Arkadia Underground',
    'HELL',
    'Secret Island',
    'Hunt The THING',
    'Ancient Greece',
    'DSEC9'
  ];
  return !subPlanets.includes(planetName);
}

export async function load({ fetch, params, locals, url }) {
  // Require verified user to edit services
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

  // Check ownership (manager or owner)
  if (service.user_id !== user.id && service.owner_user_id !== user.id && !user?.grants?.includes('admin.panel')) {
    throw error(403, 'You can only edit your own services');
  }

  // Fetch planets for location selection - needed for form dropdown
  const allPlanets = await apiCall(fetch, '/planets');

  // Filter to only main planets
  const planets = (allPlanets || []).filter(planet => isMainPlanet(planet.Name));

  // Fetch pilots for warp_privateer transportation services
  let pilots = [];
  if (service.type === 'transportation' && service.transportation_details?.transportation_type === 'warp_privateer') {
    pilots = await apiCall(fetch, `/api/services/${serviceId}/pilots`) || [];
  }

  // Clothings will be lazy loaded on client
  return {
    service,
    planets,
    pilots,
    user: { id: user.id }
  };
}
