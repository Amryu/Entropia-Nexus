//@ts-nocheck
import pg from 'pg';

const Pool = pg.Pool;

const pool = new Pool({
  connectionString: process.env.POSTGRES_CONNECTION_STRING,
});

export async function startTransaction() {
  const client = await pool.connect();
  await client.query('BEGIN');

  return client;
}

export async function commitTransaction(client) {
  await client.query('COMMIT');
  client.release();
}

export async function rollbackTransaction(client) {
  await client.query('ROLLBACK');
  client.release();
}

export async function getSession(sessionId) {
  const query = 'SELECT * FROM sessions WHERE session_id = $1';
  const values = [sessionId];

  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function createSession(userId, sessionId, accessToken, refreshToken, expires) {
  const query = 'INSERT INTO sessions (user_id, session_id, access_token, refresh_token, expires) VALUES ($1, $2, $3, $4, $5)';
  const values = [userId, sessionId, accessToken, refreshToken, expires];

  await pool.query(query, values);
}

export async function updateSession(sessionId, accessToken, refreshToken, expires) {
  const query = 'UPDATE sessions SET access_token = $2, refresh_token = $3, expires = $4 WHERE session_id = $1';
  const values = [sessionId, accessToken, refreshToken, expires];

  await pool.query(query, values);
}

export async function deleteSession(sessionId) {
  const query = 'DELETE FROM sessions WHERE session_id = $1';
  const values = [sessionId];

  await pool.query(query, values);
}

export async function getUserFromSession(sessionId) {
  const query = 'SELECT * FROM USERS WHERE id = (SELECT user_id FROM sessions WHERE session_id = $1)';
  const values = [sessionId];

  const { rows } = await pool.query(query, values);

  return rows[0];
}

export async function upsertUser(user) {
  const query = 'INSERT INTO users (id, username, global_name, discriminator, avatar) VALUES ($1, $2, $3, $4, $5) ON CONFLICT (id) DO UPDATE SET username = $2, global_name = $3, discriminator = $4, avatar = $5 RETURNING *';
  const values = [user.id, user.username, user.global_name ?? user.username, user.discriminator, user.avatar];

  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function getChangeById(id) {
  const query = 'SELECT * FROM changes WHERE id = $1';
  const values = [id];

  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function getChangeByEntityId(id) {
  const query = 'SELECT * FROM changes WHERE data->>\'Id\' = $1 AND state IN (\'Draft\', \'Pending\')';
  const values = [id];

  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function updateChange(id, data, state) {
  const query = 'UPDATE changes SET data = $2, state = $3 WHERE id = $1';
  const values = [id, data, state];

  await pool.query(query, values);
}

export async function deleteChange(id) {
  const query = `UPDATE changes SET state = 'Deleted' WHERE id = $1`;
  const values = [id];

  await pool.query(query, values);
}

export async function createChange(author_id, type, state, entity, data) {
  const query = 'INSERT INTO changes (author_id, type, state, entity, data) VALUES ($1, $2, $3, $4, $5) RETURNING *';
  const values = [author_id, type, state, entity, data];

  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function getChangeEntities() {
  const query = `SELECT enumlabel FROM pg_enum WHERE enumtypid = 'change_entity'::regtype`;

  const { rows } = await pool.query(query);
  return rows.map(row => row.enumlabel);
}

export async function getChangeTypes() {
  const query = `SELECT enumlabel FROM pg_enum WHERE enumtypid = 'change_type'::regtype`;

  const { rows } = await pool.query(query);
  return rows.map(row => row.enumlabel);
}

export async function executeVector(query, values) {
  const { rows } = await pool.query(query, values);
  return rows;
}

export async function executeScalar(query, values) {
  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function executeNonQuery(query, values) {
  await pool.query(query, values);
}

// Shop functions
export async function getShop(shopIdentifier) {
  let query, values;
  
  if (isNaN(shopIdentifier)) {
    // Search by name
    query = `
      SELECT s.*, 
             p."Name" as planet_name,
             u."Name" as owner_name
      FROM shops s
      LEFT JOIN "Planets" p ON s.planet_id = p."Id"
      LEFT JOIN users u ON s.owner_id = u.id
      WHERE s.name = $1
    `;
    values = [shopIdentifier];
  } else {
    // Search by ID
    query = `
      SELECT s.*, 
             p."Name" as planet_name,
             u."Name" as owner_name
      FROM shops s
      LEFT JOIN "Planets" p ON s.planet_id = p."Id"
      LEFT JOIN users u ON s.owner_id = u.id
      WHERE s.id = $1
    `;
    values = [parseInt(shopIdentifier)];
  }
  
  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function updateShopInventory(shopId, inventoryGroups) {
  const client = await startTransaction();
  try {
    // Get existing groups for this shop
    const existingGroupsResult = await client.query(
      'SELECT id, name, sort_order FROM shop_inventory_groups WHERE shop_id = $1',
      [shopId]
    );
    const existingGroups = new Map();
    for (const group of existingGroupsResult.rows) {
      existingGroups.set(group.name, group);
    }

    // Get existing items for this shop
    const existingItemsResult = await client.query(
      'SELECT id, group_id, item_id, stack_size, markup, sort_order FROM shop_inventory_items WHERE shop_id = $1',
      [shopId]
    );
    const existingItems = new Map();
    for (const item of existingItemsResult.rows) {
      const key = `${item.group_id}-${item.item_id}-${item.stack_size}-${item.markup}`;
      existingItems.set(key, item);
    }

    const processedGroups = new Set();
    const processedItems = new Set();

    // Process new/updated groups and items
    for (let groupIndex = 0; groupIndex < inventoryGroups.length; groupIndex++) {
      const group = inventoryGroups[groupIndex];
      let groupId;

      if (existingGroups.has(group.name)) {
        // Update existing group
        const existingGroup = existingGroups.get(group.name);
        groupId = existingGroup.id;
        processedGroups.add(group.name);
        
        // Update sort order if changed
        if (existingGroup.sort_order !== groupIndex) {
          await client.query(
            'UPDATE shop_inventory_groups SET sort_order = $1 WHERE id = $2',
            [groupIndex, groupId]
          );
        }
      } else {
        // Insert new group
        const groupResult = await client.query(
          'INSERT INTO shop_inventory_groups (shop_id, name, sort_order) VALUES ($1, $2, $3) RETURNING id',
          [shopId, group.name, groupIndex]
        );
        groupId = groupResult.rows[0].id;
        processedGroups.add(group.name);
      }

      // Process items for this group
      for (let itemIndex = 0; itemIndex < group.Items.length; itemIndex++) {
        const item = group.Items[itemIndex];
        const itemKey = `${groupId}-${item.item_id}-${item.stack_size}-${item.markup}`;
        const sortOrder = item.sort_order || itemIndex;

        if (existingItems.has(itemKey)) {
          // Update existing item (only sort_order can change for existing items)
          const existingItem = existingItems.get(itemKey);
          processedItems.add(itemKey);
          
          if (existingItem.sort_order !== sortOrder) {
            await client.query(
              'UPDATE shop_inventory_items SET sort_order = $1 WHERE id = $2',
              [sortOrder, existingItem.id]
            );
          }
        } else {
          // Insert new item
          await client.query(
            'INSERT INTO shop_inventory_items (shop_id, group_id, item_id, stack_size, markup, sort_order) VALUES ($1, $2, $3, $4, $5, $6)',
            [shopId, groupId, item.item_id, item.stack_size, item.markup, sortOrder]
          );
          processedItems.add(itemKey);
        }
      }
    }

    // Delete groups that are no longer present
    for (const [groupName, group] of existingGroups) {
      if (!processedGroups.has(groupName)) {
        await client.query('DELETE FROM shop_inventory_groups WHERE id = $1', [group.id]);
      }
    }

    // Delete items that are no longer present
    for (const [itemKey, item] of existingItems) {
      if (!processedItems.has(itemKey)) {
        await client.query('DELETE FROM shop_inventory_items WHERE id = $1', [item.id]);
      }
    }

    await commitTransaction(client);
    return true;
  } catch (error) {
    await rollbackTransaction(client);
    console.error('Error updating shop inventory:', error);
    return false;
  }
}

export async function updateShopManagers(shopId, managers) {
  const client = await startTransaction();
  try {
    // First, delete all existing managers for this shop
    await client.query('DELETE FROM shop_managers WHERE shop_id = $1', [shopId]);

    // Insert new managers
    for (let managerIndex = 0; managerIndex < managers.length; managerIndex++) {
      const manager = managers[managerIndex];
      
      await client.query(
        'INSERT INTO shop_managers (shop_id, user_id) VALUES ($1, $2)',
        [shopId, manager.user_id]
      );
    }

    await commitTransaction(client);
    return true;
  } catch (error) {
    await rollbackTransaction(client);
    console.error('Error updating shop managers:', error);
    return false;
  }
}

export async function getUserByEntropiaName(entropiaName) {
  const query = 'SELECT id, eu_name, verified FROM users WHERE LOWER(eu_name) = LOWER($1)';
  const values = [entropiaName];

  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function getShopManagers(shopId) {
  const query = `
    SELECT sm.user_id, u.eu_name as user_name
    FROM shop_managers sm
    JOIN users u ON sm.user_id = u.id
    WHERE sm.shop_id = $1 AND u.verified = true
    ORDER BY u.eu_name
  `;
  const values = [shopId];

  const { rows } = await pool.query(query, values);
  return rows.map(row => ({
    user_id: row.user_id,
    User: { Name: row.user_name },
    eu_name: row.user_name
  }));
}

export async function getShopInventory(shopId) {
  const query = `
    SELECT 
      g.id as group_id,
      g.name as group_name,
      g.sort_order as group_sort_order,
      i.id as item_table_id,
      i.item_id,
      i.stack_size,
      i.markup,
      i.sort_order as item_sort_order,
      items."Name" as item_name
    FROM shop_inventory_groups g
    LEFT JOIN shop_inventory_items i ON g.id = i.group_id
    LEFT JOIN "Items" items ON i.item_id = items."Id"
    WHERE g.shop_id = $1
    ORDER BY g.sort_order, i.sort_order
  `;
  const values = [shopId];

  const { rows } = await pool.query(query, values);
  
  // Group the results by inventory group
  const groupsMap = new Map();
  
  for (const row of rows) {
    if (!groupsMap.has(row.group_id)) {
      groupsMap.set(row.group_id, {
        id: row.group_id,
        name: row.group_name,
        sort_order: row.group_sort_order,
        Items: []
      });
    }
    
    // Add item if it exists
    if (row.item_id) {
      groupsMap.get(row.group_id).Items.push({
        id: row.item_table_id,
        item_id: row.item_id,
        stack_size: row.stack_size,
        markup: row.markup,
        sort_order: row.item_sort_order,
        Item: { Name: row.item_name }
      });
    }
  }
  
  return Array.from(groupsMap.values());
}