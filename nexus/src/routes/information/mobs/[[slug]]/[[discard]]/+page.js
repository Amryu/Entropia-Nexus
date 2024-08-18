// @ts-nocheck
let items;
let itemsGrouped;

import { handlePageLoad, getMainPlanetName, apiCall, resolveItemLink, decodeURIComponentSafe, encodeURIComponentSafe } from '$lib/util';
import { redirect } from '@sveltejs/kit';

export async function load({ fetch, params, url }) {
  if (params.discard) {
    redirect(301, `/information/mobs/${encodeURIComponentSafe(params.discard)}`);
  }

  const config = {
    items: 'mobs',
    types: { tierable: false },
    name: decodeURIComponentSafe(params.slug),
    type: null,
    mode: url.searchParams.get('mode') || 'view',
    searchParams: url.searchParams,
    isItem: false
  }

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config));

  itemsGrouped = {
    calypso: [],
    arkadia: [],
    cyrene: [],
    rocktropia: [],
    nextisland: [],
    toulan: [],
    monria: []
  }

  items.forEach(element => {
    if (element.Planet == null || element.Planet.Name == null) return;

    let planet = getMainPlanetName(element.Planet.Name).replace(/[^0-9a-zA-Z]/g, '').toLowerCase();
    itemsGrouped[planet].push(element);
  });

  response.items = itemsGrouped;
  
  if (response.object) {
    let slug = decodeURIComponentSafe(params.slug);

    let [species, maturities, loots, mobSpawns] = await Promise.all([
      response.object?.Species != null && response.object?.Species.Name != null ? apiCall(fetch, response.object.Species.Links.$Url) : Promise.resolve({ Name: null }),
      apiCall(fetch, `/mobmaturities?Mob=${encodeURIComponent(slug)}`),
      apiCall(fetch, `/mobloots?Mob=${encodeURIComponent(slug)}`),
      apiCall(fetch, `/mobspawns?Mob=${encodeURIComponent(slug)}`)
    ]);

    await Promise.all(loots.map(async (x) => {
      x.Item.Links.$ItemUrl = await resolveItemLink(fetch, x.Item);
    }));

    response.object.Species = species;
    response.object.Maturities = maturities;
  
    response.additional.loots = loots;
    response.additional.mobSpawns = mobSpawns;
  }

  return response;
}