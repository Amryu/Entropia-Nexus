// @ts-nocheck
import { apiCall } from "$lib/util";
import { categorizeItems } from "$lib/market/categorize";
import { getAllOrderCounts, getLatestExchangePriceMap, getOrderPlanets } from "$lib/server/exchange.js";
import { ABSOLUTE_MARKUP_MATERIAL_TYPES } from "$lib/common/itemTypes.js";
import { brotliCompressSync, gzipSync } from 'node:zlib';
import { createHash } from 'node:crypto';

// In-memory cache
let cache = {
  // Categorized tree and annotated payload
  categorized: null,
  annotated: null,
  // Precomputed summary payload for the exchange endpoint
  summaryJson: null,
  summaryEtag: null,
  summaryBrotli: null, // Pre-compressed Brotli buffer
  summaryGzip: null,   // Pre-compressed Gzip buffer
  // Source datasets
  items: null,
  detailed: {},
  // Offer counts per item (Map<itemId, { buys, sells }>)
  offerCounts: null,
  // Planets with orders per item (Map<itemId, string[]>)
  orderPlanets: null,
  // Exchange price data per item (Map<itemId, { wap, median, p10 }>)
  exchangePrices: null,
  // Fingerprint of last offer counts/planets/prices used to skip no-op rebuilds
  countsFingerprint: null,
  // Timestamps
  lastFullBuildAt: 0,
  lastItemsCheckAt: 0,
  lastOfferCountsAt: 0
};

// Flat lookup of slim items for server-side value computation (inventory snapshots)
let slimItemLookup = null;
// Name-based lookup (Map<lowercaseName, slimItem>) including gender aliases
let slimNameLookup = null;

// Prevent concurrent rebuilds overwhelming the API
let rebuildPromise = null; // full rebuild lock
let deltaPromise = null;   // items delta lock

const FULL_REBUILD_MS = 24 * 60 * 60 * 1000; // 24h
const ITEMS_REFRESH_MS = 15 * 60 * 1000;     // 15m
const OFFER_COUNTS_MS = 5 * 60 * 1000;       // 5m
const STALE_MAX_MS = 30 * 60 * 1000;         // 30m — max time to serve stale data

async function fetchAllDatasets(fetch) {
  // Base items + all detailed endpoints required by categorization
  const items = await apiCall(fetch, "/items");
  const [
    weapons,
    weaponAmplifiers,
    weaponVisionAttachments,
    absorbers,
    mindforceImplants,
    skills,
    armorSets,
    armors,
    armorPlatings,
    clothings,
    medicalTools,
    medicalChips,
    finders,
    finderAmplifiers,
    excavators,
    scanners,
    miscTools,
    enhancers,
    blueprints,
    materials,
    vehicles,
    strongboxes
  ] = await Promise.all([
    apiCall(fetch, "/weapons"),
    apiCall(fetch, "/weaponamplifiers"),
    apiCall(fetch, "/weaponvisionattachments"),
    apiCall(fetch, "/absorbers"),
    apiCall(fetch, "/mindforceimplants"),
    apiCall(fetch, "/skills"),
    apiCall(fetch, "/armorsets"),
    apiCall(fetch, "/armors"),
    apiCall(fetch, "/armorplatings"),
    apiCall(fetch, "/clothings"),
    apiCall(fetch, "/medicaltools"),
    apiCall(fetch, "/medicalchips"),
    apiCall(fetch, "/finders"),
    apiCall(fetch, "/finderamplifiers"),
    apiCall(fetch, "/excavators"),
    apiCall(fetch, "/scanners"),
    apiCall(fetch, "/misctools"),
    apiCall(fetch, "/enhancers"),
    apiCall(fetch, "/blueprints"),
    apiCall(fetch, "/materials"),
    apiCall(fetch, "/vehicles"),
    apiCall(fetch, "/strongboxes")
  ]);

  return {
    items,
    detailed: {
      weapons,
      weaponAmplifiers,
      weaponVisionAttachments,
      absorbers,
      mindforceImplants,
      skills,
      armorSets,
      armors,
      armorPlatings,
      clothings,
      medicalTools,
      medicalChips,
      finders,
      finderAmplifiers,
      excavators,
      scanners,
      miscTools,
      enhancers,
      blueprints,
      materials,
      vehicles,
      strongboxes
    }
  };
}

function annotateForExchange(categorized) {
  // Placeholder for future metrics
  return categorized;
}

/**
 * Some detailed endpoints (e.g. /materials) return a table-row `Id` instead of
 * the global `Items.Id`, and lack an `ItemId` field. This function backfills the
 * correct `ItemId` from the base /items list by matching on Name.
 */
function enrichWithItemIds(items, detailed) {
  if (!items || !detailed) return;
  const nameToItem = new Map();
  for (const item of items) {
    const id = item.ItemId ?? item.Id;
    if (item.Name) nameToItem.set(item.Name, item);
  }
  for (const dataset of Object.values(detailed)) {
    if (!Array.isArray(dataset)) continue;
    for (const entry of dataset) {
      const base = entry.Name ? nameToItem.get(entry.Name) : null;
      if (base) {
        const id = base.ItemId ?? base.Id;
        if (!entry.ItemId && id != null) entry.ItemId = id;
        // Copy base type so detailed items (whose Properties.Type is a sub-type) retain the top-level type
        const baseType = base.Properties?.Type ?? base.Type;
        if (baseType && !entry.Type) entry.Type = baseType;
        // Copy value for items that lack economy data (e.g. strongboxes from /strongboxes)
        const baseEconValue = base.Properties?.Economy?.Value ?? base.Properties?.Economy?.MaxTT;
        if (baseEconValue != null && entry.Value == null && entry.MaxTT == null
            && !entry.Properties?.Economy?.Value && !entry.Properties?.Economy?.MaxTT) {
          entry.Value = baseEconValue;
        }
      }
    }
  }
}

// Build/rebuild lightweight summary JSON, pre-compress, and compute content-based ETag
function buildSummary() {
  try {
    if (!cache.annotated) {
      cache.summaryJson = null;
      cache.summaryEtag = null;
      cache.summaryBrotli = null;
      cache.summaryGzip = null;
      return;
    }
    const slim = slimCategorized(cache.annotated);
    const json = JSON.stringify(slim);
    const buf = Buffer.from(json);

    // Content-based ETag using MD5 hash
    const hash = createHash('md5').update(buf).digest('hex').slice(0, 16);
    cache.summaryJson = json;
    cache.summaryEtag = `W/"${hash}"`;

    // Pre-compress so the endpoint never has to compress per-request
    cache.summaryBrotli = brotliCompressSync(buf);
    cache.summaryGzip = gzipSync(buf);

    // Build flat lookup for server-side value computation
    buildSlimLookup();
  } catch {
    cache.summaryJson = null;
    cache.summaryEtag = null;
    cache.summaryBrotli = null;
    cache.summaryGzip = null;
  }
}

// Build flat slim item lookup (Map<itemId, slimItem>) for server-side consumers
function buildSlimLookup() {
  if (!cache.annotated) { slimItemLookup = null; slimNameLookup = null; return; }
  const map = new Map();
  function walk(obj) {
    if (Array.isArray(obj)) {
      for (const item of obj) {
        const slim = slimItem(item);
        if (slim && slim.i != null) map.set(slim.i, slim);
      }
    } else if (obj && typeof obj === 'object') {
      for (const val of Object.values(obj)) walk(val);
    }
  }
  walk(cache.annotated);
  slimItemLookup = map;
  buildSlimNameLookup();
}

/**
 * Generate gender aliases for items with Gender: Both.
 * E.g. "Bear Armor" → ["Bear Armor (M)", "Bear Armor (F)"]
 * "Bear Armor (L)" → ["Bear Armor (M, L)", "Bear Armor (F, L)"]
 * Canonical source: api/endpoints/utils.js — keep in sync.
 */
function generateGenderAliases(name) {
  if (!name) return [];
  const hasGenderTag = /\((M|F)\)/.test(name) || /\(M,/.test(name) || /,\s*M\)/.test(name) || /\(F,/.test(name) || /,\s*F\)/.test(name);
  if (hasGenderTag) return [];
  const tagMatch = name.match(/^(.+?)(\s*\([^)]+\))$/);
  if (tagMatch) {
    const baseName = tagMatch[1].trim();
    const tagContent = tagMatch[2].trim().slice(1, -1);
    return [`${baseName} (M, ${tagContent})`, `${baseName} (F, ${tagContent})`];
  }
  return [`${name} (M)`, `${name} (F)`];
}

// Build name-based lookup including gender aliases for server-side item resolution
function buildSlimNameLookup() {
  if (!slimItemLookup) { slimNameLookup = null; return; }
  const map = new Map();
  for (const slim of slimItemLookup.values()) {
    if (!slim.n) continue;
    map.set(slim.n.toLowerCase(), slim);
    // Generate gender aliases for Armor/Clothing with Gender: Both
    if ((slim.t === 'Armor' || slim.t === 'Clothing') && slim.g === 'Both') {
      for (const alias of generateGenderAliases(slim.n)) {
        map.set(alias.toLowerCase(), slim);
      }
    }
  }
  slimNameLookup = map;
}

/**
 * Get the flat slim item lookup (Map<itemId, slimItem>).
 * Returns null if the cache hasn't been built yet.
 */
export function getSlimItemLookup() {
  return slimItemLookup;
}

/**
 * Get the name-based slim item lookup (Map<lowercaseName, slimItem>).
 * Includes exact names and gender aliases. Returns null if cache not built.
 */
export function getSlimNameLookup() {
  return slimNameLookup;
}

// Full rebuild (24h): fetch all datasets, categorize, annotate
export async function rebuildMarketCache(fetch) {
  if (rebuildPromise) return rebuildPromise;
  rebuildPromise = (async () => {
    const { items, detailed } = await fetchAllDatasets(fetch);
    if (!items) return cache.annotated;

    enrichWithItemIds(items, detailed);
    const categorized = categorizeItems(items, detailed);
    const annotated = annotateForExchange(categorized);

    cache.items = items;
    cache.detailed = detailed;
    cache.categorized = categorized;
    cache.annotated = annotated;
    cache.lastFullBuildAt = Date.now();
    cache.lastItemsCheckAt = Date.now();

    // Fetch offer counts and prices from exchange DB
    try {
      const [counts, planets, prices] = await Promise.all([
        getAllOrderCounts(),
        getOrderPlanets().catch(() => null),
        getLatestExchangePriceMap().catch(() => null)
      ]);
      cache.offerCounts = counts;
      if (planets) cache.orderPlanets = planets;
      if (prices) cache.exchangePrices = prices;
      cache.lastOfferCountsAt = Date.now();
    } catch { /* non-fatal */ }

    buildSummary();

    return cache.annotated;
  })();
  try {
    return await rebuildPromise;
  } finally {
    rebuildPromise = null;
  }
}

// Items-only delta (15m): fetch /items, detect new/removed, selectively refresh detailed endpoints, recategorize
async function itemsDeltaRefresh(fetch) {
  if (deltaPromise) return deltaPromise;
  deltaPromise = (async () => {
    const items = await apiCall(fetch, "/items");
    if (!items) return cache.annotated;

    // No cache yet -> do a full rebuild
    if (!cache.items || !cache.categorized) {
      return await rebuildMarketCache(fetch);
    }

    const prev = cache.items;
    const prevIds = new Set((prev || []).map(it => it.ItemId ?? it.Id));
    const newIds = new Set((items || []).map(it => it.ItemId ?? it.Id));

    const added = [];
    const removed = [];
    for (const it of items || []) {
      const id = it.ItemId ?? it.Id;
      if (id != null && !prevIds.has(id)) added.push(it);
    }
    for (const it of prev || []) {
      const id = it.ItemId ?? it.Id;
      if (id != null && !newIds.has(id)) removed.push(it);
    }

    if (added.length === 0 && removed.length === 0) {
      cache.lastItemsCheckAt = Date.now();
      // Still refresh offer counts if stale
      if (Date.now() - cache.lastOfferCountsAt > OFFER_COUNTS_MS) {
        refreshOfferCounts().catch(() => {});
      }
      return cache.annotated;
    }

    // Determine which detailed sets to refresh based on added/removed item types
    const need = new Set();
    const typeOf = (it) => (it?.Properties?.Type || it?.Type || '').toLowerCase();
    for (const it of [...added, ...removed]) {
      const t = typeOf(it);
      if (t === 'weapon') need.add('weapons');
      if (t === 'weaponvisionattachment') need.add('weaponVisionAttachments');
      if (t === 'weaponamplifier') need.add('weaponAmplifiers');
      if (t === 'absorber') need.add('absorbers');
      if (t === 'mindforceimplant') need.add('mindforceImplants');
      if (t === 'armor') { need.add('armors'); need.add('armorSets'); }
      if (t === 'armorplating') need.add('armorPlatings');
      if (t === 'clothing') need.add('clothings');
      if (t === 'medicaltool') need.add('medicalTools');
      if (t === 'finder') need.add('finders');
      if (t === 'finderamplifier') need.add('finderAmplifiers');
      if (t === 'excavator') need.add('excavators');
      if (t === 'scanner') need.add('scanners');
      if (t === 'misctool' || t === 'tool') need.add('miscTools');
      if (t === 'enhancer') need.add('enhancers');
      if (t === 'blueprint') need.add('blueprints');
      if (t === 'material') need.add('materials');
      if (t === 'vehicle') need.add('vehicles');
      if (t === 'medicalchip') need.add('medicalChips');
      if (t === 'strongbox') need.add('strongboxes');
    }

    const updates = {};
    await Promise.all([
      need.has('weapons') ? apiCall(fetch, '/weapons').then(v => { updates.weapons = v; }) : Promise.resolve(),
      need.has('weaponAmplifiers') ? apiCall(fetch, '/weaponamplifiers').then(v => { updates.weaponAmplifiers = v; }) : Promise.resolve(),
      need.has('weaponVisionAttachments') ? apiCall(fetch, '/weaponvisionattachments').then(v => { updates.weaponVisionAttachments = v; }) : Promise.resolve(),
      need.has('absorbers') ? apiCall(fetch, '/absorbers').then(v => { updates.absorbers = v; }) : Promise.resolve(),
      need.has('mindforceImplants') ? apiCall(fetch, '/mindforceimplants').then(v => { updates.mindforceImplants = v; }) : Promise.resolve(),
      need.has('skills') ? apiCall(fetch, '/skills').then(v => { updates.skills = v; }) : Promise.resolve(),
      need.has('armorSets') ? apiCall(fetch, '/armorsets').then(v => { updates.armorSets = v; }) : Promise.resolve(),
      need.has('armors') ? apiCall(fetch, '/armors').then(v => { updates.armors = v; }) : Promise.resolve(),
      need.has('armorPlatings') ? apiCall(fetch, '/armorplatings').then(v => { updates.armorPlatings = v; }) : Promise.resolve(),
      need.has('clothings') ? apiCall(fetch, '/clothings').then(v => { updates.clothings = v; }) : Promise.resolve(),
      need.has('medicalTools') ? apiCall(fetch, '/medicaltools').then(v => { updates.medicalTools = v; }) : Promise.resolve(),
      need.has('finders') ? apiCall(fetch, '/finders').then(v => { updates.finders = v; }) : Promise.resolve(),
      need.has('finderAmplifiers') ? apiCall(fetch, '/finderamplifiers').then(v => { updates.finderAmplifiers = v; }) : Promise.resolve(),
      need.has('excavators') ? apiCall(fetch, '/excavators').then(v => { updates.excavators = v; }) : Promise.resolve(),
      need.has('scanners') ? apiCall(fetch, '/scanners').then(v => { updates.scanners = v; }) : Promise.resolve(),
      need.has('miscTools') ? apiCall(fetch, '/misctools').then(v => { updates.miscTools = v; }) : Promise.resolve(),
      need.has('enhancers') ? apiCall(fetch, '/enhancers').then(v => { updates.enhancers = v; }) : Promise.resolve(),
      need.has('blueprints') ? apiCall(fetch, '/blueprints').then(v => { updates.blueprints = v; }) : Promise.resolve(),
      need.has('materials') ? apiCall(fetch, '/materials').then(v => { updates.materials = v; }) : Promise.resolve(),
      need.has('vehicles') ? apiCall(fetch, '/vehicles').then(v => { updates.vehicles = v; }) : Promise.resolve(),
      need.has('medicalChips') ? apiCall(fetch, '/medicalchips').then(v => { updates.medicalChips = v; }) : Promise.resolve(),
      need.has('strongboxes') ? apiCall(fetch, '/strongboxes').then(v => { updates.strongboxes = v; }) : Promise.resolve()
    ]);

    cache.detailed = { ...cache.detailed, ...updates };
    cache.items = items;

    enrichWithItemIds(cache.items, cache.detailed);
    const categorized = categorizeItems(cache.items, cache.detailed);
    const annotated = annotateForExchange(categorized);
    cache.categorized = categorized;
    cache.annotated = annotated;
    cache.lastItemsCheckAt = Date.now();

    // Refresh offer counts and prices
    try {
      const [counts, planets, prices] = await Promise.all([
        getAllOrderCounts(),
        getOrderPlanets().catch(() => null),
        getLatestExchangePriceMap().catch(() => null)
      ]);
      cache.offerCounts = counts;
      if (planets) cache.orderPlanets = planets;
      if (prices) cache.exchangePrices = prices;
      cache.lastOfferCountsAt = Date.now();
    } catch { /* non-fatal */ }

    buildSummary();

    return cache.annotated;
  })();
  try {
    return await deltaPromise;
  } finally {
    deltaPromise = null;
  }
}

/**
 * Compute a lightweight fingerprint of the offer counts, planets, and prices
 * so we can skip buildSummary() when nothing has changed.
 */
function countsFingerprint(counts, planets, prices) {
  const parts = [(counts?.size || 0), (planets?.size || 0), (prices?.size || 0)];
  if (counts) {
    for (const [id, c] of counts) {
      parts.push(id, c.buys, c.sells, c.buyVol, c.sellVol, c.bestBuyMarkup ?? '');
    }
  }
  if (planets) {
    for (const [id, pl] of planets) {
      parts.push(id, pl.join(','));
    }
  }
  if (prices) {
    for (const [id, p] of prices) {
      parts.push(id, p.wap, p.median, p.p10);
    }
  }
  return parts.join('|');
}

/**
 * Refresh only the offer counts and rebuild summary if data changed.
 * Lightweight — just DB queries, skips tree walk + compression when unchanged.
 */
async function refreshOfferCounts() {
  if (!cache.annotated) return; // no data yet
  try {
    const [counts, planets, prices] = await Promise.all([
      getAllOrderCounts(),
      getOrderPlanets().catch(() => null),
      getLatestExchangePriceMap().catch(() => null)
    ]);
    cache.offerCounts = counts;
    if (planets) cache.orderPlanets = planets;
    if (prices) cache.exchangePrices = prices;
    cache.lastOfferCountsAt = Date.now();

    // Only rebuild summary if the data actually changed
    const fp = countsFingerprint(counts, planets, prices);
    if (fp !== cache.countsFingerprint) {
      cache.countsFingerprint = fp;
      buildSummary();
    }
  } catch { /* non-fatal */ }
}

/**
 * Debounced invalidation of offer counts — called after order mutations
 * (create, edit, close, bump) so the exchange summary reflects changes
 * within ~500ms instead of waiting for the next 5m polling cycle.
 */
let offerCountsInvalidateTimer = null;
export function invalidateOfferCounts() {
  if (offerCountsInvalidateTimer) clearTimeout(offerCountsInvalidateTimer);
  offerCountsInvalidateTimer = setTimeout(async () => {
    offerCountsInvalidateTimer = null;
    try { await refreshOfferCounts(); } catch {}
  }, 500);
}

export async function getExchangeCategorization(fetch) {
  // First request: block on initial build
  if (!cache.annotated) {
    return await rebuildMarketCache(fetch);
  }

  const now = Date.now();
  const needsFull = now - cache.lastFullBuildAt > FULL_REBUILD_MS;
  const needsItems = now - cache.lastItemsCheckAt > ITEMS_REFRESH_MS;

  if (!needsFull && !needsItems) return cache.annotated;

  // How old is the most recent successful refresh?
  const lastUpdate = Math.max(cache.lastFullBuildAt, cache.lastItemsCheckAt, cache.lastOfferCountsAt);
  const tooStale = (now - lastUpdate) > STALE_MAX_MS;

  if (needsFull) {
    if (tooStale) {
      // Data too old — block until rebuild finishes
      return await rebuildMarketCache(fetch);
    }
    // SWR: serve stale, rebuild in background
    if (!rebuildPromise) rebuildMarketCache(fetch).catch(() => {});
    return cache.annotated;
  }

  // needsItems
  if (tooStale) {
    // Data too old — block until delta finishes
    return await itemsDeltaRefresh(fetch);
  }
  // SWR: serve stale, delta in background
  if (!deltaPromise) itemsDeltaRefresh(fetch).catch(() => {});
  return cache.annotated;
}

// Server-start initialization and staggered refresh schedules
if (typeof window === 'undefined') {
  (async () => {
    try {
      if (globalThis.fetch) {
        await rebuildMarketCache(globalThis.fetch);
      }
    } catch {}
  })();

  try {
    const scheduleFull = () => {
      const jitter = Math.floor(FULL_REBUILD_MS * (0.95 + Math.random() * 0.1));
      setTimeout(async () => {
        try {
          if (globalThis.fetch && !rebuildPromise) await rebuildMarketCache(globalThis.fetch);
        } catch {}
        scheduleFull();
      }, jitter);
    };
    const scheduleItems = () => {
      const jitter = Math.floor(ITEMS_REFRESH_MS * (0.9 + Math.random() * 0.2));
      setTimeout(async () => {
        try {
          if (globalThis.fetch && !deltaPromise) await itemsDeltaRefresh(globalThis.fetch);
        } catch {}
        scheduleItems();
      }, jitter);
    };
    const scheduleOfferCounts = () => {
      const jitter = Math.floor(OFFER_COUNTS_MS * (0.9 + Math.random() * 0.2));
      setTimeout(async () => {
        try {
          await refreshOfferCounts();
        } catch {}
        scheduleOfferCounts();
      }, jitter);
    };
    scheduleFull();
    scheduleItems();
    scheduleOfferCounts();
  } catch {}
}

// Slim client payload
function slimItem(item) {
  if (!item || typeof item !== 'object') return item;
  const ut = item.Properties?.Description?.includes('Untradeable') || undefined;
  const id = item.ItemId ?? item.Id ?? null;
  const counts = id != null && cache.offerCounts ? cache.offerCounts.get(id) : null;
  const planets = id != null && cache.orderPlanets ? cache.orderPlanets.get(id) : null;
  const ep = id != null && cache.exchangePrices ? cache.exchangePrices.get(id) : null;
  // ArmorSets have an Armors array; detect before checking Type (enrichWithItemIds may copy 'Armor' from base items)
  let type = item.Armors ? 'ArmorSet' : (item.Type ?? item.Properties?.Type ?? null);
  const name = item.Name ?? null;

  // Gender for gendered item types (Armor/Clothing from Properties, ArmorSet always 'Both')
  let g;
  if (type === 'ArmorSet') {
    g = 'Both';
  } else if (type === 'Armor' || type === 'Clothing') {
    g = item.Properties?.Gender ?? null;
  }

  let v = item.Properties?.Economy?.MaxTT ?? item.Properties?.Economy?.Value ?? item.MaxTT ?? item.Value ?? null;
  // Blueprint values: non-L MaxTT = 1.00 PED, (L) = 0.01 PED per unit
  if (type === 'Blueprint') {
    v = /\(L\)/.test(name || '') ? 0.01 : 1.00;
  }
  // Pet values: NutrioCapacity stored in cents, convert to PED
  if (type === 'Pet' && v == null && item.Properties?.NutrioCapacity != null) {
    v = item.Properties.NutrioCapacity / 100;
  }

  // Material sub-type for absolute markup items (Deed, Token)
  const st = type === 'Material' && item.Properties?.Type && ABSOLUTE_MARKUP_MATERIAL_TYPES.has(item.Properties.Type)
    ? item.Properties.Type : undefined;

  return {
    i: id,
    n: name,
    t: type,
    v,
    ...(g !== undefined && { g }),
    ...(st && { st }),
    ...(ut && { ut }),
    o: null,
    b: counts?.buys || null,
    s: counts?.sells || null,
    bv: counts?.buyVol || null,
    sv: counts?.sellVol || null,
    u: counts?.lastUpdate ? counts.lastUpdate.toISOString() : null,
    m: ep?.median ?? null,
    p: ep?.p10 ?? null,
    w: ep?.wap ?? null,
    pl: planets || null,
    bb: counts?.bestBuyMarkup ?? null,
    bs: counts?.bestSellMarkup ?? null
  };
}

function slimCategorized(obj) {
  if (Array.isArray(obj)) return obj.map(slimItem).filter(Boolean);
  if (obj && typeof obj === 'object') {
    const out = {};
    for (const [k, v] of Object.entries(obj)) {
      if (k.startsWith('_')) continue; // skip internal-only buckets (e.g. _unlisted)
      out[k] = slimCategorized(v);
    }
    return out;
  }
  return obj;
}

export async function getExchangeCategorizationSummary(fetch) {
  const full = await getExchangeCategorization(fetch);
  if (!cache.summaryJson) buildSummary();
  try {
    return JSON.parse(cache.summaryJson || '{}');
  } catch {
    return slimCategorized(full);
  }
}

// Fast path for API route: returns precomputed JSON string, ETag, and pre-compressed buffers
export async function getExchangeCategorizationSummaryJson(fetch) {
  await getExchangeCategorization(fetch);
  if (!cache.summaryJson) buildSummary();
  return {
    json: cache.summaryJson || '{}',
    etag: cache.summaryEtag || null,
    brotli: cache.summaryBrotli,
    gzip: cache.summaryGzip
  };
}
