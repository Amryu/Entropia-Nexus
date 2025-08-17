const { getItem } = require('./items');

// Simple in-memory cache with TTL
const CACHE_TTL_MS = 60 * 1000; // 1 minute
const cache = new Map(); // key -> { value, expires }

async function getItemCached(idOrName) {
  const key = String(idOrName);
  const now = Date.now();
  const entry = cache.get(key);
  if (entry && entry.expires > now) return entry.value;
  const value = await getItem(idOrName).catch(() => null);
  cache.set(key, { value, expires: now + CACHE_TTL_MS });
  return value;
}

module.exports = { getItemCached };
