// @ts-nocheck
let items;

import { handlePageLoad } from '$lib/util';

export async function load({ fetch, params }) {
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
    ]
  }

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config, params.slug, params.type));

  return response;
}