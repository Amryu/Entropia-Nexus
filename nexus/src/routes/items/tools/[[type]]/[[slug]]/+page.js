// @ts-nocheck
let items;

import { apiCall, getAcquisitionInfo, pageResponse } from '$lib/util';

export async function load({ fetch, params }) {
  if (!items) {
    items = {
      refiners: await apiCall(fetch, '/refiners'),
      scanners: await apiCall(fetch, '/scanners'),
      finders: await apiCall(fetch, '/finders'),
      excavators: await apiCall(fetch, '/excavators'),
      teleportationchips: await apiCall(fetch, '/teleportationchips'),
      effectchips: await apiCall(fetch, '/effectchips'),
      misctools: await apiCall(fetch, '/misctools'),
    };
  }

  if (!params.type || !params.slug) {
    return pageResponse(items);
  }

  let object = null;
  let tierInfo = null;

  let slug = encodeURIComponent(params.slug);

  if (params.type === 'refiners') {
    object = await apiCall(fetch, `/refiners/${slug}`);
  }
  else if (params.type === 'scanners'){
    object = await apiCall(fetch, `/scanners/${slug}`);
  }
  else if (params.type === 'finders'){
    object = await apiCall(fetch, `/finders/${slug}`);
    tierInfo = await apiCall(fetch, `/tiers?ItemId=${object.ItemId}&IsArmorSet=0`);
  }
  else if (params.type === 'excavators'){
    object = await apiCall(fetch, `/excavators/${slug}`);
    tierInfo = await apiCall(fetch, `/tiers?ItemId=${object.ItemId}&IsArmorSet=0`);
  }
  else if (params.type === 'teleportationchips'){
    object = await apiCall(fetch, `/teleportationchips/${slug}`);
  }
  else if (params.type === 'effectchips'){
    object = await apiCall(fetch, `/effectchips/${slug}`);
  }
  else if (params.type === 'misctools'){
    object = await apiCall(fetch, `/misctools/${slug}`);
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