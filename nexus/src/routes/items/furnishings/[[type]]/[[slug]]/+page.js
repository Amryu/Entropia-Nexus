// @ts-nocheck
let items;

import { apiCall, getAcquisitionInfo, pageResponse } from '$lib/util';

export async function load({ fetch, params }) {
  if (!items) {
    items = {
      furniture: await apiCall(fetch, '/furniture'),
      decorations: await apiCall(fetch, '/decorations'),
      storagecontainers: await apiCall(fetch, '/storagecontainers'),
      signs: await apiCall(fetch, '/signs'),
    };
  }

  if (!params.type || !params.slug) {
    return pageResponse(items);
  }

  let object = null;

  if (params.type === 'furniture') {
    object = await apiCall(fetch, `/furniture/${encodeURIComponent(params.slug)}`);
  }
  else if (params.type === 'decorations') {
    object = await apiCall(fetch, `/decorations/${encodeURIComponent(params.slug)}`);
  }
  else if (params.type === 'storagecontainers') {
    object = await apiCall(fetch, `/storagecontainers/${encodeURIComponent(params.slug)}`);
  }
  else if (params.type === 'signs') {
    object = await apiCall(fetch, `/signs/${encodeURIComponent(params.slug)}`);
  }

  if (object === null) {
    return pageResponse(items, null, null, 404);
  }

  return pageResponse(
    items,
    object, 
    { 
      type: params.type,
      acquisition: await getAcquisitionInfo(fetch, object?.Name)
    }
  );
}