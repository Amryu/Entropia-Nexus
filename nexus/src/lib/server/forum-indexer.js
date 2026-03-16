// @ts-nocheck
/**
 * Planet Calypso Forum Trading Indexer.
 * Fetches RSS feeds from the Selling and Buying sub-forums,
 * matches item names against the market cache, and stores
 * thread data for display across the site.
 */
import https from 'node:https';
import { getSlimNameLookup } from '$lib/market/cache.js';
import {
  upsertForumThread,
  upsertForumThreadItems,
  markStaleForumThreads
} from '$lib/server/db.js';

// ── Constants ──────────────────────────────────────────────────────

const FORUM_FEEDS = [
  { type: 'selling', url: 'https://www.planetcalypsoforum.com/forum/index.php?forums/selling.111/index.rss' },
  { type: 'buying',  url: 'https://www.planetcalypsoforum.com/forum/index.php?forums/buying.112/index.rss' },
];

const FETCH_TIMEOUT_MS = 15_000;
const INTER_FEED_DELAY_MS = 200;
const MIN_ITEM_NAME_LENGTH = 4;
const SNIPPET_MAX_LENGTH = 200;
const CONTENT_MATCH_LENGTH = 2000;
const STALE_THRESHOLD_DAYS = 90;

const CLOSED_PATTERNS = /\b(CLOSED|SOLD|EXPIRED|BOUGHT|COMPLETE|COMPLETED)\b|\[Closed\]|\[SOLD\]/i;
const TITLE_NOISE = /\b(WTS|WTB|WTT|WTS\/T|WTB\/T|WTS\/WTT|SELLING|BUYING|PRICE\s*CHECK|PC|P\/C)\b/gi;

// Word boundary characters for item name matching
const BOUNDARY_CHARS = new Set([' ', ',', '/', '+', '|', '(', ')', '[', ']', '.', ':', ';', '-', '!', '?', '\t', '\n']);

// Common words that happen to be item names but cause false positives in forum context
const BLOCKLIST = new Set([
  'knight', 'king', 'queen', 'mark', 'angel', 'shadow', 'star', 'nova',
  'genesis', 'fury', 'doom', 'rage', 'iron', 'gold', 'silver', 'copper',
  'stone', 'wood', 'rock', 'sand', 'fire', 'ice', 'price', 'offer',
  'trade', 'sold', 'sale', 'full', 'tier', 'pure', 'rare', 'boss',
  'wolf', 'bear', 'deer', 'hunt', 'mine', 'pilot',
]);

// ── State ──────────────────────────────────────────────────────────

let syncing = false;

/** @type {{ name: string, lower: string, item: any }[] | null} */
let sortedNames = null;

// ── RSS Parsing ────────────────────────────────────────────────────

/**
 * Fetch an RSS feed via node:https.
 * @param {string} url
 * @returns {Promise<string>} Raw XML string
 */
function fetchRss(url) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('RSS fetch timeout')), FETCH_TIMEOUT_MS);
    const req = https.get(url, { headers: { 'User-Agent': 'EntropiaNexus/1.0 (forum-indexer)' } }, (res) => {
      if (res.statusCode !== 200) {
        clearTimeout(timer);
        res.resume();
        reject(new Error(`RSS returned ${res.statusCode}`));
        return;
      }
      let body = '';
      res.on('data', (chunk) => { body += chunk; });
      res.on('end', () => { clearTimeout(timer); resolve(body); });
    });
    req.on('error', (err) => { clearTimeout(timer); reject(err); });
  });
}

/**
 * Decode common HTML entities in text.
 */
function decodeEntities(text) {
  return text
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&#x27;/g, "'")
    .replace(/&apos;/g, "'");
}

/**
 * Strip HTML tags from content to produce plain text.
 * Extracts link text and decodes href URLs so item names
 * embedded in links (e.g. entropianexus.com/items/weapons/Omegaton%20A204) are preserved.
 */
function stripHtml(html) {
  // Replace links with their text + decoded href path for extra matching surface
  let text = html.replace(/<a\s[^>]*href="([^"]*)"[^>]*>([\s\S]*?)<\/a>/gi, (_, href, linkText) => {
    let extra = '';
    try {
      const url = new URL(href, 'http://x');
      const path = decodeURIComponent(url.pathname);
      // Extract last path segment which often contains the item name (with ~ for spaces)
      const seg = path.split('/').pop() || '';
      extra = seg.replace(/~/g, ' ').replace(/[_-]/g, ' ');
    } catch (_) {}
    return ` ${linkText} ${extra} `;
  });
  text = text
    .replace(/<br\s*\/?>/gi, ' ')
    .replace(/<\/?[^>]+(>|$)/g, '')
    .replace(/\s+/g, ' ');
  return text.trim();
}

/**
 * Normalize text for item matching:
 * - Decode HTML entities
 * - Decode URL-encoded characters (%20, %2C, etc.)
 * - Strip square brackets (game copy-paste format: [Item Name])
 * - Normalize unicode whitespace and dashes
 */
function normalizeForMatching(text) {
  let s = decodeEntities(text);
  // Decode URL-encoded sequences (e.g. from links: Omegaton%20A204)
  try { s = decodeURIComponent(s); } catch (_) { /* ignore malformed */ }
  // Strip square brackets: [Item Name] → Item Name
  s = s.replace(/\[([^\]]*)\]/g, ' $1 ');
  // Normalize dashes and special whitespace
  s = s.replace(/\u2013|\u2014/g, '-'); // en/em dash
  s = s.replace(/\u00a0/g, ' '); // nbsp
  s = s.replace(/\s+/g, ' ');
  return s.trim();
}

/**
 * Parse RSS XML into an array of thread objects.
 * @param {string} xml - Raw RSS XML
 * @returns {Array<{ title: string, link: string, threadId: number, author: string, pubDate: Date, content: string, commentCount: number }>}
 */
function parseRss(xml) {
  const items = [];
  const itemRegex = /<item>([\s\S]*?)<\/item>/g;
  let match;

  while ((match = itemRegex.exec(xml)) !== null) {
    const block = match[1];

    const title = decodeEntities(extractTag(block, 'title'));
    const link = extractTag(block, 'link');
    const guid = extractTag(block, 'guid');
    const author = extractTag(block, 'dc:creator');
    const pubDateStr = extractTag(block, 'pubDate');
    const commentStr = extractTag(block, 'slash:comments');

    // Extract content:encoded (in CDATA)
    const contentMatch = block.match(/<content:encoded>\s*<!\[CDATA\[([\s\S]*?)\]\]>\s*<\/content:encoded>/);
    const contentHtml = contentMatch ? contentMatch[1] : '';

    const threadId = parseInt(guid, 10);
    if (!threadId || !title || !link) continue;

    items.push({
      title,
      link,
      threadId,
      author: author || 'Unknown',
      pubDate: pubDateStr ? new Date(pubDateStr) : new Date(),
      content: contentHtml,
      commentCount: parseInt(commentStr, 10) || 0,
    });
  }

  return items;
}

/**
 * Extract the text content of a simple XML tag.
 */
function extractTag(xml, tag) {
  const re = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`, 'i');
  const m = xml.match(re);
  return m ? m[1].trim() : '';
}

// ── Item Name Matching ─────────────────────────────────────────────

/**
 * Build the sorted name list from the slim name lookup.
 * Sorted longest-first for greedy matching.
 */
function buildSortedNames() {
  const lookup = getSlimNameLookup();
  if (!lookup) return null;

  const names = [];
  for (const [lower, item] of lookup.entries()) {
    if (lower.length < MIN_ITEM_NAME_LENGTH) continue;
    // Skip single-word names that are common English words
    if (!lower.includes(' ') && BLOCKLIST.has(lower)) continue;
    names.push({ name: item.n, lower, item });
  }

  // Sort longest first so greedy matching prefers longer names
  names.sort((a, b) => b.lower.length - a.lower.length);
  return names;
}

/**
 * Check if a match at [start, end) has clean word boundaries.
 * The character before start and the character at end must be boundary chars
 * (or the match must be at the start/end of string).
 */
function hasWordBoundaries(text, start, end) {
  const leftOk = start === 0 || BOUNDARY_CHARS.has(text[start - 1]);
  const rightOk = end >= text.length || BOUNDARY_CHARS.has(text[end]);
  return leftOk && rightOk;
}

/**
 * Match item names in text using greedy longest-match.
 * Names are checked longest-first so "Adjusted Melee Trauma Amplifier"
 * matches before "Melee Trauma Amplifier" or "Trauma Amplifier".
 * Matched regions are masked to prevent shorter substring items from
 * matching inside already-matched names.
 *
 * @param {string} text - Text to search in
 * @param {string} source - 'title' or 'content'
 * @returns {Array<{ itemId: number, itemName: string, matchSource: string }>}
 */
function matchItems(text, source) {
  if (!sortedNames) {
    sortedNames = buildSortedNames();
    if (!sortedNames) return [];
  }

  const lower = text.toLowerCase();
  const matched = [];
  // Mask array to prevent sub-matches in already-matched regions
  const mask = new Uint8Array(lower.length);

  for (const entry of sortedNames) {
    const nameLen = entry.lower.length;
    let searchFrom = 0;

    while (searchFrom <= lower.length - nameLen) {
      const idx = lower.indexOf(entry.lower, searchFrom);
      if (idx === -1) break;

      const endIdx = idx + nameLen;

      // Check the region isn't already masked (even partially)
      let masked = false;
      for (let k = idx; k < endIdx; k++) {
        if (mask[k]) { masked = true; break; }
      }
      if (masked) {
        searchFrom = idx + 1;
        continue;
      }

      // Require clean word boundaries on both sides
      if (hasWordBoundaries(lower, idx, endIdx)) {
        // Mask the region to prevent sub-matches
        for (let k = idx; k < endIdx; k++) mask[k] = 1;
        matched.push({
          itemId: entry.item.i,
          itemName: entry.name,
          matchSource: source,
        });
        break; // Only record each name once per text
      }

      searchFrom = idx + 1;
    }
  }

  return matched;
}

// ── Fuzzy Matching (misspellings) ──────────────────────────────────

const MIN_FUZZY_NAME_LENGTH = 8;
const MAX_EDIT_DISTANCE = 2;

/**
 * Compute Levenshtein edit distance between two strings.
 * Bails early if distance exceeds max.
 */
function editDistance(a, b, max) {
  if (Math.abs(a.length - b.length) > max) return max + 1;
  const m = a.length, n = b.length;
  let prev = new Uint8Array(n + 1);
  let curr = new Uint8Array(n + 1);
  for (let j = 0; j <= n; j++) prev[j] = j;
  for (let i = 1; i <= m; i++) {
    curr[0] = i;
    let minInRow = i;
    for (let j = 1; j <= n; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      curr[j] = Math.min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost);
      if (curr[j] < minInRow) minInRow = curr[j];
    }
    if (minInRow > max) return max + 1;
    [prev, curr] = [curr, prev];
  }
  return prev[n];
}

/**
 * Build a map of item name words for fuzzy matching.
 * Groups items by their first word for efficient lookup.
 * @type {Map<string, Array<{ name: string, lower: string, item: any }>> | null}
 */
let fuzzyIndex = null;

function buildFuzzyIndex() {
  if (!sortedNames) return null;
  const index = new Map();
  for (const entry of sortedNames) {
    if (entry.lower.length < MIN_FUZZY_NAME_LENGTH) continue;
    const firstWord = entry.lower.split(/[\s,]+/)[0];
    if (!index.has(firstWord)) index.set(firstWord, []);
    index.get(firstWord).push(entry);
  }
  return index;
}

/**
 * Fuzzy match item names in text after exact matching has been done.
 * Only matches names >= 8 chars with edit distance <= 2.
 * @param {string} text - The text to search (already lowercased)
 * @param {string} source - 'title' or 'content'
 * @param {Set<number>} alreadyMatched - Item IDs already matched exactly
 * @returns {Array<{ itemId: number, itemName: string, matchSource: string }>}
 */
function fuzzyMatchItems(text, source, alreadyMatched) {
  if (!fuzzyIndex) {
    fuzzyIndex = buildFuzzyIndex();
    if (!fuzzyIndex) return [];
  }

  const lower = text.toLowerCase();
  const words = lower.split(/[\s,;:!?|/+()]+/).filter(w => w.length >= 3);
  const matched = [];
  const seen = new Set();

  for (let wi = 0; wi < words.length; wi++) {
    const word = words[wi];

    // Check each fuzzy index entry whose first word is close to this word
    for (const [firstWord, entries] of fuzzyIndex) {
      if (editDistance(word, firstWord, MAX_EDIT_DISTANCE) > MAX_EDIT_DISTANCE) continue;

      for (const entry of entries) {
        if (alreadyMatched.has(entry.item.i) || seen.has(entry.item.i)) continue;

        // Build the candidate substring from text starting at this word position
        const nameWords = entry.lower.split(/[\s,]+/);
        if (wi + nameWords.length > words.length) continue;

        const candidateWords = words.slice(wi, wi + nameWords.length);
        let totalDist = 0;
        let valid = true;
        for (let k = 0; k < nameWords.length; k++) {
          const d = editDistance(candidateWords[k], nameWords[k], MAX_EDIT_DISTANCE);
          totalDist += d;
          if (d > MAX_EDIT_DISTANCE || totalDist > MAX_EDIT_DISTANCE) { valid = false; break; }
        }

        if (valid && totalDist > 0) { // totalDist > 0 means it's actually fuzzy (not exact, which was already handled)
          seen.add(entry.item.i);
          matched.push({
            itemId: entry.item.i,
            itemName: entry.name,
            matchSource: source,
          });
        }
      }
    }
  }

  return matched;
}

/**
 * Match items in a thread's title and content.
 */
function matchThreadItems(title, contentHtml) {
  // Clean and normalize the title
  const cleanedTitle = normalizeForMatching(title.replace(TITLE_NOISE, ''));
  const titleMatches = matchItems(cleanedTitle, 'title');

  // Normalize content: strip HTML, decode entities/URLs, strip brackets
  const rawContent = stripHtml(contentHtml).substring(0, CONTENT_MATCH_LENGTH);
  const contentText = normalizeForMatching(rawContent);
  const contentMatches = matchItems(contentText, 'content');

  // Merge: title matches take priority, content adds new items only
  const seen = new Set(titleMatches.map(m => m.itemId));
  const merged = [...titleMatches];
  for (const cm of contentMatches) {
    if (!seen.has(cm.itemId)) {
      seen.add(cm.itemId);
      merged.push(cm);
    }
  }

  // Fuzzy matching pass for misspellings (title + content)
  const fuzzyTitle = fuzzyMatchItems(cleanedTitle, 'title', seen);
  for (const fm of fuzzyTitle) {
    if (!seen.has(fm.itemId)) { seen.add(fm.itemId); merged.push(fm); }
  }
  const fuzzyContent = fuzzyMatchItems(contentText, 'content', seen);
  for (const fm of fuzzyContent) {
    if (!seen.has(fm.itemId)) { seen.add(fm.itemId); merged.push(fm); }
  }

  return merged;
}

// ── Content Snippet ────────────────────────────────────────────────

/**
 * Generate a plain-text snippet from HTML content.
 */
function generateSnippet(contentHtml) {
  if (!contentHtml) return null;
  let text = stripHtml(contentHtml);
  if (text.length > SNIPPET_MAX_LENGTH) {
    text = text.substring(0, SNIPPET_MAX_LENGTH).replace(/\s+\S*$/, '') + '...';
  }
  return text || null;
}

// ── Sync ───────────────────────────────────────────────────────────

/**
 * Main sync function. Fetches RSS feeds and upserts threads + item matches.
 */
export async function syncForumTrading() {
  if (syncing) return;
  syncing = true;
  try {
    // Rebuild name list each sync in case market cache was updated
    sortedNames = buildSortedNames();
    fuzzyIndex = sortedNames ? buildFuzzyIndex() : null;

    let totalUpserted = 0;
    let totalMatches = 0;

    for (const feed of FORUM_FEEDS) {
      try {
        const xml = await fetchRss(feed.url);
        const items = parseRss(xml);

        for (let i = 0; i < items.length; i++) {
          const item = items[i];
          const isClosed = CLOSED_PATTERNS.test(item.title);
          const snippet = generateSnippet(item.content);

          const row = await upsertForumThread({
            thread_id: item.threadId,
            forum_type: feed.type,
            title: item.title,
            author: item.author,
            url: item.link,
            content_snippet: snippet,
            comment_count: item.commentCount,
            is_closed: isClosed,
            created_at: item.pubDate,
            feed_position: i,
          });

          if (row && sortedNames) {
            const matches = matchThreadItems(item.title, item.content);
            if (matches.length > 0) {
              await upsertForumThreadItems(row.id, matches);
              totalMatches += matches.length;
            }
          }

          totalUpserted++;
        }
      } catch (err) {
        console.error(`[forum-indexer] Error fetching ${feed.type} feed:`, err.message);
      }

      // Small delay between feeds
      if (feed !== FORUM_FEEDS[FORUM_FEEDS.length - 1]) {
        await new Promise(resolve => setTimeout(resolve, INTER_FEED_DELAY_MS));
      }
    }

    // Mark threads not seen for 90 days as closed
    await markStaleForumThreads(STALE_THRESHOLD_DAYS);

    if (totalUpserted > 0) {
      console.log(`[forum-indexer] Synced ${totalUpserted} threads, ${totalMatches} item matches`);
    }

  } catch (err) {
    console.error('[forum-indexer] Sync failed:', err.message);
  } finally {
    syncing = false;
  }
}
