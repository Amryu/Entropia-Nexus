//@ts-nocheck
import { getResponse } from '$lib/util.js';
import {
  createOrder, countUserOrdersBySide, countUserOrdersForItem,
  getItemType, isPercentMarkupServer, formatRetryTime,
  MAX_SELL_ORDERS, MAX_BUY_ORDERS, MAX_ORDERS_PER_ITEM, MAX_BATCH_SIZE, PLANETS,
  RATE_LIMIT_CREATE_PER_MIN, RATE_LIMIT_CREATE_PER_HOUR, RATE_LIMIT_CREATE_PER_DAY,
  RATE_LIMIT_ITEM_COOLDOWN_MS,
} from '$lib/server/exchange.js';
import { checkRateLimitPeek, incrementRateLimit } from '$lib/server/rateLimiter.js';
import { verifyTurnstile } from '$lib/server/turnstile.js';
import {
  validateOrderDetails, enforceSetConstraint, enforceGenderConstraint, getVerifiedUser
} from '$lib/server/exchange-order-validation.js';

const VALID_TYPES = ['BUY', 'SELL'];

/**
 * POST /api/market/exchange/orders/batch — Create multiple orders in a single request.
 * Requires a single Turnstile verification for the entire batch.
 * Returns per-order results (partial success is possible).
 */
export async function POST({ request, locals, fetch }) {
  const { user, error } = getVerifiedUser(locals);
  if (error) return error;

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON' }, 400);
  }

  const { orders, turnstile_token } = body;

  // Validate batch structure
  if (!Array.isArray(orders) || orders.length === 0) {
    return getResponse({ error: 'orders must be a non-empty array' }, 400);
  }
  if (orders.length > MAX_BATCH_SIZE) {
    return getResponse({ error: `Maximum ${MAX_BATCH_SIZE} orders per batch` }, 400);
  }

  // Verify Turnstile once for the whole batch
  if (!turnstile_token) return getResponse({ error: 'Captcha verification required' }, 400);
  const ip = locals.ip || request.headers.get('x-forwarded-for') || request.headers.get('cf-connecting-ip');
  if (!await verifyTurnstile(turnstile_token, ip)) {
    return getResponse({ error: 'Captcha verification failed. Please try again.' }, 400);
  }

  // Check global rate limits — ensure user has budget for the entire batch (peek without incrementing)
  const batchSize = orders.length;
  const globalChecks = [
    { ...checkRateLimitPeek(`order:min:${user.id}`, RATE_LIMIT_CREATE_PER_MIN, 60_000), label: 'per minute', limit: RATE_LIMIT_CREATE_PER_MIN },
    { ...checkRateLimitPeek(`order:hour:${user.id}`, RATE_LIMIT_CREATE_PER_HOUR, 3_600_000), label: 'per hour', limit: RATE_LIMIT_CREATE_PER_HOUR },
    { ...checkRateLimitPeek(`order:day:${user.id}`, RATE_LIMIT_CREATE_PER_DAY, 86_400_000), label: 'per day', limit: RATE_LIMIT_CREATE_PER_DAY },
  ];
  const denied = globalChecks.find(c => c.remaining < batchSize);
  if (denied) {
    const retryAfter = Math.ceil(denied.resetIn / 1000);
    return getResponse({
      error: `Rate limit exceeded (${denied.limit} orders ${denied.label}). Try again in ${formatRetryTime(retryAfter)}.`,
      retryAfter
    }, 429);
  }

  // Pre-check sell/buy order count to avoid partial batch failures
  const sellCount = orders.filter(o => (o.type || '').toUpperCase() === 'SELL').length;
  const buyCount = orders.filter(o => (o.type || '').toUpperCase() === 'BUY').length;

  try {
    if (sellCount > 0) {
      const currentSellCount = await countUserOrdersBySide(user.id, 'SELL');
      if (currentSellCount + sellCount > MAX_SELL_ORDERS) {
        return getResponse({
          error: `This batch would exceed the maximum ${MAX_SELL_ORDERS} sell orders. You currently have ${currentSellCount} sell orders.`
        }, 409);
      }
    }
    if (buyCount > 0) {
      const currentBuyCount = await countUserOrdersBySide(user.id, 'BUY');
      if (currentBuyCount + buyCount > MAX_BUY_ORDERS) {
        return getResponse({
          error: `This batch would exceed the maximum ${MAX_BUY_ORDERS} buy orders. You currently have ${currentBuyCount} buy orders.`
        }, 409);
      }
    }
  } catch (err) {
    console.error('Error checking order counts:', err);
    return getResponse({ error: 'Failed to check order limits' }, 500);
  }

  // Process each order
  const results = [];
  let created = 0;

  // Cache item info lookups to avoid redundant API calls for the same item
  const itemInfoCache = new Map();

  for (let i = 0; i < orders.length; i++) {
    const entry = orders[i];
    const result = await processOrderEntry(entry, user, fetch, itemInfoCache);
    results.push(result);
    if (result.success) created++;
  }

  return getResponse({ results, created, failed: orders.length - created }, created > 0 ? 201 : 400);
}

/**
 * Process a single order entry within a batch.
 * Returns { success: true, order } or { success: false, error, index }.
 */
async function processOrderEntry(entry, user, fetch, itemInfoCache) {
  // Validate type
  const type = (entry.type || '').toUpperCase();
  if (!VALID_TYPES.includes(type)) {
    return { success: false, error: 'type must be BUY or SELL' };
  }

  // Validate item_id
  const itemId = parseInt(entry.item_id, 10);
  if (!Number.isFinite(itemId) || itemId <= 0) {
    return { success: false, error: 'item_id must be a positive integer' };
  }

  // Validate quantity
  const quantity = parseInt(entry.quantity, 10);
  if (!Number.isFinite(quantity) || quantity < 1) {
    return { success: false, error: 'quantity must be at least 1' };
  }

  // Validate markup
  const markup = parseFloat(entry.markup);
  if (!Number.isFinite(markup) || markup < 0) {
    return { success: false, error: 'markup must be a non-negative number' };
  }

  // Look up item type (cached across batch)
  let itemInfo = itemInfoCache.get(itemId) ?? null;
  if (!itemInfoCache.has(itemId)) {
    try {
      itemInfo = await getItemType(itemId, fetch);
      itemInfoCache.set(itemId, itemInfo);
    } catch (err) {
      console.error('Error checking item type:', err);
      itemInfoCache.set(itemId, null);
    }
  }

  // Enforce minimum markup based on item type
  if (itemInfo && isPercentMarkupServer(itemInfo.type, itemInfo.name, itemInfo.subType) && markup < 100) {
    return { success: false, error: 'Markup must be at least 100% for this item type' };
  }

  // Validate planet
  const planet = entry.planet || null;
  if (planet && !PLANETS.includes(planet)) {
    return { success: false, error: `planet must be one of: ${PLANETS.join(', ')}` };
  }

  // Optional fields
  const minQuantity = entry.min_quantity != null ? parseInt(entry.min_quantity, 10) : null;
  if (minQuantity != null && (!Number.isFinite(minQuantity) || minQuantity < 1)) {
    return { success: false, error: 'min_quantity must be a positive integer' };
  }

  let details = enforceSetConstraint(validateOrderDetails(entry.details), itemInfo?.type);

  // Validate and enforce gender constraints
  const genderResult = enforceGenderConstraint(details, itemInfo);
  if (genderResult.error) {
    return { success: false, error: genderResult.error };
  }
  details = genderResult.details;

  // Check per-item order limit
  // Note: countUserOrdersForItem sees orders created earlier in this batch
  // because each createOrder commits immediately (auto-commit).
  try {
    const itemCount = await countUserOrdersForItem(user.id, itemId, type);
    if (itemCount >= MAX_ORDERS_PER_ITEM) {
      return { success: false, error: `Maximum ${MAX_ORDERS_PER_ITEM} ${type.toLowerCase()} orders per item reached.` };
    }
  } catch (err) {
    console.error('Error checking item order count:', err);
    return { success: false, error: 'Failed to check item order limits' };
  }

  // Create the order
  try {
    const order = await createOrder({
      userId: user.id, type, itemId, quantity, minQuantity, markup, planet, details
    });

    // Increment rate limits on success (global + per-item)
    incrementRateLimit(`order:min:${user.id}`, 60_000);
    incrementRateLimit(`order:hour:${user.id}`, 3_600_000);
    incrementRateLimit(`order:day:${user.id}`, 86_400_000);
    incrementRateLimit(`order:item:${user.id}:${itemId}`, RATE_LIMIT_ITEM_COOLDOWN_MS);
    incrementRateLimit(`order:item-day:${user.id}:${itemId}`, 86_400_000);

    return { success: true, order };
  } catch (err) {
    console.error('Error creating order:', err);
    return { success: false, error: 'Failed to create order' };
  }
}
