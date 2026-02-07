// @ts-nocheck
/**
 * Blueprint wiki pages
 * Uses new WikiPage layout pattern.
 * Supports full wiki editing.
 */
let items;

import { redirect } from '@sveltejs/kit';
import { decodeURIComponentSafe, handlePageLoad, resolveItemLink, encodeURIComponentSafe, apiCall, loadPendingChangesData } from '$lib/util';

export async function load({ fetch, params, url, parent }) {
  if (url.searchParams.get('mode') === 'view') {
    redirect(301, `/items/blueprints/${encodeURIComponentSafe(params.slug)}`);
  }

  // Get session from parent layout
  const parentData = await parent();

  const mode = url.searchParams.get('mode') || 'view';
  const isCreateMode = mode === 'create';
  const changeId = url.searchParams.get('changeId');

  const config = {
    items: 'blueprints',
    types: { tierable: false },
    name: isCreateMode ? null : decodeURIComponentSafe(params.slug),
    type: null,
    mode: mode,
    searchParams: url.searchParams
  }

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config));

  if (response?.object?.Product != null) {
    response.object.Product.Links = response.object.Product.Links || {};
    response.object.Product.Links.$ItemUrl = await resolveItemLink(fetch, response.object.Product);
  }

  // Provide allItems for navigation
  response.allItems = items;

  // Set create mode flag
  response.isCreateMode = isCreateMode;

  // Fetch dependent data for edit mode dropdowns
  const [blueprintbooksList, professionsList, itemsList, materialsList] = await Promise.all([
    apiCall(fetch, '/blueprintbooks'),
    apiCall(fetch, '/professions'),
    apiCall(fetch, '/items'),
    apiCall(fetch, '/materials')
  ]);

  // Filter professions to only Manufacturing category
  response.blueprintbooks = blueprintbooksList || [];
  response.professions = (professionsList || []).filter(p => p.Category?.Name === 'Manufacturing');
  // Filter items to exclude Blueprints and Pets (they can't be products)
  response.productItems = (itemsList || []).filter(i =>
    i.Properties?.Type !== 'Blueprint' && i.Properties?.Type !== 'Pet'
  );
  response.materials = materialsList || [];

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

  const pendingData = await loadPendingChangesData(fetch, session?.user, {
    entity: 'Blueprint',
    entityId: response.object?.Id,
    changeId,
    isAdmin: session?.user?.grants?.includes('wiki.approve') || false
  });

  response.pendingChange = pendingData.pendingChange;
  response.userPendingCreates = pendingData.userPendingCreates;
  response.userPendingUpdates = pendingData.userPendingUpdates;
  response.canCreateNew = pendingData.canCreateNew;
  response.pendingCreatesCount = pendingData.pendingCreatesCount;

  return response;
}
