// @ts-nocheck
let items;
let itemsGrouped;

import { decodeURIComponentSafe, getMainPlanetName, handlePageLoad, resolveItemLink } from '$lib/util';

export async function load({ fetch, params, url }) {
  const config = {
    items: 'vendors',
    types: { tierable: false },
    name: decodeURIComponentSafe(params.slug),
    type: null,
    mode: url.searchParams.get('mode') || 'view',
    searchParams: url.searchParams
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
    monria: [],
    space: [],
  }

  items.forEach(element => {
    if (element.Planet == null || element.Planet.Name == null) return;

    let planet = getMainPlanetName(element.Planet.Name).replace(/[^0-9a-zA-Z]/g, '').toLowerCase();
    itemsGrouped[planet].push(element);
  });

  response.items = itemsGrouped;

  if (response.object != null) {
    response.object.Offers = await Promise.all(response.object.Offers.map(async offer => {
      offer.Item.Links.$ItemUrl = await resolveItemLink(fetch, offer.Item);

      return offer;
    }));
  }

  return response;
}