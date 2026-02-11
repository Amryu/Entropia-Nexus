// @ts-nocheck
import { apiCall } from '$lib/util';

const SUB_PLANETS = [
  'Asteroid F.O.M.A.', 'Crystal Palace', 'Space', 'Setesh', 'ARIS',
  'Arkadia Moon', 'Arkadia Underground', 'HELL', 'Secret Island',
  'Hunt The THING', 'Ancient Greece', 'DSEC9'
];

export async function load({ fetch, url }) {
  const planetId = url.searchParams.get('planet_id');
  const page = url.searchParams.get('page') || '1';

  const params = new URLSearchParams();
  if (planetId) params.set('planet_id', planetId);
  params.set('page', page);
  params.set('limit', '20');

  const [offers, allPlanets] = await Promise.all([
    apiCall(fetch, `/api/rental?${params}`),
    apiCall(fetch, '/planets')
  ]);

  const planets = (allPlanets || []).filter(p => p.Id > 0 && !SUB_PLANETS.includes(p.Name));

  return {
    offers: offers || [],
    planets,
    filters: {
      planet_id: planetId ? parseInt(planetId) : null,
      page: parseInt(page)
    }
  };
}
