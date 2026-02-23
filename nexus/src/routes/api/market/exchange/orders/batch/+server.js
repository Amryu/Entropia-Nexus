//@ts-nocheck
import { getResponse } from '$lib/util.js';
import {
  createOrder, getOrderById, updateOrder,
  countUserOrdersBySide, countUserOrdersForItem,
  getItemType, isPercentMarkupServer, formatRetryTime,
  MAX_SELL_ORDERS, MAX_BUY_ORDERS, MAX_ORDERS_PER_ITEM, MAX_BATCH_SIZE, PLANETS,
  RATE_LIMIT_CREATE_PER_MIN, RATE_LIMIT_CREATE_PER_HOUR, RATE_LIMIT_CREATE_PER_DAY,
  RATE_LIMIT_ITEM_COOLDOWN_MS, RATE_LIMIT_EDIT_PER_MIN,
} from '$lib/server/exchange.js';
import { checkRateLimitPeek, incrementRateLimit } from '$lib/server/rateLimiter.js';
import { verifyTurnstile } from '$lib/server/turnstile.js';
import { isOAuthRequest } from '$lib/server/auth.js';
import {
  validateOrderDetails, enforceSetConstraint, enforceGenderConstraint, getVerifiedUser
} from '$lib/server/exchange-order-validation.js';
import { invalidateOfferCounts } from '$lib/market/cache';

const VALID_TYPES = ['BUY', 'SELL'];
const isTestEnv = process.env.NODE_ENV === 'test';

/**
 * POST /api/market/exchange/orders/batch — Create or update multiple orders in a single request.
 * Supports `order_id` per entry for editing existing orders instead of creating new ones.
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

  // Verify Turnstile once for the whole batch (skipped for OAuth-authenticated requests)
  if (!isOAuthRequest(locals)) {
    if (!turnstile_token) return getResponse({ error: 'Captcha verification required' }, 400);
    const ip = locals.ip || request.headers.get('x-forwarded-for') || request.headers.get('cf-connecting-ip');
    if (!await verifyTurnstile(turnstile_token, ip)) {
      return getResponse({ error: 'Captcha verification failed. Please try again.' }, 400);
    }
  }

  // Separate new creates from edits
  const newOrders = orders.filter(o => !o.order_id);
  const editOrders = orders.filter(o => o.order_id);

  // Check global rate limits for new creates only
  if (newOrders.length > 0) {
    const globalChecks = [
      { ...checkRateLimitPeek(`order:min:${user.id}`, RATE_LIMIT_CREATE_PER_MIN, 60_000), label: 'per minute', limit: RATE_LIMIT_CREATE_PER_MIN },
      { ...checkRateLimitPeek(`order:hour:${user.id}`, RATE_LIMIT_CREATE_PER_HOUR, 3_600_000), label: 'per hour', limit: RATE_LIMIT_CREATE_PER_HOUR },
      { ...checkRateLimitPeek(`order:day:${user.id}`, RATE_LIMIT_CREATE_PER_DAY, 86_400_000), label: 'per day', limit: RATE_LIMIT_CREATE_PER_DAY },
    ];
    const denied = globalChecks.find(c => c.remaining < newOrders.length);
    if (denied) {
      const retryAfter = Math.ceil(denied.resetIn / 1000);
      return getResponse({
        error: `Rate limit exceeded (${denied.limit} orders ${denied.label}). Try again in ${formatRetryTime(retryAfter)}.`,
        retryAfter
      }, 429);
    }
  }

  // Check edit rate limit for edits
  if (editOrders.length > 0) {
    const editCheck = checkRateLimitPeek(`order:edit:${user.id}`, RATE_LIMIT_EDIT_PER_MIN, 60_000);
    if (editCheck.remaining < editOrders.length) {
      const retryAfter = Math.ceil(editCheck.resetIn / 1000);
      return getResponse({
        error: `Edit rate limit exceeded. Try again in ${formatRetryTime(retryAfter)}.`,
        retryAfter
      }, 429);
    }
  }

  // Pre-check sell/buy order count for new creates only
  // Bypassed in test environment to prevent cross-run interference
  if (!isTestEnv) {
    const newSellCount = newOrders.filter(o => (o.type || '').toUpperCase() === 'SELL').length;
    const newBuyCount = newOrders.filter(o => (o.type || '').toUpperCase() === 'BUY').length;

    try {
      if (newSellCount > 0) {
        const currentSellCount = await countUserOrdersBySide(user.id, 'SELL');
        if (currentSellCount + newSellCount > MAX_SELL_ORDERS) {
          return getResponse({
            error: `This batch would exceed the maximum ${MAX_SELL_ORDERS} sell orders. You currently have ${currentSellCount} sell orders.`
          }, 409);
        }
      }
      if (newBuyCount > 0) {
        const currentBuyCount = await countUserOrdersBySide(user.id, 'BUY');
        if (currentBuyCount + newBuyCount > MAX_BUY_ORDERS) {
          return getResponse({
            error: `This batch would exceed the maximum ${MAX_BUY_ORDERS} buy orders. You currently have ${currentBuyCount} buy orders.`
          }, 409);
        }
      }
    } catch (err) {
      console.error('Error checking order counts:', err);
      return getResponse({ error: 'Failed to check order limits' }, 500);
    }
  }

  // Process each order
  const results = [];
  let created = 0;
  let updated = 0;

  // Cache item info lookups to avoid redundant API calls for the same item
  const itemInfoCache = new Map();

  for (let i = 0; i < orders.length; i++) {
    const entry = orders[i];
    const result = await processOrderEntry(entry, user, fetch, itemInfoCache);
    results.push(result);
    if (result.success) {
      if (result.action === 'updated') updated++;
      else created++;
    }
  }

  const succeeded = created + updated;
  if (succeeded > 0) invalidateOfferCounts();
  return getResponse(
    { results, created, updated, failed: orders.length - succeeded },
    succeeded > 0 ? 200 : 400
  );
}

/**
 * Process a single order entry within a batch.
 * If entry.order_id is set, updates the existing order instead of creating a new one.
 * Returns { success: true, order, action } or { success: false, error }.
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

  // --- Update existing order ---
  const orderId = entry.order_id ? parseInt(entry.order_id, 10) : null;
  if (orderId != null) {
    if (!Number.isFinite(orderId) || orderId <= 0) {
      return { success: false, error: 'order_id must be a positive integer' };
    }

    const existing = await getOrderById(orderId);
    if (!existing) {
      return { success: false, error: 'Order not found' };
    }
    if (String(existing.user_id) !== String(user.id)) {
      return { success: false, error: 'Not authorized to edit this order' };
    }
    if (existing.state === 'closed') {
      return { success: false, error: 'Cannot edit a closed order' };
    }
    if (Number(existing.item_id) !== itemId || existing.type !== type) {
      return { success: false, error: 'Order item/type mismatch' };
    }

    try {
      const order = await updateOrder(orderId, { quantity, minQuantity: minQuantity ?? null, markup, planet, details });
      incrementRateLimit(`order:edit:${user.id}`, 60_000);
      incrementRateLimit(`order:item:${user.id}:${itemId}`, RATE_LIMIT_ITEM_COOLDOWN_MS);
      return { success: true, order, action: 'updated' };
    } catch (err) {
      console.error('Error updating order in batch:', err);
      return { success: false, error: 'Failed to update order' };
    }
  }

  // --- Create new order ---

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

    return { success: true, order, action: 'created' };
  } catch (err) {
    console.error('Error creating order:', err);
    return { success: false, error: 'Failed to create order' };
  }
}
