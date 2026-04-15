// @ts-nocheck
/**
 * Tools Wiki Page Loader
 * Handles 7 subtypes: refiners, scanners, finders, excavators, teleportationchips, effectchips, misctools
 * Supports full wiki editing.
 */
let items;

import { redirect } from '@sveltejs/kit';
import { decodeURIComponentSafe, encodeURIComponentSafe, handlePageLoad, apiCall, loadPendingChangesData } from '$lib/util';

// Map URL type to entity type for API
function getEntityType(type) {
  switch (type) {
    case 'refiners': return 'Refiner';
    case 'scanners': return 'Scanner';
    case 'finders': return 'Finder';
    case 'excavators': return 'Excavator';
    case 'teleportationchips': return 'TeleportationChip';
    case 'effectchips': return 'EffectChip';
    case 'misctools': return 'MiscTool';
    case 'fishingrods': return 'FishingRod';
    default: return null;
  }
}

export async function load({ fetch, params, url, parent }) {
  if (url.searchParams.get('mode') === 'view') {
    const path = params.type
      ? `/items/tools/${encodeURIComponentSafe(params.type)}/${encodeURIComponentSafe(params.slug)}`
      : `/items/tools/${encodeURIComponentSafe(params.slug)}`;
    redirect(301, path);
  }

  // Get session from parent layout
  const parentData = await parent();

  const mode = url.searchParams.get('mode') || 'view';
  const isCreateMode = mode === 'create';
  const changeId = url.searchParams.get('changeId');

  const config = {
    items: ['refiners', 'scanners', 'finders', 'excavators', 'teleportationchips', 'effectchips', 'misctools', 'fishingrods'],
    types: [
      { type: 'refiners', tierable: false },
      { type: 'scanners', tierable: false },
      { type: 'finders', tierable: true },
      { type: 'excavators', tierable: true },
      { type: 'teleportationchips', tierable: false },
      { type: 'effectchips', tierable: false },
      { type: 'misctools', tierable: false },
      { type: 'fishingrods', tierable: false }
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

  // Edit-mode dependencies: only load server-side in create mode
  if (isCreateMode) {
    const [effectsList, professionsList] = await Promise.all([
      apiCall(fetch, '/effects').catch(() => []),
      apiCall(fetch, '/professions').catch(() => [])
    ]);
    response.effects = effectsList || [];
    response.professions = professionsList || [];
  } else {
    response.effects = null;
    response.professions = null;
  }

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

  const userGrants = session?.user?.grants || [];
  const hasEditGrant = userGrants.some(g => g.startsWith('wiki.'));

  const pendingData = entityType
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
