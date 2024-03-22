// @ts-nocheck
let items;

import { apiCall, getAcquisitionInfo, pageResponse } from '$lib/util';

export async function load({ fetch, params }) {
  if (!items) {
    items = await apiCall(fetch, '/blueprints');
  }

  if (!params.slug) {
    return pageResponse(items);
  }

  let blueprint = await apiCall(fetch, `/blueprints/${encodeURIComponent(params.slug)}`);

  if (blueprint === null) {
    return pageResponse(items, null, null, 404);
  }

  return pageResponse(
    items,
    blueprint, 
    { 
      acquisition: await getAcquisitionInfo(fetch, blueprint?.Name)
    }
  );
}