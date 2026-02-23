// @ts-nocheck
/**
 * Layout A: Wikipedia-style weapon pages
 * Classic wiki layout with floating infobox on the right.
 */
let items;
let itemsGrouped;

import { redirect } from '@sveltejs/kit';
import { handlePageLoad, encodeURIComponentSafe, decodeURIComponentSafe, apiCall, loadPendingChangesData } from '$lib/util';

export async function load({ fetch, params, url, parent }) {
  if (url.searchParams.get('mode') === 'view') {
    redirect(301, `/items/weapons-a/${encodeURIComponentSafe(params.slug)}`);
  }

  // Get session from parent layout
  const parentData = await parent();

  const mode = url.searchParams.get('mode') || 'view';
  const isCreateMode = mode === 'create';
  const changeId = url.searchParams.get('changeId');

  const config = {
    items: 'weapons',
    types: { tierable: true },
    name: isCreateMode ? null : decodeURIComponentSafe(params.slug),
    type: null,
    mode: mode,
    searchParams: url.searchParams
  }

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config));

  // Set create mode flag
  response.isCreateMode = isCreateMode;

  itemsGrouped = {
    ranged: [],
    melee: [],
    mindforce: [],
    attached: [],
  }

  items.forEach(element => {
    if (element.Properties.Class === 'Ranged') itemsGrouped.ranged.push(element);
    if (element.Properties.Class === 'Melee') itemsGrouped.melee.push(element);
    if (element.Properties.Class === 'Mindforce') itemsGrouped.mindforce.push(element);
    if (element.Properties.Class === 'Attached') itemsGrouped.attached.push(element);
  });

  response.items = itemsGrouped;
  response.allItems = items;
  response.layoutVariant = 'A';

  // Edit-mode dependencies: only load server-side in create mode
  if (isCreateMode) {
    const [effectsList, attachmentTypes] = await Promise.all([
      apiCall(fetch, '/effects').catch(() => []),
      apiCall(fetch, '/vehicleattachmenttypes').catch(() => [])
    ]);
    response.effects = effectsList || [];
    response.vehicleAttachmentTypes = attachmentTypes || [];
  } else {
    response.effects = null;
    response.vehicleAttachmentTypes = null;
  }

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
    entity: 'Weapon',
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
