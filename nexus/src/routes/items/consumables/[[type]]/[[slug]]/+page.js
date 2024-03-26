// @ts-nocheck
let items;

import { handlePageLoad } from '$lib/util';

export async function load({ fetch, params }) {
  const config = {
    items: ['consumables', 'creaturecontrolcapsules'],
    types: [
      { type: 'consumables' },
      { type: 'creaturecontrolcapsules' }
    ]
  }

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config, params.slug, params.type));

  return response;
}