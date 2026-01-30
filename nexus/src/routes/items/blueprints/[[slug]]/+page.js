// @ts-nocheck
/**
 * Blueprint wiki pages
 * Uses new WikiPage layout pattern.
 */
let items;

import { redirect } from '@sveltejs/kit';
import { decodeURIComponentSafe, handlePageLoad, resolveItemLink, encodeURIComponentSafe } from '$lib/util';

export async function load({ fetch, params, url }) {
  if (url.searchParams.get('mode') === 'view') {
    redirect(301, `/items/blueprints/${encodeURIComponentSafe(params.slug)}`);
  }

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
    response.object.Product.Links = response.object.Product.Links || {};
    response.object.Product.Links.$ItemUrl = await resolveItemLink(fetch, response.object.Product);
  }

  // Provide allItems for navigation
  response.allItems = items;

  return response;
}
