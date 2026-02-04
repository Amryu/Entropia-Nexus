// @ts-nocheck
import { getResponse } from '$lib/util.js';
import {
  updateSocietyJoinRequestStatus,
  getSocietyById,
  updateUserSociety,
  getSocietyJoinRequestById,
  createNotification
} from '$lib/server/db.js';

/** @type {import('./$types').RequestHandler} */
export async function PATCH({ params, request, locals }) {
  const user = locals.session?.user;
  if (!user) {
    return getResponse({ error: 'Authentication required.' }, 401);
  }

  const requestId = Number(params.id);
  if (!Number.isFinite(requestId)) {
    return getResponse({ error: 'Invalid request id.' }, 400);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  const action = String(body?.action || '').toLowerCase();
  if (!['approve', 'reject'].includes(action)) {
    return getResponse({ error: 'Invalid action.' }, 400);
  }

  const existing = await getSocietyJoinRequestById(requestId);
  if (!existing) {
    return getResponse({ error: 'Request not found.' }, 404);
  }

  const society = await getSocietyById(existing.society_id);
  const userId = String(user.Id || user.id);
  if (!society || String(society.leader_id) !== userId) {
    return getResponse({ error: 'Only the society leader can approve requests.' }, 403);
  }

  const updated = await updateSocietyJoinRequestStatus(requestId, action === 'approve' ? 'Approved' : 'Rejected');

  if (action === 'approve') {
    await updateUserSociety(updated.user_id, updated.society_id);
    await createNotification(
      updated.user_id,
      'Society',
      `Your request to join ${society.name} was approved.`
    );
  } else {
    await updateUserSociety(updated.user_id, null);
    await createNotification(
      updated.user_id,
      'Society',
      `Your request to join ${society.name} was rejected.`
    );
  }

  return getResponse({ success: true, request: updated }, 200);
}
