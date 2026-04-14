// @ts-nocheck
/**
 * Missions Wiki Page Loader
 * Handles missions and mission chains with sidebar toggle.
 */
import { apiCall, decodeURIComponentSafe, loadPendingChangesData } from '$lib/util';

let cachedItems;
let cachedMobSpecies;

export async function load({ fetch, params, url, parent }) {
  const view = url.searchParams.get('view') === 'chains' ? 'chains' : 'missions';
  const isCreateMode = url.searchParams.get('mode') === 'create';
  const name = isCreateMode ? null : decodeURIComponentSafe(params.slug);
  const changeId = url.searchParams.get('changeId');

  const [missions, missionChains, planets] = await Promise.all([
    apiCall(fetch, '/missions'),
    apiCall(fetch, '/missionchains'),
    apiCall(fetch, '/planets')
  ]);

  let object = null;
  if (name && !isCreateMode) {
    const endpoint = view === 'chains' ? '/missionchains' : '/missions';
    object = await apiCall(fetch, `${endpoint}/${encodeURIComponent(name)}`);
  }

  const response = {
    missions: missions || [],
    missionChains: missionChains || [],
    planetsList: planets || [],
    object,
    view,
    isCreateMode
  };

  if (changeId && isCreateMode) {
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

  const entityType = view === 'chains' ? 'MissionChain' : 'Mission';
  const pendingData = await loadPendingChangesData(fetch, parentData.session?.user, {
    entity: entityType,
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

  if (response.object && view !== 'chains') {
    try {
      response.graph = await apiCall(fetch, `/missions/${response.object.Id}/graph`);
    } catch (e) {
      response.graph = null;
    }
  }

  // Items always loaded (needed for reward display names in view mode), cached at module level
  if (!cachedItems) {
    cachedItems = await apiCall(fetch, '/items?limit=5000').catch(() => []) || [];
  }
  response.itemsList = cachedItems;

  // Mob species always loaded (needed for species name display in AIKillCycle objectives), cached at module level
  if (!cachedMobSpecies) {
    cachedMobSpecies = await apiCall(fetch, '/mobspecies').catch(() => []) || [];
  }
  response.mobSpeciesList = cachedMobSpecies;

  // Edit deps: create mode loads everything up front; individual mission pages load locations
  // (needed for mapObjectives to resolve Dialog/Interact/HandIn location coordinates in view mode);
  // remaining deps (mobMaturities, events) are lazy-loaded client-side when edit mode activates.
  if (isCreateMode) {
    const [mobMaturities, locations, events] = await Promise.all([
      apiCall(fetch, '/mobmaturities').catch(() => []),
      apiCall(fetch, '/locations').catch(() => []),
      apiCall(fetch, '/events').catch(() => [])
    ]);
    response.mobMaturities = mobMaturities || [];
    response.locations = locations || [];
    response.events = events || [];
  } else if (response.object) {
    const [locations, mobMaturities] = await Promise.all([
      apiCall(fetch, '/locations').catch(() => []),
      apiCall(fetch, '/mobmaturities').catch(() => [])
    ]);
    response.locations = locations || [];
    response.mobMaturities = mobMaturities || [];
    response.events = null;
  } else {
    response.mobMaturities = null;
    response.locations = null;
    response.events = null;
  }

  return response;
}
