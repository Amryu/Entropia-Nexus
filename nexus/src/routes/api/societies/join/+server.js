// @ts-nocheck
import { getResponse } from '$lib/util.js';
import {
  createSocietyJoinRequest,
  updateUserSociety,
  getSocietyById,
  getPendingSocietyJoinRequest,
  getUserProfileById,
  createNotification
} from '$lib/server/db.js';

/** @type {import('./$types').RequestHandler} */
export async function POST({ request, locals }) {
  const user = locals.session?.user;
  if (!user) {
    return getResponse({ error: 'Authentication required.' }, 401);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  const societyId = Number(body?.societyId);
  if (!Number.isFinite(societyId)) {
    return getResponse({ error: 'Society id required.' }, 400);
  }

  const society = await getSocietyById(societyId);
  if (!society) {
    return getResponse({ error: 'Society not found.' }, 404);
  }

  const userId = String(user.Id || user.id);
  const userProfile = await getUserProfileById(userId);
  if (userProfile?.society_id && userProfile.society_id !== 0) {
    return getResponse({ error: 'You are already in a society or have a pending request.' }, 400);
  }
  const existing = await getPendingSocietyJoinRequest(userId);
  if (existing) {
    return getResponse({ error: 'You already have a pending request.' }, 400);
  }

  const requestRecord = await createSocietyJoinRequest(userId, societyId);
  await updateUserSociety(userId, -1);

  const requesterName = user.eu_name || user.global_name || user.username || 'User';
  await createNotification(
    society.leader_id,
    'Society',
    `${requesterName} requested to join ${society.name}.`
  );

  return getResponse({
    success: true,
    request: requestRecord,
    society
  }, 200);
}
