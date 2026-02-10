// @ts-nocheck
import { apiCall } from "$lib/util";
import { categorizeItems } from "$lib/market/categorize";
import { getAllOfferCounts, getLatestExchangePriceMap } from "$lib/server/exchange.js";

// In-memory cache
let cache = {
  // Categorized tree and annotated payload
  categorized: null,
  annotated: null,
  // Precomputed summary payload for the exchange endpoint
  summaryJson: null,
  summaryEtag: null,
  // Source datasets
  items: null,
  detailed: {},
  // Offer counts per item (Map<itemId, { buys, sells }>)
  offerCounts: null,
  // Exchange price data per item (Map<itemId, { wap, median, p10 }>)
  exchangePrices: null,
  // Timestamps
  lastFullBuildAt: 0,
  lastItemsCheckAt: 0,
  lastOfferCountsAt: 0
};

// Prevent concurrent rebuilds overwhelming the API
let rebuildPromise = null; // full rebuild lock
let deltaPromise = null;   // items delta lock

const FULL_REBUILD_MS = 24 * 60 * 60 * 1000; // 24h
const ITEMS_REFRESH_MS = 15 * 60 * 1000;     // 15m
const OFFER_COUNTS_MS = 5 * 60 * 1000;       // 5m

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
    finders,
    finderAmplifiers,
    excavators,
    scanners,
    miscTools,
    enhancers,
    blueprints,
    materials,
    vehicles
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
    apiCall(fetch, "/finders"),
    apiCall(fetch, "/finderamplifiers"),
    apiCall(fetch, "/excavators"),
    apiCall(fetch, "/scanners"),
    apiCall(fetch, "/misctools"),
    apiCall(fetch, "/enhancers"),
    apiCall(fetch, "/blueprints"),
    apiCall(fetch, "/materials"),
    apiCall(fetch, "/vehicles")
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
      finders,
      finderAmplifiers,
      excavators,
      scanners,
      miscTools,
      enhancers,
      blueprints,
      materials,
      vehicles
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
  const nameToId = new Map();
  for (const item of items) {
    const id = item.ItemId ?? item.Id;
    if (item.Name && id != null) nameToId.set(item.Name, id);
  }
  for (const dataset of Object.values(detailed)) {
    if (!Array.isArray(dataset)) continue;
    for (const entry of dataset) {
      if (!entry.ItemId && entry.Name) {
        const id = nameToId.get(entry.Name);
        if (id != null) entry.ItemId = id;
      }
    }
  }
}

// Build/rebuild lightweight summary JSON and an ETag for fast responses
function buildSummary() {
  try {
    if (!cache.annotated) {
      cache.summaryJson = null;
      cache.summaryEtag = null;
      return;
    }
    const slim = slimCategorized(cache.annotated);
    const json = JSON.stringify(slim);
    // Simple weak ETag based on length and last full build timestamp
    const len = Buffer.byteLength(json);
    const stamp = cache.lastFullBuildAt || Date.now();
    cache.summaryJson = json;
    cache.summaryEtag = `W/"${len}-${stamp}"`;
  } catch {
    cache.summaryJson = null;
    cache.summaryEtag = null;
  }
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

    // Fetch offer counts from exchange DB
    try {
      cache.offerCounts = await getAllOfferCounts();
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

    // Determine which detailed sets to refresh based on added item types
    const need = new Set();
    const typeOf = (it) => (it?.Properties?.Type || it?.Type || '').toLowerCase();
    for (const it of added) {
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
      need.has('vehicles') ? apiCall(fetch, '/vehicles').then(v => { updates.vehicles = v; }) : Promise.resolve()
    ]);

    cache.detailed = { ...cache.detailed, ...updates };
    cache.items = items;

    enrichWithItemIds(cache.items, cache.detailed);
    const categorized = categorizeItems(cache.items, cache.detailed);
    const annotated = annotateForExchange(categorized);
    cache.categorized = categorized;
    cache.annotated = annotated;
    cache.lastItemsCheckAt = Date.now();

    // Refresh offer counts
    try {
      cache.offerCounts = await getAllOfferCounts();
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
 * Refresh only the offer counts and rebuild summary.
 * Lightweight — just one DB query.
 */
async function refreshOfferCounts() {
  if (!cache.annotated) return; // no data yet
  try {
    const [counts, prices] = await Promise.all([
      getAllOfferCounts(),
      getLatestExchangePriceMap().catch(() => null)
    ]);
    cache.offerCounts = counts;
    if (prices) cache.exchangePrices = prices;
    cache.lastOfferCountsAt = Date.now();
    buildSummary();
  } catch { /* non-fatal */ }
}

export async function getExchangeCategorization(fetch) {
  const now = Date.now();
  const needsFull = !cache.annotated || (now - cache.lastFullBuildAt > FULL_REBUILD_MS);
  const needsItems = !cache.annotated || (now - cache.lastItemsCheckAt > ITEMS_REFRESH_MS);

  if (needsFull) {
    // SWR: try to rebuild in background, serve stale if available
    if (!rebuildPromise) rebuildMarketCache(fetch).catch(() => {});
    if (cache.annotated) return cache.annotated;
    return await rebuildMarketCache(fetch);
  }

  if (needsItems) {
    // Items-only refresh in the background
    if (!deltaPromise) itemsDeltaRefresh(fetch).catch(() => {});
  }

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
  const id = item.ItemId ?? item.Id ?? null;
  const counts = id != null && cache.offerCounts ? cache.offerCounts.get(id) : null;
  const ep = id != null && cache.exchangePrices ? cache.exchangePrices.get(id) : null;
  return {
    i: id,
    n: item.Name ?? null,
    t: item.Properties?.Type ?? item.Type ?? null,
    v: item.Properties?.Economy?.MaxTT ?? item.MaxTT ?? item.Value ?? null,
    o: null,
    b: counts?.buys || null,
    s: counts?.sells || null,
    m: ep?.median ?? null,
    p: ep?.p10 ?? null,
    w: ep?.wap ?? null
  };
}

function slimCategorized(obj) {
  if (Array.isArray(obj)) return obj.map(slimItem);
  if (obj && typeof obj === 'object') {
    const out = {};
    for (const [k, v] of Object.entries(obj)) {
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

// Fast path for API route: returns precomputed JSON string and ETag
export async function getExchangeCategorizationSummaryJson(fetch) {
  await getExchangeCategorization(fetch);
  if (!cache.summaryJson) buildSummary();
  return { json: cache.summaryJson || '{}', etag: cache.summaryEtag || null };
}
