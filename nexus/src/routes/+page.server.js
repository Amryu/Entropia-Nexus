// @ts-nocheck
import { getPublishedAnnouncements, getUpcomingEvents, getActiveCreators, pool } from '$lib/server/db.js';
import { formatNewsFeed } from '$lib/server/news-cache.js';
import { getActivePromos, bufferPromoView } from '$lib/server/promo-cache.js';

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

  // Collect YouTube videos: 1 per creator, more if fewer than 6 creators
  const ytCreators = creators
    .filter(c => c.platform === 'youtube' &&
      ((c.cached_data?.playlistVideos?.length > 0) || (c.cached_data?.recentVideos?.length > 0)))
    .sort((a, b) => a.display_order - b.display_order);

  if (ytCreators.length > 0) {
    const videosPerCreator = ytCreators.length < 6
      ? Math.ceil(MAX_VIDEOS / ytCreators.length)
      : 1;

    const allCandidates = [];
    for (const c of ytCreators) {
      const src = c.cached_data.playlistVideos?.length > 0 ? c.cached_data.playlistVideos : c.cached_data.recentVideos;
      const vids = (src || []).slice(0, videosPerCreator);
      for (const v of vids) {
        allCandidates.push({
          videoId: v.videoId,
          title: v.title,
          thumbnail: v.thumbnail,
          publishedAt: v.publishedAt,
          creatorName: getDisplayName(c),
          creatorAvatar: getAvatar(c),
          channelUrl: c.channel_url,
          displayOrder: c.display_order
        });
      }
    }

    // Sort: display_order ASC, then publishedAt DESC
    allCandidates.sort((a, b) => {
      if (a.displayOrder !== b.displayOrder) return a.displayOrder - b.displayOrder;
      return new Date(b.publishedAt) - new Date(a.publishedAt);
    });

    videos.push(...allCandidates.slice(0, MAX_VIDEOS));
  }

  return {
    streams: streams.slice(0, MAX_STREAMS),
    videos
  };
}

async function getRecentGlobals(limit = 15) {
  try {
    const { rows } = await pool.query(
      `SELECT id, global_type, player_name, target_name, value, value_unit,
              location, is_hof, is_ath, event_timestamp,
              mob_id, maturity_id, extra
       FROM ingested_globals
       WHERE confirmed = true
       ORDER BY event_timestamp DESC
       LIMIT $1`,
      [limit]
    );
    return rows.map(r => ({
      id: r.id,
      type: r.global_type,
      player: r.player_name,
      target: r.target_name,
      value: parseFloat(r.value),
      unit: r.value_unit,
      location: r.location,
      hof: r.is_hof,
      ath: r.is_ath,
      timestamp: r.event_timestamp,
      mob_id: r.mob_id,
      maturity_id: r.maturity_id,
      extra: r.extra,
    }));
  } catch {
    return [];
  }
}

export async function load(event) {
  const [announcements, events, creators, globals, promos] = await Promise.all([
    getPublishedAnnouncements(5),
    getUpcomingEvents(5),
    getActiveCreators(),
    getRecentGlobals(15),
    getActivePromos()
  ]);

  const news = formatNewsFeed(announcements);
  const { streams, videos } = processCreators(creators);
  const rotationSeed = Math.floor(Math.random() * 1000);

  // Buffer view impressions for active placements (non-blocking)
  const shownBookingIds = [
    ...promos.placements.left,
    ...promos.placements.right,
    ...promos.featuredPosts
  ].map(p => p.booking_id);
  if (shownBookingIds.length > 0) {
    bufferPromoView(shownBookingIds, event).catch(() => {});
  }

  return {
    news,
    events,
    streams,
    videos,
    globals,
    promos,
    rotationSeed
  };
}
