// @ts-nocheck
let items;

import { decodeURIComponentSafe, handlePageLoad } from '$lib/util.js';

export async function load({ fetch, params, url }) {
  const config = {
    items: 'pets',
    types: { tierable: false },
    name: decodeURIComponentSafe(params.slug),
    type: null,
    mode: url.searchParams.get('mode') || 'view',
    searchParams: url.searchParams
  }

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config));

  return response;
}