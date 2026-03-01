//@ts-nocheck
import { pool } from './db.js';

// Maximum data size per preference key (20 KB)
const MAX_PREFERENCE_SIZE_BYTES = 20 * 1024;

// Maximum number of preference keys per user
const MAX_KEYS_PER_USER = 50;

// Allowed preference key patterns (validated server-side)
const ALLOWED_KEY_PREFIXES = [
  'exchange.',
  'darkMode',
  'construction.',
  'loadouts',
  'wiki.',
  'services.',
  'inventory.',
];

/**
 * Validate that a preference key is allowed.
 * @param {string} key
 * @returns {boolean}
 */
export function isValidKey(key) {
  if (!key || typeof key !== 'string' || key.length > 100) return false;
  // Only allow exact matches or keys starting with prefix + '.'
  // e.g. 'darkMode' exact, 'exchange.favourites' via 'exchange.' prefix
  return ALLOWED_KEY_PREFIXES.some(prefix =>
    key === prefix || (prefix.endsWith('.') ? key.startsWith(prefix) : key.startsWith(prefix + '.'))
  );
}

/**
 * Validate that the data size is within the 20KB limit.
 * @param {*} data
 * @returns {boolean}
 */
export function validateDataSize(data) {
  try {
    const serialized = JSON.stringify(data);
    return Buffer.byteLength(serialized, 'utf8') <= MAX_PREFERENCE_SIZE_BYTES;
  } catch {
    return false;
  }
}

/**
 * Get a single preference by key for a user.
 * @param {string|bigint} userId
 * @param {string} key
 * @returns {Promise<{user_id: bigint, key: string, data: object, updated_at: Date}|null>}
 */
export async function getPreference(userId, key) {
  const query = `
    SELECT user_id, key, data, updated_at
    FROM user_preferences
    WHERE user_id = $1 AND key = $2
  `;
  const { rows } = await pool.query(query, [userId, key]);
  return rows[0] || null;
}

/**
 * Get all preferences for a user.
 * @param {string|bigint} userId
 * @returns {Promise<Array<{user_id: bigint, key: string, data: object, updated_at: Date}>>}
 */
export async function getAllPreferences(userId) {
  const query = `
    SELECT user_id, key, data, updated_at
    FROM user_preferences
    WHERE user_id = $1
    ORDER BY key ASC
  `;
  const { rows } = await pool.query(query, [userId]);
  return rows;
}

/**
 * Upsert a single preference.
 * @param {string|bigint} userId
 * @param {string} key
 * @param {object} data
 * @returns {Promise<{user_id: bigint, key: string, data: object, updated_at: Date}>}
 */
export async function upsertPreference(userId, key, data) {
  // Check key count limit (only for new keys)
  const countQuery = `SELECT COUNT(*) as count FROM user_preferences WHERE user_id = $1`;
  const { rows: countRows } = await pool.query(countQuery, [userId]);
  const currentCount = parseInt(countRows[0]?.count || '0', 10);

  // Check if key already exists for this user
  const existsQuery = `SELECT 1 FROM user_preferences WHERE user_id = $1 AND key = $2`;
  const { rows: existsRows } = await pool.query(existsQuery, [userId, key]);
  const keyExists = existsRows.length > 0;

  if (!keyExists && currentCount >= MAX_KEYS_PER_USER) {
    throw new Error(`Maximum preference keys (${MAX_KEYS_PER_USER}) exceeded`);
  }

  const query = `
    INSERT INTO user_preferences (user_id, key, data, updated_at)
    VALUES ($1, $2, $3, NOW())
    ON CONFLICT (user_id, key) DO UPDATE SET
      data = EXCLUDED.data,
      updated_at = NOW()
    RETURNING user_id, key, data, updated_at
  `;
  const { rows } = await pool.query(query, [userId, key, JSON.stringify(data)]);
  return rows[0];
}

/**
 * Delete a single preference.
 * @param {string|bigint} userId
 * @param {string} key
 * @returns {Promise<boolean>} true if a row was deleted
 */
export async function deletePreference(userId, key) {
  const query = `
    DELETE FROM user_preferences
    WHERE user_id = $1 AND key = $2
    RETURNING user_id
  `;
  const { rows } = await pool.query(query, [userId, key]);
  return rows.length > 0;
}
