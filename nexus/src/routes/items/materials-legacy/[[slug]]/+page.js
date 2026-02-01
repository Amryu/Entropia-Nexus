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

  // Ensure refining recipes are present on the material object (view + edit)
  if (response.object && response.additional?.acquisition?.RefiningRecipes) {
    if (!response.object.RefiningRecipes || response.object.RefiningRecipes.length === 0) {
      response.object.RefiningRecipes = response.additional.acquisition.RefiningRecipes;
    }
  }

  return response;
}
