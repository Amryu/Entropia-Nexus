// @ts-nocheck
/**
 * Server-side sanitization and validation for rental offers and requests.
 */

import { RENTAL_ALLOWED_ITEM_TYPES, isLimitedByName } from '$lib/common/itemTypes.js';
import { sanitizeMarketDescription } from '$lib/server/sanitizeRichText.js';

export const MAX_RENTAL_OFFERS_PER_USER = 20;
export const MAX_DISCOUNTS = 5;
export const MAX_BLOCKED_RANGES = 50;
export const MAX_DESCRIPTION_LENGTH = 5000;
export const MAX_TITLE_LENGTH = 120;
export const MAX_LOCATION_LENGTH = 200;
export const MAX_NOTE_LENGTH = 1000;
export const MAX_PRICE_PER_DAY = 100000;   // 100k PED
export const MAX_DEPOSIT = 1000000;         // 1M PED
export const MAX_RENTAL_DAYS = 365;
export const MIN_PRICE_PER_DAY = 0.01;

/**
 * Round to 2 decimal places.
 * @param {number} value
 * @returns {number}
 */
function round2(value) {
  return Math.round(value * 100) / 100;
}

/**
 * Sanitize a rental offer title.
 * @param {any} value
 * @param {string} fallback
 * @returns {string}
 */
export function sanitizeTitle(value, fallback = 'New Rental Offer') {
  if (typeof value !== 'string') return fallback;
  const trimmed = value.trim();
  return trimmed ? trimmed.slice(0, MAX_TITLE_LENGTH) : fallback;
}

/**
 * Sanitize a description string (supports rich text HTML).
 * Strips disallowed tags via sanitizeMarketDescription, then truncates.
 * @param {any} value
 * @returns {string|null}
 */
export function sanitizeDescription(value) {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  const sanitized = sanitizeMarketDescription(trimmed);
  return sanitized ? sanitized.slice(0, MAX_DESCRIPTION_LENGTH) : null;
}

/**
 * Sanitize a location string.
 * @param {any} value
 * @returns {string|null}
 */
export function sanitizeLocation(value) {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed ? trimmed.slice(0, MAX_LOCATION_LENGTH) : null;
}

/**
 * Sanitize a note string.
 * @param {any} value
 * @returns {string|null}
 */
export function sanitizeNote(value) {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed ? trimmed.slice(0, MAX_NOTE_LENGTH) : null;
}

/**
 * Sanitize a price value (PED with 2 decimal places).
 * @param {any} value
 * @param {number} min
 * @param {number} max
 * @param {number} fallback
 * @returns {number}
 */
export function sanitizePrice(value, min = 0, max = MAX_PRICE_PER_DAY, fallback = 0) {
  const num = typeof value === 'number' ? value : parseFloat(value);
  if (!Number.isFinite(num)) return fallback;
  return round2(Math.min(max, Math.max(min, num)));
}

/**
 * Sanitize discount thresholds.
 * @param {any} discounts
 * @returns {Array<{minDays: number, percent: number}>}
 */
export function sanitizeDiscounts(discounts) {
  if (!Array.isArray(discounts)) return [];

  const result = [];
  const seenDays = new Set();

  for (const d of discounts.slice(0, MAX_DISCOUNTS)) {
    if (!d || typeof d !== 'object') continue;

    const minDays = Math.floor(Number(d.minDays));
    const percent = round2(Number(d.percent));

    if (!Number.isFinite(minDays) || minDays < 2 || minDays > MAX_RENTAL_DAYS) continue;
    if (!Number.isFinite(percent) || percent <= 0 || percent > 99) continue;
    if (seenDays.has(minDays)) continue;

    seenDays.add(minDays);
    result.push({ minDays, percent });
  }

  // Sort by minDays ascending
  result.sort((a, b) => a.minDays - b.minDays);
  return result;
}

/**
 * Validate a date string (YYYY-MM-DD format).
 * @param {any} value
 * @returns {string|null} Validated date string or null
 */
export function validateDate(value) {
  if (typeof value !== 'string') return null;
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return null;

  const date = new Date(value + 'T00:00:00Z');
  if (isNaN(date.getTime())) return null;

  // Verify it round-trips correctly (e.g. rejects Feb 30)
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const day = String(date.getUTCDate()).padStart(2, '0');
  const roundTrip = `${year}-${month}-${day}`;
  if (roundTrip !== value) return null;

  return value;
}

/**
 * Validate a date range (start <= end, within max days, not in past).
 * @param {string} startDate - YYYY-MM-DD
 * @param {string} endDate - YYYY-MM-DD
 * @returns {{ valid: boolean, error?: string, totalDays?: number }}
 */
export function validateDateRange(startDate, endDate) {
  const start = validateDate(startDate);
  const end = validateDate(endDate);

  if (!start) return { valid: false, error: 'Invalid start date.' };
  if (!end) return { valid: false, error: 'Invalid end date.' };

  const startMs = new Date(start + 'T00:00:00Z').getTime();
  const endMs = new Date(end + 'T00:00:00Z').getTime();

  if (endMs < startMs) {
    return { valid: false, error: 'End date must be on or after start date.' };
  }

  const totalDays = Math.floor((endMs - startMs) / (24 * 60 * 60 * 1000)) + 1;

  if (totalDays > MAX_RENTAL_DAYS) {
    return { valid: false, error: `Rental period cannot exceed ${MAX_RENTAL_DAYS} days.` };
  }

  // Start date must not be in the past
  const today = new Date();
  today.setUTCHours(0, 0, 0, 0);
  if (startMs < today.getTime()) {
    return { valid: false, error: 'Start date cannot be in the past.' };
  }

  // End date must not be more than 1 year in the future
  const maxFuture = new Date(today);
  maxFuture.setUTCFullYear(maxFuture.getUTCFullYear() + 1);
  if (endMs > maxFuture.getTime()) {
    return { valid: false, error: 'Rental period cannot extend more than 1 year into the future.' };
  }

  return { valid: true, totalDays };
}

/**
 * Sanitize the full rental offer creation/update body.
 * @param {object} body - Request body
 * @param {boolean} isUpdate - Whether this is an update (some fields optional)
 * @returns {{ data?: object, error?: string }}
 */
export function sanitizeRentalOfferData(body, isUpdate = false) {
  if (!body || typeof body !== 'object') {
    return { error: 'Invalid request body.' };
  }

  const result = {};

  // Title
  if (body.title !== undefined || !isUpdate) {
    const title = sanitizeTitle(body.title);
    if (!title || title === 'New Rental Offer') {
      if (!isUpdate) return { error: 'Title is required.' };
    }
    if (body.title !== undefined) result.title = title;
  }

  // Description
  if (body.description !== undefined) {
    result.description = sanitizeDescription(body.description);
  }

  // Item set ID (required on create)
  if (body.item_set_id !== undefined || !isUpdate) {
    if (!isUpdate && !body.item_set_id) {
      return { error: 'Item set is required.' };
    }
    if (body.item_set_id !== undefined) {
      // UUID format - validate it's a string
      if (typeof body.item_set_id !== 'string' || !body.item_set_id.trim()) {
        return { error: 'Invalid item set ID.' };
      }
      result.item_set_id = body.item_set_id.trim();
    }
  }

  // Planet ID
  if (body.planet_id !== undefined) {
    result.planet_id = body.planet_id ? parseInt(body.planet_id) || null : null;
  }

  // Location
  if (body.location !== undefined) {
    result.location = sanitizeLocation(body.location);
  }

  // Price per day
  if (body.price_per_day !== undefined || !isUpdate) {
    const price = sanitizePrice(body.price_per_day, MIN_PRICE_PER_DAY, MAX_PRICE_PER_DAY);
    if (!isUpdate && price < MIN_PRICE_PER_DAY) {
      return { error: 'Price per day is required and must be at least 0.01 PED.' };
    }
    if (body.price_per_day !== undefined) result.price_per_day = price;
  }

  // Discounts
  if (body.discounts !== undefined) {
    result.discounts = sanitizeDiscounts(body.discounts);
  }

  // Deposit
  if (body.deposit !== undefined) {
    result.deposit = sanitizePrice(body.deposit, 0, MAX_DEPOSIT);
  }

  // Status transition
  if (body.status !== undefined) {
    const validStatuses = ['draft', 'available', 'unlisted'];
    if (validStatuses.includes(body.status)) {
      result.status = body.status;
    }
  }

  return { data: result };
}

/**
 * Validate that an item set's contents are compatible with rental offers.
 * All items must be of allowed types, and (L) blueprints are not permitted.
 * @param {object} itemSetData - The item set data object (with items array)
 * @returns {{ valid: boolean, error?: string }}
 */
export function validateItemSetForRental(itemSetData) {
  const items = itemSetData?.items;
  if (!Array.isArray(items) || items.length === 0) {
    return { valid: false, error: 'Item set is empty.' };
  }

  for (const item of items) {
    // Armor/clothing set entries are always allowed
    if (item.setType === 'ArmorSet') continue;

    const type = item.type || '';
    const name = item.name || '';

    if (!RENTAL_ALLOWED_ITEM_TYPES.has(type)) {
      return { valid: false, error: `Item type "${type}" is not allowed in rental offers. Item: ${name}` };
    }

    if (type === 'Blueprint' && isLimitedByName(name)) {
      return { valid: false, error: `Limited blueprints are not allowed in rental offers. Item: ${name}` };
    }
  }

  return { valid: true };
}
