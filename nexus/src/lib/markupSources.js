/**
 * Shared markup source utilities.
 * Fetches exchange WAP data and inventory markups for use
 * in the tiering editor and construction calculator.
 */

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
