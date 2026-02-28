//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { requireAdminAPI } from '$lib/server/auth.js';
import { getTradeChannels, addTradeChannel, removeTradeChannel } from '$lib/server/ingestion.js';

const MAX_CHANNEL_LENGTH = 100;

/**
 * GET /api/admin/ingestion/channels — List configured trade channels.
 */
export async function GET({ locals }) {
  requireAdminAPI(locals);

  try {
    const rows = await getTradeChannels();
    return getResponse({ rows }, 200);
  } catch (e) {
    console.error('[admin/ingestion] Failed to fetch trade channels:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}

/**
 * POST /api/admin/ingestion/channels — Add a trade channel.
 * Body: { channelName, planet? }
 */
export async function POST({ request, locals }) {
  const admin = requireAdminAPI(locals);

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid request body' }, 400);
  }

  if (!body.channelName || typeof body.channelName !== 'string') {
    return getResponse({ error: 'Missing channelName' }, 400);
  }
  const channelName = body.channelName.trim().toLowerCase();
  if (channelName.length === 0 || channelName.length > MAX_CHANNEL_LENGTH) {
    return getResponse({ error: 'Invalid channel name length' }, 400);
  }
  if (body.planet != null && typeof body.planet !== 'string') {
    return getResponse({ error: 'Planet must be a string' }, 400);
  }

  try {
    const added = await addTradeChannel(channelName, body.planet || null, admin.id);
    if (!added) {
      return getResponse({ error: 'Channel already configured' }, 409);
    }
    return getResponse({ success: true }, 200);
  } catch (e) {
    console.error('[admin/ingestion] Failed to add trade channel:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}

/**
 * DELETE /api/admin/ingestion/channels — Remove a trade channel.
 * Body: { channelName }
 */
export async function DELETE({ request, locals }) {
  requireAdminAPI(locals);

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid request body' }, 400);
  }

  if (!body.channelName) return getResponse({ error: 'Missing channelName' }, 400);

  try {
    const removed = await removeTradeChannel(body.channelName);
    if (!removed) {
      return getResponse({ error: 'Channel not found' }, 404);
    }
    return getResponse({ success: true }, 200);
  } catch (e) {
    console.error('[admin/ingestion] Failed to remove trade channel:', e);
    return getResponse({ error: 'Internal server error' }, 500);
  }
}
