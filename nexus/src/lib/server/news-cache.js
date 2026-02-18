// @ts-nocheck
/**
 * Steam News sync for Entropia Universe (App ID 3642750).
 * Fetches official news from Steam and persists to the announcements table.
 * Includes BBCode-to-HTML conversion for content storage.
 */
import { getSteamNewsCount, upsertSteamNews } from '$lib/server/db.js';

const STEAM_APP_ID = 3642750;
const STEAM_API_BASE = `https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=${STEAM_APP_ID}&feeds=steam_community_announcements&maxlength=0`;
const STEAM_SYNC_INTERVAL_MS = 30 * 60 * 1000; // 30 minutes
const STEAM_FETCH_COUNT = 100;
const SUMMARY_MAX_LENGTH = 300;

let lastSyncAt = 0;
let syncing = false;

/**
 * Convert Steam BBCode to HTML.
 * @param {string} bbcode - Raw BBCode content from Steam API
 * @returns {string} HTML content
 */
export function convertBBCodeToHtml(bbcode) {
  if (!bbcode) return '';
  let html = bbcode;

  // Simple tag replacements
  const tagMap = [
    [/\[b\]([\s\S]*?)\[\/b\]/gi, '<strong>$1</strong>'],
    [/\[i\]([\s\S]*?)\[\/i\]/gi, '<em>$1</em>'],
    [/\[u\]([\s\S]*?)\[\/u\]/gi, '<u>$1</u>'],
    [/\[s\]([\s\S]*?)\[\/s\]/gi, '<s>$1</s>'],
    [/\[strike\]([\s\S]*?)\[\/strike\]/gi, '<s>$1</s>'],
    [/\[h1\]([\s\S]*?)\[\/h1\]/gi, '<h1>$1</h1>'],
    [/\[h2\]([\s\S]*?)\[\/h2\]/gi, '<h2>$1</h2>'],
    [/\[h3\]([\s\S]*?)\[\/h3\]/gi, '<h3>$1</h3>'],
    [/\[p\]([\s\S]*?)\[\/p\]/gi, '<p>$1</p>'],
    [/\[code\]([\s\S]*?)\[\/code\]/gi, '<pre><code>$1</code></pre>'],
    [/\[hr\]/gi, '<hr>'],
  ];

  for (const [pattern, replacement] of tagMap) {
    html = html.replace(pattern, replacement);
  }

  // URLs: [url=X]text[/url] and [url]X[/url]
  html = html.replace(/\[url=([^\]]+)\]([\s\S]*?)\[\/url\]/gi,
    '<a href="$1" target="_blank" rel="noopener">$2</a>');
  html = html.replace(/\[url\]([\s\S]*?)\[\/url\]/gi,
    '<a href="$1" target="_blank" rel="noopener">$1</a>');

  // Images
  html = html.replace(/\[img\]([\s\S]*?)\[\/img\]/gi, '<img src="$1" />');

  // Lists
  html = html.replace(/\[list\]([\s\S]*?)\[\/list\]/gi, (_, content) => {
    const items = content.replace(/\[\/\*\]/gi, '').split(/\[\*\]/).filter(s => s.trim());
    return '<ul>' + items.map(item => `<li>${item.trim()}</li>`).join('') + '</ul>';
  });
  html = html.replace(/\[olist\]([\s\S]*?)\[\/olist\]/gi, (_, content) => {
    const items = content.replace(/\[\/\*\]/gi, '').split(/\[\*\]/).filter(s => s.trim());
    return '<ol>' + items.map(item => `<li>${item.trim()}</li>`).join('') + '</ol>';
  });

  // YouTube embeds: [previewyoutube=ID;full][/previewyoutube]
  html = html.replace(/\[previewyoutube=([^;\]]+)[^\]]*\][\s\S]*?\[\/previewyoutube\]/gi,
    '<div style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;margin:1em 0"><iframe src="https://www.youtube.com/embed/$1" style="position:absolute;top:0;left:0;width:100%;height:100%" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>');

  // Tables
  html = html.replace(/\[table\]([\s\S]*?)\[\/table\]/gi, '<table>$1</table>');
  html = html.replace(/\[tr\]([\s\S]*?)\[\/tr\]/gi, '<tr>$1</tr>');
  html = html.replace(/\[th\]([\s\S]*?)\[\/th\]/gi, '<th>$1</th>');
  html = html.replace(/\[td\]([\s\S]*?)\[\/td\]/gi, '<td>$1</td>');

  // Remove any remaining BBCode tags we don't recognize
  html = html.replace(/\[\/?[a-z*][^\]]*\]/gi, '');

  // Convert newlines to <br> (but not inside block elements)
  html = html.replace(/\n/g, '<br>');

  // Clean up excessive <br> after block elements
  html = html.replace(/(<\/(?:p|h[1-6]|ul|ol|li|pre|hr|table|tr|th|td|div)>)\s*(?:<br>)+/gi, '$1');
  html = html.replace(/(?:<br>)+\s*(<(?:p|h[1-6]|ul|ol|li|pre|hr|table|tr|th|td|div)[\s>])/gi, '$1');

  return html.trim();
}

/**
 * Strip BBCode tags to produce a plain-text summary.
 * @param {string} bbcode - Raw BBCode content
 * @param {number} maxLength - Maximum summary length
 * @returns {string} Plain text summary
 */
function bbcodeToPlainText(bbcode, maxLength = SUMMARY_MAX_LENGTH) {
  if (!bbcode) return '';
  let text = bbcode
    .replace(/\[previewyoutube=[^\]]*\][\s\S]*?\[\/previewyoutube\]/gi, '')
    .replace(/\[img\][^\[]*\[\/img\]/gi, '')
    .replace(/\[url=([^\]]+)\]([\s\S]*?)\[\/url\]/gi, '$2')
    .replace(/\[url\]([\s\S]*?)\[\/url\]/gi, '$1')
    .replace(/\[\/?[a-z*][^\]]*\]/gi, '')
    .replace(/\n+/g, ' ')
    .trim();
  if (text.length > maxLength) {
    text = text.substring(0, maxLength).replace(/\s+\S*$/, '') + '...';
  }
  return text;
}

/**
 * Fetch Steam news items from the API.
 * @param {number} count - Number of items to fetch
 * @param {number} [endDate] - Only return items before this Unix timestamp
 * @returns {Promise<Array>} Raw Steam news items
 */
async function fetchSteamNewsPage(count = STEAM_FETCH_COUNT, endDate = undefined) {
  let url = `${STEAM_API_BASE}&count=${count}`;
  if (endDate) url += `&enddate=${endDate}`;

  const response = await fetch(url);
  if (!response.ok) throw new Error(`Steam API returned ${response.status}`);
  const data = await response.json();

  return (data.appnews?.newsitems || [])
    .filter(item => item.feedlabel === 'Community Announcements');
}

/**
 * Sync Steam news to the announcements table.
 * On first run (no Steam items in DB), does a full historical backfill.
 * On subsequent runs, fetches the latest batch.
 */
export async function syncSteamNews() {
  if (syncing) return;
  const now = Date.now();
  if (now - lastSyncAt < STEAM_SYNC_INTERVAL_MS) return;

  syncing = true;
  try {
    const existingCount = await getSteamNewsCount();
    const isBackfill = existingCount === 0;

    if (isBackfill) {
      console.log('[news-sync] No Steam news in DB, starting historical backfill...');
      await backfillSteamNews();
    } else {
      const items = await fetchSteamNewsPage(STEAM_FETCH_COUNT);
      let inserted = 0;
      for (const item of items) {
        const result = await upsertSteamNews({
          title: item.title,
          summary: bbcodeToPlainText(item.contents),
          link: item.url,
          content_html: convertBBCodeToHtml(item.contents),
          source_id: item.gid,
          created_at: new Date(item.date * 1000)
        });
        if (result) inserted++;
      }
      if (inserted > 0) {
        console.log(`[news-sync] Synced ${inserted} Steam news items`);
      }
    }
    lastSyncAt = Date.now();
  } catch (err) {
    console.error('[news-sync] Failed to sync Steam news:', err.message);
  } finally {
    syncing = false;
  }
}

/**
 * Fetch all historical Steam news by paginating with enddate.
 */
async function backfillSteamNews() {
  let endDate = undefined;
  let totalInserted = 0;
  let pageNum = 0;

  while (true) {
    pageNum++;
    const items = await fetchSteamNewsPage(STEAM_FETCH_COUNT, endDate);
    if (items.length === 0) break;

    for (const item of items) {
      await upsertSteamNews({
        title: item.title,
        summary: bbcodeToPlainText(item.contents),
        link: item.url,
        content_html: convertBBCodeToHtml(item.contents),
        source_id: item.gid,
        created_at: new Date(item.date * 1000)
      });
      totalInserted++;
    }

    // Use oldest item's date as enddate for next page
    const oldestDate = Math.min(...items.map(i => i.date));
    if (endDate && oldestDate >= endDate) break; // no progress
    endDate = oldestDate;

    console.log(`[news-sync] Backfill page ${pageNum}: ${items.length} items (total: ${totalInserted})`);

    // Small delay to be kind to Steam API
    await new Promise(resolve => setTimeout(resolve, 500));
  }

  console.log(`[news-sync] Backfill complete: ${totalInserted} Steam news items imported`);
}

/**
 * Transform announcement rows into the unified news feed format.
 * @param {Array} announcements - Rows from getPublishedAnnouncements
 * @returns {Array} Normalized news items for display
 */
export function formatNewsFeed(announcements) {
  return announcements.map(a => ({
    source: a.source || 'nexus',
    id: a.id,
    title: a.title,
    summary: a.summary,
    url: (a.has_content || a.source === 'steam') ? `/news/${a.id}` : a.link,
    image_url: a.image_url,
    pinned: a.pinned,
    has_content: !!a.has_content || a.source === 'steam',
    date: a.created_at
  }));
}
