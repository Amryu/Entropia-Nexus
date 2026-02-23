// @ts-nocheck
/**
 * Material wiki pages
 * Uses new WikiPage layout pattern with full editing support.
 */
let items;

import { redirect } from '@sveltejs/kit';
import { handlePageLoad, encodeURIComponentSafe, decodeURIComponentSafe, apiCall, loadPendingChangesData } from '$lib/util';

export async function load({ fetch, params, url, parent }) {
  if (url.searchParams.get('mode') === 'view') {
    redirect(301, `/items/materials/${encodeURIComponentSafe(params.slug)}`);
  }

  // Get session from parent layout
  const parentData = await parent();

  const mode = url.searchParams.get('mode') || 'view';
  const isCreateMode = mode === 'create';
  const changeId = url.searchParams.get('changeId');

  const config = {
    items: 'materials',
    types: { tierable: false },
    name: isCreateMode ? null : decodeURIComponentSafe(params.slug),
    type: null,
    mode: mode,
    searchParams: url.searchParams
  }

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config));

  // Ensure refining recipes are present on the material object (view + edit)
  if (response.object && response.additional?.acquisition?.RefiningRecipes) {
    if (!response.object.RefiningRecipes || response.object.RefiningRecipes.length === 0) {
      response.object.RefiningRecipes = response.additional.acquisition.RefiningRecipes;
    }
  }

  // Provide allItems for navigation
  response.allItems = items;

  // Set create mode flag
  response.isCreateMode = isCreateMode;

  // Edit-mode dependency: only load server-side in create mode
  response.availableItems = isCreateMode ? ((await apiCall(fetch, '/items').catch(() => [])) || []) : null;

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
    entity: 'Material',
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
