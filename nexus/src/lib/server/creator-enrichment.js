// @ts-nocheck
/**
 * Creator enrichment — fetches data from YouTube and Twitch APIs
 * to enrich content creator profiles with live/cached data.
 *
 * YouTube: RSS feed for latest video + Data API v3 for channel info
 * Twitch: Helix API for profile + live stream status
 * Kick: No official API — static data only
 */

import { updateCreator } from '$lib/server/db.js';

const YOUTUBE_API_KEY = process.env.YOUTUBE_API_KEY || '';
const TWITCH_CLIENT_ID = process.env.TWITCH_CLIENT_ID || '';
const TWITCH_CLIENT_SECRET = process.env.TWITCH_CLIENT_SECRET || '';

// Twitch app access token cache
let twitchAccessToken = null;
let twitchTokenExpiresAt = 0;

// ============================================
// YouTube enrichment
// ============================================

async function fetchYouTubeData(channelId, playlistId) {
  if (!channelId && !playlistId) return null;

  const data = {};

  // 1. RSS feed for recent videos (free, no API key needed)
  try {
    const rssUrl = playlistId
      ? `https://www.youtube.com/feeds/videos.xml?playlist_id=${playlistId}`
      : `https://www.youtube.com/feeds/videos.xml?channel_id=${channelId}`;
    const rssResponse = await fetch(rssUrl);
    if (rssResponse.ok) {
      const xml = await rssResponse.text();
      const entries = xml.match(/<entry>[\s\S]*?<\/entry>/g);
      if (entries && entries.length > 0) {
        data.recentVideos = [];
        for (const entry of entries.slice(0, 6)) {
          const videoId = entry.match(/<yt:videoId>([^<]+)<\/yt:videoId>/)?.[1];
          const title = entry.match(/<title>([^<]+)<\/title>/)?.[1];
          const published = entry.match(/<published>([^<]+)<\/published>/)?.[1];
          if (videoId && title) {
            data.recentVideos.push({
              videoId,
              title,
              thumbnail: `https://i.ytimg.com/vi/${videoId}/mqdefault.jpg`,
              publishedAt: published
            });
          }
        }
        // Keep latestVideo for backward compatibility
        if (data.recentVideos.length > 0) {
          data.latestVideo = data.recentVideos[0];
        }
      }
    }
  } catch (err) {
    console.error(`[creator-enrichment] YouTube RSS failed for ${channelId}:`, err.message);
  }

  // 2. Data API v3 for channel info (3 quota units per call)
  if (YOUTUBE_API_KEY) {
    try {
      const apiUrl = `https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics&id=${channelId}&key=${YOUTUBE_API_KEY}`;
      const apiResponse = await fetch(apiUrl);
      if (apiResponse.ok) {
        const apiData = await apiResponse.json();
        const channel = apiData.items?.[0];
        if (channel) {
          data.channelName = channel.snippet.title;
          data.channelAvatar = channel.snippet.thumbnails?.default?.url || null;
          data.subscriberCount = parseInt(channel.statistics.subscriberCount, 10) || 0;
        }
      }
    } catch (err) {
      console.error(`[creator-enrichment] YouTube API failed for ${channelId}:`, err.message);
    }
  }

  return Object.keys(data).length > 0 ? data : null;
}

// ============================================
// Twitch enrichment
// ============================================

async function getTwitchAccessToken() {
  if (twitchAccessToken && Date.now() < twitchTokenExpiresAt) {
    return twitchAccessToken;
  }

  if (!TWITCH_CLIENT_ID || !TWITCH_CLIENT_SECRET) return null;

  const response = await fetch('https://id.twitch.tv/oauth2/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_id: TWITCH_CLIENT_ID,
      client_secret: TWITCH_CLIENT_SECRET,
      grant_type: 'client_credentials'
    })
  });

  if (!response.ok) throw new Error(`Twitch OAuth failed: ${response.status}`);

  const data = await response.json();
  twitchAccessToken = data.access_token;
  // Expire 5 minutes early to be safe
  twitchTokenExpiresAt = Date.now() + (data.expires_in - 300) * 1000;
  return twitchAccessToken;
}

function extractTwitchLogin(channelUrl) {
  // Extract login from URLs like https://twitch.tv/username or https://www.twitch.tv/username
  const match = channelUrl.match(/twitch\.tv\/([a-zA-Z0-9_]+)/);
  return match ? match[1].toLowerCase() : null;
}

async function fetchTwitchData(creator) {
  const login = creator.channel_id || extractTwitchLogin(creator.channel_url);
  if (!login) return null;

  const token = await getTwitchAccessToken();
  if (!token) return null;

  const headers = {
    'Client-ID': TWITCH_CLIENT_ID,
    'Authorization': `Bearer ${token}`
  };

  const data = { login };

  // 1. User info
  try {
    const userResponse = await fetch(`https://api.twitch.tv/helix/users?login=${login}`, { headers });
    if (userResponse.ok) {
      const userData = await userResponse.json();
      const user = userData.data?.[0];
      if (user) {
        data.displayName = user.display_name;
        data.avatar = user.profile_image_url;
      }
    }
  } catch (err) {
    console.error(`[creator-enrichment] Twitch user API failed for ${login}:`, err.message);
  }

  // 2. Stream status (live check)
  try {
    const streamResponse = await fetch(`https://api.twitch.tv/helix/streams?user_login=${login}`, { headers });
    if (streamResponse.ok) {
      const streamData = await streamResponse.json();
      const stream = streamData.data?.[0];
      if (stream) {
        data.isLive = true;
        data.viewerCount = stream.viewer_count;
        data.gameName = stream.game_name;
        data.streamTitle = stream.title;
        // Stream thumbnail with resolved dimensions (privacy-safe, no cookies)
        data.streamThumbnail = stream.thumbnail_url
          ?.replace('{width}', '440').replace('{height}', '248') || null;
      } else {
        data.isLive = false;
        data.viewerCount = 0;
        data.gameName = null;
        data.streamTitle = null;
        data.streamThumbnail = null;
      }
    }
  } catch (err) {
    console.error(`[creator-enrichment] Twitch stream API failed for ${login}:`, err.message);
  }

  return Object.keys(data).length > 0 ? data : null;
}

// ============================================
// Main refresh function
// ============================================

/**
 * Refresh cached data for a single creator.
 * @param {Object} creator - Creator row from DB
 * @returns {Object} Updated creator row
 */
export async function refreshCreator(creator) {
  let cachedData = null;

  if (creator.platform === 'youtube') {
    cachedData = await fetchYouTubeData(creator.channel_id, creator.youtube_playlist_id);
  } else if (creator.platform === 'twitch') {
    cachedData = await fetchTwitchData(creator);
    // Preserve last known stream thumbnail for offline display
    if (cachedData) {
      if (cachedData.isLive && cachedData.streamThumbnail) {
        cachedData.lastStreamThumbnail = cachedData.streamThumbnail;
      } else if (!cachedData.isLive) {
        cachedData.lastStreamThumbnail =
          creator.cached_data?.lastStreamThumbnail ||
          creator.cached_data?.streamThumbnail || null;
      }
    }
  }
  // Kick: no API, skip enrichment

  if (cachedData) {
    // updateCreator handles JSON.stringify for cached_data internally
    return await updateCreator(creator.id, {
      cached_data: cachedData,
      cached_at: new Date().toISOString()
    });
  }

  return creator;
}

/**
 * Refresh all creators with stale cached data.
 * Called periodically by the background loop.
 */
export async function refreshStaleCreators() {
  // Import here to avoid circular dependency issues at startup
  const { getCreatorsForRefresh } = await import('$lib/server/db.js');

  const creators = await getCreatorsForRefresh();
  if (creators.length === 0) return;

  console.log(`[creator-enrichment] Refreshing ${creators.length} stale creators`);

  for (const creator of creators) {
    try {
      await refreshCreator(creator);
    } catch (err) {
      console.error(`[creator-enrichment] Failed to refresh creator ${creator.id} (${creator.name}):`, err.message);
    }
  }
}
