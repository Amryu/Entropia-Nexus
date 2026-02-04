// @ts-nocheck
import { getResponse } from '$lib/util.js';
import { getSocietyById, disbandSociety, createNotification } from '$lib/server/db.js';

/** @type {import('./$types').RequestHandler} */
export async function POST({ params, locals }) {
  const user = locals.session?.user;
  if (!user) {
    return getResponse({ error: 'Authentication required.' }, 401);
  }

  const societyId = Number(params.id);
  if (!Number.isFinite(societyId)) {
    return getResponse({ error: 'Invalid society id.' }, 400);
  }

  const society = await getSocietyById(societyId);
  if (!society) {
    return getResponse({ error: 'Society not found.' }, 404);
  }

  const userId = String(user.Id || user.id);
  if (String(society.leader_id) !== userId) {
    return getResponse({ error: 'Only the society leader can disband the society.' }, 403);
  }

  const { members, pending } = await disbandSociety(societyId);

  const memberIds = Array.from(new Set(members || []))
    .filter(memberId => String(memberId) !== userId);
  const pendingIds = Array.from(new Set(pending || []));

  await Promise.all([
    ...memberIds.map(memberId => createNotification(
      memberId,
      'Society',
      `${society.name} has been disbanded by the leader.`
    )),
    ...pendingIds.map(memberId => createNotification(
      memberId,
      'Society',
      `Your request to join ${society.name} was declined because the society was disbanded.`
    ))
  ]);

  return getResponse({ success: true }, 200);
}
