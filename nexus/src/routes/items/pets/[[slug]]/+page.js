// @ts-nocheck
let items;

import { handlePageLoad } from '$lib/util.js';

export async function load({ fetch, params }) {
  const config = {
    items: 'pets',
    types: { tierable: false }
  }

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config, params.slug, params.type));

  return response;
}