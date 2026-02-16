// @ts-nocheck
import { getResponse } from '$lib/util.js';
import { createSociety, searchSocieties, updateUserSociety, getUserProfileById } from '$lib/server/db.js';
import { sanitizeRichText } from '$lib/server/sanitizeRichText.js';
import { extractDiscordInviteCode, isValidDiscordCode } from '$lib/server/discordUtils.js';

/** @type {import('./$types').RequestHandler} */
export async function GET({ url }) {
  const query = url.searchParams.get('query') || '';
  const societies = await searchSocieties(query);
  return getResponse(societies, 200);
}

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

  const name = String(body?.name || '').trim();
  if (!name) {
    return getResponse({ error: 'Society name is required.' }, 400);
  }

  const abbreviation = String(body?.abbreviation || '').trim() || null;
  const descriptionRaw = body?.description != null
    ? sanitizeRichText(String(body.description))
    : '';
  const description = descriptionRaw.trim() ? descriptionRaw : null;
  const discordInput = body?.discord != null ? String(body.discord).trim() : '';
  const discordCode = extractDiscordInviteCode(discordInput);
  if (discordCode && !isValidDiscordCode(discordCode)) {
    return getResponse({ error: 'Invalid Discord invite code.' }, 400);
  }
  const leaderId = String(user.Id || user.id);

  const userProfile = await getUserProfileById(leaderId);
  if (userProfile?.society_id && userProfile.society_id !== 0) {
    return getResponse({ error: 'You are already in a society or have a pending request.' }, 400);
  }

  const society = await createSociety({
    name,
    abbreviation,
    description,
    discordCode,
    leaderId
  });

  await updateUserSociety(leaderId, society.id);

  return getResponse({ success: true, society }, 200);
}
