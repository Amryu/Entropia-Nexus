// @ts-nocheck
/**
 * Locations Wiki Page Loader
 * Unified locations page with type filtering and wiki edit support.
 */
import { apiCall, decodeURIComponentSafe, loadPendingChangesData } from '$lib/util';

export async function load({ fetch, params, url, parent }) {
  const type = params.type || null;
  const isCreateMode = url.searchParams.get('mode') === 'create';
  const name = isCreateMode ? null : decodeURIComponentSafe(params.slug);
  const changeId = url.searchParams.get('changeId');
  const idParam = url.searchParams.get('id');

  // Fetch all base data (locations are fetched unfiltered for client-side filtering)
  const [locations, planets, facilities] = await Promise.all([
    apiCall(fetch, '/locations'),
    apiCall(fetch, '/planets'),
    apiCall(fetch, '/facilities')
  ]);

  let object = null;
  let disambiguation = null;

  if (name && !isCreateMode) {
    // If an id param is provided, fetch by ID directly to disambiguate
    if (idParam) {
      object = await apiCall(fetch, `/locations/${encodeURIComponent(idParam)}`);
    } else {
      // Fetch by name - may return disambiguation object if multiple matches
      const result = await apiCall(fetch, `/locations/${encodeURIComponent(name)}`);
      if (result && result.disambiguation) {
        disambiguation = result.matches;
      } else {
        object = result;
      }
    }
  }

  // Filter out MobAreas from the locations list (they're shown on the mobs page instead)
  const filteredLocations = (locations || []).filter(loc =>
    loc.Properties?.AreaType !== 'MobArea'
  );

  const response = {
    locations: filteredLocations,
    planetsList: planets || [],
    facilitiesList: facilities || [],
    object,
    disambiguation,
    type,
    isCreateMode
  };

  // Handle existing change in create mode
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

  // Load pending changes data
  const pendingData = await loadPendingChangesData(fetch, parentData.session?.user, {
    entity: 'Location',
    entityId: response.object?.Id,
    changeId,
    isAdmin: parentData.session?.user?.isAdmin || false
  });

  response.pendingChange = pendingData.pendingChange;
  response.userPendingCreates = pendingData.userPendingCreates;
  response.userPendingUpdates = pendingData.userPendingUpdates;
  response.canCreateNew = pendingData.canCreateNew;
  response.pendingCreatesCount = pendingData.pendingCreatesCount;

  // Fetch mob maturities for WaveEvent wave editor
  try {
    response.mobMaturities = await apiCall(fetch, '/mobmaturities');
  } catch (e) {
    console.warn('Failed to load mob maturities:', e);
    response.mobMaturities = [];
  }

  // allLocations is the same as filtered locations (both are all locations minus MobAreas)
  response.allLocations = filteredLocations;

  return response;
}
