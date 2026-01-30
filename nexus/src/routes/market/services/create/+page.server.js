// @ts-nocheck
import { apiCall } from '$lib/util';
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

export async function load({ fetch, locals, url }) {
  // Require verified user to create services
  requireVerified(locals, url.pathname);

  // Fetch planets for location selection - needed for form dropdown
  const allPlanets = await apiCall(fetch, '/planets');

  // Filter to only main planets
  const planets = (allPlanets || []).filter(planet => isMainPlanet(planet.Name));

  // Clothings will be lazy loaded on client
  return {
    planets
  };
}
