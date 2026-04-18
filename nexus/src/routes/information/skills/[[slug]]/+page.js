// @ts-nocheck
/**
 * Skills Wiki Page Loader
 * Wikipedia-style layout with floating infobox on the right.
 * Supports full wiki editing.
 */
let items;

import { redirect } from '@sveltejs/kit';
import { apiCall, decodeURIComponentSafe, encodeURIComponentSafe, handlePageLoad, loadPendingChangesData } from '$lib/util';

export async function load({ fetch, params, url, parent }) {
  if (url.searchParams.get('mode') === 'view') {
    redirect(301, `/information/skills/${encodeURIComponentSafe(params.slug)}`);
  }

  // Get session from parent layout
  const parentData = await parent();

  const mode = url.searchParams.get('mode') || 'view';
  const isCreateMode = mode === 'create';
  const changeId = url.searchParams.get('changeId');

  const config = {
    items: 'skills',
    types: { tierable: false },
    name: isCreateMode ? null : decodeURIComponentSafe(params.slug),
    type: null,
    mode: mode,
    searchParams: url.searchParams,
    isItem: false
  }

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config));

  // Add allItems for navigation
  response.allItems = items;

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
    entity: 'Skill',
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

  // Edit-mode dependency: only load server-side in create mode
  response.professions = isCreateMode ? ((await apiCall(fetch, '/professions').catch(() => [])) || []) : null;

  // Profession changes share junction tables with Skill changes; an open
  // Profession change locks the Professions/Unlocks editors on this page.
  try {
    const res = await fetch('/api/changes/any-open?entity=Profession');
    const data = res.ok ? await res.json() : null;
    response.openProfessionChangeCount = data?.counts?.Profession ?? 0;
  } catch {
    response.openProfessionChangeCount = 0;
  }

  return response;
}
