// @ts-nocheck
/**
 * Vehicles Wiki Page Loader
 * Wikipedia-style layout with floating infobox on the right.
 * Supports full wiki editing.
 */
let items;

import { redirect } from '@sveltejs/kit';
import { decodeURIComponentSafe, encodeURIComponentSafe, handlePageLoad, apiCall, loadPendingChangesData } from '$lib/util';

export async function load({ fetch, params, url, parent }) {
  if (url.searchParams.get('mode') === 'view') {
    redirect(301, `/items/vehicles/${encodeURIComponentSafe(params.slug)}`);
  }

  // Get session from parent layout
  const parentData = await parent();

  const mode = url.searchParams.get('mode') || 'view';
  const isCreateMode = mode === 'create';
  const changeId = url.searchParams.get('changeId');

  const config = {
    items: 'vehicles',
    types: { tierable: false },
    name: isCreateMode ? null : decodeURIComponentSafe(params.slug),
    type: null,
    mode: mode,
    searchParams: url.searchParams
  }

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config));

  // Add items for navigation (allItems pattern)
  response.allItems = items;

  // Set create mode flag
  response.isCreateMode = isCreateMode;

  // Fetch materials (for fuel selection) and vehicle attachment types
  const [materialsList, vehicleAttachmentTypesList] = await Promise.all([
    apiCall(fetch, '/materials'),
    apiCall(fetch, '/vehicleattachmenttypes')
  ]);
  response.materials = materialsList || [];
  response.vehicleAttachmentTypes = vehicleAttachmentTypesList || [];

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
    entity: 'Vehicle',
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
