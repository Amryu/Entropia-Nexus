// @ts-nocheck
let items;

import { apiCall, getAcquisitionInfo, pageResponse } from '$lib/util';

export async function load({ fetch, params }) {
  if (!items) {
    items = await apiCall(fetch, '/armorsets');
  }

  if (!params.slug) {
    return pageResponse(items);
  }

  let armorSet = await apiCall(fetch, `/armorsets/${encodeURIComponent(params.slug)}`);

  if (armorSet == null) {
    return pageResponse(items, null, null, 404);
  }

  let tierInfo = await apiCall(fetch, `/tiers?ItemId=${armorSet.Id}&IsArmorSet=1`);

  let armorPieceNameList = armorSet.Armors.map(armor => armor.Name.includes(',') ? `"${armor.Name}"` : armor.Name).join(',');

  return pageResponse(
    items,
    armorSet,
    {
      tierInfo,
      acquisition: await getAcquisitionInfo(fetch, armorPieceNameList)
    }
  );
}