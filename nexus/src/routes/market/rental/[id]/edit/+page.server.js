// @ts-nocheck
import { apiCall } from '$lib/util';
import { requireVerified } from '$lib/server/auth';

const SUB_PLANETS = [
  'Asteroid F.O.M.A.', 'Crystal Palace', 'Space', 'Setesh', 'ARIS',
  'Arkadia Moon', 'Arkadia Underground', 'HELL', 'Secret Island',
  'Hunt The THING', 'Ancient Greece', 'DSEC9'
];

export async function load({ fetch, params, locals, url }) {
  requireVerified(locals, url.pathname);

  const [offer, allPlanets, blockedDates, requests] = await Promise.all([
    apiCall(fetch, `/api/rental/${params.id}`),
    apiCall(fetch, '/planets'),
    apiCall(fetch, `/api/rental/${params.id}/blocked-dates`),
    apiCall(fetch, `/api/rental/${params.id}/requests`)
  ]);

  const planets = (allPlanets || []).filter(p => p.Id > 0 && !SUB_PLANETS.includes(p.Name));

  return {
    offer,
    planets,
    blockedDates: blockedDates || [],
    requests: requests || [],
    isNew: url.searchParams.get('new') === '1'
  };
}
