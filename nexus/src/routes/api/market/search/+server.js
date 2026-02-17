// @ts-nocheck
/**
 * GET /api/market/search?query=<text>
 *
 * Unified market search across exchange, services, auctions, rentals, and shops.
 * Returns scored results with type badges, price info, and navigation URLs.
 */
import { getResponse, apiCall, encodeURIComponentSafe } from '$lib/util.js';
import { getExchangeCategorizationSummary } from '$lib/market/cache.js';
import { ABSOLUTE_MARKUP_MATERIAL_TYPES, isPercentMarkupType } from '$lib/common/itemTypes.js';

const MAX_RESULTS = 20;
const MIN_QUERY_LENGTH = 2;
const MAX_QUERY_LENGTH = 100;

// Scoring constants
const NAME_MATCH_BASE = 100;
const DESCRIPTION_MATCH_BASE = 40;
const EXACT_START_BONUS = 50;
const HAS_ORDERS_BONUS = 30;

/**
 * Score a query against a text field.
 * Returns 0 if no match, otherwise a positive score.
 */
function scoreMatch(text, query, baseScore) {
  if (!text) return 0;
  const lowerText = text.toLowerCase();
  const lowerQuery = query.toLowerCase();

  const idx = lowerText.indexOf(lowerQuery);
  if (idx === -1) return 0;

  let score = baseScore;

  // Bonus for match at start of string
  if (idx === 0) {
    score += EXACT_START_BONUS;
  }
  // Bonus for match at start of a word
  else if (lowerText[idx - 1] === ' ' || lowerText[idx - 1] === '-' || lowerText[idx - 1] === '(') {
    score += EXACT_START_BONUS * 0.6;
  }

  // Slight bonus for shorter names (more relevant)
  score += Math.max(0, 20 - text.length * 0.2);

  return score;
}

/**
 * Flatten the categorized exchange tree into a list of slim items.
 */
function flattenExchangeTree(node, results) {
  if (Array.isArray(node)) {
    for (const item of node) {
      results.push(item);
    }
    return;
  }
  if (node && typeof node === 'object') {
    for (const child of Object.values(node)) {
      flattenExchangeTree(child, results);
    }
  }
}

/**
 * Format exchange price/markup for display.
 */
function formatExchangePrice(item) {
  const median = item.m;
  const maxTT = item.v;
  const subType = item.st;

  if (median == null || median <= 0) return null;

  // Absolute markup items (Deeds, Tokens, Shares) — show PED value
  if (subType && ABSOLUTE_MARKUP_MATERIAL_TYPES.has(subType)) {
    return `${median.toFixed(2)} PED`;
  }

  // Percent-markup items (stackables, (L) blueprints, (L) condition items):
  // median IS the markup percentage directly (e.g., 102.50 = 102.50%)
  if (isPercentMarkupType(item.t, item.n, subType)) {
    return `${median.toFixed(0)}% MU`;
  }

  // Absolute markup (condition items): median is +PED over TT, convert to %
  if (maxTT != null && maxTT > 0) {
    const pct = Math.round(((maxTT + median) / maxTT) * 100);
    return `${pct}% MU`;
  }

  return null;
}

/**
 * Format order counts for exchange items.
 */
function formatExchangeDetail(item) {
  const parts = [];
  if (item.s > 0) parts.push(`${item.s} sell`);
  if (item.b > 0) parts.push(`${item.b} buy`);
  return parts.length > 0 ? parts.join(' · ') : null;
}

/**
 * Search exchange items from the in-memory cache.
 */
async function searchExchange(query, fetch) {
  const summary = await getExchangeCategorizationSummary(fetch);
  if (!summary) return [];

  const allItems = [];
  flattenExchangeTree(summary, allItems);

  const results = [];
  for (const item of allItems) {
    if (!item.n) continue;

    const nameScore = scoreMatch(item.n, query, NAME_MATCH_BASE);
    if (nameScore <= 0) continue;

    // Bonus for items with active orders
    const hasOrders = (item.b > 0 || item.s > 0);
    const score = nameScore + (hasOrders ? HAS_ORDERS_BONUS : 0);

    results.push({
      id: `exchange:${item.i}`,
      name: item.n,
      marketType: 'exchange',
      entityType: item.t || null,
      price: formatExchangePrice(item),
      detail: formatExchangeDetail(item),
      url: `/market/exchange/listings/${item.i}`,
      score
    });
  }

  return results;
}

/**
 * Search services.
 */
async function searchServices(query, fetch) {
  const services = await apiCall(fetch, '/api/services');
  if (!Array.isArray(services)) return [];

  const results = [];
  for (const svc of services) {
    const nameScore = scoreMatch(svc.title, query, NAME_MATCH_BASE);
    const descScore = scoreMatch(svc.description, query, DESCRIPTION_MATCH_BASE);
    const score = Math.max(nameScore, descScore);
    if (score <= 0) continue;

    results.push({
      id: `service:${svc.id}`,
      name: svc.title,
      marketType: 'service',
      entityType: svc.type || null,
      price: null,
      detail: [svc.type, svc.planet_name].filter(Boolean).join(' · ') || null,
      url: `/market/services/${svc.id}`,
      score
    });
  }

  return results;
}

/**
 * Search auctions (uses server-side ILIKE search).
 */
async function searchAuctions(query, fetch) {
  const result = await apiCall(fetch, `/api/auction?status=active&search=${encodeURIComponent(query)}&limit=10`);
  if (!result?.auctions) return [];

  return result.auctions.map((auction, idx) => {
    const priceStr = auction.buyout_price
      ? `${parseFloat(auction.buyout_price).toFixed(2)} PED buyout`
      : auction.current_bid
        ? `${parseFloat(auction.current_bid).toFixed(2)} PED bid`
        : `${parseFloat(auction.starting_bid).toFixed(2)} PED start`;

    // Give a base score; since the API handles matching, we use position-based scoring
    const nameScore = scoreMatch(auction.title, query, NAME_MATCH_BASE);

    return {
      id: `auction:${auction.id}`,
      name: auction.title,
      marketType: 'auction',
      entityType: null,
      price: priceStr,
      detail: auction.bid_count > 0 ? `${auction.bid_count} bid${auction.bid_count !== 1 ? 's' : ''}` : null,
      url: `/market/auction/${auction.id}`,
      score: nameScore > 0 ? nameScore : NAME_MATCH_BASE - idx
    };
  });
}

/**
 * Search rental offers.
 */
async function searchRentals(query, fetch) {
  const offers = await apiCall(fetch, '/api/rental?limit=100');
  if (!Array.isArray(offers)) return [];

  const results = [];
  for (const offer of offers) {
    const nameScore = scoreMatch(offer.title, query, NAME_MATCH_BASE);
    const descScore = scoreMatch(offer.description, query, DESCRIPTION_MATCH_BASE);
    const score = Math.max(nameScore, descScore);
    if (score <= 0) continue;

    const priceStr = offer.price_per_day
      ? `${parseFloat(offer.price_per_day).toFixed(2)} PED/day`
      : null;

    results.push({
      id: `rental:${offer.id}`,
      name: offer.title,
      marketType: 'rental',
      entityType: null,
      price: priceStr,
      detail: offer.owner_name || null,
      url: `/market/rental/${offer.id}`,
      score
    });
  }

  return results;
}

/**
 * Search shops.
 */
async function searchShops(query, fetch) {
  const shops = await apiCall(fetch, '/shops');
  if (!Array.isArray(shops)) return [];

  const results = [];
  for (const shop of shops) {
    const name = shop.Name || shop.name;
    const nameScore = scoreMatch(name, query, NAME_MATCH_BASE);
    if (nameScore <= 0) continue;

    results.push({
      id: `shop:${shop.Id || shop.id}`,
      name,
      marketType: 'shop',
      entityType: null,
      price: null,
      detail: shop.Planet?.Name || null,
      url: `/market/shops/${encodeURIComponentSafe(name)}`,
      score: nameScore
    });
  }

  return results;
}

export async function GET({ url, fetch }) {
  const query = (url.searchParams.get('query') || '').trim();

  if (query.length < MIN_QUERY_LENGTH) {
    return getResponse({ error: `Query must be at least ${MIN_QUERY_LENGTH} characters` }, 400);
  }

  if (query.length > MAX_QUERY_LENGTH) {
    return getResponse({ error: `Query must be at most ${MAX_QUERY_LENGTH} characters` }, 400);
  }

  try {
    // Search all market types in parallel
    const [exchange, services, auctions, rentals, shops] = await Promise.all([
      searchExchange(query, fetch),
      searchServices(query, fetch),
      searchAuctions(query, fetch),
      searchRentals(query, fetch),
      searchShops(query, fetch)
    ]);

    // Merge and sort by score
    const allResults = [...exchange, ...services, ...auctions, ...rentals, ...shops]
      .sort((a, b) => b.score - a.score)
      .slice(0, MAX_RESULTS);

    return getResponse(allResults, 200);
  } catch (err) {
    console.error('Market search error:', err);
    return getResponse({ error: 'Search failed' }, 500);
  }
}
