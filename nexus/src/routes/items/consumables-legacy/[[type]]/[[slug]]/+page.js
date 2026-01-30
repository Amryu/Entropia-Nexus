// @ts-nocheck
let items;

import { decodeURIComponentSafe, encodeURIComponentSafe, handlePageLoad } from '$lib/util';
import { redirect } from '@sveltejs/kit';

export async function load({ fetch, params, url }) {
  if (params.type === 'consumables') {
    redirect(301, `/items/consumables/stimulants/${encodeURIComponentSafe(params.slug)}`);
  }
  else if (params.type === 'creaturecontrolcapsules') {
    redirect(301, `/items/consumables/capsules/${encodeURIComponentSafe(params.slug)}`);
  }

  const config = {
    items: ['stimulants', 'capsules'],
    types: [
      { type: 'stimulants' },
      { type: 'capsules' }
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