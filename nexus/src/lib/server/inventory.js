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
 * Full-sync inventory import.
 * Replaces the entire server inventory for a user in a single transaction.
 * Returns a diff summary of what changed.
 */
export async function syncInventory(userId, items) {
  if (!items) items = [];
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    // 1. Fetch existing inventory for diff
    const { rows: oldItems } = await client.query(
      `SELECT item_id, item_name, quantity, instance_key, value, container
       FROM user_items WHERE user_id = $1 AND storage = 'server'`,
      [userId]
    );

    // Build lookup of old items by diffKey
    // Include container for fungible items so same item on different planets gets separate keys
    const oldMap = new Map();
    for (const row of oldItems) {
      const key = row.instance_key
        ? `${row.item_id}::${row.instance_key}`
        : `${row.item_id}::${row.container || ''}`;
      oldMap.set(key, row);
    }

    // 2. Delete all existing server inventory
    await client.query(
      `DELETE FROM user_items WHERE user_id = $1 AND storage = 'server'`,
      [userId]
    );

    // 3. Batch INSERT new items (chunks of 100)
    const BATCH_SIZE = 100;
    for (let offset = 0; offset < items.length; offset += BATCH_SIZE) {
      const batch = items.slice(offset, offset + BATCH_SIZE);
      const values = [];
      const params = [];
      let paramIdx = 1;

      for (const item of batch) {
        values.push(
          `($${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, 'server', NOW())`
        );
        params.push(
          userId,
          item.item_id,
          item.item_name,
          item.quantity ?? 0,
          item.instance_key || null,
          item.details ? JSON.stringify(item.details) : null,
          item.value ?? null,
          item.container ?? null
        );
      }

      await client.query(
        `INSERT INTO user_items (user_id, item_id, item_name, quantity, instance_key, details, value, container, storage, updated_at)
         VALUES ${values.join(', ')}`,
        params
      );
    }

    await client.query('COMMIT');

    // 4. Compute diff summary
    const newMap = new Map();
    for (const item of items) {
      const key = item.instance_key
        ? `${item.item_id}::${item.instance_key}`
        : `${item.item_id}::${item.container || ''}`;
      newMap.set(key, item);
    }

    let added = 0, updated = 0, removed = 0, unchanged = 0;
    for (const [key, newItem] of newMap) {
      const oldItem = oldMap.get(key);
      if (!oldItem) {
        added++;
      } else if (oldItem.quantity !== newItem.quantity || oldItem.value !== newItem.value) {
        updated++;
      } else {
        unchanged++;
      }
    }
    for (const key of oldMap.keys()) {
      if (!newMap.has(key)) removed++;
    }

    return { added, updated, removed, unchanged, total: items.length };
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

/**
 * Update an inventory item's mutable fields (quantity, value, details).
 * Only updates fields that are explicitly provided (not undefined).
 */
export async function updateInventoryItem(itemRowId, userId, { quantity, value, details }) {
  const setClauses = [];
  const params = [itemRowId, userId];
  let idx = 3;

  if (quantity !== undefined) {
    setClauses.push(`quantity = $${idx++}`);
    params.push(quantity);
  }
  if (value !== undefined) {
    setClauses.push(`value = $${idx++}`);
    params.push(value);
  }
  if (details !== undefined) {
    setClauses.push(`details = $${idx++}`);
    params.push(details ? JSON.stringify(details) : null);
  }

  if (setClauses.length === 0) return null;

  setClauses.push('updated_at = NOW()');

  const query = `
    UPDATE ONLY user_items
    SET ${setClauses.join(', ')}
    WHERE id = $1 AND user_id = $2
    RETURNING id, user_id, item_id, item_name, quantity, instance_key, details, value, container, storage, updated_at
  `;
  const { rows } = await pool.query(query, params);
  return rows[0] || null;
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
