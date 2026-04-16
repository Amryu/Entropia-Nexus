// @ts-nocheck
import { apiCall, pageResponse } from '$lib/util';

/**
 * Load entity data for all Gear Advisor tools.
 * Lists are a few-hundred entries each; they're cached by the API layer
 * so reusing this loader across sub-tools is cheap.
 */
export async function load({ fetch, params }) {
  const tool = params.tool || 'armor-vs-mob';

  const [
    armorSets, armorPlatings, mobs,
    weapons, weaponAmplifiers, weaponVisionAttachments, absorbers, mindforceImplants,
    clothings, pets, effects,
    fishingRods, fishingReels, fishingBlanks, fishingLines, fishingLures
  ] = await Promise.all([
    apiCall(fetch, '/armorsets').catch(() => []),
    apiCall(fetch, '/armorplatings').catch(() => []),
    apiCall(fetch, '/mobs').catch(() => []),
    apiCall(fetch, '/weapons').catch(() => []),
    apiCall(fetch, '/weaponamplifiers').catch(() => []),
    apiCall(fetch, '/weaponvisionattachments').catch(() => []),
    apiCall(fetch, '/absorbers').catch(() => []),
    apiCall(fetch, '/mindforceimplants').catch(() => []),
    apiCall(fetch, '/clothings').catch(() => []),
    apiCall(fetch, '/pets').catch(() => []),
    apiCall(fetch, '/effects').catch(() => []),
    apiCall(fetch, '/fishingrods').catch(() => []),
    apiCall(fetch, '/fishingreels').catch(() => []),
    apiCall(fetch, '/fishingblanks').catch(() => []),
    apiCall(fetch, '/fishinglines').catch(() => []),
    apiCall(fetch, '/fishinglures').catch(() => [])
  ]);

  const ensureArray = v => Array.isArray(v) ? v : [];

  return pageResponse(null, null, {
    tool,
    armorSets: ensureArray(armorSets),
    armorPlatings: ensureArray(armorPlatings),
    mobs: ensureArray(mobs),
    weapons: ensureArray(weapons),
    weaponAmplifiers: ensureArray(weaponAmplifiers),
    weaponVisionAttachments: ensureArray(weaponVisionAttachments),
    absorbers: ensureArray(absorbers),
    mindforceImplants: ensureArray(mindforceImplants),
    clothings: ensureArray(clothings),
    pets: ensureArray(pets),
    effects: ensureArray(effects),
    fishingRods: ensureArray(fishingRods),
    fishingReels: ensureArray(fishingReels),
    fishingBlanks: ensureArray(fishingBlanks),
    fishingLines: ensureArray(fishingLines),
    fishingLures: ensureArray(fishingLures)
  });
}
