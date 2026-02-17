// @ts-nocheck
/**
 * Steam News API cache for Entropia Universe (App ID 3642750).
 * Fetches official news from Steam and caches in memory with a 30-minute TTL.
 * Returns stale data on fetch failure.
 */

const STEAM_APP_ID = 3642750;
const STEAM_NEWS_COUNT = 10;
const STEAM_NEWS_MAX_LENGTH = 300;
const STEAM_NEWS_URL = `https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=${STEAM_APP_ID}&count=${STEAM_NEWS_COUNT}&maxlength=${STEAM_NEWS_MAX_LENGTH}`;
const STEAM_NEWS_REFRESH_MS = 30 * 60 * 1000; // 30 minutes

let steamNewsCache = {
  items: [],
  lastFetchAt: 0,
  fetchPromise: null
};

/**
 * Get cached Steam news items. Fetches from the API if the cache is stale.
 * Coalesces concurrent requests to avoid duplicate API calls.
 * @returns {Promise<Array>} Array of normalized news items
 */
export async function getCachedSteamNews() {
  const now = Date.now();
  if (steamNewsCache.items.length > 0 && now - steamNewsCache.lastFetchAt < STEAM_NEWS_REFRESH_MS) {
    return steamNewsCache.items;
  }

  // Coalesce concurrent requests
  if (steamNewsCache.fetchPromise) return steamNewsCache.fetchPromise;

  steamNewsCache.fetchPromise = fetchSteamNews()
    .then(items => {
      steamNewsCache.items = items;
      steamNewsCache.lastFetchAt = Date.now();
      steamNewsCache.fetchPromise = null;
      return items;
    })
    .catch(err => {
      console.error('[news-cache] Failed to fetch Steam news:', err.message);
      steamNewsCache.fetchPromise = null;
      return steamNewsCache.items; // return stale data on error
    });

  return steamNewsCache.fetchPromise;
}

async function fetchSteamNews() {
  const response = await fetch(STEAM_NEWS_URL);
  if (!response.ok) throw new Error(`Steam API returned ${response.status}`);
  const data = await response.json();

  return (data.appnews?.newsitems || [])
    .filter(item => item.feedlabel === 'Community Announcements')
    .map(item => ({
      source: 'steam',
      id: item.gid,
      title: item.title,
      summary: item.contents,
      url: item.url,
      author: item.author,
      date: new Date(item.date * 1000).toISOString()
    }));
}

/**
 * Merge Nexus announcements with Steam news items into a unified feed.
 * Pinned Nexus items appear first, then all items sorted by date descending.
 * @param {Array} announcements - Published Nexus announcements from DB
 * @param {Array} steamItems - Normalized Steam news items
 * @param {number} limit - Maximum items to return
 * @returns {Array} Merged and sorted news feed
 */
export function mergeAndSortNews(announcements, steamItems, limit = 6) {
  const nexusItems = announcements.map(a => ({
    source: 'nexus',
    id: a.id,
    title: a.title,
    summary: a.summary,
    url: a.has_content ? `/news/${a.id}` : a.link,
    image_url: a.image_url,
    pinned: a.pinned,
    has_content: !!a.has_content,
    date: a.created_at
  }));

  const merged = [...nexusItems, ...steamItems];

  // Pinned items first, then by date descending
  merged.sort((a, b) => {
    if (a.pinned && !b.pinned) return -1;
    if (!a.pinned && b.pinned) return 1;
    return new Date(b.date) - new Date(a.date);
  });

  return merged.slice(0, limit);
}
