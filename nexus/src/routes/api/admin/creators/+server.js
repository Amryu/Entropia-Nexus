// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getCreatorsAdmin, createCreator } from '$lib/server/db.js';
import { requireAdmin } from '$lib/server/auth.js';

export async function GET({ locals }) {
  requireAdmin(locals);

  const creators = await getCreatorsAdmin();
  return json(creators);
}

export async function POST({ request, locals }) {
  const user = requireAdmin(locals);
  const body = await request.json();

  if (!body.name?.trim()) {
    return json({ error: 'Name is required' }, { status: 400 });
  }
  if (!body.channel_url?.trim()) {
    return json({ error: 'Channel URL is required' }, { status: 400 });
  }
  if (!['youtube', 'twitch', 'kick'].includes(body.platform)) {
    return json({ error: 'Platform must be youtube, twitch, or kick' }, { status: 400 });
  }

  const creator = await createCreator({
    name: body.name.trim(),
    platform: body.platform,
    channel_id: body.channel_id?.trim() || null,
    channel_url: body.channel_url.trim(),
    description: body.description?.trim() || null,
    avatar_url: body.avatar_url?.trim() || null,
    active: body.active !== false,
    display_order: parseInt(body.display_order, 10) || 0,
    added_by: user.id
  });

  return json(creator, { status: 201 });
}
