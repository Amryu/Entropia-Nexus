// @ts-nocheck
/**
 * Shops Wiki Page Loader
 * Supports full wiki editing for wiki data properties.
 * Owner-managed data (managers/inventory) uses existing dialogs.
 */
import { redirect } from '@sveltejs/kit';
import { handlePageLoad, decodeURIComponentSafe, encodeURIComponentSafe, loadPendingChangesData } from '$lib/util';

let items;

export async function load({ fetch, params, url, parent }) {
  if (url.searchParams.get('mode') === 'view') {
    redirect(301, `/market/shops/${encodeURIComponentSafe(params.slug)}`);
  }

  // Get session from parent layout
  const parentData = await parent();

  const mode = url.searchParams.get('mode') || 'view';
  const isCreateMode = mode === 'create';
  const changeId = url.searchParams.get('changeId');

  const config = {
    items: 'shops',
    types: { tierable: false },
    name: isCreateMode ? null : decodeURIComponentSafe(params.slug),
    type: null,
    mode: mode,
    searchParams: url.searchParams,
    isItem: false
  };

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config));

  // Group shops by planet name for filtering in navigation
  const itemsGrouped = {};
  if (items) {
    for (const shop of items) {
      const planetName = shop.Planet?.Name || shop.Planet?.Properties?.TechnicalName;
      if (!planetName) continue;
      const key = planetName.toLowerCase().replace(/[\s.]+/g, '');
      if (!itemsGrouped[key]) itemsGrouped[key] = [];
      itemsGrouped[key].push(shop);
    }
  }

  if (response) {
    response.itemsGrouped = itemsGrouped;
    response.allItems = items || [];
  }

  // Set create mode flag
  response.isCreateMode = isCreateMode;

  // If a changeId is provided (editing an existing pending create), fetch that change
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

  // Use session from parent layout data
  const session = parentData.session;
  response.session = session;

  const userGrants = session?.user?.grants || [];
  const hasEditGrant = userGrants.some(g => g.startsWith('wiki.'));

  const pendingData = await loadPendingChangesData(fetch, session?.user, {
    entity: 'Shop',
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

  return response;
}
