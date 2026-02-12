//@ts-nocheck
import { getResponse } from '$lib/util.js';
import {
  getUserOrders, createOrder, countUserOrdersBySide, countUserOrdersForItem,
  getItemType, isPercentMarkupServer, isItemFungible, formatRetryTime,
  MAX_SELL_ORDERS, MAX_BUY_ORDERS, MAX_ORDERS_PER_ITEM, PLANETS,
  RATE_LIMIT_CREATE_PER_MIN, RATE_LIMIT_CREATE_PER_HOUR, RATE_LIMIT_CREATE_PER_DAY,
  RATE_LIMIT_ITEM_COOLDOWN_MS, RATE_LIMIT_ITEM_FUNGIBLE_COOLDOWN, RATE_LIMIT_ITEM_NONFUNGIBLE_COOLDOWN,
  RATE_LIMIT_ITEM_DAILY_FUNGIBLE,
} from '$lib/server/exchange.js';
import { GENDERED_TYPES } from '$lib/common/itemTypes.js';
import { checkRateLimit, checkRateLimitPeek, incrementRateLimit } from '$lib/server/rateLimiter.js';
import { verifyTurnstile } from '$lib/server/turnstile.js';

const VALID_TYPES = ['BUY', 'SELL'];

/**
 * Validate and sanitize order details JSONB.
 * Only allows known metadata keys with correct types.
 */
function validateOrderDetails(details) {
  if (details === null || details === undefined) return null;
  if (typeof details !== 'object' || Array.isArray(details)) return null;

  const clean = {};

  if (typeof details.item_name === 'string') {
    clean.item_name = details.item_name.slice(0, 200);
  }
  if (details.Tier != null) {
    const tier = Math.round(Number(details.Tier));
    if (Number.isFinite(tier) && tier >= 0 && tier <= 10) clean.Tier = tier;
  }
  if (details.TierIncreaseRate != null) {
    const tir = Math.round(Number(details.TierIncreaseRate));
    // (L) items allow TiR up to 4000, non-(L) up to 200
    const itemName = details.item_name || '';
    const isL = /\(.*L.*\)/.test(itemName);
    const maxTir = isL ? 4000 : 200;
    if (Number.isFinite(tir) && tir >= 0 && tir <= maxTir) clean.TierIncreaseRate = tir;
  }
  if (details.QualityRating != null) {
    const qr = Math.round(Number(details.QualityRating));
    if (Number.isFinite(qr) && qr >= 1 && qr <= 100) clean.QualityRating = qr;
  }
  if (details.CurrentTT != null) {
    const ct = parseFloat(details.CurrentTT);
    if (Number.isFinite(ct) && ct >= 0) clean.CurrentTT = ct;
  }
  if (details.Pet != null && typeof details.Pet === 'object' && !Array.isArray(details.Pet)) {
    const pet = {};
    if (details.Pet.Level != null) {
      const lvl = parseInt(details.Pet.Level, 10);
      if (Number.isFinite(lvl) && lvl >= 0) pet.Level = lvl;
    }
    if (Object.keys(pet).length > 0) clean.Pet = pet;
  }
  if (details.is_set === true) {
    clean.is_set = true;
  }
  if (details.Gender != null && typeof details.Gender === 'string') {
    if (details.Gender === 'Male' || details.Gender === 'Female') {
      clean.Gender = details.Gender;
    }
  }

  return Object.keys(clean).length > 0 ? clean : null;
}

/**
 * Strip is_set from details if the item type doesn't support it.
 */
function enforceSetConstraint(details, itemType) {
  if (!details?.is_set) return details;
  if (itemType !== 'ArmorPlating') {
    const { is_set, ...rest } = details;
    return Object.keys(rest).length > 0 ? rest : null;
  }
  return details;
}

/**
 * Validate and enforce gender constraints based on item type.
 * Gender is available on itemInfo.gender (fetched from API).
 * Returns { details } on success, { error } on failure.
 */
function enforceGenderConstraint(details, itemInfo) {
  if (!GENDERED_TYPES.has(itemInfo?.type)) {
    // Strip Gender from non-gendered types
    if (details?.Gender) {
      const { Gender, ...rest } = details;
      return { details: Object.keys(rest).length > 0 ? rest : null };
    }
    return { details };
  }

  const itemGender = itemInfo.gender;

  // Clothing with null gender → not tradeable
  if (itemInfo.type === 'Clothing' && itemGender === null) {
    return { error: 'This clothing item cannot be traded (no gender classification).' };
  }

  // Neutral clothing → no gender required, strip if provided
  if (itemGender === 'Neutral') {
    if (details?.Gender) {
      const { Gender, ...rest } = details;
      return { details: Object.keys(rest).length > 0 ? rest : null };
    }
    return { details };
  }

  // Gender required (Both, Male, or Female)
  if (!details?.Gender || !['Male', 'Female'].includes(details.Gender)) {
    return { error: 'Gender (Male or Female) is required for this item type.' };
  }

  // Set-gender items: must match
  if (itemGender !== 'Both' && details.Gender !== itemGender) {
    return { error: `This item is ${itemGender}-only. Gender must be "${itemGender}".` };
  }

  return { details };
}

function getVerifiedUser(locals) {
  const user = locals.session?.user;
  if (!user) return { error: getResponse({ error: 'Authentication required' }, 401) };
  if (!user.verified) return { error: getResponse({ error: 'Verified account required' }, 403) };
  return { user };
}

/**
 * GET /api/market/exchange/orders — Get current user's orders (My Orders)
 */
export async function GET({ locals }) {
  const { user, error } = getVerifiedUser(locals);
  if (error) return error;

  try {
    const orders = await getUserOrders(user.id);
    return getResponse(orders, 200);
  } catch (err) {
    console.error('Error fetching user orders:', err);
    return getResponse({ error: 'Failed to fetch orders' }, 500);
  }
}

/**
 * POST /api/market/exchange/orders — Create a new order
 */
export async function POST({ request, locals, fetch }) {
  const { user, error } = getVerifiedUser(locals);
  if (error) return error;

  // --- Global rate limits (increment on every attempt to prevent abuse via validation errors) ---
  const globalChecks = [
    { ...checkRateLimit(`order:min:${user.id}`, RATE_LIMIT_CREATE_PER_MIN, 60_000), label: 'per minute', limit: RATE_LIMIT_CREATE_PER_MIN },
    { ...checkRateLimit(`order:hour:${user.id}`, RATE_LIMIT_CREATE_PER_HOUR, 3_600_000), label: 'per hour', limit: RATE_LIMIT_CREATE_PER_HOUR },
    { ...checkRateLimit(`order:day:${user.id}`, RATE_LIMIT_CREATE_PER_DAY, 86_400_000), label: 'per day', limit: RATE_LIMIT_CREATE_PER_DAY },
  ];
  const denied = globalChecks.find(c => !c.allowed);
  if (denied) {
    const retryAfter = Math.ceil(denied.resetIn / 1000);
    return getResponse({
      error: `Rate limit exceeded (${denied.limit} orders ${denied.label}). Try again in ${formatRetryTime(retryAfter)}.`,
      retryAfter
    }, 429);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON' }, 400);
  }

  // Verify Turnstile
  const turnstileToken = body.turnstile_token;
  if (!turnstileToken) return getResponse({ error: 'Captcha verification required' }, 400);
  const ip = locals.ip || request.headers.get('x-forwarded-for') || request.headers.get('cf-connecting-ip');
  if (!await verifyTurnstile(turnstileToken, ip)) return getResponse({ error: 'Captcha verification failed. Please try again.' }, 400);

  // Validate type
  const type = (body.type || '').toUpperCase();
  if (!VALID_TYPES.includes(type)) {
    return getResponse({ error: 'type must be BUY or SELL' }, 400);
  }

  // Validate item_id
  const itemId = parseInt(body.item_id, 10);
  if (!Number.isFinite(itemId) || itemId <= 0) {
    return getResponse({ error: 'item_id must be a positive integer' }, 400);
  }

  // Validate quantity
  const quantity = parseInt(body.quantity, 10);
  if (!Number.isFinite(quantity) || quantity < 1) {
    return getResponse({ error: 'quantity must be at least 1' }, 400);
  }

  // Validate markup (basic check first, type-aware check after item lookup)
  const markup = parseFloat(body.markup);
  if (!Number.isFinite(markup) || markup < 0) {
    return getResponse({ error: 'markup must be a non-negative number' }, 400);
  }

  // Look up item type (used for markup validation and per-item rate limits)
  let itemInfo = null;
  try {
    itemInfo = await getItemType(itemId, fetch);
  } catch (err) {
    console.error('Error checking item type:', err);
  }

  // Enforce minimum markup based on item type
  if (itemInfo && isPercentMarkupServer(itemInfo.type, itemInfo.name, itemInfo.subType) && markup < 100) {
    return getResponse({ error: 'Markup must be at least 100% for this item type' }, 400);
  }

  // --- Per-item rate limits (peek first, increment only on success) ---
  const isFungible = itemInfo ? isItemFungible(itemInfo.type, itemInfo.name) : false;

  // Per-item cooldown (3-minute window, shared with edits)
  const itemCooldownMax = isFungible ? RATE_LIMIT_ITEM_FUNGIBLE_COOLDOWN : RATE_LIMIT_ITEM_NONFUNGIBLE_COOLDOWN;
  const itemCooldownKey = `order:item:${user.id}:${itemId}`;
  const itemCooldown = checkRateLimitPeek(itemCooldownKey, itemCooldownMax, RATE_LIMIT_ITEM_COOLDOWN_MS);
  if (!itemCooldown.allowed) {
    const retryAfter = Math.ceil(itemCooldown.resetIn / 1000);
    return getResponse({
      error: `Please wait before creating another order for this item. Try again in ${formatRetryTime(retryAfter)}.`,
      retryAfter
    }, 429);
  }

  // Per-item daily limit
  const itemDailyMax = isFungible ? RATE_LIMIT_ITEM_DAILY_FUNGIBLE : RATE_LIMIT_ITEM_DAILY_FUNGIBLE * MAX_ORDERS_PER_ITEM;
  const itemDailyKey = `order:item-day:${user.id}:${itemId}`;
  const itemDaily = checkRateLimitPeek(itemDailyKey, itemDailyMax, 86_400_000);
  if (!itemDaily.allowed) {
    const retryAfter = Math.ceil(itemDaily.resetIn / 1000);
    return getResponse({
      error: `Daily order limit for this item reached (${itemDailyMax}/day). Try again in ${formatRetryTime(retryAfter)}.`,
      retryAfter
    }, 429);
  }

  // Validate planet
  const planet = body.planet || null;
  if (planet && !PLANETS.includes(planet)) {
    return getResponse({ error: `planet must be one of: ${PLANETS.join(', ')}` }, 400);
  }

  // Optional fields
  const minQuantity = body.min_quantity != null ? parseInt(body.min_quantity, 10) : null;
  if (minQuantity != null && (!Number.isFinite(minQuantity) || minQuantity < 1)) {
    return getResponse({ error: 'min_quantity must be a positive integer' }, 400);
  }

  let details = enforceSetConstraint(validateOrderDetails(body.details), itemInfo?.type);

  // Validate and enforce gender constraints
  const genderResult = enforceGenderConstraint(details, itemInfo);
  if (genderResult.error) {
    return getResponse({ error: genderResult.error }, 400);
  }
  details = genderResult.details;

  // Check order limit per side (separate caps for buy/sell)
  try {
    const sideCount = await countUserOrdersBySide(user.id, type);
    const maxForSide = type === 'SELL' ? MAX_SELL_ORDERS : MAX_BUY_ORDERS;
    if (sideCount >= maxForSide) {
      return getResponse({
        error: `Maximum ${maxForSide} ${type.toLowerCase()} orders reached. Close some orders first.`
      }, 409);
    }
  } catch (err) {
    console.error('Error checking order count:', err);
    return getResponse({ error: 'Failed to check order limits' }, 500);
  }

  // Check per-item order limit (up to MAX_ORDERS_PER_ITEM per item per side)
  try {
    const itemCount = await countUserOrdersForItem(user.id, itemId, type);
    if (itemCount >= MAX_ORDERS_PER_ITEM) {
      return getResponse({
        error: `Maximum ${MAX_ORDERS_PER_ITEM} ${type.toLowerCase()} orders per item reached.`,
        itemOrderCount: itemCount
      }, 409);
    }
  } catch (err) {
    console.error('Error checking item order count:', err);
    return getResponse({ error: 'Failed to check item order limits' }, 500);
  }

  // Create the order
  try {
    const order = await createOrder({
      userId: user.id, type, itemId, quantity, minQuantity, markup, planet, details
    });

    // Increment per-item rate limits on successful creation
    incrementRateLimit(itemCooldownKey, RATE_LIMIT_ITEM_COOLDOWN_MS);
    incrementRateLimit(itemDailyKey, 86_400_000);

    return getResponse(order, 201);
  } catch (err) {
    console.error('Error creating order:', err);
    return getResponse({ error: 'Failed to create order' }, 500);
  }
}
