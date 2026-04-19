// @ts-nocheck
/**
 * Mobs Wiki Page Loader
 * Wikipedia-style layout with floating infobox on the right.
 */
let items;
let itemsGrouped;
let cachedSkills;

import { handlePageLoad, getMainPlanetName, apiCall, resolveItemLink, decodeURIComponentSafe, loadPendingChangesData } from '$lib/util';

export async function load({ fetch, params, url, parent }) {
  const view = url.searchParams.get('view') === 'maturities' ? 'maturities' : 'mobs';
  const selectedMaturityRaw = url.searchParams.get('maturity');
  const selectedMaturityId = selectedMaturityRaw && /^\d+$/.test(selectedMaturityRaw)
    ? Number(selectedMaturityRaw)
    : null;

  const config = {
    items: 'mobs',
    types: { tierable: false },
    name: url.searchParams.get('mode') === 'create' ? null : decodeURIComponentSafe(params.slug),
    type: null,
    mode: url.searchParams.get('mode') || 'view',
    searchParams: url.searchParams,
    isItem: false
  }

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config));

  // Group mobs by planet for navigation
  itemsGrouped = {
    calypso: [],
    aris: [],
    arkadia: [],
    cyrene: [],
    rocktropia: [],
    nextisland: [],
    toulan: [],
    monria: [],
    space: []
  }

  items.forEach(element => {
    if (element.Planet == null || element.Planet.Name == null) return;

    let planet = getMainPlanetName(element.Planet.Name).replace(/[^0-9a-zA-Z]/g, '').toLowerCase();
    if (itemsGrouped[planet]) {
      itemsGrouped[planet].push(element);
    }
  });

  response.items = itemsGrouped;
  response.allItems = items;
  response.isCreateMode = config.mode === 'create';
  response.view = view;
  response.selectedMaturityId = selectedMaturityId;

  const changeId = url.searchParams.get('changeId');
  if (changeId && response.isCreateMode) {
    try {
      const changeRes = await fetch(`/api/changes/${changeId}`);
      if (changeRes.ok) {
        const change = await changeRes.json();
        response.existingChange = change;
        response.pendingChange = change;
      }
    } catch (e) {
      console.warn('Failed to fetch existing change:', e);
    }
  }

  const parentData = await parent();
  response.session = parentData.session;

  const userGrants = parentData.session?.user?.grants || [];
  const hasEditGrant = userGrants.some(g => g.startsWith('wiki.'));

  const pendingData = await loadPendingChangesData(fetch, parentData.session?.user, {
    entity: 'Mob',
    entityId: response.object?.Id,
    changeId,
    isAdmin: userGrants.includes('wiki.approve'),
    hasEditGrant
  });

  response.pendingChange = pendingData.pendingChange;
  response.userPendingCreates = pendingData.userPendingCreates;
  response.userPendingUpdates = pendingData.userPendingUpdates;
  response.canCreateNew = pendingData.canCreateNew;
  response.pendingCreatesCount = pendingData.pendingCreatesCount;

  // Skills always loaded (codex calculator needs them in view mode), cached at module level
  if (!cachedSkills) {
    cachedSkills = await apiCall(fetch, '/skills').catch(() => []) || [];
  }
  response.skillsList = cachedSkills;

  // Other edit deps only loaded server-side in create mode, otherwise lazy-loaded client-side
  if (config.mode === 'create') {
    const [speciesData, itemsData, planetsData] = await Promise.all([
      apiCall(fetch, '/mobspecies').catch(() => []),
      apiCall(fetch, '/items?limit=5000').catch(() => []),
      apiCall(fetch, '/planets').catch(() => [])
    ]);
    response.speciesList = speciesData || [];
    response.itemsList = itemsData || [];
    response.planetsList = planetsData || [];
  } else {
    response.speciesList = null;
    response.itemsList = null;
    response.planetsList = null;
  }

  // If we have a specific mob, resolve item links for loots
  if (response.object) {
    // Batch resolve item links to reduce API calls
    const armorItems = response.object.Loots
      .filter(x => x?.Item?.Properties?.Type === 'Armor' && !x.Item.Set)
      .map(x => x.Item);

    // If we have armor items without set info, fetch them in batch
    if (armorItems.length > 0) {
      const armorPromises = armorItems.map(async (item) => {
        const armor = await apiCall(fetch, item.Links.$Url);
        if (armor != null) {
          item.Set = armor.Set;
        }
        return item;
      });

      await Promise.all(armorPromises);
    }

    // Now resolve all item links (many will be cached/direct)
    await Promise.all(response.object.Loots.map(async (x) => {
      x.Item.Links.$ItemUrl = await resolveItemLink(fetch, x.Item);
    }));

    response.mobMissions = await apiCall(fetch, `/mobs/${response.object.Id}/missions`).catch(() => []) || [];
  }

  return response;
}
