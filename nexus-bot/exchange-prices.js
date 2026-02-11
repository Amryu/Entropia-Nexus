import { poolUsers } from './db.js';

// Staleness: include active + stale offers (bumped within 7 days)
const SNAPSHOT_STALENESS_DAYS = 7;
const IQR_K = 1.5;
const MIN_OFFERS_FOR_IQR = 4;

const VALID_PERIOD_TYPES = ['hour', 'day', 'week'];

// ---- Outlier Filtering ----

function interpolatedPercentile(sortedArr, p) {
  const idx = p * (sortedArr.length - 1);
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  if (lo === hi) return sortedArr[lo];
  return sortedArr[lo] + (sortedArr[hi] - sortedArr[lo]) * (idx - lo);
}

function iqrFilter(offers) {
  if (offers.length === 0) return [];
  if (offers.length < MIN_OFFERS_FOR_IQR) return offers;

  const sorted = [...offers].sort((a, b) => a.markup - b.markup);
  const values = sorted.map(o => o.markup);
  const q1 = interpolatedPercentile(values, 0.25);
  const q3 = interpolatedPercentile(values, 0.75);
  const iqr = q3 - q1;
  const lower = q1 - IQR_K * iqr;
  const upper = q3 + IQR_K * iqr;

  return sorted.filter(o => o.markup >= lower && o.markup <= upper);
}

function sideWAP(offers) {
  if (offers.length === 0) return null;
  const totalQty = offers.reduce((s, o) => s + o.quantity, 0);
  if (totalQty === 0) return null;
  return offers.reduce((s, o) => s + o.markup * o.quantity, 0) / totalQty;
}

// ---- Snapshot ----

/**
 * Snapshot exchange prices from active trade_offers.
 * Applies IQR outlier filtering per side, computes volume-weighted average
 * combining buy and sell sides, and inserts into exchange_price_snapshots.
 * @returns {number} Number of items snapshotted
 */
export async function snapshotExchangePrices() {
  const { rows } = await poolUsers.query(`
    SELECT item_id, type, markup, quantity, details
    FROM trade_offers
    WHERE state != 'closed'
      AND bumped_at >= NOW() - INTERVAL '${SNAPSHOT_STALENESS_DAYS} days'
    ORDER BY item_id, type, markup
  `);

  // Group by (item_id, gender) with separate buy/sell sides
  const itemOffers = new Map();
  for (const row of rows) {
    const gender = row.details?.Gender || '';
    const key = `${row.item_id}:${gender}`;
    if (!itemOffers.has(key)) {
      itemOffers.set(key, { item_id: row.item_id, gender, buy: [], sell: [] });
    }
    const side = row.type === 'BUY' ? 'buy' : 'sell';
    // Armor plate sets count as 7 individual plates for price weighting
    const isSet = row.details?.is_set === true;
    const effectiveQty = isSet ? parseInt(row.quantity, 10) * 7 : parseInt(row.quantity, 10);
    itemOffers.get(key)[side].push({
      markup: parseFloat(row.markup),
      quantity: effectiveQty
    });
  }

  const snapshots = [];
  const now = new Date();

  for (const [, { item_id: itemId, gender, buy, sell }] of itemOffers) {
    const sides = { buy, sell };
    const filteredBuy = iqrFilter(sides.buy);
    const filteredSell = iqrFilter(sides.sell);

    if (filteredBuy.length === 0 && filteredSell.length === 0) continue;

    const buyWap = sideWAP(filteredBuy);
    const sellWap = sideWAP(filteredSell);
    const buyVol = filteredBuy.reduce((s, o) => s + o.quantity, 0);
    const sellVol = filteredSell.reduce((s, o) => s + o.quantity, 0);

    let wap, totalVolume;

    if (buyWap !== null && sellWap !== null) {
      const total = buyVol + sellVol;
      wap = (buyWap * buyVol + sellWap * sellVol) / total;
      totalVolume = total;
    } else if (buyWap !== null) {
      wap = buyWap;
      totalVolume = buyVol;
    } else {
      wap = sellWap;
      totalVolume = sellVol;
    }

    snapshots.push({
      item_id: itemId,
      gender,
      markup_value: Math.round(wap * 10000) / 10000,
      volume: totalVolume,
      buy_count: filteredBuy.length,
      sell_count: filteredSell.length,
      recorded_at: now
    });
  }

  if (snapshots.length > 0) {
    await insertSnapshots(snapshots);
  }

  return snapshots.length;
}

async function insertSnapshots(snapshots) {
  const valueClauses = [];
  const values = [];
  let idx = 1;

  for (const s of snapshots) {
    valueClauses.push(`($${idx}, $${idx + 1}, $${idx + 2}, $${idx + 3}, $${idx + 4}, $${idx + 5}, $${idx + 6})`);
    values.push(s.item_id, s.gender, s.markup_value, s.volume, s.buy_count, s.sell_count, s.recorded_at);
    idx += 7;
  }

  await poolUsers.query(
    `INSERT INTO exchange_price_snapshots (item_id, gender, markup_value, volume, buy_count, sell_count, recorded_at)
     VALUES ${valueClauses.join(', ')}`,
    values
  );
}

// ---- Summary Computation ----

function periodTruncSql(periodType) {
  switch (periodType) {
    case 'hour': return `date_trunc('hour', recorded_at)`;
    case 'day': return `date_trunc('day', recorded_at)`;
    case 'week': return `date_trunc('week', recorded_at)`;
    default: throw new Error(`Unknown period type: ${periodType}`);
  }
}

function currentBoundarySql(periodType) {
  switch (periodType) {
    case 'hour': return `date_trunc('hour', now())`;
    case 'day': return `date_trunc('day', now())`;
    case 'week': return `date_trunc('week', now())`;
    default: throw new Error(`Unknown period type: ${periodType}`);
  }
}

/**
 * Compute exchange price summaries for a single period type.
 * Uses watermarks for incremental processing. Idempotent.
 */
export async function computeExchangeSummaries(periodType) {
  if (!VALID_PERIOD_TYPES.includes(periodType)) {
    throw new Error(`Invalid period type: ${periodType}`);
  }

  const wmResult = await poolUsers.query(
    'SELECT last_computed_until FROM exchange_price_summary_watermarks WHERE period_type = $1',
    [periodType]
  );
  const watermark = wmResult.rows[0]?.last_computed_until;

  const boundaryResult = await poolUsers.query(`SELECT ${currentBoundarySql(periodType)} AS boundary`);
  const boundary = boundaryResult.rows[0].boundary;

  if (!boundary) return { period_type: periodType, processed: 0 };

  if (watermark && new Date(watermark) >= new Date(boundary)) {
    return { period_type: periodType, processed: 0 };
  }

  const periodTrunc = periodTruncSql(periodType);
  const conditions = ['recorded_at < $1'];
  const values = [boundary];
  let idx = 2;

  if (watermark) {
    conditions.push(`recorded_at >= $${idx}`);
    values.push(watermark);
    idx++;
  }

  const query = `
    INSERT INTO exchange_price_summaries (
      item_id, gender, period_type, period_start,
      price_min, price_max, price_avg,
      price_p10, price_median, price_p90,
      price_wap, volume, sample_count, computed_at
    )
    SELECT
      item_id,
      gender,
      '${periodType}'::exchange_price_period,
      ${periodTrunc} AS period_start,
      MIN(markup_value),
      MAX(markup_value),
      AVG(markup_value),
      PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY markup_value),
      PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY markup_value),
      PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY markup_value),
      SUM(markup_value * volume) / NULLIF(SUM(volume), 0),
      SUM(volume),
      COUNT(*),
      now()
    FROM exchange_price_snapshots
    WHERE ${conditions.join(' AND ')}
    GROUP BY item_id, gender, ${periodTrunc}
    ON CONFLICT (item_id, gender, period_type, period_start)
    DO UPDATE SET
      price_min = EXCLUDED.price_min,
      price_max = EXCLUDED.price_max,
      price_avg = EXCLUDED.price_avg,
      price_p10 = EXCLUDED.price_p10,
      price_median = EXCLUDED.price_median,
      price_p90 = EXCLUDED.price_p90,
      price_wap = EXCLUDED.price_wap,
      volume = EXCLUDED.volume,
      sample_count = EXCLUDED.sample_count,
      computed_at = EXCLUDED.computed_at
  `;

  const result = await poolUsers.query(query, values);

  await poolUsers.query(
    `UPDATE exchange_price_summary_watermarks
     SET last_computed_until = $1, last_run_at = now()
     WHERE period_type = $2`,
    [boundary, periodType]
  );

  return { period_type: periodType, processed: result.rowCount };
}

/**
 * Compute exchange summaries for all period types.
 */
export async function computeAllExchangeSummaries() {
  const results = [];
  for (const pt of VALID_PERIOD_TYPES) {
    results.push(await computeExchangeSummaries(pt));
  }
  return results;
}
