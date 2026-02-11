// @ts-nocheck
import { TIERABLE_TYPES, CONDITION_TYPES, isLimitedByName } from '$lib/common/itemTypes.js';

export const MAX_ITEM_SET_BYTES = 102400; // 100KB
export const MAX_ITEMS_PER_SET = 100;
export const MAX_ITEM_SETS_PER_USER = 50;

const VALID_GENDERS = new Set(['Male', 'Female']);
const VALID_SET_TYPES = new Set(['ArmorSet', 'ClothingSet']);

function clampNumber(value, fallback = 0, min = null, max = null) {
  const num = typeof value === 'number' ? value : parseFloat(value);
  if (!Number.isFinite(num)) return fallback;
  if (min != null && num < min) return min;
  if (max != null && num > max) return max;
  return num;
}

function sanitizeString(value, fallback = null, maxLen = 200) {
  if (typeof value !== 'string') return fallback;
  const trimmed = value.trim();
  if (!trimmed) return fallback;
  return trimmed.slice(0, maxLen);
}

function roundTo(value, decimals) {
  const factor = Math.pow(10, decimals);
  return Math.round(value * factor) / factor;
}

/**
 * Sanitize item-level metadata based on item type and name.
 * @param {object} meta - Raw metadata object
 * @param {string} type - Item type string
 * @param {string} name - Item name string
 * @returns {object} Sanitized metadata
 */
function sanitizeItemMeta(meta, type, name) {
  if (!meta || typeof meta !== 'object') return {};

  const result = {};
  const isLimited = isLimitedByName(name);

  // Tier and TiR — for tierable item types (non-L only)
  if (TIERABLE_TYPES.has(type) && !isLimited) {
    if (meta.tier != null) {
      result.tier = clampNumber(meta.tier, 0, 0, 9);
      result.tier = Math.floor(result.tier);
    }
    if (meta.tiR != null) {
      result.tiR = clampNumber(meta.tiR, 0, 0, 999999);
      result.tiR = roundTo(result.tiR, 2);
    }
  }

  // CurrentTT — for condition item types
  if (CONDITION_TYPES.has(type)) {
    if (meta.currentTT != null) {
      result.currentTT = clampNumber(meta.currentTT, 0, 0, 10000);
      result.currentTT = roundTo(result.currentTT, 2);
    }
  }

  // QR — for non-(L) blueprints only
  if (type === 'Blueprint' && !isLimited) {
    if (meta.qr != null) {
      result.qr = clampNumber(meta.qr, 0.01, 0.01, 1.0);
      result.qr = roundTo(result.qr, 4);
    }
  }

  // Gender — for armor/clothing with Gender="Both"
  if (meta.gender != null) {
    const g = sanitizeString(meta.gender);
    if (g && VALID_GENDERS.has(g)) {
      result.gender = g;
    }
  }

  // Pet data
  if (type === 'Pet' && meta.pet && typeof meta.pet === 'object') {
    const pet = {};

    if (meta.pet.level != null) {
      pet.level = Math.floor(clampNumber(meta.pet.level, 0, 0, 200));
    }
    if (meta.pet.currentTT != null) {
      pet.currentTT = clampNumber(meta.pet.currentTT, 0, 0, 10000);
      pet.currentTT = roundTo(pet.currentTT, 2);
    }
    if (meta.pet.skills && typeof meta.pet.skills === 'object') {
      pet.skills = {};
      const entries = Object.entries(meta.pet.skills);
      for (const [key, val] of entries.slice(0, 50)) {
        const skillName = sanitizeString(key, null, 100);
        if (skillName) {
          pet.skills[skillName] = !!val;
        }
      }
    }

    if (Object.keys(pet).length > 0) {
      result.pet = pet;
    }
  }

  return result;
}

/**
 * Sanitize a single item entry in the set.
 * @param {object} entry - Raw item entry
 * @returns {object|null} Sanitized entry, or null if invalid
 */
function sanitizeItemEntry(entry) {
  if (!entry || typeof entry !== 'object') return null;

  // Set entry (armor/clothing set)
  if (entry.setType) {
    const setType = sanitizeString(entry.setType);
    if (!setType || !VALID_SET_TYPES.has(setType)) return null;

    const setName = sanitizeString(entry.setName, null, 200);
    if (!setName) return null;

    const result = {
      setType,
      setId: entry.setId != null ? clampNumber(entry.setId, null, 0, 999999999) : null,
      setName
    };

    // Gender for the set
    const gender = sanitizeString(entry.gender);
    if (gender && VALID_GENDERS.has(gender)) {
      result.gender = gender;
    }

    // Pieces
    if (Array.isArray(entry.pieces)) {
      result.pieces = entry.pieces
        .slice(0, 20) // Max 20 pieces per set
        .map(piece => {
          if (!piece || typeof piece !== 'object') return null;
          const itemId = piece.itemId != null ? clampNumber(piece.itemId, null, 0, 999999999) : null;
          const name = sanitizeString(piece.name, null, 200);
          if (!name) return null;

          const sanitized = { itemId, name };

          const slot = sanitizeString(piece.slot, null, 50);
          if (slot) sanitized.slot = slot;

          // Gender for individual piece (inherited from set or piece-specific)
          const pieceGender = sanitizeString(piece.gender);
          if (pieceGender && VALID_GENDERS.has(pieceGender)) {
            sanitized.gender = pieceGender;
          }

          // Per-piece metadata (typically just currentTT for armor/clothing)
          if (piece.meta && typeof piece.meta === 'object') {
            sanitized.meta = {};
            if (piece.meta.currentTT != null) {
              sanitized.meta.currentTT = clampNumber(piece.meta.currentTT, 0, 0, 10000);
              sanitized.meta.currentTT = roundTo(sanitized.meta.currentTT, 2);
            }
          }

          return sanitized;
        })
        .filter(Boolean);
    } else {
      result.pieces = [];
    }

    return result;
  }

  // Regular item entry
  const itemId = entry.itemId != null ? clampNumber(entry.itemId, null, 0, 999999999) : null;
  const type = sanitizeString(entry.type, null, 50);
  const name = sanitizeString(entry.name, null, 200);

  if (!name || !type) return null;

  const result = {
    itemId,
    type,
    name,
    quantity: Math.floor(clampNumber(entry.quantity, 1, 1, 9999999))
  };

  // Sanitize metadata
  if (entry.meta && typeof entry.meta === 'object') {
    result.meta = sanitizeItemMeta(entry.meta, type, name);
  }

  return result;
}

/**
 * Sanitize the full item set data object.
 * @param {object} input - Raw data from client
 * @returns {object} Sanitized data { items: [...] }
 */
export function sanitizeItemSetData(input) {
  if (!input || typeof input !== 'object') {
    return { items: [] };
  }

  const items = Array.isArray(input.items)
    ? input.items.slice(0, MAX_ITEMS_PER_SET).map(sanitizeItemEntry).filter(Boolean)
    : [];

  return { items };
}

/**
 * Get the byte size of a JSON payload.
 * @param {any} payload
 * @returns {number}
 */
export function getPayloadSizeBytes(payload) {
  try {
    return new TextEncoder().encode(JSON.stringify(payload)).length;
  } catch {
    return Number.MAX_SAFE_INTEGER;
  }
}
