// @ts-nocheck
/**
 * GET /api/market/search?query=<text>
 *
 * Unified market search across exchange, services, auctions, rentals, and shops.
 * Uses the standard fuzzy scoring algorithm from $lib/search.js.
 * Searches within item sets (rentals, auctions) and shop inventories.
 * Non-exchange results are preferred via a score bonus.
 */
import { getResponse, apiCall, encodeURIComponentSafe } from '$lib/util.js';
import { getExchangeCategorizationSummary, getSlimItemLookup } from '$lib/market/cache.js';
import { isPercentMarkupType } from '$lib/common/itemTypes.js';
import { scoreSearchResult } from '$lib/search.js';

const MAX_RESULTS = 30;
const MIN_QUERY_LENGTH = 2;
const MAX_QUERY_LENGTH = 100;

// Per-type result limits
const MAX_EXCHANGE_RESULTS = 10;
const MAX_OTHER_RESULTS = 5;

// Scoring adjustments
const HAS_ORDERS_BONUS = 30;
const NON_EXCHANGE_BONUS = 50;
const ITEM_MATCH_PENALTY = 50;
const DESCRIPTION_FACTOR = 0.4;
const MULTI_FIELD_BONUS = 30; // bonus per additional field that also matches

/**
 * Extract all searchable item names from item_set_data JSONB.
 * Handles direct items and armor set pieces.
 */
function extractItemSetNames(itemSetData) {
  if (!itemSetData?.items) return [];
  const names = [];
  for (const item of itemSetData.items) {
    if (item.name) names.push(item.name);
    if (item.setName) names.push(item.setName);
    if (Array.isArray(item.pieces)) {
      for (const piece of item.pieces) {
        if (piece.name) names.push(piece.name);
      }
    }
  }
  return names;
}

/**
 * Score query against a list of item names, returning the best match.
 */
function bestItemSetScore(itemNames, query) {
  let bestScore = 0;
  let matchedName = null;
  for (const name of itemNames) {
    const s = scoreSearchResult(name, query);
    if (s > bestScore) {
      bestScore = s;
      matchedName = name;
    }
  }
  return { score: bestScore, matchedName };
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

  // Percent-markup items (stackables, (L) blueprints, (L) condition items):
  // median IS the markup percentage directly (e.g., 102.50 = 102.50%)
  // Exception: Deed/Token/Share materials use absolute markup despite being stackable
  if (isPercentMarkupType(item.t, item.n, subType)) {
    return `${median.toFixed(0)}% MU`;
  }

  // Absolute markup (condition items, non-L BPs, Deeds/Tokens/Shares):
  // median is +PED over TT
  return `+${median.toFixed(2)} PED`;
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

    const nameScore = scoreSearchResult(item.n, query);
    if (nameScore <= 0) continue;

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

  return results
    .sort((a, b) => b.score - a.score)
    .slice(0, MAX_EXCHANGE_RESULTS);
}

/**
 * Search services.
 */
async function searchServices(query, fetch) {
  const services = await apiCall(fetch, '/api/services');
  if (!Array.isArray(services)) return [];

  const results = [];
  for (const svc of services) {
    const nameScore = scoreSearchResult(svc.title, query);
    const descScore = Math.round(scoreSearchResult(svc.description, query) * DESCRIPTION_FACTOR);
    const score = Math.max(nameScore, descScore);
    if (score <= 0) continue;

    // Bonus when multiple fields match
    const fieldsHit = (nameScore > 0 ? 1 : 0) + (descScore > 0 ? 1 : 0);
    const multiBonus = fieldsHit > 1 ? (fieldsHit - 1) * MULTI_FIELD_BONUS : 0;

    results.push({
      id: `service:${svc.id}`,
      name: svc.title,
      marketType: 'service',
      entityType: svc.type || null,
      price: null,
      detail: [svc.type, svc.planet_name].filter(Boolean).join(' · ') || null,
      url: `/market/services/${svc.id}`,
      score: score + NON_EXCHANGE_BONUS + multiBonus
    });
  }

  return results
    .sort((a, b) => b.score - a.score)
    .slice(0, MAX_OTHER_RESULTS);
}

/**
 * Search auctions — fetches all active auctions and scores locally
 * against both title and item set item names.
 */
async function searchAuctions(query, fetch) {
  const result = await apiCall(fetch, '/api/auction?status=active&limit=100');
  if (!result?.auctions) return [];

  const results = [];
  for (const auction of result.auctions) {
    const titleScore = scoreSearchResult(auction.title, query);

    // Score against item set item names
    let itemScore = 0;
    let matchedItemName = null;
    if (auction.item_set_data?.items) {
      const itemNames = extractItemSetNames(auction.item_set_data);
      const best = bestItemSetScore(itemNames, query);
      itemScore = best.score > 0 ? best.score - ITEM_MATCH_PENALTY : 0;
      matchedItemName = best.matchedName;
    }

    const score = Math.max(titleScore, itemScore);
    if (score <= 0) continue;

    // Bonus when both title and items match
    const fieldsHit = (titleScore > 0 ? 1 : 0) + (itemScore > 0 ? 1 : 0);
    const multiBonus = fieldsHit > 1 ? (fieldsHit - 1) * MULTI_FIELD_BONUS : 0;

    const priceStr = auction.buyout_price
      ? `${parseFloat(auction.buyout_price).toFixed(2)} PED buyout`
      : auction.current_bid
        ? `${parseFloat(auction.current_bid).toFixed(2)} PED bid`
        : `${parseFloat(auction.starting_bid).toFixed(2)} PED start`;

    const matchDetail = (itemScore > titleScore && matchedItemName)
      ? matchedItemName
      : null;
    const bidDetail = auction.bid_count > 0
      ? `${auction.bid_count} bid${auction.bid_count !== 1 ? 's' : ''}`
      : null;

    results.push({
      id: `auction:${auction.id}`,
      name: auction.title,
      marketType: 'auction',
      entityType: null,
      price: priceStr,
      detail: [matchDetail, bidDetail].filter(Boolean).join(' · ') || null,
      url: `/market/auction/${auction.id}`,
      score: score + NON_EXCHANGE_BONUS + multiBonus
    });
  }

  return results
    .sort((a, b) => b.score - a.score)
    .slice(0, MAX_OTHER_RESULTS);
}

/**
 * Search rental offers — scores against title, description,
 * and item names within the item set.
 */
async function searchRentals(query, fetch) {
  const offers = await apiCall(fetch, '/api/rental?limit=100');
  if (!Array.isArray(offers)) return [];

  const results = [];
  for (const offer of offers) {
    const titleScore = scoreSearchResult(offer.title, query);
    const descScore = Math.round(scoreSearchResult(offer.description, query) * DESCRIPTION_FACTOR);

    // Score against item set item names
    let itemScore = 0;
    let matchedItemName = null;
    if (offer.item_set_data?.items) {
      const itemNames = extractItemSetNames(offer.item_set_data);
      const best = bestItemSetScore(itemNames, query);
      itemScore = best.score > 0 ? best.score - ITEM_MATCH_PENALTY : 0;
      matchedItemName = best.matchedName;
    }

    const score = Math.max(titleScore, descScore, itemScore);
    if (score <= 0) continue;

    // Bonus when multiple fields match (title, description, items)
    const fieldsHit = (titleScore > 0 ? 1 : 0) + (descScore > 0 ? 1 : 0) + (itemScore > 0 ? 1 : 0);
    const multiBonus = fieldsHit > 1 ? (fieldsHit - 1) * MULTI_FIELD_BONUS : 0;

    const priceStr = offer.price_per_day
      ? `${parseFloat(offer.price_per_day).toFixed(2)} PED/day`
      : null;

    const matchDetail = (itemScore > Math.max(titleScore, descScore) && matchedItemName)
      ? matchedItemName
      : null;

    results.push({
      id: `rental:${offer.id}`,
      name: offer.title,
      marketType: 'rental',
      entityType: null,
      price: priceStr,
      detail: [matchDetail, offer.owner_name].filter(Boolean).join(' · ') || null,
      url: `/market/rental/${offer.id}`,
      score: score + NON_EXCHANGE_BONUS + multiBonus
    });
  }

  return results
    .sort((a, b) => b.score - a.score)
    .slice(0, MAX_OTHER_RESULTS);
}

/**
 * Search shops — scores against shop name and inventory item names.
 * Inventory item IDs are resolved to names via the exchange cache's slim item lookup.
 */
async function searchShops(query, fetch) {
  const shops = await apiCall(fetch, '/shops');
  if (!Array.isArray(shops)) return [];

  // Resolve inventory item IDs to names using the exchange cache
  const slimLookup = getSlimItemLookup();

  const results = [];
  for (const shop of shops) {
    const name = shop.Name || shop.name;
    const nameScore = scoreSearchResult(name, query);

    // Score against inventory item names
    let bestItemScore = 0;
    let matchedItemName = null;
    if (slimLookup && Array.isArray(shop.InventoryGroups)) {
      for (const group of shop.InventoryGroups) {
        if (!Array.isArray(group.Items)) continue;
        for (const invItem of group.Items) {
          const itemId = invItem.ItemId ?? invItem.item_id;
          if (!itemId) continue;
          const slim = slimLookup.get(itemId);
          if (!slim?.n) continue;
          const s = scoreSearchResult(slim.n, query);
          if (s > bestItemScore) {
            bestItemScore = s;
            matchedItemName = slim.n;
          }
        }
      }
    }
    const itemScore = bestItemScore > 0 ? bestItemScore - ITEM_MATCH_PENALTY : 0;

    const score = Math.max(nameScore, itemScore);
    if (score <= 0) continue;

    const matchDetail = (itemScore > nameScore && matchedItemName)
      ? matchedItemName
      : null;
    const planetDetail = shop.Planet?.Name || null;

    results.push({
      id: `shop:${shop.Id || shop.id}`,
      name,
      marketType: 'shop',
      entityType: null,
      price: null,
      detail: [matchDetail, planetDetail].filter(Boolean).join(' · ') || null,
      url: `/market/shops/${encodeURIComponentSafe(name)}`,
      score: score + NON_EXCHANGE_BONUS
    });
  }

  return results
    .sort((a, b) => b.score - a.score)
    .slice(0, MAX_OTHER_RESULTS);
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

    // Merge and sort by score (non-exchange already boosted by NON_EXCHANGE_BONUS)
    const allResults = [...services, ...auctions, ...rentals, ...shops, ...exchange]
      .sort((a, b) => b.score - a.score)
      .slice(0, MAX_RESULTS);

    return getResponse(allResults, 200);
  } catch (err) {
    console.error('Market search error:', err);
    return getResponse({ error: 'Search failed' }, 500);
  }
}
