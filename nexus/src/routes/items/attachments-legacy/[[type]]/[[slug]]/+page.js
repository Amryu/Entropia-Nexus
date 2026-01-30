// @ts-nocheck
let items;

import { decodeURIComponentSafe, handlePageLoad } from '$lib/util';

export async function load({ fetch, params, url }) {
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
    ],
    name: decodeURIComponentSafe(params.slug),
    type: decodeURIComponentSafe(params.type),
    mode: url.searchParams.get('mode') || 'view',
    searchParams: url.searchParams
  }

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config));

  return response;
}
