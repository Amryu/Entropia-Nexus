// @ts-nocheck
import { apiCall, pageResponse } from '$lib/util.js';

let items;

export async function load({ fetch, params }) {
  if (!items) {
    items = await apiCall(fetch, '/pets');
  }

  if (!params.slug) {
    return pageResponse(items);
  }

  let pet = await apiCall(fetch, `/pets/${encodeURIComponent(params.slug)}`);

  if (pet === null) {
    return pageResponse(items, null, null, 404);
  }

  return pageResponse(
    items,
    pet,
  );
}