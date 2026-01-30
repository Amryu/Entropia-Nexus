// @ts-nocheck
import {
  getFlightInstance,
  getServiceById,
  getUserTicketsForService,
  getExistingCheckin,
  createCheckinWithTransaction
} from "$lib/server/db.js";
import { getResponse } from "$lib/util.js";

export async function POST({ params, request, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to check in.' }, 401);
  }

  const flightId = parseInt(params.flightId);
  if (isNaN(flightId)) {
    return getResponse({ error: 'Invalid flight ID.' }, 400);
  }

  let body;
  try {
    body = await request.json();
  } catch (error) {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  try {
    // Get flight
    const flight = await getFlightInstance(flightId);
    if (!flight) {
      return getResponse({ error: 'Flight not found.' }, 404);
    }

    // Check flight status
    if (flight.status !== 'scheduled' && flight.status !== 'boarding') {
      return getResponse({ error: 'Cannot check in to this flight. It may have already started or been cancelled.' }, 400);
    }

    // Check if within 7 days of departure
    const departureTime = new Date(flight.scheduled_departure);
    const now = new Date();
    const diffMs = departureTime - now;
    const diffMinutes = diffMs / (1000 * 60);
    const sevenDaysInMinutes = 7 * 24 * 60;

    if (diffMinutes > sevenDaysInMinutes) {
      return getResponse({ error: 'Check-in opens 7 days before departure.' }, 400);
    }

    if (diffMinutes < 0) {
      return getResponse({ error: 'This flight has already departed.' }, 400);
    }

    // Check if user already has an active check-in for this flight
    const existingCheckin = await getExistingCheckin(flightId, user.id);
    if (existingCheckin) {
      return getResponse({ error: 'You already have an active check-in for this flight.' }, 400);
    }

    // Verify ticket
    const service = await getServiceById(flight.service_id);
    if (!service) {
      return getResponse({ error: 'Service not found.' }, 404);
    }

    const userTickets = await getUserTicketsForService(user.id, flight.service_id);
    const flightDate = new Date(flight.scheduled_departure);

    // Find a suitable ticket:
    // 1. Must be active or pending
    // 2. Must have uses remaining
    // 3. If duration-based, the flight date must be within the validity period
    const suitableTicket = userTickets.find(t => {
      if (t.status !== 'active' && t.status !== 'pending') return false;
      if (t.uses_remaining <= 0) return false;

      // Check validity period for duration-based tickets
      if (t.valid_until) {
        const validUntil = new Date(t.valid_until);
        // Set to end of day for comparison
        validUntil.setHours(23, 59, 59, 999);
        if (flightDate > validUntil) return false;
      }

      return true;
    });

    if (!suitableTicket) {
      return getResponse({
        error: 'You need a valid ticket to check in. Make sure your ticket has remaining uses and covers the flight date.'
      }, 400);
    }

    // For flexible routes, require exit location
    if (flight.route_type === 'flexible') {
      if (!body.exit_location || !body.exit_planet_id) {
        return getResponse({ error: 'For flexible routes, you must specify your exit location.' }, 400);
      }
    }

    // Create check-in and reserve ticket use atomically
    const { checkin, ticket } = await createCheckinWithTransaction(suitableTicket.id, {
      flight_id: flightId,
      user_id: user.id,
      join_location: body.join_location,
      join_planet_id: body.join_planet_id,
      exit_location: body.exit_location || null,
      exit_planet_id: body.exit_planet_id || null
    });

    return getResponse({ ...checkin, ticket_uses_remaining: ticket.uses_remaining }, 201);
  } catch (error) {
    console.error('Error creating check-in:', error);
    return getResponse({ error: 'Failed to create check-in.' }, 500);
  }
}
