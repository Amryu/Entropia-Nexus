// @ts-nocheck
import {
  getServiceById,
  updateServiceCurrentLocation,
  canManageService
} from "$lib/server/db.js";
import { getResponse } from "$lib/util.js";

// PUT update current location for a transportation service
export async function PUT({ params, request, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  const serviceId = parseInt(params.id);
  if (isNaN(serviceId)) {
    return getResponse({ error: 'Invalid service ID.' }, 400);
  }

  // Check ownership or pilot status
  const service = await getServiceById(serviceId);
  if (!service) {
    return getResponse({ error: 'Service not found.' }, 404);
  }

  const canManage = await canManageService(serviceId, user.id, user.administrator);
  if (!canManage) {
    return getResponse({ error: 'You do not have permission to manage this service.' }, 403);
  }

  if (service.type !== 'transportation') {
    return getResponse({ error: 'Location can only be set for transportation services.' }, 400);
  }

  let body;
  try {
    body = await request.json();
  } catch (error) {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  try {
    // Allow null to unset location
    const planetId = body.planet_id === null ? null : parseInt(body.planet_id);

    if (planetId !== null && isNaN(planetId)) {
      return getResponse({ error: 'Invalid planet ID.' }, 400);
    }

    const updated = await updateServiceCurrentLocation(serviceId, planetId);

    return getResponse({
      current_planet_id: updated.current_planet_id,
      message: planetId === null ? 'Location cleared.' : 'Location updated successfully.'
    }, 200);
  } catch (error) {
    console.error('Error updating location:', error);
    return getResponse({ error: 'Failed to update location.' }, 500);
  }
}
