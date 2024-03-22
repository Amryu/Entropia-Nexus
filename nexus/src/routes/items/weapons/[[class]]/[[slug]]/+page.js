// @ts-nocheck
let items;

import { redirect } from '@sveltejs/kit';
import { apiCall, getAcquisitionInfo, pageResponse } from '$lib/util';

export async function load({ fetch, params }) {
  if (!items) {
    let weapons = await apiCall(fetch, '/weapons');

    items = {
      ranged: weapons.filter(w => w.Properties.Class === 'Ranged'),
      melee: weapons.filter(w => w.Properties.Class === 'Melee'),
      mindforce: weapons.filter(w => w.Properties.Class === 'Mindforce'),
      attached: weapons.filter(w => w.Properties.Class === 'Attached'),
    }
  }

  if (!params.class && !params.slug) {
    return pageResponse(items);
  }

  // If the site is only called with the weapons name, try to redirect to the correct URL
  if (params.class && !params.slug) {
    let weapon = await apiCall(fetch, `/weapons/${encodeURIComponent(params.class)}`);

    if (!weapon) {
      redirect(301, `/items/weapons`);
    }
    else {
      redirect(301, `/items/weapons/${encodeURIComponent(weapon.Properties.Class).toLowerCase()}/${encodeURIComponent(weapon.Name)}`);
    }
  }

  let weapon = await apiCall(fetch, `/weapons/${encodeURIComponent(params.slug)}`);
  let tierInfo = await apiCall(fetch, `/tiers?ItemId=${weapon.ItemId}&IsArmorSet=0`);

  if (weapon == null) {
    return pageResponse(items, null, null, 404);
  }

  return pageResponse(
    items,
    weapon,
    {
      tierInfo,
      class: params.class,
      acquisition: await getAcquisitionInfo(fetch, weapon?.Name)
    }
  );
}