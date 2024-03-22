// @ts-nocheck
let items;

import { apiCall, getAcquisitionInfo, pageResponse } from '$lib/util';

export async function load({ fetch, params }) {
  if (!items) {
    items = {
      consumables: await apiCall(fetch, '/consumables'),
      creaturecontrolcapsules: await apiCall(fetch, '/creaturecontrolcapsules'),
    }
  }

  if (!params.type || !params.slug) {
    return pageResponse(items);
  }

  let object = null;

  if (params.type === 'consumables') {
    object = await apiCall(fetch, `/consumables/${encodeURIComponent(params.slug)}`);
  }
  else if (params.type === 'creaturecontrolcapsules'){
    object = await apiCall(fetch, `/creaturecontrolcapsules/${encodeURIComponent(params.slug)}`);
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