// @ts-nocheck
/**
 * Armor Set wiki pages
 * Uses new WikiPage layout pattern.
 */
let items;

import { redirect } from '@sveltejs/kit';
import { decodeURIComponentSafe, handlePageLoad, encodeURIComponentSafe } from '$lib/util';

export async function load({ fetch, params, url }) {
  if (url.searchParams.get('mode') === 'view') {
    redirect(301, `/items/armorsets/${encodeURIComponentSafe(params.slug)}`);
  }

  const config = {
    items: 'armorsets',
    types: { tierable: true },
    name: decodeURIComponentSafe(params.slug),
    type: null,
    mode: url.searchParams.get('mode') || 'view',
    searchParams: url.searchParams,
    isArmorSet: true
  }

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config));

  // Provide allItems for navigation
  response.allItems = items;

  return response;
}
