// @ts-nocheck
let items;

import { apiCall, getAcquisitionInfo, pageResponse } from '$lib/util';

export async function load({ fetch, params }) {
  if (!items) {
    items = await apiCall(fetch, '/vehicles');
  }

  if (!params.slug) {
    return pageResponse(items);
  }

  let vehicle = await apiCall(fetch, `/vehicles/${encodeURIComponent(params.slug)}`);

  if (vehicle === null) {
    return pageResponse(items, null, null, 404);
  }

  return pageResponse(
    items,
    vehicle, 
    { 
      acquisition: await getAcquisitionInfo(fetch, vehicle?.Name)
    }
  );
}