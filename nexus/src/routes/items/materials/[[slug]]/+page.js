// @ts-nocheck
/**
 * Material wiki pages
 * Uses new WikiPage layout pattern.
 */
let items;

import { redirect } from '@sveltejs/kit';
import { handlePageLoad, encodeURIComponentSafe, decodeURIComponentSafe } from '$lib/util';

export async function load({ fetch, params, url }) {
  if (url.searchParams.get('mode') === 'view') {
    redirect(301, `/items/materials/${encodeURIComponentSafe(params.slug)}`);
  }

  const config = {
    items: 'materials',
    types: { tierable: false },
    name: decodeURIComponentSafe(params.slug),
    type: null,
    mode: url.searchParams.get('mode') || 'view',
    searchParams: url.searchParams
  }

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config));

  // Add RefiningRecipes to the material object structure for edit mode
  if (response.object && config.mode === 'edit' && response.additional?.acquisition?.RefiningRecipes) {
    response.object.RefiningRecipes = response.additional.acquisition.RefiningRecipes;
  }

  // Provide allItems for navigation
  response.allItems = items;

  return response;
}
