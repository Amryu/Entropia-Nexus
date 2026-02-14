// @ts-nocheck
/**
 * Mobs Wiki Page Loader
 * Wikipedia-style layout with floating infobox on the right.
 */
let items;
let itemsGrouped;

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

  const pendingData = await loadPendingChangesData(fetch, parentData.session?.user, {
    entity: 'Mob',
    entityId: response.object?.Id,
    changeId,
    isAdmin: parentData.session?.user?.grants?.includes('wiki.approve') || false
  });

  response.pendingChange = pendingData.pendingChange;
  response.userPendingCreates = pendingData.userPendingCreates;
  response.userPendingUpdates = pendingData.userPendingUpdates;
  response.canCreateNew = pendingData.canCreateNew;
  response.pendingCreatesCount = pendingData.pendingCreatesCount;

  // Fetch mob species for dropdown
  try {
    const speciesData = await apiCall(fetch, '/mobspecies');
    response.speciesList = speciesData || [];
  } catch (e) {
    console.error('Failed to load mob species:', e);
    response.speciesList = [];
  }

  // Fetch items list for loot autocomplete (in edit mode)
  try {
    const itemsData = await apiCall(fetch, '/items?limit=5000');
    response.itemsList = itemsData || [];
  } catch (e) {
    console.error('Failed to load items list:', e);
    response.itemsList = [];
  }

  // Fetch planets list for planet dropdown
  try {
    const planetsData = await apiCall(fetch, '/planets');
    response.planetsList = planetsData || [];
  } catch (e) {
    console.error('Failed to load planets list:', e);
    response.planetsList = [];
  }

  // Fetch skills data for codex calculator (HP increase, looter contributions)
  try {
    const skillsData = await apiCall(fetch, '/skills');
    response.skillsList = skillsData || [];
  } catch (e) {
    console.error('Failed to load skills list:', e);
    response.skillsList = [];
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
  }

  return response;
}
