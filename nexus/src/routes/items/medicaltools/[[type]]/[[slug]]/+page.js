// @ts-nocheck
let items;

import { apiCall, getAcquisitionInfo, pageResponse } from '$lib/util';

export async function load({ fetch, params }) {
  if (!items) {
    items = {
      tools: await apiCall(fetch, '/medicaltools'),
      chips: await apiCall(fetch, '/medicalchips'),
    }
  }

  if (!params.type || !params.slug) {
    return pageResponse(items);
  }

  let object = null;
  let tierInfo = null;

  if (params.type === 'tools') {
    object = await apiCall(fetch, `/medicaltools/${encodeURIComponent(params.slug)}`);
    tierInfo = await apiCall(fetch, `/tiers?ItemId=${object.ItemId}&IsArmorSet=0`);
  }
  else if (params.type === 'chips'){
    object = await apiCall(fetch, `/medicalchips/${encodeURIComponent(params.slug)}`);
  }

  if (object === null) {
    return pageResponse(items, null, null, 404);
  }

  return pageResponse(
    items,
    object,
    {
      type: params.type,
      tierInfo,
      acquisition: await getAcquisitionInfo(fetch, object?.Name)
    }
  );
}