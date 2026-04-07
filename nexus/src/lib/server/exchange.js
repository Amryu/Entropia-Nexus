//@ts-nocheck
import { pool, nexusPool } from './db.js';

// Staleness thresholds (days)
const STALE_DAYS = 3;
const EXPIRED_DAYS = 7;
const TERMINATED_DAYS = 30;
const MAX_SELL_ORDERS = 1000;
const MAX_BUY_ORDERS = 1000;
const MAX_ORDERS_PER_ITEM = 5;
const MAX_BATCH_SIZE = 50;

// ---------- Rate Limit Constants ----------

/** Global order creation rate limits */
const RATE_LIMIT_CREATE_PER_MIN = 100;
const RATE_LIMIT_CREATE_PER_HOUR = 500;
const RATE_LIMIT_CREATE_PER_DAY = 3000;

/** Per-item cooldown (shared by create + edit) */
const RATE_LIMIT_ITEM_COOLDOWN_MS = 3 * 60 * 1000; // 3 minutes
const RATE_LIMIT_ITEM_FUNGIBLE_COOLDOWN = 1;         // 1 per 3 min for stackable items
const RATE_LIMIT_ITEM_NONFUNGIBLE_COOLDOWN = MAX_ORDERS_PER_ITEM; // up to limit per 3 min

/** Per-item daily creation limits */
const RATE_LIMIT_ITEM_DAILY_FUNGIBLE = 10;
// Non-fungible daily = RATE_LIMIT_ITEM_DAILY_FUNGIBLE * MAX_ORDERS_PER_ITEM

/** Edit/bump/close rate limits */
const RATE_LIMIT_EDIT_PER_MIN = 60;
const RATE_LIMIT_BUMP_ALL_PER_HOUR = 1;
const RATE_LIMIT_CLOSE_PER_MIN = 100;

/**
 * SQL fragment that computes the effective state from bumped_at.
 * The DB `state` column stores 'closed' explicitly; all other states are derived on read.
 */
const COMPUTED_STATE_SQL = `
  CASE
    WHEN state = 'closed' THEN 'closed'
    WHEN bumped_at < NOW() - INTERVAL '${TERMINATED_DAYS} days' THEN 'terminated'
    WHEN bumped_at < NOW() - INTERVAL '${EXPIRED_DAYS} days' THEN 'expired'
    WHEN bumped_at < NOW() - INTERVAL '${STALE_DAYS} days' THEN 'stale'
    ELSE 'active'
  END
`;

// ---------- Orders ----------

/**
 * Get order book for an item (buy + sell orders visible to everyone).
 * Only returns non-closed, non-terminated orders.
 */
export async function getOrderBook(itemId) {
  const query = `
    SELECT
      o.id, o.user_id, o.type, o.item_id, o.quantity, o.min_quantity,
      o.markup, o.planet, o.details, o.created, o.updated, o.bumped_at,
      ${COMPUTED_STATE_SQL} AS computed_state,
      u.eu_name AS seller_name
    FROM trade_offers o
    LEFT JOIN users u ON u.id = o.user_id
    WHERE o.item_id = $1
      AND o.state != 'closed'
      AND o.bumped_at >= NOW() - INTERVAL '${TERMINATED_DAYS} days'
    ORDER BY o.type, o.markup ASC, o.bumped_at DESC
  `;
  const { rows } = await pool.query(query, [itemId]);
  return rows;
}

/**
 * Get all orders for a user (My Orders view).
 */
export async function getUserOrders(userId) {
  const query = `
    SELECT
      o.id, o.user_id, o.type, o.item_id, o.quantity, o.min_quantity,
      o.markup, o.planet, o.details, o.created, o.updated, o.bumped_at,
      o.state,
      ${COMPUTED_STATE_SQL} AS computed_state
    FROM trade_offers o
    WHERE o.user_id = $1
    ORDER BY
      CASE WHEN o.state = 'closed' THEN 1 ELSE 0 END,
      o.bumped_at DESC
  `;
  const { rows } = await pool.query(query, [userId]);
  return rows;
}

/**
 * Get all active orders by a specific user (public endpoint).
 */
export async function getUserPublicOrders(userId, fetch) {
  const query = `
    SELECT
      o.id, o.type, o.item_id, o.quantity, o.min_quantity,
      o.markup, o.planet, o.details, o.bumped_at,
      ${COMPUTED_STATE_SQL} AS computed_state,
      u.eu_name AS seller_name
    FROM trade_offers o
    LEFT JOIN users u ON u.id = o.user_id
    WHERE o.user_id = $1
      AND o.state != 'closed'
      AND o.bumped_at >= NOW() - INTERVAL '${TERMINATED_DAYS} days'
    ORDER BY o.bumped_at DESC
  `;
  const { rows } = await pool.query(query, [userId]);
  const itemIds = [...new Set(rows.map(row => row.item_id).filter(Boolean))];
  const typeMap = await resolveItemTypesByItemId(itemIds, fetch);

  return rows.map(row => ({
    ...row,
    item_type: typeMap[row.item_id]?.type || null,
    item_sub_type: typeMap[row.item_id]?.subType || null
  }));
}

/**
 * Count a user's active (non-closed, non-terminated) orders on a given side.
 */
export async function countUserOrdersBySide(userId, type) {
  const query = `
    SELECT COUNT(*) AS count
    FROM trade_offers
    WHERE user_id = $1
      AND type = $2
      AND state NOT IN ('closed')
      AND bumped_at >= NOW() - INTERVAL '${TERMINATED_DAYS} days'
  `;
  const { rows } = await pool.query(query, [userId, type]);
  return parseInt(rows[0].count, 10);
}

/**
 * Create a new order.
 */
export async function createOrder({ userId, type, itemId, quantity, minQuantity, markup, planet, details }) {
  const query = `
    INSERT INTO trade_offers (user_id, type, item_id, quantity, min_quantity, markup, planet, details, created, updated, bumped_at, state)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW(), NOW(), 'active')
    RETURNING id, user_id, type, item_id, quantity, min_quantity, markup, planet, details, created, updated, bumped_at, state
  `;
  const { rows } = await pool.query(query, [
    userId, type, itemId, quantity, minQuantity ?? null, markup, planet, details ? JSON.stringify(details) : null
  ]);
  return rows[0];
}

/**
 * Get a single order by ID.
 */
export async function getOrderById(orderId) {
  const query = `
    SELECT
      id, user_id, type, item_id, quantity, min_quantity,
      markup, planet, details, created, updated, bumped_at, state,
      ${COMPUTED_STATE_SQL} AS computed_state
    FROM trade_offers
    WHERE id = $1
  `;
  const { rows } = await pool.query(query, [orderId]);
  return rows[0] || null;
}

/**
 * Update an existing order (edit). Resets bumped_at.
 */
export async function updateOrder(orderId, { quantity, minQuantity, markup, planet, details }) {
  const query = `
    UPDATE trade_offers
    SET quantity = $2, min_quantity = $3, markup = $4, planet = $5, details = $6,
        updated = NOW(), bumped_at = NOW(), state = 'active'
    WHERE id = $1
    RETURNING id, user_id, type, item_id, quantity, min_quantity, markup, planet, details, created, updated, bumped_at, state
  `;
  const { rows } = await pool.query(query, [
    orderId, quantity, minQuantity ?? null, markup, planet, details ? JSON.stringify(details) : null
  ]);
  return rows[0] || null;
}

/**
 * Close an order (soft delete).
 */
export async function closeOrder(orderId) {
  const query = `
    UPDATE trade_offers
    SET state = 'closed', updated = NOW()
    WHERE id = $1
    RETURNING id, user_id, type, item_id, quantity, min_quantity, markup, planet, details, created, updated, bumped_at, state
  `;
  const { rows } = await pool.query(query, [orderId]);
  return rows[0] || null;
}

/**
 * Delete exchange offers for items marked as untradeable in ItemProperties.
 * Runs periodically to clean up orders that became invalid after entity updates.
 */
export async function closeUntradeableOrders() {
  if (!nexusPool) return 0;
  const { rows: untradeable } = await nexusPool.query(
    `SELECT "ItemId" FROM "ItemProperties" WHERE "IsUntradeable" = TRUE`
  );
  if (untradeable.length === 0) return 0;
  const itemIds = untradeable.map(r => r.ItemId);
  const { rowCount: deleted } = await pool.query(
    `DELETE FROM trade_offers WHERE item_id = ANY($1) AND state != 'closed'`,
    [itemIds]
  );
  if (deleted > 0) console.log(`[exchange] Untradeable cleanup: deleted ${deleted} orders`);
  return deleted;
}

/**
 * Bump all eligible orders for a user (reset bumped_at to now).
 * Skips closed and terminated (>30 days) orders.
 */
export async function bumpAllOrders(userId) {
  const query = `
    UPDATE trade_offers
    SET bumped_at = NOW(), updated = NOW(), state = 'active'
    WHERE user_id = $1
      AND state != 'closed'
      AND bumped_at >= NOW() - INTERVAL '${TERMINATED_DAYS} days'
    RETURNING id, user_id, type, item_id, quantity, min_quantity, markup, planet, details, created, updated, bumped_at, state
  `;
  const { rows } = await pool.query(query, [userId]);
  return rows;
}

// ---------- Exchange Prices ----------

/**
 * Get exchange-derived price data for an item from active orders.
 */
export async function getExchangePrices(itemId, gender = null) {
  const conditions = [
    'item_id = $1',
    'markup IS NOT NULL',
    `state != 'closed'`,
    `bumped_at >= NOW() - INTERVAL '${EXPIRED_DAYS} days'`
  ];
  const values = [itemId];
  if (gender) {
    conditions.push(`details->>'Gender' = $2`);
    values.push(gender);
  }
  const query = `
    SELECT
      type,
      COUNT(*) AS order_count,
      MIN(markup) AS best_markup,
      MAX(markup) AS worst_markup,
      SUM(quantity) AS total_volume
    FROM trade_offers
    WHERE ${conditions.join(' AND ')}
    GROUP BY type
  `;
  const { rows } = await pool.query(query, values);
  const result = { buy: null, sell: null };
  for (const row of rows) {
    const side = row.type === 'BUY' ? 'buy' : 'sell';
    result[side] = {
      order_count: parseInt(row.order_count, 10),
      best_markup: parseFloat(row.best_markup),
      worst_markup: parseFloat(row.worst_markup),
      total_volume: parseInt(row.total_volume, 10)
    };
  }
  return result;
}

/**
 * Get the best (lowest sell / highest buy) markup for an item, excluding a specific user's orders.
 * Used for undercut enforcement — ensures new orders undercut by the minimum amount.
 * @param {number} itemId
 * @param {'BUY'|'SELL'} type
 * @param {number|string} excludeUserId - User whose orders to exclude (so users aren't blocked by their own orders)
 * @param {string|null} gender - Optional gender filter for gendered items
 * @returns {Promise<number|null>} Best markup, or null if no competing orders exist
 */
export async function getBestMarkupForItem(itemId, type, excludeUserId, gender = null) {
  const agg = type === 'BUY' ? 'MAX' : 'MIN';
  const conditions = [
    'item_id = $1',
    'type = $2',
    'user_id != $3',
    'markup IS NOT NULL',
    `state != 'closed'`,
    `bumped_at >= NOW() - INTERVAL '${EXPIRED_DAYS} days'`
  ];
  const values = [itemId, type, excludeUserId];
  if (gender) {
    conditions.push(`details->>'Gender' = $${values.length + 1}`);
    values.push(gender);
  }
  const { rows } = await pool.query(
    `SELECT ${agg}(markup) AS best FROM trade_offers WHERE ${conditions.join(' AND ')}`,
    values
  );
  return rows[0]?.best != null ? parseFloat(rows[0].best) : null;
}

/**
 * Get order counts and volume per item for all active (non-closed, non-terminated) orders.
 * Returns a Map of itemId -> { buys, sells, buyVol, sellVol, lastUpdate, bestBuyMarkup, bestSellMarkup }.
 */
export async function getAllOrderCounts() {
  const query = `
    SELECT item_id, type, COUNT(*) AS cnt, COALESCE(SUM(quantity), 0) AS vol,
      MAX(bumped_at) AS last_update,
      CASE WHEN type = 'BUY' THEN MAX(markup) ELSE NULL END AS best_buy_markup,
      CASE WHEN type = 'SELL' THEN MIN(markup) ELSE NULL END AS best_sell_markup,
      COUNT(*) FILTER (WHERE markup IS NULL AND type = 'SELL') AS negotiable_sells
    FROM trade_offers
    WHERE state != 'closed'
      AND bumped_at >= NOW() - INTERVAL '${TERMINATED_DAYS} days'
    GROUP BY item_id, type
  `;
  const { rows } = await pool.query(query);
  const counts = new Map();
  for (const row of rows) {
    const id = row.item_id;
    if (!counts.has(id)) counts.set(id, { buys: 0, sells: 0, buyVol: 0, sellVol: 0, lastUpdate: null, bestBuyMarkup: null, bestSellMarkup: null, negotiableSells: 0 });
    const entry = counts.get(id);
    if (row.type === 'BUY') {
      entry.buys = parseInt(row.cnt, 10);
      entry.buyVol = parseInt(row.vol, 10);
      entry.bestBuyMarkup = row.best_buy_markup != null ? parseFloat(row.best_buy_markup) : null;
    } else {
      entry.sells = parseInt(row.cnt, 10);
      entry.sellVol = parseInt(row.vol, 10);
      entry.bestSellMarkup = row.best_sell_markup != null ? parseFloat(row.best_sell_markup) : null;
      entry.negotiableSells = parseInt(row.negotiable_sells, 10) || 0;
    }
    const ts = row.last_update ? new Date(row.last_update) : null;
    if (ts && (!entry.lastUpdate || ts > entry.lastUpdate)) entry.lastUpdate = ts;
  }
  return counts;
}

const PLANETS = [
  'Calypso', 'Arkadia', 'Cyrene', 'Rocktropia',
  'Next Island', 'Monria', 'Toulan', 'Howling Mine (Space)',
];

// ---------- Exchange Price History ----------

const PERIOD_INTERVALS = {
  '24h': '1 day',
  '7d': '7 days',
  '30d': '30 days',
  '3m': '90 days',
  '6m': '180 days',
  '1y': '365 days',
  '5y': '1825 days',
  'all': null
};

/**
 * Get period-based exchange price statistics for an item.
 * Returns latest snapshot WAP and aggregate stats for the selected period.
 */
export async function getExchangePriceSummary(itemId, period = '7d', gender = null) {
  const interval = PERIOD_INTERVALS[period] ?? PERIOD_INTERVALS['7d'];

  // Latest snapshot
  const latestConds = ['item_id = $1'];
  const latestVals = [itemId];
  if (gender) {
    latestConds.push(`gender = $2`);
    latestVals.push(gender);
  }
  const latestResult = await pool.query(
    `SELECT markup_value, volume, recorded_at
     FROM exchange_price_snapshots
     WHERE ${latestConds.join(' AND ')}
     ORDER BY recorded_at DESC LIMIT 1`,
    latestVals
  );

  // Period aggregation
  const conditions = ['item_id = $1'];
  const values = [itemId];
  let paramIdx = 2;
  if (gender) {
    conditions.push(`gender = $${paramIdx}`);
    values.push(gender);
    paramIdx++;
  }
  if (interval) {
    conditions.push(`recorded_at >= NOW() - INTERVAL '${interval}'`);
  }

  const statsResult = await pool.query(`
    SELECT
      PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY markup_value) AS median,
      PERCENTILE_CONT(0.1) WITHIN GROUP (ORDER BY markup_value) AS p10,
      SUM(markup_value * volume) / NULLIF(SUM(volume), 0) AS wap,
      COUNT(*) AS sample_count
    FROM exchange_price_snapshots
    WHERE ${conditions.join(' AND ')}
  `, values);

  const stats = statsResult.rows[0];

  return {
    latest: latestResult.rows[0] ? {
      wap: parseFloat(latestResult.rows[0].markup_value),
      volume: parseInt(latestResult.rows[0].volume, 10),
      recorded_at: latestResult.rows[0].recorded_at
    } : null,
    period: stats?.sample_count > 0 ? {
      median: stats.median != null ? parseFloat(stats.median) : null,
      p10: stats.p10 != null ? parseFloat(stats.p10) : null,
      wap: stats.wap != null ? parseFloat(stats.wap) : null,
      sample_count: parseInt(stats.sample_count, 10)
    } : null
  };
}

/**
 * Get exchange price history time series for charting.
 * Returns raw snapshots for short periods, summaries for longer ones.
 */
export async function getExchangePriceHistory(itemId, period = '7d', gender = null) {
  const interval = PERIOD_INTERVALS[period] ?? PERIOD_INTERVALS['7d'];

  // For ≤30d use raw snapshots, for longer use summaries
  const useRaw = ['24h', '7d', '30d'].includes(period);

  if (useRaw) {
    const conditions = ['item_id = $1'];
    const values = [itemId];
    let paramIdx = 2;
    if (gender) {
      conditions.push(`gender = $${paramIdx}`);
      values.push(gender);
      paramIdx++;
    }
    if (interval) {
      conditions.push(`recorded_at >= NOW() - INTERVAL '${interval}'`);
    }
    const { rows } = await pool.query(`
      SELECT markup_value, volume, recorded_at AS timestamp
      FROM exchange_price_snapshots
      WHERE ${conditions.join(' AND ')}
      ORDER BY recorded_at ASC
    `, values);

    return rows.map(r => ({
      timestamp: r.timestamp,
      wap: parseFloat(r.markup_value),
      volume: parseInt(r.volume, 10)
    }));
  }

  // For longer periods use pre-computed summaries
  const periodType = ['3m', '6m'].includes(period) ? 'day' : 'week';
  const conditions = ['item_id = $1', 'period_type = $2'];
  const values = [itemId, periodType];
  let paramIdx = 3;
  if (gender) {
    conditions.push(`gender = $${paramIdx}`);
    values.push(gender);
    paramIdx++;
  }
  if (interval) {
    conditions.push(`period_start >= NOW() - INTERVAL '${interval}'`);
  }
  const { rows } = await pool.query(`
    SELECT period_start AS timestamp, price_min, price_max, price_median, price_wap, volume, sample_count
    FROM exchange_price_summaries
    WHERE ${conditions.join(' AND ')}
    ORDER BY period_start ASC
  `, values);

  return rows.map(r => ({
    timestamp: r.timestamp,
    min: parseFloat(r.price_min),
    max: parseFloat(r.price_max),
    median: r.price_median != null ? parseFloat(r.price_median) : null,
    wap: parseFloat(r.price_wap),
    volume: parseInt(r.volume, 10),
    sample_count: parseInt(r.sample_count, 10)
  }));
}

/**
 * Get price stats for all items from the latest exchange price summaries
 * (pre-computed by the bot every 15 minutes with IQR outlier filtering).
 * Prefers non-gendered (gender='') rows; falls back to gendered aggregates.
 * Falls back to raw snapshots for items with no summaries yet.
 * Returns a Map of itemId -> { wap, median, p10 }.
 */
export async function getLatestExchangePriceMap() {
  const map = new Map();

  function parseRow(r) {
    return {
      median: r.price_median != null ? parseFloat(r.price_median) : null,
      p10: r.price_p10 != null ? parseFloat(r.price_p10) : null,
      wap: r.price_wap != null ? parseFloat(r.price_wap) : null
    };
  }

  // Base: daily summaries within 7 days — prefer non-gendered rows
  const { rows: dailyRows } = await pool.query(`
    SELECT DISTINCT ON (item_id)
      item_id, price_median, price_p10, price_wap
    FROM exchange_price_summaries
    WHERE period_type = 'day'
      AND period_start >= NOW() - INTERVAL '7 days'
      AND gender = ''
    ORDER BY item_id, period_start DESC
  `);
  for (const r of dailyRows) map.set(r.item_id, parseRow(r));

  // Daily fallback: gendered items that have no gender='' row — aggregate across variants
  const { rows: dailyGendered } = await pool.query(`
    SELECT item_id,
      PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_median) AS price_median,
      PERCENTILE_CONT(0.1) WITHIN GROUP (ORDER BY price_p10) AS price_p10,
      SUM(price_wap * volume) / NULLIF(SUM(volume), 0) AS price_wap
    FROM (
      SELECT DISTINCT ON (item_id, gender)
        item_id, gender, price_median, price_p10, price_wap, volume
      FROM exchange_price_summaries
      WHERE period_type = 'day'
        AND period_start >= NOW() - INTERVAL '7 days'
        AND gender != ''
      ORDER BY item_id, gender, period_start DESC
    ) sub
    GROUP BY item_id
  `);
  for (const r of dailyGendered) {
    if (!map.has(r.item_id)) map.set(r.item_id, parseRow(r));
  }

  // Overlay: fresh hourly summaries override daily where available
  const { rows: hourlyRows } = await pool.query(`
    SELECT DISTINCT ON (item_id)
      item_id, price_median, price_p10, price_wap
    FROM exchange_price_summaries
    WHERE period_type = 'hour'
      AND period_start >= NOW() - INTERVAL '24 hours'
      AND gender = ''
    ORDER BY item_id, period_start DESC
  `);
  for (const r of hourlyRows) map.set(r.item_id, parseRow(r));

  // Hourly fallback for gendered items
  const { rows: hourlyGendered } = await pool.query(`
    SELECT item_id,
      PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_median) AS price_median,
      PERCENTILE_CONT(0.1) WITHIN GROUP (ORDER BY price_p10) AS price_p10,
      SUM(price_wap * volume) / NULLIF(SUM(volume), 0) AS price_wap
    FROM (
      SELECT DISTINCT ON (item_id, gender)
        item_id, gender, price_median, price_p10, price_wap, volume
      FROM exchange_price_summaries
      WHERE period_type = 'hour'
        AND period_start >= NOW() - INTERVAL '24 hours'
        AND gender != ''
      ORDER BY item_id, gender, period_start DESC
    ) sub
    GROUP BY item_id
  `);
  for (const r of hourlyGendered) {
    if (!map.has(r.item_id)) map.set(r.item_id, parseRow(r));
  }

  // Per-item fallback: raw snapshots for items with snapshots but no summaries yet
  const { rows: snaps } = await pool.query(`
    SELECT DISTINCT ON (item_id)
      item_id, markup_value
    FROM exchange_price_snapshots
    WHERE recorded_at >= NOW() - INTERVAL '7 days'
      AND gender = ''
    ORDER BY item_id, recorded_at DESC
  `);
  for (const r of snaps) {
    if (!map.has(r.item_id)) {
      const wap = r.markup_value != null ? parseFloat(r.markup_value) : null;
      map.set(r.item_id, { median: wap, p10: wap, wap });
    }
  }

  return map;
}

/**
 * Get the set of planets with active orders per item.
 * Returns a Map of itemId -> string[] (planet names).
 */
export async function getOrderPlanets() {
  const query = `
    SELECT item_id, planet
    FROM trade_offers
    WHERE state != 'closed'
      AND bumped_at >= NOW() - INTERVAL '${TERMINATED_DAYS} days'
      AND planet IS NOT NULL
    GROUP BY item_id, planet
  `;
  const { rows } = await pool.query(query);
  const map = new Map();
  for (const row of rows) {
    const id = row.item_id;
    if (!map.has(id)) map.set(id, []);
    map.get(id).push(row.planet);
  }
  return map;
}

/**
 * Count a user's active orders for a specific item and side.
 */
export async function countUserOrdersForItem(userId, itemId, type) {
  const query = `
    SELECT COUNT(*) AS count
    FROM trade_offers
    WHERE user_id = $1
      AND item_id = $2
      AND type = $3
      AND state NOT IN ('closed')
      AND bumped_at >= NOW() - INTERVAL '${TERMINATED_DAYS} days'
  `;
  const { rows } = await pool.query(query, [userId, itemId, type]);
  return parseInt(rows[0].count, 10);
}

// ---------- Item Type Lookup ----------
// Fetches item metadata via the entity API (not direct DB queries — entity tables
// live in the nexus database, while this module's pool connects to nexus_users).

import { apiCall, hasItemTag } from '$lib/util.js';
import { isPercentMarkupType, isStackableType, ARMOR_SET_OFFSET, STRONGBOX_OFFSET, GENDERED_TYPES } from '$lib/common/itemTypes.js';
import { resolveItemTypesByItemId } from '$lib/server/item-type-cache.js';

// Material ID offset for sub-type lookup (mirrors api/endpoints/constants.js)
const MATERIAL_ID_OFFSET = 1000000;

/**
 * Get item type, name, gender, and optional sub-type via the entity API.
 * ArmorSets (13M+ range) are detected by ID since they aren't in the Items table.
 * Gender is included for Armor/Clothing items (from the /items endpoint).
 * For Materials, also fetches the sub-type from /materials (e.g., 'Deed', 'Token').
 *
 * @param {number} itemId
 * @param {typeof fetch} fetch - SvelteKit fetch for server-side API calls
 * @returns {Promise<{type: string, name: string, gender?: string, subType?: string}|null>}
 */
export async function getItemType(itemId, fetch) {
  // ArmorSet IDs live in the 13000000–13999999 range (not in Items table)
  if (itemId >= ARMOR_SET_OFFSET && itemId < ARMOR_SET_OFFSET + 1000000) {
    return { type: 'ArmorSet', name: null, gender: 'Both' };
  }

  // Strongbox IDs live in the 12000000–12999999 range (not in Items table)
  if (itemId >= STRONGBOX_OFFSET && itemId < STRONGBOX_OFFSET + 1000000) {
    return { type: 'Strongbox', name: null };
  }

  const item = await apiCall(fetch, `/items/${itemId}`);
  if (!item) return null;

  const type = item.Properties?.Type;
  const result = {
    type,
    name: item.Name,
    // For gendered types: null means "no gender data" (e.g. clothing with NULL gender → non-tradeable).
    // For non-gendered types: undefined means "gender not applicable".
    gender: GENDERED_TYPES.has(type) ? (item.Properties?.Gender ?? null) : undefined
  };

  // For Materials, look up sub-type (Deed, Token, etc.) from detailed endpoint
  if (result.type === 'Material') {
    const matId = itemId - MATERIAL_ID_OFFSET;
    const mat = await apiCall(fetch, `/materials/${matId}`);
    if (mat?.Properties?.Type) result.subType = mat.Properties.Type;
  }

  return result;
}

/**
 * Server-side check: does this item type use percentage markup?
 * Delegates to shared itemTypes module.
 * @param {string} type - Item type (e.g., 'Material')
 * @param {string} name - Item name
 * @param {string|null} subType - Material sub-type (e.g., 'Deed', 'Token')
 */
export function isPercentMarkupServer(type, name, subType = null) {
  return isPercentMarkupType(type, name, subType);
}

/**
 * Check if an item type is fungible (stackable = quantity-based, percent markup).
 */
export function isItemFungible(type, name) {
  return isStackableType(type, name);
}

/**
 * Format seconds into a human-readable retry time.
 * @param {number} seconds
 * @returns {string}
 */
export function formatRetryTime(seconds) {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.ceil(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.ceil(seconds / 3600)}h`;
  return `${Math.ceil(seconds / 86400)}d`;
}

// ---------- Negotiable Listing Config ----------

/**
 * Get a user's negotiable listing configuration.
 */
export async function getUserNegotiableConfig(userId) {
  const { rows } = await pool.query(
    `SELECT id, config, created_at, updated_at FROM user_negotiable_configs WHERE user_id = $1`,
    [userId]
  );
  return rows[0] || null;
}

/**
 * Upsert a user's negotiable listing configuration.
 */
export async function upsertNegotiableConfig(userId, config) {
  const { rows } = await pool.query(
    `INSERT INTO user_negotiable_configs (user_id, config, updated_at)
     VALUES ($1, $2, NOW())
     ON CONFLICT (user_id)
     DO UPDATE SET config = EXCLUDED.config, updated_at = NOW()
     RETURNING id, config, created_at, updated_at`,
    [userId, JSON.stringify(config)]
  );
  return rows[0];
}

/**
 * Delete a user's negotiable listing configuration.
 */
export async function deleteNegotiableConfig(userId) {
  const { rowCount } = await pool.query(
    `DELETE FROM user_negotiable_configs WHERE user_id = $1`,
    [userId]
  );
  return rowCount > 0;
}

/**
 * Delete all negotiable (markup IS NULL) sell offers for a user.
 * Negotiable listings are deleted rather than closed to avoid cluttering My Orders.
 */
export async function deleteAllNegotiableOffers(userId) {
  const { rowCount } = await pool.query(
    `DELETE FROM trade_offers
     WHERE user_id = $1 AND markup IS NULL AND type = 'SELL' AND state != 'closed'`,
    [userId]
  );
  return rowCount;
}

/**
 * Validate and sanitize a negotiable config object.
 * Returns the sanitized config or throws on invalid input.
 */
const MAX_CONFIG_NODES = 200;
const MAX_PATH_LENGTH = 500;
const MAX_SUBSTRING_LENGTH = 200;
const MAX_WHITELIST_IDS = 1000;
const VALID_FILTER_MODES = ['whitelist', 'blacklist', 'match'];
const VALID_ITEM_TYPES = [
  'Weapon', 'Armor', 'ArmorPlating', 'ArmorSet', 'Vehicle',
  'WeaponAmplifier', 'WeaponVisionAttachment', 'Absorber',
  'Finder', 'FinderAmplifier', 'Excavator', 'Refiner', 'Scanner',
  'TeleportationChip', 'EffectChip', 'MedicalChip',
  'MiscTool', 'MedicalTool', 'MindforceImplant', 'Pet', 'Clothing',
  'Material', 'Consumable', 'Capsule', 'Enhancer', 'Strongbox',
  'Blueprint', 'BlueprintBook', 'SkillImplant',
  'Furniture', 'Decoration', 'StorageContainer', 'Sign',
];

export function validateNegotiableConfig(config) {
  if (!config || typeof config !== 'object') throw new Error('Config must be an object');
  if (!Array.isArray(config.nodes)) throw new Error('Config must have a nodes array');
  if (config.nodes.length > MAX_CONFIG_NODES) throw new Error(`Maximum ${MAX_CONFIG_NODES} nodes`);

  const sanitized = { nodes: [] };

  for (let i = 0; i < config.nodes.length; i++) {
    const node = config.nodes[i];
    if (!node || typeof node !== 'object') throw new Error(`nodes[${i}] must be an object`);

    const path = typeof node.path === 'string' ? node.path.trim() : '';
    if (!path) throw new Error(`nodes[${i}].path is required`);
    if (path.length > MAX_PATH_LENGTH) throw new Error(`nodes[${i}].path exceeds maximum length`);

    const state = node.state;
    if (state !== 'included' && state !== 'excluded') throw new Error(`nodes[${i}].state must be 'included' or 'excluded'`);

    const sanitizedNode = { path, state };

    if (state === 'included' && node.filter != null) {
      const f = node.filter;
      if (typeof f !== 'object') throw new Error(`nodes[${i}].filter must be an object`);
      if (!VALID_FILTER_MODES.includes(f.mode)) throw new Error(`nodes[${i}].filter.mode must be one of: ${VALID_FILTER_MODES.join(', ')}`);

      const sanitizedFilter = { mode: f.mode };

      if (f.mode === 'whitelist' || f.mode === 'blacklist') {
        if (!Array.isArray(f.itemIds)) throw new Error(`nodes[${i}].filter.itemIds must be an array`);
        if (f.itemIds.length > MAX_WHITELIST_IDS) throw new Error(`nodes[${i}].filter.itemIds exceeds maximum ${MAX_WHITELIST_IDS}`);
        sanitizedFilter.itemIds = f.itemIds
          .map(id => parseInt(id, 10))
          .filter(id => Number.isFinite(id) && id > 0);
      } else if (f.mode === 'match') {
        const sub = typeof f.substring === 'string' ? f.substring.replace(/[\x00-\x1f]/g, '').trim() : '';
        if (sub.length > MAX_SUBSTRING_LENGTH) throw new Error(`nodes[${i}].filter.substring exceeds maximum length`);
        sanitizedFilter.substring = sub;
        sanitizedFilter.useRegex = !!f.useRegex;
        if (sanitizedFilter.useRegex && sub) {
          // Reject patterns with known catastrophic backtracking constructs
          if (/(\.\*){3,}|\(\[?[^)]*\+\)\+|\(\[?[^)]*\*\)\+|\(\[?[^)]*\+\)\*/.test(sub)) {
            throw new Error(`nodes[${i}].filter.substring contains a potentially unsafe regex pattern`);
          }
          try { new RegExp(sub); } catch { throw new Error(`nodes[${i}].filter.substring is not a valid regex`); }
        }
        sanitizedFilter.negate = !!f.negate;
        if (Array.isArray(f.itemTypes)) {
          sanitizedFilter.itemTypes = f.itemTypes.filter(t => VALID_ITEM_TYPES.includes(t));
        } else {
          sanitizedFilter.itemTypes = [];
        }
      }

      sanitizedNode.filter = sanitizedFilter;
    }

    sanitized.nodes.push(sanitizedNode);
  }

  return sanitized;
}

/**
 * Resolve a negotiable config against the user's inventory.
 * Returns an array of items to list: [{ item_id, item_name, quantity, value, details, planet }]
 */
export function resolveNegotiableConfig(config, inventoryItems, slimLookup) {
  if (!config?.nodes?.length || !inventoryItems?.length) return [];

  // Build included/excluded path sets
  const includedNodes = [];
  const excludedPaths = new Set();
  for (const node of config.nodes) {
    if (node.state === 'included') includedNodes.push(node);
    else if (node.state === 'excluded') excludedPaths.add(node.path);
  }
  if (includedNodes.length === 0) return [];

  // Extract planet from a container_path root segment
  function extractPlanet(containerPath) {
    if (!containerPath) return null;
    const root = containerPath.split(' > ')[0];
    const m = root.match(/^STORAGE \(([^)]+)\)$/i);
    return m ? m[1].trim() : null;
  }

  // Check if an item's container_path is under an excluded path
  function isExcluded(itemPath) {
    if (!itemPath) return false;
    for (const ep of excludedPaths) {
      if (itemPath === ep || itemPath.startsWith(ep + ' > ')) return true;
    }
    return false;
  }

  // Pre-compile regexes for match filters
  const compiledRegexes = new Map();
  for (const node of includedNodes) {
    if (node.filter?.mode === 'match' && node.filter.useRegex && node.filter.substring) {
      try { compiledRegexes.set(node.path, new RegExp(node.filter.substring, 'i')); } catch { /* skip */ }
    }
  }

  // Check if an item matches a filter
  function matchesFilter(item, filter, slim, nodePath) {
    if (!filter) return true; // null filter = include all

    if (filter.mode === 'whitelist') {
      return filter.itemIds?.includes(item.item_id);
    }
    if (filter.mode === 'blacklist') {
      return !filter.itemIds?.includes(item.item_id);
    }
    if (filter.mode === 'match') {
      let nameMatch = true;
      if (filter.substring) {
        const re = compiledRegexes.get(nodePath);
        if (re) {
          nameMatch = re.test(item.item_name);
        } else if (!filter.useRegex) {
          nameMatch = item.item_name.toLowerCase().includes(filter.substring.toLowerCase());
        } else {
          nameMatch = false;
        }
      }
      let typeMatch = true;
      if (filter.itemTypes?.length > 0) {
        const itemType = slim?.t || null;
        typeMatch = itemType ? filter.itemTypes.includes(itemType) : false;
      }
      const result = nameMatch && typeMatch;
      return filter.negate ? !result : result;
    }
    return true;
  }

  const results = [];
  const seen = new Map(); // key → results index (for merge/dedup)

  for (const node of includedNodes) {
    for (const item of inventoryItems) {
      // Skip unresolved items
      if (!item.item_id || item.item_id === 0) continue;

      // Check container_path prefix match: item is in this node or a descendant
      const itemPath = item.container_path || '';
      const isDirectMatch = itemPath === node.path;
      const isDescendant = node.path && itemPath.startsWith(node.path + ' > ');
      if (!isDirectMatch && !isDescendant) continue;

      // Check exclusions
      if (isExcluded(itemPath)) continue;

      // Skip items not in the exchange cache or marked untradeable
      const slim = slimLookup?.get(item.item_id) || null;
      if (!slim || slim.ut) continue;

      // Apply filter
      if (!matchesFilter(item, node.filter || null, slim, node.path)) continue;

      const planet = extractPlanet(itemPath);
      if (!planet) continue; // Skip items without a determinable planet

      const itemType = slim?.t || null;
      const itemName = slim?.n || item.item_name;
      const stackable = itemType ? isStackableType(itemType, itemName) : false;

      // Determine gender for gendered item types
      let gender;
      if (slim?.g === 'Male' || slim?.g === 'Female') {
        gender = slim.g;
      } else if (slim?.g === 'Both') {
        if (hasItemTag(item.item_name, 'M')) gender = 'Male';
        else if (hasItemTag(item.item_name, 'F')) gender = 'Female';
      }

      const genderSuffix = gender ? `::${gender}` : '';

      if (stackable) {
        // Stackable items: merge all stacks on the same planet into one listing
        const mergeKey = `${item.item_id}::${planet}${genderSuffix}`;
        if (seen.has(mergeKey)) {
          const existing = results[seen.get(mergeKey)];
          existing.quantity += item.quantity || 1;
          if (item.value != null) {
            existing.value = (existing.value ?? 0) + Number(item.value);
          }
        } else {
          seen.set(mergeKey, results.length);
          results.push({
            item_id: item.item_id,
            item_name: itemName,
            quantity: item.quantity || 1,
            value: item.value != null ? Number(item.value) : null,
            details: item.details || null,
            planet,
            instance_key: null,
            gender,
          });
        }
      } else {
        // Non-stackable (condition) items: each gets its own listing
        const dedupKey = `${item.item_id}::${planet}::${item.instance_key || item.id}`;
        if (seen.has(dedupKey)) continue;

        seen.set(dedupKey, results.length);
        results.push({
          item_id: item.item_id,
          item_name: itemName,
          quantity: item.quantity || 1,
          value: item.value ?? null,
          details: item.details || null,
          planet,
          instance_key: item.instance_key || null,
          gender,
        });
      }
    }
  }

  // Prefer highest-TT condition items when per-item limits apply
  results.sort((a, b) => (b.value ?? 0) - (a.value ?? 0));

  return results;
}

/**
 * Sync negotiable exchange listings for a user based on their config and inventory.
 * Creates new offers for items not yet listed, closes offers for items no longer matching.
 * Returns { created, closed, skipped }.
 */
export async function syncNegotiableListings(userId, { slimLookup } = {}) {
  // 1. Load config — if empty/missing, close all negotiable offers
  const configRow = await getUserNegotiableConfig(userId);
  if (!configRow?.config?.nodes?.length) {
    const closed = await deleteAllNegotiableOffers(userId);
    return { created: 0, closed, skipped: 0 };
  }

  // 2. Load inventory
  const { rows: inventory } = await pool.query(
    `SELECT id, item_id, item_name, quantity, instance_key, details, value, container, container_path
     FROM user_items WHERE user_id = $1 AND storage = 'server'`,
    [userId]
  );

  // 3. Resolve config
  const resolved = resolveNegotiableConfig(configRow.config, inventory, slimLookup);

  // 4. Load existing sell offers (priced + negotiable)
  const { rows: existingOffers } = await pool.query(
    `SELECT id, item_id, planet, markup, details
     FROM trade_offers
     WHERE user_id = $1 AND type = 'SELL' AND state != 'closed'
       AND bumped_at >= NOW() - INTERVAL '${TERMINATED_DAYS} days'`,
    [userId]
  );

  // Build lookup of existing offers
  // For non-stackable items, include instance_key in the key to allow multiple per item+planet
  const pricedByItemPlanet = new Set();
  const negotiableByKey = new Map(); // key → offer row
  const orderCountByItem = new Map(); // item_id → count of all active sell offers
  for (const offer of existingOffers) {
    const offerGender = offer.details?.Gender;
    const genderSuffix = offerGender ? `::${offerGender}` : '';
    const instanceSuffix = offer.details?.instance_key ? `::${offer.details.instance_key}` : '';
    const key = `${offer.item_id}::${offer.planet}${genderSuffix}${instanceSuffix}`;
    const cnt = orderCountByItem.get(offer.item_id) || 0;
    orderCountByItem.set(offer.item_id, cnt + 1);
    if (offer.markup != null) {
      pricedByItemPlanet.add(`${offer.item_id}::${offer.planet}${genderSuffix}`);
    } else {
      negotiableByKey.set(key, offer);
    }
  }

  // 5. Determine what to create and what to close
  const toCreate = [];
  const resolvedKeys = new Set();
  let skipped = 0;

  for (const item of resolved) {
    const genderSuffix = item.gender ? `::${item.gender}` : '';
    const instanceSuffix = item.instance_key ? `::${item.instance_key}` : '';
    const key = `${item.item_id}::${item.planet}${genderSuffix}${instanceSuffix}`;
    const pricedKey = `${item.item_id}::${item.planet}${genderSuffix}`;
    resolvedKeys.add(key);

    // Skip if priced sell offer already exists
    if (pricedByItemPlanet.has(pricedKey)) { skipped++; continue; }
    // Skip if negotiable offer already exists
    if (negotiableByKey.has(key)) continue;
    // Check per-item limit
    const currentCount = orderCountByItem.get(item.item_id) || 0;
    if (currentCount >= MAX_ORDERS_PER_ITEM) { skipped++; continue; }
    // Check global sell order limit
    if (existingOffers.length + toCreate.length >= MAX_SELL_ORDERS) { skipped++; continue; }

    toCreate.push(item);
    orderCountByItem.set(item.item_id, currentCount + 1);
  }

  // Close negotiable offers that are no longer in the resolved set
  const toClose = [];
  for (const [key, offer] of negotiableByKey) {
    if (!resolvedKeys.has(key)) toClose.push(offer.id);
  }

  // 6. Execute in transaction
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    // Delete removed negotiable offers (delete, not close, to avoid My Orders clutter)
    if (toClose.length > 0) {
      await client.query(
        `DELETE FROM trade_offers WHERE id = ANY($1) AND user_id = $2 AND markup IS NULL`,
        [toClose, userId]
      );
    }

    // Create new offers in batches
    const BATCH = 50;
    for (let i = 0; i < toCreate.length; i += BATCH) {
      const batch = toCreate.slice(i, i + BATCH);
      const values = [];
      const params = [];
      let idx = 1;
      for (const item of batch) {
        const details = { item_name: item.item_name };
        if (item.gender) details.Gender = item.gender;
        if (item.instance_key) details.instance_key = item.instance_key;
        if (item.details?.Tier != null) details.Tier = item.details.Tier;
        if (item.details?.TierIncreaseRate != null) details.TierIncreaseRate = item.details.TierIncreaseRate;
        if (item.details?.QualityRating != null) details.QualityRating = item.details.QualityRating;
        if (item.value != null) details.CurrentTT = Number(item.value);

        values.push(`($${idx++}, 'SELL', $${idx++}, $${idx++}, NULL, NULL, $${idx++}, $${idx++}, NOW(), NOW(), NOW(), 'active')`);
        params.push(userId, item.item_id, item.quantity, item.planet, JSON.stringify(details));
      }
      await client.query(
        `INSERT INTO trade_offers (user_id, type, item_id, quantity, min_quantity, markup, planet, details, created, updated, bumped_at, state)
         VALUES ${values.join(', ')}`,
        params
      );
    }

    await client.query('COMMIT');
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }

  return { created: toCreate.length, removed: toClose.length, skipped };
}

export {
  MAX_SELL_ORDERS, MAX_BUY_ORDERS, MAX_ORDERS_PER_ITEM, MAX_BATCH_SIZE, PLANETS,
  RATE_LIMIT_CREATE_PER_MIN, RATE_LIMIT_CREATE_PER_HOUR, RATE_LIMIT_CREATE_PER_DAY,
  RATE_LIMIT_ITEM_COOLDOWN_MS, RATE_LIMIT_ITEM_FUNGIBLE_COOLDOWN, RATE_LIMIT_ITEM_NONFUNGIBLE_COOLDOWN,
  RATE_LIMIT_ITEM_DAILY_FUNGIBLE,
  RATE_LIMIT_EDIT_PER_MIN, RATE_LIMIT_BUMP_ALL_PER_HOUR, RATE_LIMIT_CLOSE_PER_MIN,
};
