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
    aris: [],
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
    // Batch resolve item links to reduce API calls
    const armorItems = response.object.Loots
      .filter(x => x.Item.Properties.Type === 'Armor' && !x.Item.Set)
      .map(x => x.Item);
    
    // If we have armor items without set info, fetch them in batch
    if (armorItems.length > 0) {
      const armorPromises = armorItems.map(async (item) => {
        const armor = await apiCall(fetch, item.Links.$Url);
        if (armor != null) {
          item.Set = armor.Set;
        }
        return item;
      });
      
      await Promise.all(armorPromises);
    }
    
    // Now resolve all item links (many will be cached/direct)
    await Promise.all(response.object.Loots.map(async (x) => {
      x.Item.Links.$ItemUrl = await resolveItemLink(fetch, x.Item);
    }));
  }

  return response;
}