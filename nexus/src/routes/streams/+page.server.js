// @ts-nocheck
import { getActiveCreators } from '$lib/server/db.js';

function getDisplayName(creator) {
  return creator.cached_data?.channelName || creator.cached_data?.displayName || creator.name;
}

function getAvatar(creator) {
  return creator.cached_data?.channelAvatar || creator.cached_data?.avatar || creator.avatar_url;
}

export async function load() {
  const creators = await getActiveCreators();

  const live = [];
  const offline = [];

  for (const c of creators) {
    if (c.platform === 'youtube') continue;

    const entry = {
      id: c.id,
      name: getDisplayName(c),
      avatar: getAvatar(c),
      platform: c.platform,
      channelUrl: c.channel_url,
      displayOrder: c.display_order
    };

    if (c.cached_data?.isLive) {
      live.push({
        ...entry,
        thumbnail: c.cached_data.streamThumbnail || null,
        title: c.cached_data.streamTitle,
        viewerCount: c.cached_data.viewerCount || 0,
        gameName: c.cached_data.gameName,
        offline: false
      });
    } else {
      let thumbnail = null;
      if (c.platform === 'twitch') {
        const login = c.cached_data?.login || c.channel_id;
        thumbnail = c.cached_data?.lastStreamThumbnail ||
          (login ? `https://static-cdn.jtvnw.net/previews-ttv/live_user_${login}-440x248.jpg` : null);
      }
      offline.push({
        ...entry,
        thumbnail,
        title: null,
        viewerCount: 0,
        gameName: null,
        offline: true
      });
    }
  }

  // Sort: display_order ASC, then viewerCount DESC
  live.sort((a, b) => {
    if (a.displayOrder !== b.displayOrder) return a.displayOrder - b.displayOrder;
    return b.viewerCount - a.viewerCount;
  });

  offline.sort((a, b) => a.displayOrder - b.displayOrder);

  return { streams: [...live, ...offline], hasLive: live.length > 0 };
}
