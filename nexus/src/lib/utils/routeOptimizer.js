// @ts-nocheck
/**
 * Route Optimizer for Flexible Flights
 *
 * Optimizes the order of stops to minimize the number of warp jumps
 * while respecting constraints:
 * - Each customer's pickup must come before their dropoff
 * - Already visited stops (locked) cannot be reordered
 * - Start and optional end points are fixed
 */

/**
 * Optimize route based on check-ins
 * @param {Object} params
 * @param {Array} params.lockedStops - Stops that have already been visited (cannot change)
 * @param {Object|null} params.startPoint - The starting point { planet_id, name }
 * @param {Object|null} params.endPoint - The optional ending point { planet_id, name }
 * @param {Array} params.checkins - Array of check-ins with join_planet_id and exit_planet_id
 * @returns {Array} Optimized route stops
 */
export function optimizeRoute({ lockedStops = [], startPoint = null, endPoint = null, checkins = [] }) {
  // Build list of required pickup/dropoff pairs
  // Use join_planet_name/exit_planet_name from the DB query, or fall back to join_location/exit_location
  const requirements = checkins
    .filter(c => c.status === 'accepted' || c.status === 'pending')
    .map(c => ({
      id: c.id,
      pickup: c.join_planet_id,
      pickupName: c.join_planet_name || c.join_location || `Unknown Planet`,
      dropoff: c.exit_planet_id,
      dropoffName: c.exit_planet_name || c.exit_location || `Unknown Planet`
    }))
    .filter(r => r.pickup && r.dropoff);

  // Build a map of planet_id to name for easy lookup
  const planetNames = new Map();
  for (const req of requirements) {
    if (req.pickup && req.pickupName) {
      planetNames.set(req.pickup, req.pickupName);
    }
    if (req.dropoff && req.dropoffName) {
      planetNames.set(req.dropoff, req.dropoffName);
    }
  }
  // Also include locked stops
  for (const stop of lockedStops) {
    if (stop.planet_id && stop.name) {
      planetNames.set(stop.planet_id, stop.name);
    }
  }
  // Include start and end points
  if (startPoint?.planet_id && startPoint?.name) {
    planetNames.set(startPoint.planet_id, startPoint.name);
  }
  if (endPoint?.planet_id && endPoint?.name) {
    planetNames.set(endPoint.planet_id, endPoint.name);
  }

  // Collect all unique planets we need to visit
  const pickupPlanets = new Set(requirements.map(r => r.pickup));
  const dropoffPlanets = new Set(requirements.map(r => r.dropoff));

  // Build dependency graph: for each customer, pickup must come before dropoff
  const dependencies = requirements.map(r => ({ before: r.pickup, after: r.dropoff }));

  // Get locked planet IDs
  const lockedPlanetIds = lockedStops.map(s => s.planet_id);

  // Filter out requirements where pickup is already in locked stops
  const activeRequirements = requirements.filter(r => !lockedPlanetIds.includes(r.pickup) || !lockedPlanetIds.includes(r.dropoff));

  // Collect all planets that still need to be visited
  const neededPlanets = new Set();
  for (const req of activeRequirements) {
    if (!lockedPlanetIds.includes(req.pickup)) {
      neededPlanets.add(req.pickup);
    }
    if (!lockedPlanetIds.includes(req.dropoff)) {
      neededPlanets.add(req.dropoff);
    }
  }

  // If there's an end point, include it
  if (endPoint?.planet_id) {
    neededPlanets.add(endPoint.planet_id);
  }

  // Use a greedy approach to build the route
  // Strategy: At each step, choose the planet that satisfies the most pending pickups/dropoffs
  const unlockedRoute = [];
  const visited = new Set(lockedPlanetIds);
  const pickedUp = new Set(); // Customers who have been picked up

  // Process each customer - mark as picked up if their pickup is in locked
  for (const req of requirements) {
    if (visited.has(req.pickup)) {
      pickedUp.add(req.id);
    }
  }

  const remainingPlanets = [...neededPlanets];

  while (remainingPlanets.length > 0) {
    let bestPlanet = null;
    let bestScore = -1;

    for (const planetId of remainingPlanets) {
      // Calculate score: how many pickups/dropoffs does this satisfy?
      let score = 0;

      // Count pickups at this planet (customers not yet picked up)
      for (const req of requirements) {
        if (req.pickup === planetId && !pickedUp.has(req.id)) {
          score += 1;
        }
      }

      // Count dropoffs at this planet (only for customers already picked up)
      for (const req of requirements) {
        if (req.dropoff === planetId && pickedUp.has(req.id)) {
          score += 1;
        }
      }

      if (score > bestScore) {
        bestScore = score;
        bestPlanet = planetId;
      }
    }

    // If no planet satisfies anything, pick the first remaining
    if (bestPlanet === null) {
      bestPlanet = remainingPlanets[0];
    }

    // Add to route
    unlockedRoute.push(bestPlanet);
    visited.add(bestPlanet);

    // Update picked up status
    for (const req of requirements) {
      if (req.pickup === bestPlanet) {
        pickedUp.add(req.id);
      }
    }

    // Remove from remaining
    const idx = remainingPlanets.indexOf(bestPlanet);
    if (idx !== -1) {
      remainingPlanets.splice(idx, 1);
    }
  }

  // Ensure end point is last if specified
  if (endPoint?.planet_id) {
    const endIdx = unlockedRoute.indexOf(endPoint.planet_id);
    if (endIdx !== -1 && endIdx !== unlockedRoute.length - 1) {
      unlockedRoute.splice(endIdx, 1);
      unlockedRoute.push(endPoint.planet_id);
    }
  }

  // Helper to get planet name from our map
  const getPlanetName = (planetId) => {
    return planetNames.get(planetId) || `Unknown Planet (ID: ${planetId})`;
  };

  // Combine locked + unlocked
  return {
    lockedStops: lockedStops,
    newStops: unlockedRoute.map(planetId => ({
      planet_id: planetId,
      name: getPlanetName(planetId)
    })),
    fullRoute: [
      ...lockedStops,
      ...unlockedRoute.map(planetId => ({
        planet_id: planetId,
        name: getPlanetName(planetId)
      }))
    ],
    requirements: requirements // Include requirements for validation
  };
}

/**
 * Validate that a route satisfies all pickup-before-dropoff constraints
 * @param {Array} route - Array of planet_ids in order
 * @param {Array} requirements - Array of { pickup, dropoff } pairs
 * @returns {Object} { valid: boolean, errors: string[] }
 */
export function validateRoute(route, requirements) {
  const errors = [];
  const planetOrder = new Map();

  route.forEach((stop, idx) => {
    const planetId = stop.planet_id || stop;
    if (!planetOrder.has(planetId)) {
      planetOrder.set(planetId, idx);
    }
  });

  for (const req of requirements) {
    const pickupIdx = planetOrder.get(req.pickup);
    const dropoffIdx = planetOrder.get(req.dropoff);

    if (pickupIdx === undefined) {
      errors.push(`Pickup planet ${req.pickup} not in route`);
    }
    if (dropoffIdx === undefined) {
      errors.push(`Dropoff planet ${req.dropoff} not in route`);
    }
    if (pickupIdx !== undefined && dropoffIdx !== undefined && pickupIdx >= dropoffIdx) {
      errors.push(`Customer pickup at planet ${req.pickup} must come before dropoff at planet ${req.dropoff}`);
    }
  }

  return {
    valid: errors.length === 0,
    errors
  };
}
