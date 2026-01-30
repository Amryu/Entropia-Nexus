// @ts-nocheck
/**
 * Layout A: Wikipedia-style weapon pages
 * Classic wiki layout with floating infobox on the right.
 */
let items;
let itemsGrouped;

import { redirect } from '@sveltejs/kit';
import { handlePageLoad, encodeURIComponentSafe, decodeURIComponentSafe } from '$lib/util';

export async function load({ fetch, params, url }) {
  if (url.searchParams.get('mode') === 'view') {
    redirect(301, `/items/weapons-a/${encodeURIComponentSafe(params.slug)}`);
  }

  const config = {
    items: 'weapons',
    types: { tierable: true },
    name: decodeURIComponentSafe(params.slug),
    type: null,
    mode: url.searchParams.get('mode') || 'view',
    searchParams: url.searchParams
  }

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config));

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
  response.allItems = items;
  response.layoutVariant = 'A';

  return response;
}
