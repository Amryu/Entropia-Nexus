// @ts-nocheck
import { apiCall, pageResponse } from '$lib/util';

/**
 * Load armor sets, platings and mobs once for the Gear Advisor tools.
 * Lists are a few-hundred entries each; they're cached by the API layer
 * so reusing this loader across sub-tools is cheap.
 */
export async function load({ fetch, params }) {
  const tool = params.tool || 'armor-vs-mob';

  const [armorSets, armorPlatings, mobs] = await Promise.all([
    apiCall(fetch, '/armorsets').catch(() => []),
    apiCall(fetch, '/armorplatings').catch(() => []),
    apiCall(fetch, '/mobs').catch(() => [])
  ]);

  return pageResponse(null, null, {
    tool,
    armorSets: Array.isArray(armorSets) ? armorSets : [],
    armorPlatings: Array.isArray(armorPlatings) ? armorPlatings : [],
    mobs: Array.isArray(mobs) ? mobs : []
  });
}
