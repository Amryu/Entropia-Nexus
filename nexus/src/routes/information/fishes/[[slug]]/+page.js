// @ts-nocheck
/**
 * Fishes Wiki Page Loader.
 * Wikipedia-style layout; supports full wiki editing.
 */
let items;

import { redirect } from '@sveltejs/kit';
import { apiCall, decodeURIComponentSafe, encodeURIComponentSafe, handlePageLoad, loadPendingChangesData } from '$lib/util';

export async function load({ fetch, params, url, parent }) {
  if (url.searchParams.get('mode') === 'view') {
    redirect(301, `/information/fishes/${encodeURIComponentSafe(params.slug)}`);
  }

  const parentData = await parent();

  const mode = url.searchParams.get('mode') || 'view';
  const isCreateMode = mode === 'create';
  const changeId = url.searchParams.get('changeId');

  const config = {
    items: 'fishes',
    types: { tierable: false },
    name: isCreateMode ? null : decodeURIComponentSafe(params.slug),
    type: null,
    mode,
    searchParams: url.searchParams,
    isItem: false
  };

  let response;
  ({ items, response } = await handlePageLoad(fetch, items, config));

  response.allItems = items;
  response.isCreateMode = isCreateMode;

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

  const session = parentData.session;
  response.session = session;

  const userGrants = session?.user?.grants || [];
  const hasEditGrant = userGrants.some(g => g.startsWith('wiki.'));

  const pendingData = await loadPendingChangesData(fetch, session?.user, {
    entity: 'Fish',
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

  // Edit-mode dependencies: item/lure picker, planet toggles, plus the list
  // of existing Fish-type species so the form can distinguish "pick existing"
  // from "create new". Species list is filtered client-side on CodexType.
  if (isCreateMode) {
    const [itemsData, planetsData, speciesData] = await Promise.all([
      apiCall(fetch, '/items?limit=5000').catch(() => []),
      apiCall(fetch, '/planets').catch(() => []),
      apiCall(fetch, '/mobspecies').catch(() => [])
    ]);
    response.itemsList = itemsData || [];
    response.planetsList = planetsData || [];
    response.speciesList = speciesData || [];
  } else {
    response.itemsList = null;
    response.planetsList = null;
    response.speciesList = null;
  }

  return response;
}
