// @ts-nocheck
let items;
let itemsGrouped;

import { redirect } from '@sveltejs/kit';
import { handlePageLoad, apiCall } from '$lib/util';

export async function load({ fetch, params }) {
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

  const config = {
    items: 'weapons',
    types: { tierable: true },
  }

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config, params.slug, params.type));

  itemsGrouped = {
    ranged: [],
    melee: [],
    mindforce: [],
    attached: [],
  }

  items.forEach(element => {
    if (element.Properties.Class === 'Ranged') itemsGrouped.ranged.push(element);
    if (element.Properties.Class === 'Melee') itemsGrouped.melee.push(element);
    if (element.Properties.Class === 'Mindforce') itemsGrouped.mindforce.push(element);
    if (element.Properties.Class === 'Attached') itemsGrouped.attached.push(element);
  });

  response.items = itemsGrouped;

  return response;
}