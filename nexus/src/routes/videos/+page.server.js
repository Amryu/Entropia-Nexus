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

  const videos = [];
  for (const c of creators) {
    if (c.platform !== 'youtube') continue;
    const vids = c.cached_data?.playlistVideos?.length > 0 ? c.cached_data.playlistVideos : (c.cached_data?.recentVideos || []);
    for (const v of vids) {
      videos.push({
        videoId: v.videoId,
        title: v.title,
        thumbnail: v.thumbnail,
        publishedAt: v.publishedAt,
        creatorName: getDisplayName(c),
        creatorAvatar: getAvatar(c),
        channelUrl: c.channel_url
      });
    }
  }

  videos.sort((a, b) => new Date(b.publishedAt) - new Date(a.publishedAt));

  return { videos };
}
