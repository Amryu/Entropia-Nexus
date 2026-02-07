// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getChangeFullDetails, getChangeHistory, buildInitialHistoryIfNeeded, getRelatedApprovedChanges } from '$lib/server/db';

/**
 * Get single change with full details (admin only)
 * GET /api/admin/changes/[id]
 */
export async function GET({ params, locals }) {
  const realUser = locals.session?.realUser || locals.session?.user;

  if (!realUser) {
    return json({ error: 'Not authenticated' }, { status: 401 });
  }

  if (!realUser?.grants?.includes('wiki.approve')) {
    return json({ error: 'Only administrators can access this endpoint' }, { status: 403 });
  }

  const changeId = parseInt(params.id);

  if (isNaN(changeId)) {
    return json({ error: 'Invalid change ID' }, { status: 400 });
  }

  try {
    const change = await getChangeFullDetails(changeId);

    if (!change) {
      return json({ error: 'Change not found' }, { status: 404 });
    }

    // Build initial history if none exists (auto-build feature)
    await buildInitialHistoryIfNeeded(changeId);

    // Get change history for diff viewing (edit history of this change)
    const history = await getChangeHistory(changeId);

    // Get other approved changes for the same entity (for comparison)
    const entityId = change.data?.Id;
    const relatedChanges = await getRelatedApprovedChanges(changeId, change.entity, entityId);

    return json({
      change: {
        ...change,
        id: change.id,
        author_id: String(change.author_id),
        reviewed_by: change.reviewed_by ? String(change.reviewed_by) : null
      },
      history: history.map(h => ({
        ...h,
        id: h.id,
        change_id: h.change_id,
        created_by: h.created_by ? String(h.created_by) : null
      })),
      relatedChanges: relatedChanges.map(rc => ({
        id: rc.id,
        data: rc.data,
        last_update: rc.last_update,
        type: rc.type,
        author_name: rc.author_name
      }))
    });
  } catch (error) {
    console.error('Error fetching change:', error);
    return json({ error: 'Failed to fetch change' }, { status: 500 });
  }
}
