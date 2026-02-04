// @ts-nocheck
import { getResponse } from '$lib/util.js';
import {
  getSocietyById,
  getSocietyByName,
  getSocietyJoinRequests,
  countSocietyJoinRequests
} from '$lib/server/db.js';

/** @type {import('./$types').RequestHandler} */
export async function GET({ params, url, locals }) {
  const user = locals.session?.user;
  if (!user) {
    return getResponse({ error: 'Authentication required.' }, 401);
  }

  const identifier = params.identifier;
  if (!identifier) {
    return getResponse({ error: 'Society identifier required.' }, 400);
  }

  const isNumeric = /^\d+$/.test(identifier);
  const decodedName = decodeURIComponent(identifier).replace(/~/g, ' ');

  const society = isNumeric
    ? await getSocietyById(identifier)
    : await getSocietyByName(decodedName);

  if (!society) {
    return getResponse({ error: 'Society not found.' }, 404);
  }

  const userId = String(user.Id || user.id);
  if (String(society.leader_id) !== userId) {
    return getResponse({ error: 'Only the society leader can view requests.' }, 403);
  }

  const rawStatus = String(url.searchParams.get('status') || 'Pending');
  const statusLookup = {
    pending: 'Pending',
    approved: 'Approved',
    rejected: 'Rejected',
    Pending: 'Pending',
    Approved: 'Approved',
    Rejected: 'Rejected'
  };
  const status = statusLookup[rawStatus] || statusLookup[rawStatus.toLowerCase()];
  if (!status) {
    return getResponse({ error: 'Invalid status filter.' }, 400);
  }

  const page = Math.max(1, parseInt(url.searchParams.get('page') || '1', 10));
  const pageSize = Math.min(50, Math.max(5, parseInt(url.searchParams.get('pageSize') || '10', 10)));
  const offset = (page - 1) * pageSize;

  const [rows, total] = await Promise.all([
    getSocietyJoinRequests(society.id, status, pageSize, offset),
    countSocietyJoinRequests(society.id, status)
  ]);

  return getResponse({ rows, total, page, pageSize }, 200);
}
