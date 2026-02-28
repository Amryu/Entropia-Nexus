// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getActiveCreators } from '$lib/server/db.js';

/** @type {import('./$types').RequestHandler} */
export async function GET() {
  const creators = await getActiveCreators();

  const result = creators.map(c => {
    const isLive = !!c.cached_data?.isLive;
    const avatar = c.cached_data?.channelAvatar || c.cached_data?.avatar || c.avatar_url;
    const name = c.cached_data?.channelName || c.cached_data?.displayName || c.name;

    return {
      id: c.id,
      name,
      platform: c.platform,
      channel_url: c.channel_url,
      avatar_url: avatar,
      is_live: isLive,
      stream_title: isLive ? (c.cached_data.streamTitle || null) : null,
      game_name: isLive ? (c.cached_data.gameName || null) : null,
      viewer_count: isLive ? (c.cached_data.viewerCount || 0) : 0,
    };
  });

  return json({ creators: result }, {
    headers: { 'Cache-Control': 'public, max-age=60' }
  });
}
