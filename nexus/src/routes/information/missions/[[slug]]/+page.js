// @ts-nocheck
/**
 * Missions Wiki Page Loader
 * Handles missions and mission chains with sidebar toggle.
 */
import { apiCall, decodeURIComponentSafe, loadPendingChangesData } from '$lib/util';

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

  const entityType = view === 'chains' ? 'MissionChain' : 'Mission';
  const pendingData = await loadPendingChangesData(fetch, parentData.session?.user, {
    entity: entityType,
    entityId: response.object?.Id,
    changeId,
    isAdmin: parentData.session?.user?.grants?.includes('wiki.approve') || false
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

  // Fetch mob maturities for objective target search
  try {
    response.mobMaturities = await apiCall(fetch, '/mobmaturities');
  } catch (e) {
    console.warn('Failed to load mob maturities:', e);
    response.mobMaturities = [];
  }

  // Fetch mob species for AIKillCycle objectives
  try {
    response.mobSpeciesList = await apiCall(fetch, '/mobspecies');
  } catch (e) {
    console.warn('Failed to load mob species:', e);
    response.mobSpeciesList = [];
  }

  // Fetch locations for dialog/interact objectives
  try {
    response.locations = await apiCall(fetch, '/locations');
  } catch (e) {
    console.warn('Failed to load locations:', e);
    response.locations = [];
  }

  // Fetch items list for rewards + hand-in lookup (names by id)
  try {
    response.itemsList = await apiCall(fetch, '/items?limit=5000');
  } catch (e) {
    console.warn('Failed to load items list:', e);
    response.itemsList = [];
  }

  // Fetch events for event-type mission selection
  try {
    response.events = await apiCall(fetch, '/events');
  } catch (e) {
    console.warn('Failed to load events:', e);
    response.events = [];
  }

  return response;
}
