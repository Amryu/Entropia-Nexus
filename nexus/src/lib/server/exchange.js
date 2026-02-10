//@ts-nocheck
import { pool } from './db.js';

// Staleness thresholds (days)
const STALE_DAYS = 3;
const EXPIRED_DAYS = 7;
const TERMINATED_DAYS = 30;
const MAX_ORDERS_PER_SIDE = 200;
const MAX_ORDERS_PER_ITEM = 5;

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
 * Bump an order (reset bumped_at to now).
 */
export async function bumpOrder(orderId) {
  const query = `
    UPDATE trade_offers
    SET bumped_at = NOW(), updated = NOW(), state = 'active'
    WHERE id = $1
      AND state != 'closed'
    RETURNING id, user_id, type, item_id, quantity, min_quantity, markup, planet, details, created, updated, bumped_at, state
  `;
  const { rows } = await pool.query(query, [orderId]);
  return rows[0] || null;
}

// ---------- Exchange Prices ----------

/**
 * Get exchange-derived price data for an item from active orders.
 */
export async function getExchangePrices(itemId) {
  const query = `
    SELECT
      type,
      COUNT(*) AS order_count,
      MIN(markup) AS best_markup,
      MAX(markup) AS worst_markup,
      SUM(quantity) AS total_volume
    FROM trade_offers
    WHERE item_id = $1
      AND state != 'closed'
      AND bumped_at >= NOW() - INTERVAL '${EXPIRED_DAYS} days'
    GROUP BY type
  `;
  const { rows } = await pool.query(query, [itemId]);
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
 * Get order counts per item for all active (non-closed, non-terminated) orders.
 * Returns a Map of itemId -> { buys, sells, lastUpdate }.
 */
export async function getAllOrderCounts() {
  const query = `
    SELECT item_id, type, COUNT(*) AS cnt, MAX(bumped_at) AS last_update
    FROM trade_offers
    WHERE state != 'closed'
      AND bumped_at >= NOW() - INTERVAL '${TERMINATED_DAYS} days'
    GROUP BY item_id, type
  `;
  const { rows } = await pool.query(query);
  const counts = new Map();
  for (const row of rows) {
    const id = row.item_id;
    if (!counts.has(id)) counts.set(id, { buys: 0, sells: 0, lastUpdate: null });
    const entry = counts.get(id);
    if (row.type === 'BUY') entry.buys = parseInt(row.cnt, 10);
    else entry.sells = parseInt(row.cnt, 10);
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
export async function getExchangePriceSummary(itemId, period = '7d') {
  const interval = PERIOD_INTERVALS[period] ?? PERIOD_INTERVALS['7d'];

  // Latest snapshot
  const latestResult = await pool.query(
    `SELECT markup_value, volume, recorded_at
     FROM exchange_price_snapshots
     WHERE item_id = $1
     ORDER BY recorded_at DESC LIMIT 1`,
    [itemId]
  );

  // Period aggregation
  const conditions = ['item_id = $1'];
  const values = [itemId];
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
export async function getExchangePriceHistory(itemId, period = '7d') {
  const interval = PERIOD_INTERVALS[period] ?? PERIOD_INTERVALS['7d'];

  // For ≤30d use raw snapshots, for longer use summaries
  const useRaw = ['24h', '7d', '30d'].includes(period);

  if (useRaw) {
    const conditions = ['item_id = $1'];
    const values = [itemId];
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
 * Get price stats for all items from the latest hourly exchange price summaries
 * (pre-computed by the bot every 15 minutes with IQR outlier filtering).
 * Falls back to raw snapshots if no summaries exist yet.
 * Returns a Map of itemId -> { wap, median, p10 }.
 */
export async function getLatestExchangePriceMap() {
  // Try hourly summaries first (has median/p10/wap breakdown)
  const { rows } = await pool.query(`
    SELECT DISTINCT ON (item_id)
      item_id, price_median, price_p10, price_wap
    FROM exchange_price_summaries
    WHERE period_type = 'hour'
      AND period_start >= NOW() - INTERVAL '24 hours'
    ORDER BY item_id, period_start DESC
  `);

  const map = new Map();
  for (const r of rows) {
    map.set(r.item_id, {
      median: r.price_median != null ? parseFloat(r.price_median) : null,
      p10: r.price_p10 != null ? parseFloat(r.price_p10) : null,
      wap: r.price_wap != null ? parseFloat(r.price_wap) : null
    });
  }

  // Fallback: if no summaries yet, use raw snapshots
  if (map.size === 0) {
    const { rows: snaps } = await pool.query(`
      SELECT DISTINCT ON (item_id)
        item_id, markup_value
      FROM exchange_price_snapshots
      WHERE recorded_at >= NOW() - INTERVAL '24 hours'
      ORDER BY item_id, recorded_at DESC
    `);
    for (const r of snaps) {
      const wap = r.markup_value != null ? parseFloat(r.markup_value) : null;
      map.set(r.item_id, { median: wap, p10: wap, wap });
    }
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

export { MAX_ORDERS_PER_SIDE, MAX_ORDERS_PER_ITEM, PLANETS };
