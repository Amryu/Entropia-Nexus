// @ts-nocheck
let items;

import { decodeURIComponentSafe, handlePageLoad, apiCall } from '$lib/util';

export async function load({ fetch, params, url }) {
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

  return response;
}