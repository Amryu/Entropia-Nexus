// @ts-nocheck
let items;

import { handlePageLoad } from '$lib/util';

export async function load({ fetch, params }) {
  const config = {
    items: ['furniture', 'decorations', 'storagecontainers', 'signs'],
    types: [
      { type: 'furniture' },
      { type: 'decorations' },
      { type: 'storagecontainers' },
      { type: 'signs' }
    ]
  }

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config, params.slug, params.type));

  return response;
}