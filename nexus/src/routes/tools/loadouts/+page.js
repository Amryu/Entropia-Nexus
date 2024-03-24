// @ts-nocheck
import { apiCall, pageResponse } from '$lib/util';

export async function load({ fetch }) {
  const [weapons, weaponamplifiers, weaponvisionattachments, absorbers, mindforceimplants, armorsets, armors, armorplatings, enhancers, pets, clothing, consumables] = await Promise.all([
    apiCall(fetch, `/weapons`),
    apiCall(fetch, `/weaponamplifiers`),
    apiCall(fetch, `/weaponvisionattachments`),
    apiCall(fetch, `/absorbers`),
    apiCall(fetch, `/mindforceimplants`),
    apiCall(fetch, `/armorsets`),
    apiCall(fetch, `/armors`),
    apiCall(fetch, `/armorplatings`),
    apiCall(fetch, `/enhancers`),
    apiCall(fetch, `/pets`),
    apiCall(fetch, `/clothes`),
    apiCall(fetch, `/consumables`)
  ]);

  return pageResponse(
    null,
    null,
    {
      weapons,
      weaponamplifiers,
      weaponvisionattachments,
      absorbers,
      mindforceimplants,
      armorsets,
      armors,
      armorplatings,
      enhancers,
      clothing,
      pets,
      consumables
    }
  );
}