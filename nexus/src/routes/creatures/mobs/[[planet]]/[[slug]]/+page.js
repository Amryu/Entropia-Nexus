// @ts-nocheck
let items;
let itemsGrouped;

import { handlePageLoad, getMainPlanetName, apiCall } from '$lib/util';

export async function load({ fetch, params }) {
  const config = {
    items: 'mobs',
    types: { tierable: false },
  }

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config, params.slug, params.type, false));

  itemsGrouped = {
    calypso: [],
    arkadia: [],
    cyrene: [],
    rocktropia: [],
    nextisland: [],
    toulan: [],
    monria: [],
    space: [],
  }

  items.forEach(element => {
    let planet = getMainPlanetName(element.Planet.Name).replace(/[^0-9a-zA-Z]/, '').toLowerCase();
    itemsGrouped[planet].push(element);
  });

  response.items = itemsGrouped;
  
  const [species, maturities, loots] = await Promise.all([
    response.object?.Species != null ? apiCall(fetch, response.object.Species.Links.$Url) : Promise.resolve(null),
    apiCall(fetch, `/mobmaturities?Mob=${encodeURIComponent(params.slug)}`),
    apiCall(fetch, `/mobloots?Mob=${encodeURIComponent(params.slug)}`)
  ]);

  response.object.Species = species;
  response.object.Maturities = maturities;

  response.additional.loots = loots;

  return response;
}