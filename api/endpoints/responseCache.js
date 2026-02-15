const { pool } = require('./dbClient');

// --- In-memory response cache ---
// Stores: route → { data, timestamp }
const cache = new Map();

// --- In-memory mirror of TableChanges ---
// Stores: table_name → max change timestamp (ms)
const changeMap = new Map();

// --- Concurrent rebuild protection ---
// Stores: route → Promise (coalesces concurrent fetches for the same route)
const pending = new Map();

const POLL_INTERVAL_MS = parseInt(process.env.CACHE_POLL_INTERVAL_MS || '1000', 10);
let pollTimer = null;
let pollHealthy = false;

/**
 * Fetch all rows from TableChanges and update the in-memory changeMap.
 * Runs on a background interval. If the table doesn't exist (migration not run),
 * pollHealthy stays false and caching is bypassed.
 */
async function pollChanges() {
  try {
    const { rows } = await pool.query(
      'SELECT "table_name", "last_insert", "last_update", "last_delete" FROM "TableChanges"'
    );
    for (const row of rows) {
      const ts = Math.max(
        row.last_insert ? new Date(row.last_insert).getTime() : 0,
        row.last_update ? new Date(row.last_update).getTime() : 0,
        row.last_delete ? new Date(row.last_delete).getTime() : 0
      );
      changeMap.set(row.table_name, ts);
    }
    if (!pollHealthy) console.log('[cache] Change tracking active');
    pollHealthy = true;
  } catch (e) {
    if (pollHealthy) console.warn('[cache] Poll failed, caching disabled:', e.message);
    pollHealthy = false;
  }
}

/**
 * Get the most recent change timestamp across a set of tables.
 */
function getMaxChangeTime(tables) {
  let max = 0;
  for (const t of tables) {
    const ts = changeMap.get(t) || 0;
    if (ts > max) max = ts;
  }
  return max;
}

/**
 * Cache-aware fetch. Returns cached data if no dependent tables have changed
 * since the cache was built; otherwise calls fetchFn and caches the result.
 *
 * @param {string} route - Cache key (e.g. '/items')
 * @param {string[]} tables - Database tables this route depends on
 * @param {Function} fetchFn - Async function that returns the data
 * @returns {Promise<any>} The (possibly cached) data
 */
async function withCache(route, tables, fetchFn) {
  // If polling isn't healthy (table missing, DB error), bypass cache entirely
  if (!pollHealthy) return fetchFn();

  const entry = cache.get(route);
  if (entry) {
    const maxChange = getMaxChangeTime(tables);
    if (entry.timestamp >= maxChange) {
      return entry.data;
    }
  }

  // Coalesce concurrent requests for the same stale/missing route
  if (pending.has(route)) return pending.get(route);

  const promise = fetchFn().then(data => {
    cache.set(route, { data, timestamp: Date.now() });
    pending.delete(route);
    return data;
  }).catch(err => {
    pending.delete(route);
    throw err;
  });

  pending.set(route, promise);
  return promise;
}

/**
 * Start the background poller. Awaits the first poll so the cache is primed
 * before the API starts serving requests.
 */
async function startPolling() {
  await pollChanges();
  pollTimer = setInterval(pollChanges, POLL_INTERVAL_MS);
  pollTimer.unref();
}

/**
 * Look up a single item from a cached list by Id or Name.
 * Lazily builds byId/byName Map indexes on the cache entry.
 * Indexes are automatically discarded when the cache entry is rebuilt.
 *
 * @param {string} route - Cache key for the list (e.g. '/weapons')
 * @param {string[]} tables - Database tables this route depends on
 * @param {Function} listFn - Async function returning the full list
 * @param {string} idOrName - The Id or Name to look up
 * @returns {Promise<any|null>} Single item or null
 */
async function withCachedLookup(route, tables, listFn, idOrName) {
  await withCache(route, tables, listFn);

  const entry = cache.get(route);
  if (!entry) return null;

  if (!entry._byId) {
    const byId = new Map();
    const byName = new Map();
    for (const item of entry.data) {
      if (item.Id != null) byId.set(item.Id, item);
      if (item.Name) byName.set(item.Name, item);
    }
    entry._byId = byId;
    entry._byName = byName;
  }

  if (/^\d+$/.test(String(idOrName))) {
    return entry._byId.get(Number(idOrName)) || null;
  }
  return entry._byName.get(String(idOrName)) || null;
}

/**
 * Stop the background poller (for graceful shutdown).
 */
function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

module.exports = { withCache, withCachedLookup, startPolling, stopPolling };
