// @ts-nocheck
import { pageResponse } from '$lib/util';

export async function load({ params, url }) {
  const addBlueprint = url.searchParams.get('addBlueprint') || null;
  // Blueprint data will be lazy loaded on client for faster initial page load
  return pageResponse(null, null, {
    planId: params.planId || null,
    addBlueprint: addBlueprint ? parseInt(addBlueprint) : null
  });
}
