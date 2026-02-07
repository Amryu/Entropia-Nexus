// @ts-nocheck
/**
 * Attachments Wiki Page Loader
 * Handles 7 subtypes: weaponamplifiers, weaponvisionattachments, absorbers,
 * finderamplifiers, armorplatings, enhancers, mindforceimplants
 * Supports full wiki editing (except enhancers, which are database-generated).
 */
let items;

import { redirect } from '@sveltejs/kit';
import { decodeURIComponentSafe, encodeURIComponentSafe, handlePageLoad, apiCall, loadPendingChangesData } from '$lib/util';

// Map URL type to entity type for API
function getEntityType(type) {
  switch (type) {
    case 'weaponamplifiers': return 'WeaponAmplifier';
    case 'weaponvisionattachments': return 'WeaponVisionAttachment';
    case 'absorbers': return 'Absorber';
    case 'finderamplifiers': return 'FinderAmplifier';
    case 'armorplatings': return 'ArmorPlating';
    case 'enhancers': return 'Enhancer';
    case 'mindforceimplants': return 'MindforceImplant';
    default: return null;
  }
}

export async function load({ fetch, params, url, parent }) {
  if (url.searchParams.get('mode') === 'view') {
    const path = params.type
      ? `/items/attachments/${encodeURIComponentSafe(params.type)}/${encodeURIComponentSafe(params.slug)}`
      : `/items/attachments/${encodeURIComponentSafe(params.slug)}`;
    redirect(301, path);
  }

  // Get session from parent layout
  const parentData = await parent();

  const mode = url.searchParams.get('mode') || 'view';
  const isCreateMode = mode === 'create';
  const changeId = url.searchParams.get('changeId');

  const config = {
    items: ['weaponamplifiers', 'weaponvisionattachments', 'absorbers', 'finderamplifiers', 'armorplatings', 'enhancers', 'mindforceimplants'],
    types: [
      { type: 'weaponamplifiers' },
      { type: 'weaponvisionattachments' },
      { type: 'absorbers' },
      { type: 'finderamplifiers' },
      { type: 'armorplatings' },
      { type: 'enhancers' },
      { type: 'mindforceimplants' }
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

  // Fetch effects list for edit mode dropdown
  const effectsList = await apiCall(fetch, '/effects');
  response.effects = effectsList || [];

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
      isAdmin: session?.user?.grants?.includes('wiki.approve') || false
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
