// @ts-nocheck
let items;

import { decodeURIComponentSafe, handlePageLoad } from '$lib/util';

export async function load({ fetch, params, parent }) {
  const parentData = await parent();

  const config = {
    items: 'enumerations',
    types: { tierable: false },
    name: params.slug ? decodeURIComponentSafe(params.slug) : null,
    type: null,
    mode: 'view',
    isItem: false
  };

  let response;
  ({ items, response } = await handlePageLoad(fetch, items, config));

  response.allItems = items;
  response.session = parentData.session;
  response.isCreateMode = false;

  return response;
}
