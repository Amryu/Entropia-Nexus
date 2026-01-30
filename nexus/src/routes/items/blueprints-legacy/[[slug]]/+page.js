// @ts-nocheck
let items;

import { decodeURIComponentSafe, handlePageLoad, resolveItemLink } from '$lib/util';

export async function load({ fetch, params, url }) {
  const config = {
    items: 'blueprints',
    types: { tierable: false },
    name: decodeURIComponentSafe(params.slug),
    type: null,
    mode: url.searchParams.get('mode') || 'view',
    searchParams: url.searchParams
  }

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config));

  if (response?.object?.Product != null) {
    response.object.Product.Links.$ItemUrl = await resolveItemLink(fetch, response.object.Product);
  }

  return response;
}