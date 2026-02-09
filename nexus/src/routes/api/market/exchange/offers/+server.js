//@ts-nocheck
import { getResponse } from '$lib/util.js';
import { getUserOffers, createOffer, countUserOffersBySide, MAX_OFFERS_PER_SIDE, PLANETS } from '$lib/server/exchange.js';

const VALID_TYPES = ['BUY', 'SELL'];

/**
 * Validate and sanitize offer details JSONB.
 * Only allows known metadata keys with correct types.
 */
function validateOfferDetails(details) {
  if (details === null || details === undefined) return null;
  if (typeof details !== 'object' || Array.isArray(details)) return null;

  const clean = {};

  if (typeof details.item_name === 'string') {
    clean.item_name = details.item_name.slice(0, 200);
  }
  if (details.Tier != null) {
    const tier = parseFloat(details.Tier);
    if (Number.isFinite(tier) && tier >= 0 && tier <= 10) clean.Tier = tier;
  }
  if (details.TierIncreaseRate != null) {
    const tir = parseInt(details.TierIncreaseRate, 10);
    if (Number.isFinite(tir) && tir >= 1 && tir <= 4000) clean.TierIncreaseRate = tir;
  }
  if (details.QualityRating != null) {
    const qr = parseFloat(details.QualityRating);
    if (Number.isFinite(qr) && qr >= 0 && qr <= 100) clean.QualityRating = qr;
  }
  if (details.CurrentTT != null) {
    const ct = parseFloat(details.CurrentTT);
    if (Number.isFinite(ct) && ct >= 0) clean.CurrentTT = ct;
  }
  if (details.Pet != null && typeof details.Pet === 'object' && !Array.isArray(details.Pet)) {
    const pet = {};
    if (details.Pet.Level != null) {
      const lvl = parseInt(details.Pet.Level, 10);
      if (Number.isFinite(lvl) && lvl >= 1) pet.Level = lvl;
    }
    if (details.Pet.Experience != null) {
      const exp = parseFloat(details.Pet.Experience);
      if (Number.isFinite(exp) && exp >= 0) pet.Experience = exp;
    }
    if (details.Pet.Food != null) {
      const food = parseFloat(details.Pet.Food);
      if (Number.isFinite(food) && food >= 0) pet.Food = food;
    }
    if (Array.isArray(details.Pet.Skills)) {
      pet.Skills = details.Pet.Skills
        .filter(s => s && typeof s === 'object' && typeof s.Name === 'string')
        .slice(0, 20)
        .map(s => ({ Name: s.Name.slice(0, 100), Level: parseInt(s.Level, 10) || 0 }));
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
 * GET /api/market/exchange/offers — Get current user's offers (My Offers)
 */
export async function GET({ locals }) {
  const { user, error } = getVerifiedUser(locals);
  if (error) return error;

  try {
    const offers = await getUserOffers(user.id);
    return getResponse(offers, 200);
  } catch (err) {
    console.error('Error fetching user offers:', err);
    return getResponse({ error: 'Failed to fetch offers' }, 500);
  }
}

/**
 * POST /api/market/exchange/offers — Create a new offer
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

  // Validate markup
  const markup = parseFloat(body.markup);
  if (!Number.isFinite(markup) || markup < 0) {
    return getResponse({ error: 'markup must be a non-negative number' }, 400);
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

  const details = validateOfferDetails(body.details);

  // Check offer limit per side
  try {
    const count = await countUserOffersBySide(user.id, type);
    if (count >= MAX_OFFERS_PER_SIDE) {
      return getResponse({
        error: `Maximum ${MAX_OFFERS_PER_SIDE} ${type.toLowerCase()} offers reached. Close some offers first.`
      }, 409);
    }
  } catch (err) {
    console.error('Error checking offer count:', err);
    return getResponse({ error: 'Failed to check offer limits' }, 500);
  }

  // Create the offer (unique constraint enforces 1 per item/side)
  try {
    const offer = await createOffer({
      userId: user.id, type, itemId, quantity, minQuantity, markup, planet, details
    });
    return getResponse(offer, 201);
  } catch (err) {
    // Check for unique constraint violation (1 offer per item per side)
    if (err.code === '23505') {
      return getResponse({
        error: `You already have an active ${type.toLowerCase()} offer for this item`
      }, 409);
    }
    console.error('Error creating offer:', err);
    return getResponse({ error: 'Failed to create offer' }, 500);
  }
}
