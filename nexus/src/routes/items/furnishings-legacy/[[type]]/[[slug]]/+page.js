// @ts-nocheck
let items;

import { decodeURIComponentSafe, handlePageLoad } from '$lib/util';

export async function load({ fetch, params, url }) {
  const config = {
    items: ['furniture', 'decorations', 'storagecontainers', 'signs'],
    types: [
      { type: 'furniture' },
      { type: 'decorations' },
      { type: 'storagecontainers' },
      { type: 'signs' }
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