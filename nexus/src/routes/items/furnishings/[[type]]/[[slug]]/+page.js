// @ts-nocheck
/**
 * Furnishings Wiki Page Loader
 * Handles 4 subtypes: furniture, decorations, storagecontainers, signs
 * Supports full wiki editing.
 */
let items;

import { redirect } from '@sveltejs/kit';
import { decodeURIComponentSafe, encodeURIComponentSafe, handlePageLoad, loadPendingChangesData } from '$lib/util';

// Map URL type to entity type for API
function getEntityType(type) {
  switch (type) {
    case 'furniture': return 'Furniture';
    case 'decorations': return 'Decoration';
    case 'storagecontainers': return 'StorageContainer';
    case 'signs': return 'Sign';
    default: return null;
  }
}

export async function load({ fetch, params, url, parent }) {
  if (url.searchParams.get('mode') === 'view') {
    const path = params.type
      ? `/items/furnishings/${encodeURIComponentSafe(params.type)}/${encodeURIComponentSafe(params.slug)}`
      : `/items/furnishings/${encodeURIComponentSafe(params.slug)}`;
    redirect(301, path);
  }

  // Get session from parent layout
  const parentData = await parent();

  const mode = url.searchParams.get('mode') || 'view';
  const isCreateMode = mode === 'create';
  const changeId = url.searchParams.get('changeId');

  const config = {
    items: ['furniture', 'decorations', 'storagecontainers', 'signs'],
    types: [
      { type: 'furniture' },
      { type: 'decorations' },
      { type: 'storagecontainers' },
      { type: 'signs' }
    ],
    name: isCreateMode ? null : decodeURIComponentSafe(params.slug),
    type: decodeURIComponentSafe(params.type),
    mode: mode,
    searchParams: url.searchParams
  }

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config));

  // Set create mode flag
  response.isCreateMode = isCreateMode;

  // Get entity type for API calls
  const entityType = getEntityType(response.additional?.type);

  // If a changeId is provided (editing an existing pending create), fetch that change
  if (changeId && isCreateMode && entityType) {
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

  const pendingData = entityType
    ? await loadPendingChangesData(fetch, session?.user, {
      entity: entityType,
      entityId: response.object?.Id,
      changeId,
      isAdmin: session?.user?.isAdmin || false
    })
    : {
      pendingChange: null,
      userPendingCreates: [],
      userPendingUpdates: [],
      canCreateNew: true,
      pendingCreatesCount: 0
    };

  response.pendingChange = pendingData.pendingChange;
  response.userPendingCreates = pendingData.userPendingCreates;
  response.userPendingUpdates = pendingData.userPendingUpdates;
  response.canCreateNew = pendingData.canCreateNew;
  response.pendingCreatesCount = pendingData.pendingCreatesCount;

  return response;
}
