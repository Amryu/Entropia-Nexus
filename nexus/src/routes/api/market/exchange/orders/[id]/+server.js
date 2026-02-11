//@ts-nocheck
import { getResponse } from '$lib/util.js';
import {
  getOrderById, updateOrder, closeOrder, getItemType, isPercentMarkupServer,
  isItemFungible, formatRetryTime, PLANETS,
  RATE_LIMIT_EDIT_PER_MIN, RATE_LIMIT_CLOSE_PER_MIN,
  RATE_LIMIT_ITEM_COOLDOWN_MS, RATE_LIMIT_ITEM_FUNGIBLE_COOLDOWN, RATE_LIMIT_ITEM_NONFUNGIBLE_COOLDOWN,
} from '$lib/server/exchange.js';
import { checkRateLimit } from '$lib/server/rateLimiter.js';

/**
 * Validate and sanitize order details JSONB.
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

function getVerifiedUser(locals) {
  const user = locals.session?.user;
  if (!user) return { error: getResponse({ error: 'Authentication required' }, 401) };
  if (!user.verified) return { error: getResponse({ error: 'Verified account required' }, 403) };
  return { user };
}

/**
 * PUT /api/market/exchange/orders/[id] — Edit an order
 */
export async function PUT({ params, request, locals }) {
  const { user, error } = getVerifiedUser(locals);
  if (error) return error;

  // Global edit rate limit
  const editCheck = checkRateLimit(`order:edit:${user.id}`, RATE_LIMIT_EDIT_PER_MIN, 60_000);
  if (!editCheck.allowed) {
    const retryAfter = Math.ceil(editCheck.resetIn / 1000);
    return getResponse({
      error: `Edit rate limit exceeded. Try again in ${formatRetryTime(retryAfter)}.`,
      retryAfter
    }, 429);
  }

  const orderId = parseInt(params.id, 10);
  if (!Number.isFinite(orderId)) {
    return getResponse({ error: 'Invalid order ID' }, 400);
  }

  // Verify ownership
  const existing = await getOrderById(orderId);
  if (!existing) {
    return getResponse({ error: 'Order not found' }, 404);
  }
  if (String(existing.user_id) !== String(user.id)) {
    return getResponse({ error: 'Not authorized' }, 403);
  }
  if (existing.state === 'closed') {
    return getResponse({ error: 'Cannot edit a closed order' }, 400);
  }

  // Per-item 3-minute cooldown (shared with create)
  let itemInfo = null;
  try {
    itemInfo = await getItemType(existing.item_id);
  } catch (err) {
    console.error('Error checking item type for edit cooldown:', err);
  }
  const isFungible = itemInfo ? isItemFungible(itemInfo.type, itemInfo.name) : false;
  const itemCooldownMax = isFungible ? RATE_LIMIT_ITEM_FUNGIBLE_COOLDOWN : RATE_LIMIT_ITEM_NONFUNGIBLE_COOLDOWN;
  const itemCooldown = checkRateLimit(`order:item:${user.id}:${existing.item_id}`, itemCooldownMax, RATE_LIMIT_ITEM_COOLDOWN_MS);
  if (!itemCooldown.allowed) {
    const retryAfter = Math.ceil(itemCooldown.resetIn / 1000);
    return getResponse({
      error: `Please wait before modifying another order for this item. Try again in ${formatRetryTime(retryAfter)}.`,
      retryAfter
    }, 429);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON' }, 400);
  }

  // Validate fields
  const quantity = parseInt(body.quantity, 10);
  if (!Number.isFinite(quantity) || quantity < 1) {
    return getResponse({ error: 'quantity must be at least 1' }, 400);
  }

  const markup = parseFloat(body.markup);
  if (!Number.isFinite(markup) || markup < 0) {
    return getResponse({ error: 'markup must be a non-negative number' }, 400);
  }

  // Enforce minimum markup based on item type (reuse itemInfo from cooldown check)
  if (itemInfo && isPercentMarkupServer(itemInfo.type, itemInfo.name) && markup < 100) {
    return getResponse({ error: 'Markup must be at least 100% for this item type' }, 400);
  }

  const planet = body.planet || null;
  if (planet && !PLANETS.includes(planet)) {
    return getResponse({ error: `planet must be one of: ${PLANETS.join(', ')}` }, 400);
  }

  const minQuantity = body.min_quantity != null ? parseInt(body.min_quantity, 10) : null;
  const details = enforceSetConstraint(validateOrderDetails(body.details), itemInfo?.type);

  try {
    const updated = await updateOrder(orderId, { quantity, minQuantity, markup, planet, details });
    return getResponse(updated, 200);
  } catch (err) {
    console.error('Error updating order:', err);
    return getResponse({ error: 'Failed to update order' }, 500);
  }
}

/**
 * DELETE /api/market/exchange/orders/[id] — Close an order
 */
export async function DELETE({ params, locals }) {
  const { user, error: authErr } = getVerifiedUser(locals);
  if (authErr) return authErr;

  // Global close rate limit
  const closeCheck = checkRateLimit(`order:close:${user.id}`, RATE_LIMIT_CLOSE_PER_MIN, 60_000);
  if (!closeCheck.allowed) {
    const retryAfter = Math.ceil(closeCheck.resetIn / 1000);
    return getResponse({
      error: `Close rate limit exceeded. Try again in ${formatRetryTime(retryAfter)}.`,
      retryAfter
    }, 429);
  }

  const orderId = parseInt(params.id, 10);
  if (!Number.isFinite(orderId)) {
    return getResponse({ error: 'Invalid order ID' }, 400);
  }

  const existing = await getOrderById(orderId);
  if (!existing) {
    return getResponse({ error: 'Order not found' }, 404);
  }
  if (String(existing.user_id) !== String(user.id)) {
    return getResponse({ error: 'Not authorized' }, 403);
  }
  if (existing.state === 'closed') {
    return getResponse({ error: 'Order is already closed' }, 400);
  }

  try {
    const closed = await closeOrder(orderId);
    return getResponse(closed, 200);
  } catch (err) {
    console.error('Error closing order:', err);
    return getResponse({ error: 'Failed to close order' }, 500);
  }
}
