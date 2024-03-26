// @ts-nocheck
let items;

import { handlePageLoad } from '$lib/util';

export async function load({ fetch, params }) {
  const config = {
    items: ['weaponamplifiers', 'weaponvisionattachments', 'absorbers', 'finderamplifiers', 'armorplatings', 'enhancers', 'mindforceimplants'],
    types: [
      { type: 'weaponamplifiers' },
      { type: 'weaponvisionattachments' },
      { type: 'absorbers' },
      { type: 'finderamplifiers' },
      { type: 'armorplatings' },
      { type: 'enhancers' },
      { type: 'mindforceimplants' }
    ]
  }

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config, params.slug, params.type));

  return response;
}