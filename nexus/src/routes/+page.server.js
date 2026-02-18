// @ts-nocheck
import { getPublishedAnnouncements, getUpcomingEvents, getActiveCreators } from '$lib/server/db.js';
import { getCachedSteamNews, mergeAndSortNews } from '$lib/server/news-cache.js';

const MAX_STREAMS = 6;
const MAX_VIDEOS = 6;

function getDisplayName(creator) {
  return creator.cached_data?.channelName || creator.cached_data?.displayName || creator.name;
}

function getAvatar(creator) {
  return creator.cached_data?.channelAvatar || creator.cached_data?.avatar || creator.avatar_url;
}

function processCreators(creators) {
  const streams = [];
  const videos = [];

  // Collect live streams (Twitch)
  for (const c of creators) {
    if (c.cached_data?.isLive) {
      streams.push({
        id: c.id,
        name: getDisplayName(c),
        avatar: getAvatar(c),
        platform: c.platform,
        channelUrl: c.channel_url,
        displayOrder: c.display_order,
        thumbnail: c.cached_data.streamThumbnail || null,
        title: c.cached_data.streamTitle,
        viewerCount: c.cached_data.viewerCount || 0,
        gameName: c.cached_data.gameName,
        offline: false
      });
    }
  }

  // If no live streams, show offline channels (Twitch + Kick) as fallback
  if (streams.length === 0) {
    for (const c of creators) {
      if (c.platform === 'youtube') continue;
      let thumbnail = null;
      if (c.platform === 'twitch') {
        const login = c.cached_data?.login || c.channel_id;
        thumbnail = c.cached_data?.lastStreamThumbnail ||
          (login ? `https://static-cdn.jtvnw.net/previews-ttv/live_user_${login}-440x248.jpg` : null);
      }
      streams.push({
        id: c.id,
        name: getDisplayName(c),
        avatar: getAvatar(c),
        platform: c.platform,
        channelUrl: c.channel_url,
        displayOrder: c.display_order,
        thumbnail,
        title: null,
        viewerCount: 0,
        gameName: null,
        offline: true
      });
    }
  }

  // Sort streams: display_order ASC, then viewerCount DESC
  streams.sort((a, b) => {
    if (a.displayOrder !== b.displayOrder) return a.displayOrder - b.displayOrder;
    return b.viewerCount - a.viewerCount;
  });

  // Collect YouTube videos, evenly distributed across creators
  const ytCreators = creators.filter(c =>
    c.platform === 'youtube' && c.cached_data?.recentVideos?.length > 0
  );

  if (ytCreators.length > 0) {
    const indices = new Map();
    ytCreators.forEach(c => indices.set(c.id, 0));

    // Round-robin: take 1 video from each creator per pass
    while (videos.length < MAX_VIDEOS) {
      let added = false;
      for (const c of ytCreators) {
        if (videos.length >= MAX_VIDEOS) break;
        const idx = indices.get(c.id);
        const vids = c.cached_data.recentVideos;
        if (idx < vids.length) {
          videos.push({
            videoId: vids[idx].videoId,
            title: vids[idx].title,
            thumbnail: vids[idx].thumbnail,
            publishedAt: vids[idx].publishedAt,
            creatorName: getDisplayName(c),
            creatorAvatar: getAvatar(c),
            channelUrl: c.channel_url
          });
          indices.set(c.id, idx + 1);
          added = true;
        }
      }
      if (!added) break;
    }
  }

  return {
    streams: streams.slice(0, MAX_STREAMS),
    videos
  };
}

export async function load() {
  const [announcements, steamNews, events, creators] = await Promise.all([
    getPublishedAnnouncements(6),
    getCachedSteamNews(),
    getUpcomingEvents(5),
    getActiveCreators()
  ]);

  const news = mergeAndSortNews(announcements, steamNews);
  const { streams, videos } = processCreators(creators);

  return {
    news,
    events,
    streams,
    videos
  };
}
