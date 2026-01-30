// @ts-nocheck
let items;

import { decodeURIComponentSafe, handlePageLoad } from '$lib/util';

export async function load({ fetch, params, url }) {
  const config = {
    items: ['medicaltools', 'medicalchips'],
    types: [
      { type: 'tools', tierable: true },
      { type: 'chips', tierable: false }
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
