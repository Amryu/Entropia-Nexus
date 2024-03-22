// @ts-nocheck
let items;

import { apiCall, getAcquisitionInfo, pageResponse } from '$lib/util';

export async function load({ fetch, params }) {
  if (!items) {
    items = {
      weaponamplifiers: await apiCall(fetch, '/weaponamplifiers'),
      weaponvisionattachments: await apiCall(fetch, '/weaponvisionattachments'),
      absorbers: await apiCall(fetch, '/absorbers'),
      finderamplifiers: await apiCall(fetch, '/finderamplifiers'),
      armorplatings: await apiCall(fetch, '/armorplatings'),
      enhancers: await apiCall(fetch, '/enhancers'),
      mindforceimplants: await apiCall(fetch, '/mindforceimplants'),
    };
  }

  if (!params.type || !params.slug) {
    return pageResponse(items);
  }

  let object = null;

  let slug = encodeURIComponent(params.slug);

  if (params.type === 'weaponamplifiers') {
    object = await apiCall(fetch, `/weaponamplifiers/${slug}`);
  }
  else if (params.type === 'weaponvisionattachments') {
    object = await apiCall(fetch, `/weaponvisionattachments/${slug}`);
  }
  else if (params.type === 'absorbers') {
    object = await apiCall(fetch, `/absorbers/${slug}`);
  }
  else if (params.type === 'finderamplifiers') {
    object = await apiCall(fetch, `/finderamplifiers/${slug}`);
  }
  else if (params.type === 'armorplatings') {
    object = await apiCall(fetch, `/armorplatings/${slug}`);
  }
  else if (params.type === 'enhancers') {
    object = await apiCall(fetch, `/enhancers/${slug}`);
  }
  else if (params.type === 'mindforceimplants') {
    object = await apiCall(fetch, `/mindforceimplants/${slug}`);
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