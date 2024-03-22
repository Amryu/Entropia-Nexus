// @ts-nocheck
let items;

import { apiCall, getAcquisitionInfo, pageResponse } from '$lib/util';

export async function load({ fetch, params }) {
  if (!items) {
    items = await apiCall(fetch, '/clothes');
  }

  if (!params.slug) {
    return pageResponse(items);
  }

  let clothing = await apiCall(fetch, `/clothes/${encodeURIComponent(params.slug)}`);

  if (clothing === null) {
    return pageResponse(items, null, null, 404);
  }

  return pageResponse(
    items,
    clothing,
    {
      acquisition: await getAcquisitionInfo(fetch, clothing?.Name)
    }
  );
}