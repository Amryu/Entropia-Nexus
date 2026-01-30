// @ts-nocheck
import { error } from '@sveltejs/kit';
import {
  getServiceById,
  getFlightInstance,
  getFlightStateLog,
  getFlightCheckins,
  getServicePilots
} from "$lib/server/db.js";
import { requireVerified } from '$lib/server/auth';

export async function load({ params, locals, url }) {
  // Require verified user to manage flights
  const user = requireVerified(locals, url.pathname);

  const serviceId = parseInt(params.id);
  const flightId = parseInt(params.flightId);

  if (isNaN(serviceId) || isNaN(flightId)) {
    throw error(400, 'Invalid service or flight ID');
  }

  try {
    const [service, flight] = await Promise.all([
      getServiceById(serviceId),
      getFlightInstance(flightId)
    ]);

    if (!service) {
      throw error(404, 'Service not found');
    }

    if (!flight || flight.service_id !== serviceId) {
      throw error(404, 'Flight not found');
    }

    // Check if user is owner, admin, or a pilot
    const pilots = await getServicePilots(serviceId);
    const isPilot = pilots.some(p => p.user_id === user.id);
    const isOwner = service.user_id === user.id;

    if (!isOwner && !user.administrator && !isPilot) {
      throw error(403, 'You do not have permission to manage this flight');
    }

    // Fetch state log and checkins
    const [stateLog, checkins] = await Promise.all([
      getFlightStateLog(flightId),
      getFlightCheckins(flightId)
    ]);

    return {
      service,
      flight,
      stateLog,
      checkins,
      session: locals.session
    };
  } catch (err) {
    // Re-throw HTTP errors
    if (err?.status) {
      throw err;
    }
    console.error('Error loading flight management page:', err);
    throw error(500, 'Failed to load flight data');
  }
}
