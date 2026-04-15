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
    case 'fishingreels': return 'FishingReel';
    case 'fishingblanks': return 'FishingBlank';
    case 'fishinglines': return 'FishingLine';
    case 'fishinglures': return 'FishingLure';
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
    items: ['weaponamplifiers', 'weaponvisionattachments', 'absorbers', 'finderamplifiers', 'armorplatings', 'enhancers', 'mindforceimplants', 'fishingreels', 'fishingblanks', 'fishinglines', 'fishinglures'],
    types: [
      { type: 'weaponamplifiers' },
      { type: 'weaponvisionattachments' },
      { type: 'absorbers' },
      { type: 'finderamplifiers' },
      { type: 'armorplatings' },
      { type: 'enhancers' },
      { type: 'mindforceimplants' },
      { type: 'fishingreels' },
      { type: 'fishingblanks' },
      { type: 'fishinglines' },
      { type: 'fishinglures' }
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

  // Edit-mode dependency: only load server-side in create mode
  response.effects = isCreateMode ? ((await apiCall(fetch, '/effects').catch(() => [])) || []) : null;

  // Get entity type for API calls
  const entityType = getEntityType(response.additional?.type);

  // Enhancers are database-generated and not wiki-editable
  const isEditable = entityType && entityType !== 'Enhancer';

  // If a changeId is provided (editing an existing pending create), fetch that change
  if (changeId && isCreateMode && isEditable) {
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

  const pendingData = isEditable
    ? await loadPendingChangesData(fetch, session?.user, {
      entity: entityType,
      entityId: response.object?.Id,
      changeId,
      isAdmin: userGrants.includes('wiki.approve'),
      hasEditGrant
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
