// @ts-nocheck
let items;

import { apiCall, getAcquisitionInfo, pageResponse } from '$lib/util';

export async function load({ fetch, params }) {
  if (!items) {
    items = await apiCall(fetch, '/materials');
  }

  if (!params.slug) {
    return pageResponse(items);
  }

  let material = await apiCall(fetch, `/materials/${encodeURIComponent(params.slug)}`);

  if (material === null) {
    return pageResponse(items, null, null, 404);
  }

  return pageResponse(
    items,
    material, 
    { 
      acquisition: await getAcquisitionInfo(fetch, material.Name)
    }
  );
}