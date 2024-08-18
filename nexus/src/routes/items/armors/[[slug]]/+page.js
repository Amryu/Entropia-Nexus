// @ts-nocheck
import { apiCall, decodeURIComponentSafe } from '$lib/util.js';
import { redirect } from '@sveltejs/kit';

export async function load({ fetch, params }) {
  let armor = await apiCall(fetch, `/armors/${encodeURIComponent(decodeURIComponentSafe(params.slug))}`);
  
  if (!armor.Name) {
    redirect(301, `/items/armorsets`);
  }
  else {
    redirect(301, `/items/armorsets/${encodeURIComponent(armor.Set.Name)}`);
  }
}