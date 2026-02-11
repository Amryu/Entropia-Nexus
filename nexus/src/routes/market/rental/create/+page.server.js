// @ts-nocheck
import { apiCall } from '$lib/util';
import { requireVerified } from '$lib/server/auth';
import { getUserLoadouts } from '$lib/server/db.js';

const SUB_PLANETS = [
  'Asteroid F.O.M.A.', 'Crystal Palace', 'Space', 'Setesh', 'ARIS',
  'Arkadia Moon', 'Arkadia Underground', 'HELL', 'Secret Island',
  'Hunt The THING', 'Ancient Greece', 'DSEC9'
];

export async function load({ fetch, locals, url }) {
  const user = requireVerified(locals, url.pathname);

  const [allPlanets, loadoutsRaw] = await Promise.all([
    apiCall(fetch, '/planets'),
    getUserLoadouts(user.id).catch(() => [])
  ]);

  const planets = (allPlanets || []).filter(p => p.Id > 0 && !SUB_PLANETS.includes(p.Name));

  // Strip loadout data (large), keep id/name/linked status
  const loadouts = (loadoutsRaw || []).map(l => ({
    id: l.id,
    name: l.name,
    linked_item_set: l.linked_item_set
  }));

  return {
    planets,
    loadouts
  };
}
