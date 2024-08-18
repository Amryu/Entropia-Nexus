// @ts-nocheck
let items;

import { decodeURIComponentSafe, handlePageLoad } from '$lib/util';

export async function load({ fetch, params, url }) {
  const config = {
    items: ['refiners', 'scanners', 'finders', 'excavators', 'teleportationchips', 'effectchips', 'misctools'],
    types: [
      { type: 'refiners', tierable: false },
      { type: 'scanners', tierable: false },
      { type: 'finders', tierable: true },
      { type: 'excavators', tierable: true },
      { type: 'teleportationchips', tierable: false },
      { type: 'effectchips', tierable: false },
      { type: 'misctools', tierable: false }
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