// @ts-nocheck
import { getResponse } from '$lib/util.js';
import {
  getSocietyById,
  getSocietyByName,
  getSocietyMembers,
  getSocietyJoinRequests,
  countSocietyJoinRequests,
  updateSocietyDetails
} from '$lib/server/db.js';
import { sanitizeRichText } from '$lib/server/sanitizeRichText.js';
import { extractDiscordInviteCode, isValidDiscordCode } from '$lib/server/discordUtils.js';

/** @type {import('./$types').RequestHandler} */
export async function GET({ params, locals }) {
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

  const members = await getSocietyMembers(society.id);
  const sessionUser = locals.session?.user;
  const userId = sessionUser ? String(sessionUser.Id || sessionUser.id) : null;
  const isLeader = userId && userId === String(society.leader_id);
  const isMember = userId && members.some(m => String(m.id) === userId);

  // Discord link is private by default — only expose to members unless explicitly public
  if (!society.discord_public && !isMember) {
    society.discord_code = null;
  }

  let pending = [];
  let pendingCount = 0;
  if (isLeader) {
    pending = await getSocietyJoinRequests(society.id, 'Pending', 10, 0);
    pendingCount = await countSocietyJoinRequests(society.id, 'Pending');
  }

  return getResponse({
    society,
    members,
    isLeader,
    isMember: !!isMember,
    pending,
    pendingCount
  }, 200);
}

/** @type {import('./$types').RequestHandler} */
export async function PATCH({ params, request, locals }) {
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
    return getResponse({ error: 'Only the society leader can update this society.' }, 403);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON in request body.' }, 400);
  }

  const nextDescription = body?.description != null
    ? sanitizeRichText(String(body.description))
    : society.description;

  const discordInput = body?.discord != null ? String(body.discord).trim() : society.discord_code || '';
  const discordCode = extractDiscordInviteCode(discordInput);
  if (discordCode && !isValidDiscordCode(discordCode)) {
    return getResponse({ error: 'Invalid Discord invite code.' }, 400);
  }

  const discordPublic = body?.discordPublic != null ? !!body.discordPublic : !!society.discord_public;

  const updated = await updateSocietyDetails(society.id, nextDescription || null, discordCode || null, discordPublic);
  return getResponse({ success: true, society: updated }, 200);
}
