//@ts-nocheck
import {
  getServiceById,
  getServiceFlights,
  createFlightInstance,
  logFlightStateChange
} from "$lib/server/db.js";
import { getResponse } from "$lib/util.js";

// GET upcoming flights for a service
export async function GET({ params, url, locals }) {
  const serviceId = parseInt(params.id);
  if (isNaN(serviceId)) {
    return getResponse({ error: 'Invalid service ID.' }, 400);
  }

  try {
    const includeCompleted = url.searchParams.get('include_completed') === 'true';
    const upcoming = url.searchParams.get('upcoming') === 'true';

    let flights;
    if (upcoming) {
      const { getUpcomingServiceFlights } = await import('$lib/server/db.js');
      flights = await getUpcomingServiceFlights(serviceId, 7);
    } else {
      flights = await getServiceFlights(serviceId, includeCompleted);
    }

    return getResponse(flights, 200);
  } catch (error) {
    console.error('Error fetching flights:', error);
    return getResponse({ error: 'Failed to fetch flights.' }, 500);
  }
}

// POST create a new flight instance
export async function POST({ params, request, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to create a flight.' }, 401);
  }
  if (!user.verified) {
    return getResponse({ error: 'You must verify your account.' }, 403);
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
    return getResponse({ error: 'You can only create flights for your own services.' }, 403);
  }

  if (service.type !== 'transportation') {
    return getResponse({ error: 'Flights are only for transportation services.' }, 400);
  }

  let body;
  try {
    body = await request.json();
  } catch (error) {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  if (!body.scheduled_departure) {
    return getResponse({ error: 'Scheduled departure time is required.' }, 400);
  }

  const routeType = body.route_type || 'fixed';
  if (!['fixed', 'flexible'].includes(routeType)) {
    return getResponse({ error: 'Route type must be "fixed" or "flexible".' }, 400);
  }

  if (!body.route_stops || !Array.isArray(body.route_stops)) {
    return getResponse({ error: 'Route stops are required.' }, 400);
  }

  // Fixed routes need at least 2 stops; flexible can have 1 (start only) or 2 (start + end)
  if (routeType === 'fixed' && body.route_stops.length < 2) {
    return getResponse({ error: 'At least 2 route stops are required for fixed routes.' }, 400);
  }

  if (routeType === 'flexible' && body.route_stops.length < 1) {
    return getResponse({ error: 'At least a starting point is required for flexible routes.' }, 400);
  }

  try {
    // Calculate auto-cancel time (2h after scheduled departure)
    const departure = new Date(body.scheduled_departure);
    const autoCancelAt = new Date(departure.getTime() + 2 * 60 * 60 * 1000);

    const flight = await createFlightInstance({
      schedule_id: body.schedule_id || null,
      service_id: serviceId,
      scheduled_departure: body.scheduled_departure,
      status: 'scheduled',
      route_type: routeType,
      route_stops: body.route_stops,
      auto_cancel_at: autoCancelAt.toISOString()
    });

    // Log initial state
    await logFlightStateChange(flight.id, null, 'scheduled');

    return getResponse(flight, 201);
  } catch (error) {
    console.error('Error creating flight:', error);
    return getResponse({ error: 'Failed to create flight.' }, 500);
  }
}
