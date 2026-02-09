//@ts-nocheck
import { pool } from './db.js';

/**
 * Get a user's server-stored inventory.
 */
export async function getUserInventory(userId) {
  const query = `
    SELECT id, user_id, item_id, item_name, quantity, instance_key, details, value, container, storage, updated_at
    FROM user_items
    WHERE user_id = $1 AND storage = 'server'
    ORDER BY item_name ASC
  `;
  const { rows } = await pool.query(query, [userId]);
  return rows;
}

/**
 * Bulk upsert inventory items (import).
 * Fungible items (instance_key IS NULL) are upserted by (user_id, item_id).
 * Non-fungible items are upserted by (user_id, item_id, instance_key).
 */
export async function upsertInventory(userId, items) {
  if (!items || items.length === 0) return [];

  const results = [];
  for (const item of items) {
    const { item_id, item_name, quantity, instance_key, details, value, container } = item;

    if (instance_key) {
      // Non-fungible
      const query = `
        INSERT INTO user_items (user_id, item_id, item_name, quantity, instance_key, details, value, container, storage, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'server', NOW())
        ON CONFLICT (user_id, item_id, instance_key) WHERE instance_key IS NOT NULL
        DO UPDATE SET
          item_name = EXCLUDED.item_name,
          quantity = EXCLUDED.quantity,
          details = EXCLUDED.details,
          value = EXCLUDED.value,
          container = EXCLUDED.container,
          updated_at = NOW()
        RETURNING id, item_id, item_name, quantity, instance_key, details, value, container
      `;
      const { rows } = await pool.query(query, [
        userId, item_id, item_name, quantity ?? 1, instance_key,
        details ? JSON.stringify(details) : null, value ?? null, container ?? null
      ]);
      results.push(rows[0]);
    } else {
      // Fungible
      const query = `
        INSERT INTO user_items (user_id, item_id, item_name, quantity, instance_key, details, value, container, storage, updated_at)
        VALUES ($1, $2, $3, $4, NULL, $5, $6, $7, 'server', NOW())
        ON CONFLICT (user_id, item_id) WHERE instance_key IS NULL
        DO UPDATE SET
          item_name = EXCLUDED.item_name,
          quantity = EXCLUDED.quantity,
          details = EXCLUDED.details,
          value = EXCLUDED.value,
          container = EXCLUDED.container,
          updated_at = NOW()
        RETURNING id, item_id, item_name, quantity, instance_key, details, value, container
      `;
      const { rows } = await pool.query(query, [
        userId, item_id, item_name, quantity ?? 0,
        details ? JSON.stringify(details) : null, value ?? null, container ?? null
      ]);
      results.push(rows[0]);
    }
  }
  return results;
}

/**
 * Delete an inventory item.
 */
export async function deleteInventoryItem(itemRowId, userId) {
  const query = `
    DELETE FROM user_items
    WHERE id = $1 AND user_id = $2
    RETURNING id
  `;
  const { rows } = await pool.query(query, [itemRowId, userId]);
  return rows[0] || null;
}
