//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getUserOrders, createOrder, countUserOrdersBySide, countUserOrdersForItem, getItemType, isPercentMarkupServer, MAX_ORDERS_PER_SIDE, MAX_ORDERS_PER_ITEM, PLANETS } from '$lib/server/exchange.js';

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

  return Object.keys(clean).length > 0 ? clean : null;
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
export async function POST({ request, locals }) {
  const { user, error } = getVerifiedUser(locals);
  if (error) return error;

  let body;
  try {
    body = await request.json();
  } catch {
    return getResponse({ error: 'Invalid JSON' }, 400);
  }

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

  // Enforce minimum markup based on item type
  try {
    const itemInfo = await getItemType(itemId);
    if (itemInfo && isPercentMarkupServer(itemInfo.type, itemInfo.name) && markup < 100) {
      return getResponse({ error: 'Markup must be at least 100% for this item type' }, 400);
    }
  } catch (err) {
    console.error('Error checking item type for markup validation:', err);
    // Non-fatal: proceed with basic validation only
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

  const details = validateOrderDetails(body.details);

  // Check order limit per side (global cap)
  try {
    const sideCount = await countUserOrdersBySide(user.id, type);
    if (sideCount >= MAX_ORDERS_PER_SIDE) {
      return getResponse({
        error: `Maximum ${MAX_ORDERS_PER_SIDE} ${type.toLowerCase()} orders reached. Close some orders first.`
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
    return getResponse(order, 201);
  } catch (err) {
    console.error('Error creating order:', err);
    return getResponse({ error: 'Failed to create order' }, 500);
  }
}
