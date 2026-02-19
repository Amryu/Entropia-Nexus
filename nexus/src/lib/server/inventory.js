//@ts-nocheck
import { pool } from './db.js';

/**
 * Get a user's server-stored inventory.
 */
export async function getUserInventory(userId) {
  const query = `
    SELECT id, user_id, item_id, item_name, quantity, instance_key, details, value, container, container_path, storage, updated_at
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
    const { item_id, item_name, quantity, instance_key, details, value, container, container_path } = item;

    if (instance_key) {
      // Non-fungible
      const query = `
        INSERT INTO user_items (user_id, item_id, item_name, quantity, instance_key, details, value, container, container_path, storage, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'server', NOW())
        ON CONFLICT (user_id, item_id, instance_key) WHERE instance_key IS NOT NULL
        DO UPDATE SET
          item_name = EXCLUDED.item_name,
          quantity = EXCLUDED.quantity,
          details = EXCLUDED.details,
          value = EXCLUDED.value,
          container = EXCLUDED.container,
          container_path = EXCLUDED.container_path,
          updated_at = NOW()
        RETURNING id, item_id, item_name, quantity, instance_key, details, value, container, container_path
      `;
      const { rows } = await pool.query(query, [
        userId, item_id, item_name, quantity ?? 1, instance_key,
        details ? JSON.stringify(details) : null, value ?? null, container ?? null,
        container_path ?? null
      ]);
      results.push(rows[0]);
    } else {
      // Fungible
      const query = `
        INSERT INTO user_items (user_id, item_id, item_name, quantity, instance_key, details, value, container, container_path, storage, updated_at)
        VALUES ($1, $2, $3, $4, NULL, $5, $6, $7, $8, 'server', NOW())
        ON CONFLICT (user_id, item_id) WHERE instance_key IS NULL
        DO UPDATE SET
          item_name = EXCLUDED.item_name,
          quantity = EXCLUDED.quantity,
          details = EXCLUDED.details,
          value = EXCLUDED.value,
          container = EXCLUDED.container,
          container_path = EXCLUDED.container_path,
          updated_at = NOW()
        RETURNING id, item_id, item_name, quantity, instance_key, details, value, container, container_path
      `;
      const { rows } = await pool.query(query, [
        userId, item_id, item_name, quantity ?? 0,
        details ? JSON.stringify(details) : null, value ?? null, container ?? null,
        container_path ?? null
      ]);
      results.push(rows[0]);
    }
  }
  return results;
}

/**
 * Full-sync inventory import.
 * Replaces the entire server inventory for a user in a single transaction.
 * Records import history and per-item deltas for change tracking.
 * Tracks unknown items (item_id=0) for admin visibility.
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

    // 3. Batch INSERT new items (chunks of 100) — now includes container_path
    const BATCH_SIZE = 100;
    for (let offset = 0; offset < items.length; offset += BATCH_SIZE) {
      const batch = items.slice(offset, offset + BATCH_SIZE);
      const values = [];
      const params = [];
      let paramIdx = 1;

      for (const item of batch) {
        values.push(
          `($${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, 'server', NOW())`
        );
        params.push(
          userId,
          item.item_id,
          item.item_name,
          item.quantity ?? 0,
          item.instance_key || null,
          item.details ? JSON.stringify(item.details) : null,
          item.value ?? null,
          item.container ?? null,
          item.container_path ?? null
        );
      }

      await client.query(
        `INSERT INTO user_items (user_id, item_id, item_name, quantity, instance_key, details, value, container, container_path, storage, updated_at)
         VALUES ${values.join(', ')}`,
        params
      );
    }

    // 4. Compute diff and record deltas
    const newMap = new Map();
    for (const item of items) {
      const key = item.instance_key
        ? `${item.item_id}::${item.instance_key}`
        : `${item.item_id}::${item.container || ''}`;
      newMap.set(key, item);
    }

    let added = 0, updated = 0, removed = 0, unchanged = 0;
    const deltas = [];

    for (const [key, newItem] of newMap) {
      const oldItem = oldMap.get(key);
      if (!oldItem) {
        added++;
        deltas.push({
          delta_type: 'added',
          item_id: newItem.item_id,
          item_name: newItem.item_name,
          container: newItem.container || null,
          instance_key: newItem.instance_key || null,
          old_quantity: null, new_quantity: newItem.quantity,
          old_value: null, new_value: newItem.value ?? null,
        });
      } else if (oldItem.quantity !== newItem.quantity || Number(oldItem.value) !== Number(newItem.value)) {
        updated++;
        deltas.push({
          delta_type: 'changed',
          item_id: newItem.item_id,
          item_name: newItem.item_name,
          container: newItem.container || null,
          instance_key: newItem.instance_key || null,
          old_quantity: oldItem.quantity, new_quantity: newItem.quantity,
          old_value: oldItem.value ?? null, new_value: newItem.value ?? null,
        });
      } else {
        unchanged++;
      }
    }
    for (const [key, oldItem] of oldMap) {
      if (!newMap.has(key)) {
        removed++;
        deltas.push({
          delta_type: 'removed',
          item_id: oldItem.item_id,
          item_name: oldItem.item_name,
          container: oldItem.container || null,
          instance_key: oldItem.instance_key || null,
          old_quantity: oldItem.quantity, new_quantity: null,
          old_value: oldItem.value ?? null, new_value: null,
        });
      }
    }

    // 5. Record import history
    const totalValue = items.reduce((sum, item) => sum + (Number(item.value) || 0), 0);
    const summary = { added, updated, removed, unchanged };
    const { rows: [importRow] } = await client.query(
      `INSERT INTO inventory_imports (user_id, item_count, total_value, summary)
       VALUES ($1, $2, $3, $4)
       RETURNING id`,
      [userId, items.length, totalValue || null, JSON.stringify(summary)]
    );

    // 6. Record deltas in batches
    if (deltas.length > 0) {
      const DELTA_BATCH = 100;
      for (let offset = 0; offset < deltas.length; offset += DELTA_BATCH) {
        const batch = deltas.slice(offset, offset + DELTA_BATCH);
        const values = [];
        const params = [];
        let paramIdx = 1;

        for (const d of batch) {
          values.push(
            `($${paramIdx++}, $${paramIdx++}::inventory_delta_type, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++}, $${paramIdx++})`
          );
          params.push(
            importRow.id, d.delta_type, d.item_id, d.item_name,
            d.container, d.instance_key,
            d.old_quantity, d.new_quantity, d.old_value, d.new_value
          );
        }

        await client.query(
          `INSERT INTO inventory_import_deltas (import_id, delta_type, item_id, item_name, container, instance_key, old_quantity, new_quantity, old_value, new_value)
           VALUES ${values.join(', ')}`,
          params
        );
      }
    }

    // 7. Track unknown items (item_id = 0)
    await trackUnknownItems(client, userId, items);

    await client.query('COMMIT');

    return { added, updated, removed, unchanged, total: items.length };
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

/**
 * Track unknown items from an import.
 * Upserts into unknown_items table and tracks per-user occurrence.
 */
async function trackUnknownItems(client, userId, items) {
  const unknowns = items.filter(item => item.item_id === 0);
  if (unknowns.length === 0) return;

  // Deduplicate by name (case-insensitive)
  const seen = new Map();
  for (const item of unknowns) {
    const lower = item.item_name.toLowerCase();
    if (!seen.has(lower)) {
      seen.set(lower, item);
    }
  }

  for (const item of seen.values()) {
    // Compute per-unit value: for stackable items, value is total TT, so divide by quantity
    const qty = item.quantity || 1;
    const perUnitValue = item.value != null ? Number(item.value) / qty : null;

    // Upsert the unknown item
    const { rows: [unknownRow] } = await client.query(
      `INSERT INTO unknown_items (item_name, value, user_count, first_seen_at, last_seen_at)
       VALUES ($1, $2, 0, NOW(), NOW())
       ON CONFLICT (LOWER(item_name)) DO UPDATE SET
         value = COALESCE(EXCLUDED.value, unknown_items.value),
         last_seen_at = NOW()
       RETURNING id`,
      [item.item_name, perUnitValue]
    );

    // Track user occurrence — increment user_count only if new association
    const { rowCount } = await client.query(
      `INSERT INTO unknown_item_users (unknown_item_id, user_id)
       VALUES ($1, $2)
       ON CONFLICT DO NOTHING`,
      [unknownRow.id, userId]
    );

    if (rowCount > 0) {
      await client.query(
        `UPDATE unknown_items SET user_count = user_count + 1 WHERE id = $1`,
        [unknownRow.id]
      );
    }
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
    RETURNING id, user_id, item_id, item_name, quantity, instance_key, details, value, container, container_path, storage, updated_at
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

/**
 * Get user's import history (paginated, most recent first).
 */
export async function getImportHistory(userId, limit = 20, offset = 0) {
  const { rows } = await pool.query(
    `SELECT id, user_id, imported_at, item_count, total_value, summary
     FROM inventory_imports
     WHERE user_id = $1
     ORDER BY imported_at DESC
     LIMIT $2 OFFSET $3`,
    [userId, limit, offset]
  );
  return rows;
}

/**
 * Get deltas for a specific import.
 */
export async function getImportDeltas(importId, userId) {
  // Verify ownership first
  const { rows: [importRow] } = await pool.query(
    `SELECT id FROM inventory_imports WHERE id = $1 AND user_id = $2`,
    [importId, userId]
  );
  if (!importRow) return null;

  const { rows } = await pool.query(
    `SELECT id, delta_type, item_id, item_name, container, instance_key,
            old_quantity, new_quantity, old_value, new_value
     FROM inventory_import_deltas
     WHERE import_id = $1
     ORDER BY item_name ASC`,
    [importId]
  );
  return rows;
}

/**
 * Get portfolio value history (all imports with non-null total_value).
 */
export async function getValueHistory(userId) {
  const { rows } = await pool.query(
    `SELECT imported_at, total_value, item_count
     FROM inventory_imports
     WHERE user_id = $1 AND total_value IS NOT NULL
     ORDER BY imported_at ASC`,
    [userId]
  );
  return rows;
}

/**
 * Get user's markup configurations.
 */
export async function getUserMarkups(userId) {
  const { rows } = await pool.query(
    `SELECT item_id, markup, updated_at
     FROM user_item_markups
     WHERE user_id = $1`,
    [userId]
  );
  return rows;
}

/**
 * Bulk upsert user markup configurations.
 */
export async function upsertUserMarkups(userId, markups) {
  if (!markups || markups.length === 0) return [];

  const results = [];
  for (const { item_id, markup } of markups) {
    const { rows } = await pool.query(
      `INSERT INTO user_item_markups (user_id, item_id, markup, updated_at)
       VALUES ($1, $2, $3, NOW())
       ON CONFLICT (user_id, item_id)
       DO UPDATE SET markup = EXCLUDED.markup, updated_at = NOW()
       RETURNING item_id, markup, updated_at`,
      [userId, item_id, markup]
    );
    results.push(rows[0]);
  }
  return results;
}

/**
 * Delete a user's markup for a specific item.
 */
export async function deleteUserMarkup(userId, itemId) {
  const { rowCount } = await pool.query(
    `DELETE FROM user_item_markups WHERE user_id = $1 AND item_id = $2`,
    [userId, itemId]
  );
  return rowCount > 0;
}

/**
 * Get unknown items list (for admin panel).
 */
export async function getUnknownItems({ resolved = false, limit = 50, offset = 0 } = {}) {
  const { rows } = await pool.query(
    `SELECT id, item_name, value, user_count, first_seen_at, last_seen_at, resolved, resolved_item_id
     FROM unknown_items
     WHERE resolved = $1
     ORDER BY user_count DESC, last_seen_at DESC
     LIMIT $2 OFFSET $3`,
    [resolved, limit, offset]
  );
  return rows;
}

/**
 * Mark an unknown item as resolved.
 */
export async function resolveUnknownItem(unknownItemId, resolvedItemId = null) {
  const { rows } = await pool.query(
    `UPDATE unknown_items
     SET resolved = TRUE, resolved_item_id = $2
     WHERE id = $1
     RETURNING id, item_name, resolved, resolved_item_id`,
    [unknownItemId, resolvedItemId]
  );
  return rows[0] || null;
}
