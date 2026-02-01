// @ts-nocheck
let items;
let itemsGrouped;

import { handlePageLoad, decodeURIComponentSafe, encodeURIComponentSafe } from '$lib/util';

export async function load({ fetch, params, url }) {
  const config = {
    items: 'shops',
    types: { tierable: false },
    name: decodeURIComponentSafe(params.slug),
    type: null,
    mode: url.searchParams.get('mode') || 'view',
    searchParams: url.searchParams,
    isItem: false
  }

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config));

  console.log('DEBUG: Initial response from handlePageLoad:', response);

  // Group shops by planet for filtering
  itemsGrouped = {
    calypso: [],
    aris: [],
    arkadia: [],
    cyrene: [],
    monria: [],
    rocktropia: [],
    toulan: [],
    nextisland: [],
  };

  if (items) {
    for (let shop of items) {
      let planetName = shop.Planet?.Properties?.TechnicalName;
      if (planetName && itemsGrouped[planetName]) {
        itemsGrouped[planetName].push(shop);
      }
    }
  }

  if (response && (response.object || response.items)) {
    response.itemsGrouped = itemsGrouped;
  }

  console.log('DEBUG: Final response:', response);

  return response;
}
