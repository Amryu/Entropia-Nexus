/**
 * Shared markup source utilities.
 * Fetches exchange WAP data, in-game market prices, and inventory markups
 * for use in the inventory page, tiering editor, and construction calculator.
 */

/**
 * In-game market price periods in order from shortest to longest.
 * Used by buildInGameLookup for period-based fallback.
 */
export const INGAME_PERIODS = [
  { key: '1d',    label: 'Daily',   column: 'markup_1d' },
  { key: '7d',    label: 'Weekly',  column: 'markup_7d' },
  { key: '30d',   label: 'Monthly', column: 'markup_30d' },
  { key: '365d',  label: 'Yearly',  column: 'markup_365d' },
  { key: '3650d', label: 'Decade',  column: 'markup_3650d' },
];

/**
 * Recursively flatten the nested exchange categorization into a flat array of slim items.
 * Each item has shape: { i: id, n: name, t: type, w: wapPercent, ... }
 */
function flattenExchangeItems(obj) {
  const items = [];
  function traverse(current) {
    if (Array.isArray(current)) items.push(...current);
    else if (typeof current === 'object' && current !== null) Object.values(current).forEach(traverse);
  }
  traverse(obj);
  return items;
}

/**
 * Fetch exchange slim items and build lookup maps keyed by name.
 * Returns { wapByName: Map<name, wapPercent>, nameToId: Map<name, itemId> }
 */
export async function fetchExchangeWapByName() {
  try {
    const res = await fetch('/api/market/exchange');
    if (!res.ok) return { wapByName: new Map(), nameToId: new Map() };
    const data = await res.json();
    const items = flattenExchangeItems(data);

    const wapByName = new Map();
    const nameToId = new Map();

    for (const item of items) {
      if (item.i && item.n) {
        nameToId.set(item.n, item.i);
        if (item.w != null) {
          wapByName.set(item.n, item.w);
        }
      }
    }
    return { wapByName, nameToId };
  } catch {
    return { wapByName: new Map(), nameToId: new Map() };
  }
}

/**
 * Fetch raw in-game market price snapshots from the API.
 * Returns the raw array of snapshot objects (no markup resolution).
 */
async function fetchInGamePriceSnapshots() {
  try {
    const res = await fetch('/api/market/prices/snapshots/latest?all=true');
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

/**
 * Build a name → markup lookup from raw in-game price snapshots.
 * Starts from the given period and falls back to the next longer period
 * when the value is null (e.g. startPeriod='7d' tries 7d → 30d → 365d → 3650d).
 *
 * @param {Array} snapshots - Raw snapshot objects from fetchInGamePriceSnapshots()
 * @param {string} startPeriod - Period key to start from ('1d'|'7d'|'30d'|'365d'|'3650d')
 * @returns {Map<string, number>} itemName → markup percentage
 */
export function buildInGameLookup(snapshots, startPeriod = '1d') {
  const startIdx = INGAME_PERIODS.findIndex(p => p.key === startPeriod);
  const periods = startIdx >= 0 ? INGAME_PERIODS.slice(startIdx) : INGAME_PERIODS;
  const map = new Map();
  for (const row of snapshots) {
    if (!row.item_name) continue;
    let mu = null;
    for (const p of periods) {
      const v = row[p.column];
      if (v != null) { mu = v; break; }
    }
    if (mu != null) map.set(row.item_name, parseFloat(mu));
  }
  return map;
}

/**
 * Fetch in-game market price data from OCR'd snapshots.
 * Returns Map<itemName, markupPercent> using first non-null markup
 * in priority: 1d → 7d → 30d → 365d → 3650d.
 */
export async function fetchInGamePrices() {
  const snapshots = await fetchInGamePriceSnapshots();
  return buildInGameLookup(snapshots, '1d');
}

/**
 * Fetch the user's inventory markups.
 * Returns Map<itemId, markupPercent>.
 * Fails silently if user is not logged in or not verified.
 */
export async function fetchInventoryMarkups() {
  const res = await fetch('/api/users/inventory/markups');
  if (!res.ok) return new Map();
  const data = await res.json();
  const map = new Map();
  for (const m of data) {
    map.set(m.item_id, m.markup);
  }
  return map;
}

/**
 * Save a single inventory markup via the API.
 * @param {number} itemId
 * @param {number} markup
 * @returns {Promise<boolean>} true if saved successfully
 */
export async function saveInventoryMarkup(itemId, markup) {
  try {
    const res = await fetch('/api/users/inventory/markups', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: [{ item_id: itemId, markup }] })
    });
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Delete a single inventory markup (resets to default).
 * @param {number} itemId
 * @returns {Promise<boolean>} true if deleted successfully
 */
export async function deleteInventoryMarkup(itemId) {
  try {
    const res = await fetch(`/api/users/inventory/markups/${itemId}`, {
      method: 'DELETE'
    });
    return res.ok;
  } catch {
    return false;
  }
}
