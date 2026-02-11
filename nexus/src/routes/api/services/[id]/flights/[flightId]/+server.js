//@ts-nocheck
import {
  getServiceById,
  getFlightInstance,
  updateFlightInstance,
  logFlightStateChange,
  getFlightStateLog,
  undoFlightStateChange,
  getFlightCheckins,
  cancelAllFlightCheckins,
  createRescheduleNotification,
  getActiveServiceFlights,
  restoreTicketUsesForFlight,
  updateServiceCurrentLocation,
  canManageService
} from "$lib/server/db.js";
import { getResponse } from "$lib/util.js";
import { checkRateLimit } from "$lib/server/rateLimiter.js";
import { optimizeRoute, validateRoute } from "$lib/utils/routeOptimizer.js";

// GET single flight with state log and checkins
export async function GET({ params, locals }) {
  const flightId = parseInt(params.flightId);
  if (isNaN(flightId)) {
    return getResponse({ error: 'Invalid flight ID.' }, 400);
  }

  try {
    const flight = await getFlightInstance(flightId);
    if (!flight) {
      return getResponse({ error: 'Flight not found.' }, 404);
    }

    // Include state log and checkins
    const [stateLog, checkins] = await Promise.all([
      getFlightStateLog(flightId),
      getFlightCheckins(flightId)
    ]);

    return getResponse({
      ...flight,
      state_log: stateLog,
      checkins: checkins
    }, 200);
  } catch (error) {
    console.error('Error fetching flight:', error);
    return getResponse({ error: 'Failed to fetch flight.' }, 500);
  }
}

// PUT update flight (start, advance, cancel, restore)
export async function PUT({ params, request, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in.' }, 401);
  }

  const rateCheck = checkRateLimit(`services:flights:${user.id}`, 20, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  const serviceId = parseInt(params.id);
  const flightId = parseInt(params.flightId);

  if (isNaN(serviceId) || isNaN(flightId)) {
    return getResponse({ error: 'Invalid service or flight ID.' }, 400);
  }

  // Check ownership or pilot status
  const service = await getServiceById(serviceId);
  if (!service) {
    return getResponse({ error: 'Service not found.' }, 404);
  }

  const canManage = await canManageService(serviceId, user.id, user.administrator);
  if (!canManage) {
    return getResponse({ error: 'You do not have permission to manage flights for this service.' }, 403);
  }

  const flight = await getFlightInstance(flightId);
  if (!flight || flight.service_id !== serviceId) {
    return getResponse({ error: 'Flight not found for this service.' }, 404);
  }

  let body;
  try {
    body = await request.json();
  } catch (error) {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  const action = body.action;

  try {
    switch (action) {
      case 'board': {
        if (flight.status !== 'scheduled') {
          return getResponse({ error: `Cannot start boarding for a flight with status '${flight.status}'.` }, 400);
        }

        const updatedFlight = await updateFlightInstance(flightId, {
          status: 'boarding'
        });

        await logFlightStateChange(flightId, 'scheduled', 'boarding', 0);

        return getResponse(updatedFlight, 200);
      }

      case 'start': {
        if (flight.status !== 'boarding') {
          return getResponse({ error: `Flight must be in boarding status to start. Current status: '${flight.status}'.` }, 400);
        }

        const routeType = flight.route_type || 'fixed';
        const checkins = await getFlightCheckins(flightId);

        // For flexible routes, all check-ins must be accepted or declined before starting
        if (routeType === 'flexible') {
          const pendingCheckins = checkins.filter(c => c.status === 'pending');
          if (pendingCheckins.length > 0) {
            return getResponse({
              error: `Cannot start flexible route flight with ${pendingCheckins.length} pending check-in(s). Please accept or decline all check-ins first.`
            }, 400);
          }
        }

        // Validate that all accepted passengers can reach their destinations
        const acceptedPassengers = checkins.filter(c => c.status === 'accepted' && c.join_planet_id && c.exit_planet_id);
        if (acceptedPassengers.length > 0) {
          const routeStops = typeof flight.route_stops === 'string'
            ? JSON.parse(flight.route_stops)
            : (flight.route_stops || []);

          const requirements = acceptedPassengers.map(c => ({
            pickup: c.join_planet_id,
            dropoff: c.exit_planet_id,
            userName: c.user_name
          }));

          const validation = validateRoute(routeStops, requirements);

          if (!validation.valid) {
            // Build a user-friendly error message
            const missingPickups = [];
            const missingDropoffs = [];
            const orderErrors = [];

            for (const error of validation.errors) {
              if (error.includes('Pickup planet') && error.includes('not in route')) {
                const match = acceptedPassengers.find(p => error.includes(p.join_planet_id.toString()));
                if (match) {
                  missingPickups.push(`${match.user_name} (pickup: ${match.join_planet_name || 'Unknown'})`);
                }
              } else if (error.includes('Dropoff planet') && error.includes('not in route')) {
                const match = acceptedPassengers.find(p => error.includes(p.exit_planet_id.toString()));
                if (match) {
                  missingDropoffs.push(`${match.user_name} (destination: ${match.exit_planet_name || 'Unknown'})`);
                }
              } else if (error.includes('must come before')) {
                orderErrors.push(error);
              }
            }

            let errorMessage = 'Cannot start flight: ';
            if (missingPickups.length > 0) {
              errorMessage += `Missing pickup stops for: ${missingPickups.join(', ')}. `;
            }
            if (missingDropoffs.length > 0) {
              errorMessage += `Missing destination stops for: ${missingDropoffs.join(', ')}. `;
            }
            if (orderErrors.length > 0) {
              errorMessage += `Route order issues: ${orderErrors.length}. `;
            }
            errorMessage += 'Please update the route to include all passenger stops.';

            return getResponse({ error: errorMessage, validation_errors: validation.errors }, 400);
          }
        }

        const updatedFlight = await updateFlightInstance(flightId, {
          status: 'running',
          actual_departure: new Date().toISOString(),
          current_stop_index: 0,
          current_state: 'departing'
        });

        await logFlightStateChange(flightId, 'boarding', 'running', 0);

        return getResponse(updatedFlight, 200);
      }

      case 'advance': {
        if (flight.status !== 'running') {
          return getResponse({ error: 'Flight must be running to advance.' }, 400);
        }

        const routeStops = typeof flight.route_stops === 'string'
          ? JSON.parse(flight.route_stops)
          : flight.route_stops;
        const currentStopIndex = flight.current_stop_index || 0;
        const currentState = flight.current_state || 'departing';

        // Determine next state based on current state
        // States alternate between at_stop_X and warp_to_X
        let newState;
        let newStopIndex = currentStopIndex;

        if (currentState === 'departing' || currentState.startsWith('at_stop_')) {
          // Currently at a stop, next is warp
          const nextStopIndex = currentStopIndex + 1;

          if (nextStopIndex >= routeStops.length) {
            // No more stops, flight complete
            const updatedFlight = await updateFlightInstance(flightId, {
              status: 'completed',
              current_state: 'arrived',
              completed_at: new Date().toISOString()
            });

            await logFlightStateChange(flightId, 'running', 'completed', currentStopIndex);

            return getResponse(updatedFlight, 200);
          }

          // Enter warp to next stop
          newState = `warp_to_${nextStopIndex}`;
          newStopIndex = currentStopIndex; // Don't increment stop index yet
        } else if (currentState.startsWith('warp_to_')) {
          // Currently in warp, arrive at next stop
          const targetStop = parseInt(currentState.split('_')[2]);
          newState = `at_stop_${targetStop}`;
          newStopIndex = targetStop;

          // Update current location to the planet at this stop
          const stopPlanetId = routeStops[targetStop]?.planet_id;
          if (stopPlanetId) {
            await updateServiceCurrentLocation(flight.service_id, stopPlanetId);
          }
        } else {
          return getResponse({ error: 'Invalid flight state.' }, 400);
        }

        const updatedFlight = await updateFlightInstance(flightId, {
          current_stop_index: newStopIndex,
          current_state: newState
        });

        await logFlightStateChange(flightId, 'running', 'running', newStopIndex);

        return getResponse(updatedFlight, 200);
      }

      case 'undo': {
        // Get the most recent undoable state change
        const stateLog = await getFlightStateLog(flightId);
        const recentUndoable = stateLog.find(log =>
          log.can_undo && !log.undone
        );

        if (!recentUndoable) {
          return getResponse({ error: 'No undoable state changes found.' }, 400);
        }

        // Check if within 10s window
        const changedAt = new Date(recentUndoable.changed_at);
        const now = new Date();
        if (now.getTime() - changedAt.getTime() > 10000) {
          return getResponse({ error: 'Undo window has expired (10 seconds).' }, 400);
        }

        // Undo the state change
        await undoFlightStateChange(recentUndoable.id);

        // Determine previous state based on current state
        const updateData = {};
        const currentState = flight.current_state;
        const currentStopIndex = flight.current_stop_index || 0;

        if (recentUndoable.previous_state) {
          updateData.status = recentUndoable.previous_state;
        }

        // Reconstruct previous current_state and stop_index based on what we're undoing
        if (recentUndoable.previous_state === 'scheduled') {
          // Going back to scheduled from boarding - clear flight progress
          updateData.current_state = null;
          updateData.current_stop_index = null;
          updateData.actual_departure = null;
        } else if (recentUndoable.previous_state === 'boarding') {
          // Going back to boarding from running - clear flight progress
          updateData.current_state = null;
          updateData.current_stop_index = null;
          updateData.actual_departure = null;
        } else if (currentState?.startsWith('at_stop_')) {
          // Was at a stop, go back to warp state
          const stopNum = parseInt(currentState.split('_')[2]);
          updateData.current_state = `warp_to_${stopNum}`;
          updateData.current_stop_index = stopNum - 1;
        } else if (currentState?.startsWith('warp_to_')) {
          // Was in warp, go back to previous stop or departing
          const targetStopNum = parseInt(currentState.split('_')[2]);
          if (targetStopNum === 1) {
            // Was warping to first stop, go back to departing
            updateData.current_state = 'departing';
            updateData.current_stop_index = 0;
          } else {
            // Was warping to later stop, go back to previous stop
            updateData.current_state = `at_stop_${targetStopNum - 1}`;
            updateData.current_stop_index = targetStopNum - 1;
          }
        }

        const updatedFlight = await updateFlightInstance(flightId, updateData);

        return getResponse({ ...updatedFlight, undone: true }, 200);
      }

      case 'cancel': {
        if (flight.status === 'completed' || flight.status === 'cancelled') {
          return getResponse({ error: `Cannot cancel a ${flight.status} flight.` }, 400);
        }

        const previousState = flight.status;

        // Restore ticket uses for all accepted/pending check-ins
        await restoreTicketUsesForFlight(flightId);

        const updatedFlight = await updateFlightInstance(flightId, {
          status: 'cancelled'
        });

        // Log the cancellation with current stop index to track where it was cancelled
        await logFlightStateChange(flightId, previousState, 'cancelled', flight.current_stop_index);

        return getResponse(updatedFlight, 200);
      }

      case 'restore': {
        if (flight.status !== 'cancelled') {
          return getResponse({ error: 'Only cancelled flights can be restored.' }, 400);
        }

        // Check if flight has been started and advanced (has a state log beyond initial start)
        const stateLog = await getFlightStateLog(flightId);
        const hasAdvanced = stateLog.some(log =>
          log.new_state === 'running' && log.stop_index > 0
        );
        if (hasAdvanced) {
          return getResponse({ error: 'Cannot restore a flight that has been started and advanced.' }, 400);
        }

        // Check if within 2h grace period after scheduled departure
        const scheduledDeparture = new Date(flight.scheduled_departure);
        const now = new Date();
        const gracePeriodEnd = new Date(scheduledDeparture.getTime() + 2 * 60 * 60 * 1000);

        if (now > gracePeriodEnd) {
          return getResponse({ error: 'Restore window has expired (2 hours after scheduled departure).' }, 400);
        }

        // Check for overlaps with other active flights (within 15 minutes)
        const activeFlights = await getActiveServiceFlights(flight.service_id, flightId);
        const restoreTime = scheduledDeparture.getTime();

        for (const activeFlight of activeFlights) {
          const activeTime = new Date(activeFlight.scheduled_departure).getTime();
          const diffMs = Math.abs(restoreTime - activeTime);
          const diffMinutes = diffMs / (1000 * 60);

          if (diffMinutes < 15) {
            return getResponse({
              error: 'Cannot restore this flight - it overlaps within 15 minutes of another active flight. Please reschedule one of the flights first.'
            }, 400);
          }
        }

        const updatedFlight = await updateFlightInstance(flightId, {
          status: 'scheduled'
        });

        await logFlightStateChange(flightId, 'cancelled', 'scheduled');

        return getResponse(updatedFlight, 200);
      }

      case 'update_route': {
        if (flight.status === 'completed' || flight.status === 'cancelled') {
          return getResponse({ error: 'Cannot modify route of a completed or cancelled flight.' }, 400);
        }

        const routeType = flight.route_type || 'fixed';
        const minStops = routeType === 'flexible' ? 1 : 2;

        if (!body.route_stops || !Array.isArray(body.route_stops) || body.route_stops.length < minStops) {
          return getResponse({ error: `At least ${minStops} route stops are required.` }, 400);
        }

        // Calculate how many stops are locked (visited, current, or being warped to)
        let lockedCount = flight.current_stop_index || 0;
        if (flight.status === 'running') {
          lockedCount += 1; // Lock current/departure stop
          if (flight.current_state?.startsWith('warp_to_')) {
            lockedCount += 1; // Also lock the warp target
          }
        }

        // Validate that locked stops haven't been modified
        const currentStops = typeof flight.route_stops === 'string'
          ? JSON.parse(flight.route_stops)
          : (flight.route_stops || []);

        for (let i = 0; i < lockedCount; i++) {
          const currentStop = currentStops[i];
          const newStop = body.route_stops[i];

          if (!newStop) {
            return getResponse({ error: `Cannot remove locked stop at position ${i + 1}.` }, 400);
          }

          // Check if the stop has been changed
          if (currentStop.planet_id !== newStop.planet_id ||
              (currentStop.name !== newStop.name && newStop.planet_id === null)) {
            return getResponse({ error: `Cannot modify locked stop at position ${i + 1}. This stop has already been visited or is in progress.` }, 400);
          }
        }

        const updatedFlight = await updateFlightInstance(flightId, {
          route_stops: body.route_stops
        });

        // Log the route change for Discord notifications
        await logFlightStateChange(flightId, 'route_changed', 'route_changed', flight.current_stop_index || 0);

        return getResponse(updatedFlight, 200);
      }

      case 'optimize_route': {
        if (flight.status === 'completed' || flight.status === 'cancelled') {
          return getResponse({ error: 'Cannot optimize route of a completed or cancelled flight.' }, 400);
        }

        if (flight.route_type !== 'flexible') {
          return getResponse({ error: 'Route optimization is only available for flexible routes.' }, 400);
        }

        // Get current check-ins
        const checkins = await getFlightCheckins(flightId);

        // Check if there are any accepted passengers
        const acceptedPassengers = checkins.filter(c => c.status === 'accepted' && c.join_planet_id && c.exit_planet_id);
        if (acceptedPassengers.length === 0) {
          return getResponse({
            error: 'No accepted passengers with valid pickup and destination. Accept check-ins first before optimizing the route.',
            no_passengers: true
          }, 400);
        }

        // Parse current route
        const routeStops = typeof flight.route_stops === 'string'
          ? JSON.parse(flight.route_stops)
          : (flight.route_stops || []);

        // Determine locked stops (already visited based on current_stop_index)
        const lockedStops = routeStops.slice(0, (flight.current_stop_index || 0) + 1);
        const startPoint = routeStops[0] || null;
        const endPoint = routeStops.length > 1 ? routeStops[routeStops.length - 1] : null;

        // Optimize the route
        const optimized = optimizeRoute({
          lockedStops,
          startPoint,
          endPoint,
          checkins
        });

        // Validate the result
        const requirements = checkins
          .filter(c => c.status === 'accepted')
          .filter(c => c.join_planet_id && c.exit_planet_id)
          .map(c => ({
            pickup: c.join_planet_id,
            dropoff: c.exit_planet_id,
            userName: c.user_name
          }));

        const validation = validateRoute(optimized.fullRoute, requirements);

        return getResponse({
          optimized_route: optimized.fullRoute,
          locked_count: lockedStops.length,
          validation: validation,
          passenger_count: acceptedPassengers.length,
          message: validation.valid
            ? `Route optimized for ${acceptedPassengers.length} passenger(s). Review and confirm to apply.`
            : 'Route optimization completed with warnings. Some passengers may not be able to reach their destination.'
        }, 200);
      }

      case 'reschedule': {
        if (flight.status === 'completed') {
          return getResponse({ error: 'Cannot reschedule a completed flight.' }, 400);
        }

        if (flight.status === 'running') {
          return getResponse({ error: 'Cannot reschedule a flight that has already started.' }, 400);
        }

        if (!body.scheduled_departure) {
          return getResponse({ error: 'New scheduled departure time is required.' }, 400);
        }

        const newDeparture = new Date(body.scheduled_departure);
        if (isNaN(newDeparture.getTime())) {
          return getResponse({ error: 'Invalid departure time format.' }, 400);
        }

        // Get the service for the title
        const oldDeparture = flight.scheduled_departure;

        // Restore ticket uses for all accepted/pending check-ins before cancelling
        await restoreTicketUsesForFlight(flightId);

        // Cancel all check-ins and get affected user IDs
        const affectedUserIds = await cancelAllFlightCheckins(flightId);

        // Create notification for each affected user
        for (const userId of affectedUserIds) {
          await createRescheduleNotification(
            userId,
            flightId,
            oldDeparture,
            newDeparture.toISOString(),
            service.title
          );
        }

        // Update flight departure time
        const updatedFlight = await updateFlightInstance(flightId, {
          scheduled_departure: newDeparture.toISOString()
        });

        await logFlightStateChange(flightId, flight.status, flight.status, flight.current_stop_index);

        return getResponse({
          ...updatedFlight,
          cancelled_checkins: affectedUserIds.length,
          message: `Flight rescheduled. ${affectedUserIds.length} check-in(s) cancelled and users will be notified via Discord DM.`
        }, 200);
      }

      default:
        return getResponse({ error: 'Invalid action. Valid actions: board, start, advance, undo, cancel, restore, update_route, reschedule' }, 400);
    }
  } catch (error) {
    console.error('Error updating flight:', error);
    return getResponse({ error: 'Failed to update flight.' }, 500);
  }
}
