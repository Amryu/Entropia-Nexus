// @ts-nocheck
let items;

import { apiCall, getMainPlanetName, pageResponse } from '$lib/util';

export async function load({ fetch, params }) {
  if (!items) {
    let mobs = await apiCall(fetch, '/mobs');

    items = {
      calypso: mobs.filter(mob => getMainPlanetName(mob.Planet.Name) === 'Calypso'),
      arkadia: mobs.filter(mob => getMainPlanetName(mob.Planet.Name) === 'Arkadia'),
      cyrene: mobs.filter(mob => getMainPlanetName(mob.Planet.Name) === 'Cyrene'),
      rocktropia: mobs.filter(mob => getMainPlanetName(mob.Planet.Name) === 'ROCKtropia'),
      nextisland: mobs.filter(mob => getMainPlanetName(mob.Planet.Name) === 'Next Island'),
      toulan: mobs.filter(mob => getMainPlanetName(mob.Planet.Name) === 'Toulan'),
      monria: mobs.filter(mob => getMainPlanetName(mob.Planet.Name) === 'Monria'),
      space: mobs.filter(mob => getMainPlanetName(mob.Planet.Name) === 'Space'),
    }
  }

  if (!params.planet || !params.slug) {
    return pageResponse(items);
  }

  let mob = await apiCall(fetch, `/mobs/${encodeURIComponent(params.slug)}`);

  if (mob == null) {
    return pageResponse(items, null, null, 404);
  }

  let [species, maturities, loots] = await Promise.all([
    mob?.Species != null ? apiCall(fetch, mob.Species.Links.$Url) : Promise.resolve(null),
    apiCall(fetch, `/mobmaturities?Mob=${encodeURIComponent(params.slug)}`),
    apiCall(fetch, `/mobloots?Mob=${encodeURIComponent(params.slug)}`)
  ]);

  mob.Species = species;
  mob.Maturities = maturities;

  return pageResponse(
    items,
    mob,
    {
      planet: params.planet,
      loots,
    }
  );
}