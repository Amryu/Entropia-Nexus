// @ts-nocheck
import { getResponse } from '$lib/util';
import { checkRateLimit } from '$lib/server/rateLimiter.js';
import { getServiceById, getUserActiveRequestsForService, createServiceRequest } from '$lib/server/db';

const PLANET_NAMES = {
  1: 'Calypso',
  2: 'Arkadia',
  3: 'Monria',
  4: 'ROCKtropia',
  5: 'Toulan',
  6: 'Next Island',
  7: 'Cyrene'
};

export async function POST({ params, request, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to request a flight.' }, 401);
  }

  const rateCheck = checkRateLimit(`services:request:${user.id}`, 5, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }
  const rateCheckH = checkRateLimit(`services:request-h:${user.id}`, 20, 3_600_000);
  if (!rateCheckH.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  const serviceId = parseInt(params.id);
  if (isNaN(serviceId)) {
    return getResponse({ error: 'Invalid service ID.' }, 400);
  }

  try {
    const body = await request.json();
    const { customer_planet_id, dropoff_location, requested_start, message } = body;

    // Validate required fields
    const pickupPlanetId = parseInt(customer_planet_id);
    const dropoffPlanetId = parseInt(dropoff_location);
    if (!pickupPlanetId || !dropoffPlanetId) {
      return getResponse({ error: 'Both pickup and destination planets are required.' }, 400);
    }
    if (pickupPlanetId === dropoffPlanetId) {
      return getResponse({ error: 'Pickup and destination planets must be different.' }, 400);
    }

    // Get the service
    const service = await getServiceById(serviceId);
    if (!service) {
      return getResponse({ error: 'Service not found.' }, 404);
    }
    if (service.type !== 'transportation') {
      return getResponse({ error: 'Only transportation services support flight requests.' }, 400);
    }

    // Check if user is the owner (only admins can request their own services)
    if (service.user_id === user.id && !user?.grants?.includes('admin.panel')) {
      return getResponse({ error: 'You cannot request your own service.' }, 403);
    }

    // Check for existing active request
    const existingRequests = await getUserActiveRequestsForService(user.id, serviceId);
    if (existingRequests.length > 0) {
      return getResponse({ error: 'You already have an active request for this service.' }, 409);
    }

    // Build service notes with planet names
    const pickupName = PLANET_NAMES[pickupPlanetId] || `Planet ${pickupPlanetId}`;
    const dropoffName = PLANET_NAMES[dropoffPlanetId] || `Planet ${dropoffPlanetId}`;
    let notes = `[FLIGHT_REQUEST] From: ${pickupName} → To: ${dropoffName}`;
    if (requested_start) {
      notes += `\nRequested time: ${requested_start}`;
    }
    if (message && message.trim()) {
      notes += `\n${message.trim()}`;
    }

    const requestData = {
      service_id: serviceId,
      requester_id: user.id,
      status: 'pending',
      service_notes: notes
    };

    const newRequest = await createServiceRequest(requestData);

    return getResponse({
      success: true,
      request: newRequest,
      message: 'Your flight request has been sent. A Discord thread will be created shortly.'
    }, 201);
  } catch (error) {
    console.error('Error creating flight request:', error);
    return getResponse({ error: 'Failed to submit flight request.' }, 500);
  }
}
