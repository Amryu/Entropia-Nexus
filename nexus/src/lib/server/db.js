//@ts-nocheck
import pg from 'pg';

const Pool = pg.Pool;

export const pool = new Pool({
  connectionString: process.env.POSTGRES_CONNECTION_STRING,
});

// Global error/logging guards to avoid silent process crashes
if (!globalThis.__dbErrorHooksRegistered) {
  process.on('unhandledRejection', (reason, p) => {
    console.error('Unhandled Rejection at:', p, 'reason:', reason);
  });
  process.on('uncaughtException', (err) => {
    console.error('Uncaught Exception:', err);
  });
  globalThis.__dbErrorHooksRegistered = true;
}

// Log pool-level errors from idle clients so they don't crash the process
pool.on('error', (err) => {
  console.error('Postgres pool error (idle client):', err);
});

// Set a sane statement timeout per connection so queries fail fast
const STATEMENT_TIMEOUT_MS = Number(process.env.PG_STATEMENT_TIMEOUT_MS ?? 5000);
pool.on('connect', (client) => {
  // Best-effort; if it fails, we still keep the connection and log
  client
    .query(`SET statement_timeout = ${STATEMENT_TIMEOUT_MS}`)
    .catch((e) => console.error('Failed to set statement_timeout', e));
});

// Wrap pool.query to ensure consistent logging on failures
const _poolQuery = pool.query.bind(pool);
pool.query = async (text, params) => {
  try {
    return await _poolQuery(text, params);
  } catch (err) {
    console.error('DB query failed:', { text, params, err });
    throw err;
  }
};

export async function startTransaction() {
  console.log('[DB] startTransaction - Pool status before acquire:', {
    total: pool.totalCount,
    idle: pool.idleCount,
    waiting: pool.waitingCount
  });
  const client = await pool.connect();
  console.log('[DB] startTransaction - Client acquired from pool');
  
  try {
    await client.query('BEGIN');
    console.log('[DB] startTransaction - Transaction started');
    return client;
  } catch (err) {
    try { client.release(); } catch (_) { /* ignore */ }
    console.error('BEGIN failed:', err);
    throw err;
  }
}

export async function commitTransaction(client) {
  try {
    await client.query('COMMIT');
    console.log('[DB] commitTransaction - COMMIT successful');
  } catch (err) {
    console.error('COMMIT failed:', err);
    throw err;
  } finally {
    try {
      console.log('[DB] commitTransaction - Releasing client back to pool');
      client.release();
      console.log('[DB] commitTransaction - Client released, pool status:', {
        total: pool.totalCount,
        idle: pool.idleCount,
        waiting: pool.waitingCount
      });
    } catch (e) {
      console.error('Release after COMMIT failed:', e);
    }
  }
}

export async function rollbackTransaction(client) {
  try {
    await client.query('ROLLBACK');
  } catch (err) {
    console.error('ROLLBACK failed:', err);
  } finally {
    try { client.release(); } catch (e) { console.error('Release after ROLLBACK failed:', e); }
  }
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

export async function getUserById(userId) {
  const query = 'SELECT * FROM users WHERE id = $1';
  const values = [userId];

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
  try { await rollbackTransaction(client); } catch (rbErr) { console.error('Error during rollback:', rbErr); }
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
  try { await rollbackTransaction(client); } catch (rbErr) { console.error('Error during rollback:', rbErr); }
  console.error('Error updating shop managers:', error);
    return false;
  }
}

export async function updateShopOwner(shopId, newOwnerId) {
  const client = await startTransaction();
  try {
    // Update owner
    await client.query(
      'UPDATE shops SET owner_id = $1 WHERE id = $2',
      [newOwnerId, shopId]
    );

    // Clear all managers when owner changes
    await client.query('DELETE FROM shop_managers WHERE shop_id = $1', [shopId]);

    await commitTransaction(client);
    return true;
  } catch (error) {
    try { await rollbackTransaction(client); } catch (rbErr) { console.error('Error during rollback:', rbErr); }
    console.error('Error updating shop owner:', error);
    return false;
  }
}

export async function getUserByEntropiaName(entropiaName) {
  const query = 'SELECT id, eu_name, verified FROM users WHERE LOWER(eu_name) = LOWER($1)';
  const values = [entropiaName];

  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function getUserByUsernameOrDiscordTag(identifier) {
  const query = `
    SELECT id, username, eu_name, verified
    FROM users
    WHERE LOWER(username) = LOWER($1) OR LOWER(eu_name) = LOWER($1)
  `;
  const values = [identifier];

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
  return rows;
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
      i.sort_order as item_sort_order
    FROM shop_inventory_groups g
    LEFT JOIN shop_inventory_items i ON g.id = i.group_id
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
        sort_order: row.item_sort_order
      });
    }
  }

  return Array.from(groupsMap.values());
}

// ============================================
// SERVICE FUNCTIONS
// ============================================

export async function getServices(filters = {}) {
  // Note: review_stats removed - review_score column dropped in migration 010
  let query = `
    SELECT
      s.*,
      u.eu_name as owner_name,
      u.id as owner_id,
      ticket_prices.min_price,
      ticket_prices.max_price
    FROM services s
    JOIN users u ON s.user_id = u.id
    LEFT JOIN (
      SELECT
        service_id,
        MIN(price) as min_price,
        MAX(price) as max_price
      FROM service_ticket_offers
      WHERE is_active = true AND uses_count IS NOT NULL
      GROUP BY service_id
    ) ticket_prices ON s.id = ticket_prices.service_id
    WHERE s.is_active = true
  `;
  const values = [];
  let paramIndex = 1;

  if (filters.type) {
    query += ` AND s.type = $${paramIndex}`;
    values.push(filters.type);
    paramIndex++;
  }

  if (filters.planet_id) {
    query += ` AND s.planet_id = $${paramIndex}`;
    values.push(filters.planet_id);
    paramIndex++;
  }

  if (filters.user_id) {
    query += ` AND s.user_id = $${paramIndex}`;
    values.push(filters.user_id);
    paramIndex++;
  }

  query += ' ORDER BY s.created_at DESC';

  const { rows } = await pool.query(query, values);
  return rows;
}

export async function getServiceById(serviceId) {
  console.log('[DB] getServiceById - Pool status:', {
    total: pool.totalCount,
    idle: pool.idleCount,
    waiting: pool.waitingCount
  });
  
  // Check for blocking queries
  const lockCheck = await pool.query(`
    SELECT pid, state, query, wait_event_type, wait_event 
    FROM pg_stat_activity 
    WHERE datname = current_database() AND state != 'idle'
  `);
  console.log('[DB] Active connections:', lockCheck.rows);
  
  const query = `
    SELECT
      s.*,
      u.eu_name as owner_name,
      u.id as owner_id
    FROM services s
    JOIN users u ON s.user_id = u.id
    WHERE s.id = $1
  `;
  console.log('[DB] getServiceById - Executing query for service', serviceId);
  const { rows } = await pool.query(query, [serviceId]);
  console.log('[DB] getServiceById - Query completed, got', rows.length, 'rows');
  return rows[0];
}

export async function getServiceByIdOrTitle(identifier) {
  let query, values;

  if (!isNaN(identifier)) {
    query = `
      SELECT
        s.*,
        u.eu_name as owner_name,
        u.id as owner_id
      FROM services s
      JOIN users u ON s.user_id = u.id
      WHERE s.id = $1
    `;
    values = [parseInt(identifier)];
  } else {
    query = `
      SELECT
        s.*,
        u.eu_name as owner_name,
        u.id as owner_id
      FROM services s
      JOIN users u ON s.user_id = u.id
      WHERE LOWER(s.title) = LOWER($1)
    `;
    values = [identifier];
  }

  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function createService(serviceData) {
  const query = `
    INSERT INTO services (
      user_id, type, custom_type_name, title, description,
      planet_id, willing_to_travel, travel_fee,
      is_active, is_busy
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
    RETURNING *
  `;
  const values = [
    serviceData.user_id,
    serviceData.type,
    serviceData.custom_type_name || null,
    serviceData.title,
    serviceData.description || null,
    serviceData.planet_id || null,
    serviceData.willing_to_travel || false,
    serviceData.travel_fee || null,
    false, // Services start deactivated so provider can configure first
    false
  ];

  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function updateService(serviceId, serviceData) {
  const query = `
    UPDATE services SET
      type = $2,
      custom_type_name = $3,
      title = $4,
      description = $5,
      planet_id = $6,
      willing_to_travel = $7,
      travel_fee = $8,
      is_active = $9,
      updated_at = CURRENT_TIMESTAMP
    WHERE id = $1
    RETURNING *
  `;
  const values = [
    serviceId,
    serviceData.type,
    serviceData.custom_type_name || null,
    serviceData.title,
    serviceData.description || null,
    serviceData.planet_id || null,
    serviceData.willing_to_travel || false,
    serviceData.travel_fee || null,
    serviceData.is_active !== false
  ];

  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function deleteService(serviceId) {
  // Soft delete by setting is_active to false
  const query = `UPDATE services SET is_active = false, updated_at = CURRENT_TIMESTAMP WHERE id = $1`;
  await pool.query(query, [serviceId]);
  return true;
}

export async function getUserServices(userId) {
  const query = `
    SELECT
      s.*,
      u.eu_name as owner_name,
      u.id as owner_id
    FROM services s
    JOIN users u ON s.user_id = u.id
    WHERE s.user_id = $1
    ORDER BY s.is_active DESC, s.created_at DESC
  `;
  const { rows } = await pool.query(query, [userId]);
  return rows;
}

// Service type-specific details
export async function getServiceHealingDetails(serviceId) {
  const query = `SELECT * FROM service_healing_details WHERE service_id = $1`;
  const { rows } = await pool.query(query, [serviceId]);
  return rows[0];
}

export async function upsertServiceHealingDetails(serviceId, details) {
  const query = `
    INSERT INTO service_healing_details (service_id, paramedic_level, accepts_time_billing, rate_per_hour, accepts_decay_billing)
    VALUES ($1, $2, $3, $4, $5)
    ON CONFLICT (service_id) DO UPDATE SET
      paramedic_level = $2,
      accepts_time_billing = $3,
      rate_per_hour = $4,
      accepts_decay_billing = $5
    RETURNING *
  `;
  const values = [
    serviceId,
    details.paramedic_level || null,
    details.accepts_time_billing !== false,
    details.rate_per_hour || null,
    details.accepts_decay_billing !== false
  ];
  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function getServiceDpsDetails(serviceId) {
  const query = `SELECT * FROM service_dps_details WHERE service_id = $1`;
  const { rows } = await pool.query(query, [serviceId]);
  return rows[0];
}

export async function upsertServiceDpsDetails(serviceId, details) {
  const query = `
    INSERT INTO service_dps_details (service_id, profession_id, profession_level, accepts_time_billing, rate_per_hour, accepts_decay_billing, notes)
    VALUES ($1, $2, $3, $4, $5, $6, $7)
    ON CONFLICT (service_id) DO UPDATE SET
      profession_id = $2,
      profession_level = $3,
      accepts_time_billing = $4,
      rate_per_hour = $5,
      accepts_decay_billing = $6,
      notes = $7
    RETURNING *
  `;
  const values = [
    serviceId,
    details.profession_id || null,
    details.profession_level || null,
    details.accepts_time_billing !== false,
    details.rate_per_hour || null,
    details.accepts_decay_billing !== false,
    details.notes || null
  ];
  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function getServiceTransportationDetails(serviceId) {
  const query = `SELECT * FROM service_transportation_details WHERE service_id = $1`;
  const { rows } = await pool.query(query, [serviceId]);
  return rows[0];
}

export async function upsertServiceTransportationDetails(serviceId, details) {
  const query = `
    INSERT INTO service_transportation_details (
      service_id, vehicle_id, route_description,
      departure_planet_id, departure_location, arrival_planet_id, arrival_location,
      allows_pickup, pickup_fee, request_window_hours_before, request_cutoff_minutes,
      transportation_type, ship_name, service_mode, current_planet_id
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
    ON CONFLICT (service_id) DO UPDATE SET
      vehicle_id = $2,
      route_description = $3,
      departure_planet_id = $4,
      departure_location = $5,
      arrival_planet_id = $6,
      arrival_location = $7,
      allows_pickup = $8,
      pickup_fee = $9,
      request_window_hours_before = $10,
      request_cutoff_minutes = $11,
      transportation_type = $12,
      ship_name = $13,
      service_mode = $14,
      current_planet_id = $15
    RETURNING *
  `;
  const values = [
    serviceId,
    details.vehicle_id || null,
    details.route_description || null,
    details.departure_planet_id || null,
    details.departure_location || null,
    details.arrival_planet_id || null,
    details.arrival_location || null,
    details.allows_pickup || false,
    details.pickup_fee || null,
    details.request_window_hours_before || 24,
    details.request_cutoff_minutes || 30,
    details.transportation_type || 'regular',
    details.ship_name || null,
    details.service_mode || 'on_demand',
    details.current_planet_id || null
  ];
  const { rows } = await pool.query(query, values);
  return rows[0];
}

// Service equipment
export async function getServiceEquipment(serviceId) {
  const query = `
    SELECT * FROM service_equipment
    WHERE service_id = $1
    ORDER BY is_primary DESC, sort_order ASC
  `;
  const { rows } = await pool.query(query, [serviceId]);
  return rows;
}

export async function addServiceEquipment(serviceId, equipment) {
  const query = `
    INSERT INTO service_equipment (service_id, item_id, item_name, item_type, tier, is_primary, attachments, extra_price, notes, sort_order)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
    RETURNING *
  `;
  const values = [
    serviceId,
    equipment.item_id,
    equipment.item_name || null,
    equipment.item_type,
    equipment.tier || null,
    equipment.is_primary !== false,
    equipment.attachments ? JSON.stringify(equipment.attachments) : null,
    equipment.extra_price || null,
    equipment.notes || null,
    equipment.sort_order || 0
  ];
  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function updateServiceEquipment(equipmentId, equipment) {
  const query = `
    UPDATE service_equipment SET
      item_id = $2,
      item_name = $3,
      item_type = $4,
      tier = $5,
      is_primary = $6,
      attachments = $7,
      extra_price = $8,
      notes = $9,
      sort_order = $10
    WHERE id = $1
    RETURNING *
  `;
  const values = [
    equipmentId,
    equipment.item_id,
    equipment.item_name || null,
    equipment.item_type,
    equipment.tier || null,
    equipment.is_primary !== false,
    equipment.attachments ? JSON.stringify(equipment.attachments) : null,
    equipment.extra_price || null,
    equipment.notes || null,
    equipment.sort_order || 0
  ];
  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function deleteServiceEquipment(equipmentId) {
  await pool.query('DELETE FROM service_equipment WHERE id = $1', [equipmentId]);
  return true;
}

// Service armor sets
export async function getServiceArmorSets(serviceId) {
  const query = `SELECT * FROM service_armor_sets WHERE service_id = $1 ORDER BY sort_order ASC`;
  const { rows } = await pool.query(query, [serviceId]);
  return rows;
}

export async function addServiceArmorSet(serviceId, armorSet) {
  const query = `
    INSERT INTO service_armor_sets (service_id, armor_set_id, set_name, pieces, notes, sort_order)
    VALUES ($1, $2, $3, $4, $5, $6)
    RETURNING *
  `;
  const values = [
    serviceId,
    armorSet.armor_set_id || null,
    armorSet.set_name || null,
    armorSet.pieces ? JSON.stringify(armorSet.pieces) : null,
    armorSet.notes || null,
    armorSet.sort_order || 0
  ];
  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function updateServiceArmorSet(armorSetId, armorSet) {
  const query = `
    UPDATE service_armor_sets SET
      armor_set_id = $2,
      set_name = $3,
      pieces = $4,
      notes = $5,
      sort_order = $6
    WHERE id = $1
    RETURNING *
  `;
  const values = [
    armorSetId,
    armorSet.armor_set_id || null,
    armorSet.set_name || null,
    armorSet.pieces ? JSON.stringify(armorSet.pieces) : null,
    armorSet.notes || null,
    armorSet.sort_order || 0
  ];
  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function deleteServiceArmorSet(armorSetId) {
  await pool.query('DELETE FROM service_armor_sets WHERE id = $1', [armorSetId]);
  return true;
}

// Service availability
export async function getServiceAvailability(serviceId) {
  const query = `
    SELECT * FROM service_availability
    WHERE service_id = $1
    ORDER BY day_of_week, start_time
  `;
  const { rows } = await pool.query(query, [serviceId]);
  return rows;
}

export async function setServiceAvailability(serviceId, slots) {
  console.log('[SAVE] Starting setServiceAvailability for service', serviceId, 'with', slots.length, 'slots');
  const client = await startTransaction();
  console.log('[SAVE] Transaction started');
  
  try {
    // Delete existing availability
    console.log('[SAVE] Deleting existing availability');
    await client.query('DELETE FROM service_availability WHERE service_id = $1', [serviceId]);
    console.log('[SAVE] Delete complete');

    // Batch insert new slots
    if (slots.length > 0) {
      console.log('[SAVE] Deduplicating slots');
      // Deduplicate slots by unique key (day_of_week, start_time)
      const uniqueSlots = [];
      const seen = new Set();
      
      for (const slot of slots) {
        const key = `${slot.day_of_week}-${slot.start_time}`;
        if (!seen.has(key)) {
          seen.add(key);
          uniqueSlots.push(slot);
        }
      }
      
      console.log('[SAVE] Building batch insert for', uniqueSlots.length, 'unique slots');
      // Build VALUES clause with proper parameter indexing
      const values = [];
      const valueStrings = [];
      let paramIndex = 1;
      
      for (const slot of uniqueSlots) {
        valueStrings.push(`($${paramIndex}, $${paramIndex + 1}, $${paramIndex + 2}, $${paramIndex + 3}, $${paramIndex + 4})`);
        values.push(
          serviceId,
          slot.day_of_week,
          slot.start_time,
          slot.end_time,
          slot.is_available !== false
        );
        paramIndex += 5;
      }
      
      const batchQuery = `
        INSERT INTO service_availability (service_id, day_of_week, start_time, end_time, is_available)
        VALUES ${valueStrings.join(', ')}
      `;
      
      console.log('[SAVE] Executing batch insert');
      await client.query(batchQuery, values);
      console.log('[SAVE] Batch insert complete');
    }

    // Fetch the data BEFORE committing (within same transaction to avoid lock issues)
    console.log('[SAVE] Fetching updated availability');
    const query = `
      SELECT * FROM service_availability
      WHERE service_id = $1
      ORDER BY day_of_week, start_time
    `;
    const { rows } = await client.query(query, [serviceId]);
    console.log('[SAVE] Fetched', rows.length, 'rows');

    console.log('[SAVE] Committing transaction');
    await commitTransaction(client);
    console.log('[SAVE] Transaction committed, returning data');
    
    return rows;
  } catch (error) {
    console.error('[SAVE] Error occurred, rolling back');
    await rollbackTransaction(client);
    console.error('[SAVE] Error setting service availability:', error);
    throw error;
  }
}

// Service requests
export async function getServiceRequests(serviceId, status = null) {
  let query = `
    SELECT
      sr.*,
      u.eu_name as requester_name
    FROM service_requests sr
    JOIN users u ON sr.requester_id = u.id
    WHERE sr.service_id = $1
  `;
  const values = [serviceId];

  if (status) {
    query += ' AND sr.status = $2';
    values.push(status);
  }

  query += ' ORDER BY sr.created_at DESC';

  const { rows } = await pool.query(query, values);
  return rows;
}

export async function getUserServiceRequests(userId) {
  const query = `
    SELECT
      sr.*,
      s.title as service_title,
      s.type as service_type,
      owner.eu_name as provider_name
    FROM service_requests sr
    JOIN services s ON sr.service_id = s.id
    JOIN users owner ON s.user_id = owner.id
    WHERE sr.requester_id = $1
    ORDER BY sr.created_at DESC
  `;
  const { rows } = await pool.query(query, [userId]);
  return rows;
}

export async function getServiceRequestById(requestId) {
  const query = `
    SELECT
      sr.*,
      u.eu_name as requester_name,
      s.title as service_title,
      s.type as service_type,
      s.user_id as provider_id,
      owner.eu_name as provider_name
    FROM service_requests sr
    JOIN users u ON sr.requester_id = u.id
    JOIN services s ON sr.service_id = s.id
    JOIN users owner ON s.user_id = owner.id
    WHERE sr.id = $1
  `;
  const { rows } = await pool.query(query, [requestId]);
  return rows[0];
}

// Get user's active requests for a specific service (non-terminal statuses)
// Excludes questions (service_notes starting with [QUESTION]) as they shouldn't block new requests
export async function getUserActiveRequestsForService(userId, serviceId) {
  const query = `
    SELECT *
    FROM service_requests
    WHERE requester_id = $1
      AND service_id = $2
      AND status NOT IN ('completed', 'cancelled', 'declined', 'aborted')
      AND (service_notes IS NULL OR service_notes NOT LIKE '[QUESTION]%')
    ORDER BY created_at DESC
  `;
  const { rows } = await pool.query(query, [userId, serviceId]);
  return rows;
}

export async function createServiceRequest(requestData) {
  const query = `
    INSERT INTO service_requests (
      service_id, requester_id, status, service_notes
    ) VALUES ($1, $2, $3, $4)
    RETURNING *
  `;
  const values = [
    requestData.service_id,
    requestData.requester_id,
    requestData.status || 'pending',
    requestData.service_notes || null
  ];

  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function updateServiceRequest(requestId, data) {
  const setClauses = [];
  const values = [requestId];
  let paramIndex = 2;

  // Only fields remaining after migration: status, service_notes, discord_thread_id
  const allowedFields = ['status', 'service_notes', 'discord_thread_id'];

  for (const field of allowedFields) {
    if (data[field] !== undefined) {
      setClauses.push(`${field} = $${paramIndex}`);
      values.push(data[field]);
      paramIndex++;
    }
  }

  if (setClauses.length === 0) return null;

  setClauses.push('updated_at = CURRENT_TIMESTAMP');

  const query = `UPDATE service_requests SET ${setClauses.join(', ')} WHERE id = $1 RETURNING *`;
  const { rows } = await pool.query(query, values);
  return rows[0];
}

// Note: getServiceReviewStats removed - review_score column dropped in migration 010

// ============================================
// PROVIDER REQUEST MANAGEMENT
// ============================================

// Get all incoming requests for a provider's services
export async function getProviderIncomingRequests(userId, filters = {}) {
  let query = `
    SELECT
      sr.*,
      u.eu_name as requester_name,
      s.title as service_title,
      s.type as service_type
    FROM service_requests sr
    JOIN users u ON sr.requester_id = u.id
    JOIN services s ON sr.service_id = s.id
    WHERE s.user_id = $1
  `;
  const values = [userId];
  let paramIndex = 2;

  if (filters.status) {
    query += ` AND sr.status = $${paramIndex}`;
    values.push(filters.status);
    paramIndex++;
  }

  if (filters.serviceId) {
    query += ` AND sr.service_id = $${paramIndex}`;
    values.push(filters.serviceId);
    paramIndex++;
  }

  query += ' ORDER BY sr.created_at DESC';

  const { rows } = await pool.query(query, values);
  return rows;
}

// Get user's outgoing requests (requests they made to others)
export async function getUserOutgoingRequests(userId, filters = {}) {
  let query = `
    SELECT
      sr.*,
      s.title as service_title,
      s.type as service_type,
      owner.eu_name as provider_name
    FROM service_requests sr
    JOIN services s ON sr.service_id = s.id
    JOIN users owner ON s.user_id = owner.id
    WHERE sr.requester_id = $1
  `;
  const values = [userId];
  let paramIndex = 2;

  if (filters.status) {
    query += ` AND sr.status = $${paramIndex}`;
    values.push(filters.status);
    paramIndex++;
  }

  query += ' ORDER BY sr.created_at DESC';

  const { rows } = await pool.query(query, values);
  return rows;
}

// Get request with full context (for both provider and customer views)
export async function getRequestWithContext(requestId) {
  const query = `
    SELECT
      sr.*,
      u.eu_name as requester_name,
      s.title as service_title,
      s.type as service_type,
      s.user_id as provider_id,
      owner.eu_name as provider_name
    FROM service_requests sr
    JOIN users u ON sr.requester_id = u.id
    JOIN services s ON sr.service_id = s.id
    JOIN users owner ON s.user_id = owner.id
    WHERE sr.id = $1
  `;
  const { rows } = await pool.query(query, [requestId]);
  return rows[0];
}

// Update request status with validation (simplified for questions only)
export async function updateRequestStatus(requestId, newStatus, additionalData = {}) {
  const setClauses = ['status = $2', 'updated_at = CURRENT_TIMESTAMP'];
  const values = [requestId, newStatus];
  let paramIndex = 3;

  // Only fields remaining after migration: service_notes, discord_thread_id
  const allowedFields = ['service_notes', 'discord_thread_id'];

  for (const field of allowedFields) {
    if (additionalData[field] !== undefined) {
      setClauses.push(`${field} = $${paramIndex}`);
      values.push(additionalData[field]);
      paramIndex++;
    }
  }

  const query = `UPDATE service_requests SET ${setClauses.join(', ')} WHERE id = $1 RETURNING *`;
  const { rows } = await pool.query(query, values);
  return rows[0];
}

// ============================================
// TICKET FUNCTIONS
// ============================================

// Get tickets owned by user
export async function getUserOwnedTickets(userId, includeExpired = false, recentExpiredOnly = false) {
  let query = `
    SELECT
      st.*,
      sto.name as offer_name,
      sto.uses_count as offer_uses,
      sto.validity_days,
      s.id as service_id,
      s.title as service_title,
      s.type as service_type
    FROM service_tickets st
    JOIN service_ticket_offers sto ON st.offer_id = sto.id
    JOIN services s ON sto.service_id = s.id
    WHERE st.user_id = $1
  `;

  if (recentExpiredOnly) {
    // Get most recent expired ticket per service
    query = `
      WITH ranked_expired AS (
        SELECT
          st.*,
          sto.name as offer_name,
          sto.uses_count as offer_uses,
          sto.validity_days,
          s.id as service_id,
          s.title as service_title,
          s.type as service_type,
          ROW_NUMBER() OVER (PARTITION BY s.id ORDER BY st.valid_until DESC) as rn
        FROM service_tickets st
        JOIN service_ticket_offers sto ON st.offer_id = sto.id
        JOIN services s ON sto.service_id = s.id
        WHERE st.user_id = $1
          AND (st.status = 'expired' OR (st.valid_until IS NOT NULL AND st.valid_until < CURRENT_DATE))
      )
      SELECT * FROM ranked_expired WHERE rn = 1 ORDER BY created_at DESC
    `;
  } else {
    if (!includeExpired) {
      query += ` AND st.status = 'active' AND (st.valid_until IS NULL OR st.valid_until >= CURRENT_DATE)`;
    }
    query += ' ORDER BY st.created_at DESC';
  }

  const { rows } = await pool.query(query, [userId]);
  return rows;
}

// Get tickets issued by provider's transportation services
export async function getProviderIssuedTickets(userId, includeExpired = true) {
  let query = `
    SELECT
      st.*,
      sto.name as offer_name,
      sto.uses_count as offer_uses,
      sto.validity_days,
      buyer.eu_name as buyer_name,
      s.id as service_id,
      s.title as service_title
    FROM service_tickets st
    JOIN service_ticket_offers sto ON st.offer_id = sto.id
    JOIN services s ON sto.service_id = s.id
    JOIN users buyer ON st.user_id = buyer.id
    WHERE s.user_id = $1
  `;

  if (!includeExpired) {
    query += ` AND st.status = 'active' AND (st.valid_until IS NULL OR st.valid_until >= CURRENT_DATE)`;
  }

  query += ' ORDER BY st.created_at DESC';

  const { rows } = await pool.query(query, [userId]);
  return rows;
}

// Get recently expired issued tickets (most recent per service per user) for provider
export async function getProviderExpiredIssuedTickets(userId) {
  const query = `
    SELECT DISTINCT ON (sto.service_id, st.user_id)
      st.*,
      sto.name as offer_name,
      sto.uses_count as offer_uses,
      sto.validity_days,
      buyer.eu_name as buyer_name,
      s.id as service_id,
      s.title as service_title
    FROM service_tickets st
    JOIN service_ticket_offers sto ON st.offer_id = sto.id
    JOIN services s ON sto.service_id = s.id
    JOIN users buyer ON st.user_id = buyer.id
    WHERE s.user_id = $1
      AND (st.status = 'expired' OR st.status = 'used' OR (st.valid_until IS NOT NULL AND st.valid_until < CURRENT_DATE))
    ORDER BY sto.service_id, st.user_id, st.created_at DESC
  `;

  const { rows } = await pool.query(query, [userId]);
  return rows;
}

// ============================================
// AVAILABILITY SYNC
// ============================================

// Copy availability from one service to multiple others
export async function syncServiceAvailability(sourceServiceId, targetServiceIds, userId) {
  const client = await startTransaction();

  try {
    // Verify ownership of all services
    const ownershipCheck = await client.query(
      'SELECT id FROM services WHERE id = ANY($1) AND user_id = $2',
      [[sourceServiceId, ...targetServiceIds], userId]
    );

    if (ownershipCheck.rows.length !== targetServiceIds.length + 1) {
      throw new Error('You can only sync availability for your own services');
    }

    // Get source availability
    const sourceAvailability = await client.query(
      'SELECT day_of_week, start_time, end_time, is_available FROM service_availability WHERE service_id = $1',
      [sourceServiceId]
    );

    // Delete existing availability for target services
    await client.query(
      'DELETE FROM service_availability WHERE service_id = ANY($1)',
      [targetServiceIds]
    );

    // Copy availability to each target service
    for (const targetId of targetServiceIds) {
      for (const slot of sourceAvailability.rows) {
        await client.query(
          'INSERT INTO service_availability (service_id, day_of_week, start_time, end_time, is_available) VALUES ($1, $2, $3, $4, $5)',
          [targetId, slot.day_of_week, slot.start_time, slot.end_time, slot.is_available]
        );
      }
    }

    await commitTransaction(client);
    return true;
  } catch (error) {
    await rollbackTransaction(client);
    throw error;
  }
}

// Soft delete service (set deleted_at)
export async function softDeleteService(serviceId) {
  const query = `UPDATE services SET deleted_at = CURRENT_TIMESTAMP, is_active = false, updated_at = CURRENT_TIMESTAMP WHERE id = $1`;
  await pool.query(query, [serviceId]);
  return true;
}

// =============================================
// SERVICE TICKET OFFERS (Service-Level Tickets)
// =============================================

export async function getServiceTicketOffers(serviceId) {
  const query = `
    SELECT * FROM service_ticket_offers
    WHERE service_id = $1 AND is_active = true
    ORDER BY sort_order ASC, created_at ASC
  `;
  const result = await pool.query(query, [serviceId]);
  return result.rows;
}

export async function getTicketOfferById(offerId) {
  const query = `SELECT * FROM service_ticket_offers WHERE id = $1`;
  const result = await pool.query(query, [offerId]);
  return result.rows[0] || null;
}

export async function createTicketOffer(serviceId, offerData) {
  const query = `
    INSERT INTO service_ticket_offers (
      service_id, name, uses_count, validity_days, price,
      waives_pickup_fee, description, sort_order, is_active
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, true)
    RETURNING *
  `;
  const values = [
    serviceId,
    offerData.name,
    offerData.uses_count || null,
    offerData.validity_days || null,
    offerData.price,
    offerData.waives_pickup_fee || false,
    offerData.description || null,
    offerData.sort_order || 0
  ];
  const result = await pool.query(query, values);
  return result.rows[0];
}

export async function updateTicketOffer(offerId, offerData) {
  const query = `
    UPDATE service_ticket_offers SET
      name = COALESCE($2, name),
      uses_count = $3,
      validity_days = $4,
      price = COALESCE($5, price),
      waives_pickup_fee = COALESCE($6, waives_pickup_fee),
      description = $7,
      sort_order = COALESCE($8, sort_order)
    WHERE id = $1
    RETURNING *
  `;
  const values = [
    offerId,
    offerData.name,
    offerData.uses_count !== undefined ? offerData.uses_count : null,
    offerData.validity_days !== undefined ? offerData.validity_days : null,
    offerData.price,
    offerData.waives_pickup_fee,
    offerData.description !== undefined ? offerData.description : null,
    offerData.sort_order
  ];
  const result = await pool.query(query, values);
  return result.rows[0];
}

export async function deleteTicketOffer(offerId) {
  // Soft delete by setting is_active = false
  const query = `UPDATE service_ticket_offers SET is_active = false WHERE id = $1`;
  await pool.query(query, [offerId]);
  return true;
}

// =============================================
// SERVICE TICKETS (User-Purchased Tickets)
// =============================================

export async function getUserTickets(userId, includeExpired = false) {
  let query = `
    SELECT st.*, sto.name as offer_name, sto.service_id,
           s.title as service_title, s.type as service_type,
           u.username as provider_name
    FROM service_tickets st
    JOIN service_ticket_offers sto ON st.offer_id = sto.id
    JOIN services s ON sto.service_id = s.id
    JOIN users u ON s.user_id = u.id
    WHERE st.user_id = $1
  `;
  if (!includeExpired) {
    query += ` AND (st.status NOT IN ('used', 'expired', 'cancelled') OR (st.status = 'active' AND st.uses_remaining > 0))`;
  }
  query += ` ORDER BY st.created_at DESC`;
  const result = await pool.query(query, [userId]);
  return result.rows;
}

export async function getTicketById(ticketId) {
  const query = `
    SELECT st.*, sto.name as offer_name, sto.service_id, sto.waives_pickup_fee,
           s.title as service_title, s.type as service_type,
           u.username as provider_name, u.id as provider_id
    FROM service_tickets st
    JOIN service_ticket_offers sto ON st.offer_id = sto.id
    JOIN services s ON sto.service_id = s.id
    JOIN users u ON s.user_id = u.id
    WHERE st.id = $1
  `;
  const result = await pool.query(query, [ticketId]);
  return result.rows[0] || null;
}

export async function getUserTicketsForService(userId, serviceId) {
  const query = `
    SELECT st.*, sto.name as offer_name, sto.service_id, sto.waives_pickup_fee
    FROM service_tickets st
    JOIN service_ticket_offers sto ON st.offer_id = sto.id
    WHERE st.user_id = $1 AND sto.service_id = $2
    ORDER BY st.created_at DESC
  `;
  const result = await pool.query(query, [userId, serviceId]);
  return result.rows;
}

export async function createTicket(ticketData) {
  const query = `
    INSERT INTO service_tickets (
      offer_id, user_id, uses_total, uses_remaining, valid_until, price_paid, status
    )
    VALUES ($1, $2, $3, $4, $5, $6, 'pending')
    RETURNING *
  `;
  const values = [
    ticketData.offer_id,
    ticketData.user_id,
    ticketData.uses_total,
    ticketData.uses_total, // uses_remaining starts equal to uses_total
    ticketData.valid_until || null,
    ticketData.price_paid
  ];
  const result = await pool.query(query, values);
  return result.rows[0];
}

export async function activateTicket(ticketId) {
  const query = `
    UPDATE service_tickets SET
      status = 'active',
      activated_at = CURRENT_TIMESTAMP
    WHERE id = $1 AND status = 'pending'
    RETURNING *
  `;
  const result = await pool.query(query, [ticketId]);
  return result.rows[0];
}

export async function extendTicketUses(ticketId, additionalUses) {
  const query = `
    UPDATE service_tickets SET
      uses_total = uses_total + $2,
      uses_remaining = uses_remaining + $2,
      status = CASE
        WHEN status = 'used' THEN 'active'
        ELSE status
      END
    WHERE id = $1
    RETURNING *
  `;
  const result = await pool.query(query, [ticketId, additionalUses]);
  return result.rows[0];
}

export async function extendTicketValidity(ticketId, additionalDays) {
  const query = `
    UPDATE service_tickets SET
      valid_until = CASE
        WHEN valid_until IS NULL THEN CURRENT_DATE + $2 * INTERVAL '1 day'
        WHEN valid_until < CURRENT_DATE THEN CURRENT_DATE + $2 * INTERVAL '1 day'
        ELSE valid_until + $2 * INTERVAL '1 day'
      END,
      status = CASE
        WHEN status = 'expired' THEN 'active'
        ELSE status
      END
    WHERE id = $1
    RETURNING *
  `;
  const result = await pool.query(query, [ticketId, additionalDays]);
  return result.rows[0];
}

export async function reactivateExpiredTicket(ticketId, validityDays, additionalUses = 0) {
  const query = `
    UPDATE service_tickets SET
      valid_until = CURRENT_DATE + $2 * INTERVAL '1 day',
      uses_remaining = uses_remaining + $3,
      uses_total = CASE
        WHEN $3 > 0 THEN uses_total + $3
        ELSE uses_total
      END,
      status = 'active'
    WHERE id = $1
    RETURNING *
  `;
  const result = await pool.query(query, [ticketId, validityDays, additionalUses]);
  return result.rows[0];
}

export async function useTicket(ticketId, usageData = {}) {
  const client = await startTransaction();
  try {
    // Decrement uses_remaining
    const updateQuery = `
      UPDATE service_tickets SET
        uses_remaining = uses_remaining - 1,
        status = CASE WHEN uses_remaining - 1 <= 0 THEN 'used' ELSE status END
      WHERE id = $1 AND status = 'active' AND uses_remaining > 0
      RETURNING *
    `;
    const updateResult = await client.query(updateQuery, [ticketId]);
    if (updateResult.rows.length === 0) {
      throw new Error('Ticket not found, not active, or no uses remaining');
    }

    // Log the usage
    const usageQuery = `
      INSERT INTO service_ticket_usage (ticket_id, departure_date, notes)
      VALUES ($1, $2, $3)
      RETURNING *
    `;
    await client.query(usageQuery, [
      ticketId,
      usageData.departure_date || new Date().toISOString().split('T')[0],
      usageData.notes || null
    ]);

    await commitTransaction(client);
    return updateResult.rows[0];
  } catch (error) {
    await rollbackTransaction(client);
    throw error;
  }
}

export async function cancelTicket(ticketId) {
  const query = `
    UPDATE service_tickets SET status = 'cancelled'
    WHERE id = $1
    RETURNING *
  `;
  const result = await pool.query(query, [ticketId]);
  return result.rows[0];
}

export async function getTicketUsageHistory(ticketId) {
  const query = `
    SELECT * FROM service_ticket_usage
    WHERE ticket_id = $1
    ORDER BY used_at DESC
  `;
  const result = await pool.query(query, [ticketId]);
  return result.rows;
}

// Log ticket usage without decrementing (use was already reserved at check-in time)
export async function logTicketUsage(ticketId, usageData = {}) {
  const query = `
    INSERT INTO service_ticket_usage (ticket_id, departure_date, notes)
    VALUES ($1, $2, $3)
    RETURNING *
  `;
  const result = await pool.query(query, [
    ticketId,
    usageData.departure_date || new Date().toISOString().split('T')[0],
    usageData.notes || null
  ]);
  return result.rows[0];
}

export async function expireTickets() {
  // Called periodically to expire tickets past their valid_until date
  const query = `
    UPDATE service_tickets SET status = 'expired'
    WHERE status = 'active' AND valid_until IS NOT NULL AND valid_until < CURRENT_DATE
    RETURNING id
  `;
  const result = await pool.query(query);
  return result.rows.length;
}

export async function getServiceTicketStats(serviceId) {
  const query = `
    SELECT
      COUNT(*) FILTER (WHERE st.status = 'pending') as pending_count,
      COUNT(*) FILTER (WHERE st.status = 'active') as active_count,
      COUNT(*) FILTER (WHERE st.status = 'used') as used_count,
      SUM(st.price_paid) FILTER (WHERE st.status IN ('active', 'used')) as total_revenue
    FROM service_tickets st
    JOIN service_ticket_offers sto ON st.offer_id = sto.id
    WHERE sto.service_id = $1
  `;
  const result = await pool.query(query, [serviceId]);
  return result.rows[0];
}

// =============================================
// TRANSPORT REQUEST DETAILS
// =============================================
// Note: createTransportRequestDetails and getTransportRequestDetails removed
// service_transport_request_details table dropped in migration 010
// Transportation now uses tickets + check-ins + flights directly

export async function updateProviderLocation(serviceId, planetId) {
  const query = `
    UPDATE service_transportation_details
    SET current_planet_id = $2
    WHERE service_id = $1
    RETURNING *
  `;
  const result = await pool.query(query, [serviceId, planetId]);
  return result.rows[0];
}

// =============================================
// FLIGHT INSTANCES
// =============================================

export async function createFlightInstance(flightData) {
  const query = `
    INSERT INTO service_flight_instances (
      schedule_id, service_id, scheduled_departure, status,
      route_type, route_stops, auto_cancel_at
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7)
    RETURNING *
  `;
  const values = [
    flightData.schedule_id || null,
    flightData.service_id,
    flightData.scheduled_departure,
    flightData.status || 'scheduled',
    flightData.route_type || 'fixed',
    JSON.stringify(flightData.route_stops),
    flightData.auto_cancel_at || null
  ];
  const result = await pool.query(query, values);
  return result.rows[0];
}

export async function getFlightInstance(flightId) {
  const query = `SELECT * FROM service_flight_instances WHERE id = $1`;
  const result = await pool.query(query, [flightId]);
  return result.rows[0] || null;
}

export async function getServiceFlights(serviceId, includeCompleted = false) {
  let query = `
    SELECT * FROM service_flight_instances
    WHERE service_id = $1
  `;
  if (!includeCompleted) {
    query += ` AND status NOT IN ('completed', 'cancelled')`;
  }
  query += ` ORDER BY scheduled_departure ASC`;
  const result = await pool.query(query, [serviceId]);
  return result.rows;
}

export async function getUpcomingServiceFlights(serviceId, daysAhead = 7) {
  const query = `
    SELECT sfi.*
    FROM service_flight_instances sfi
    WHERE service_id = $1
      AND (
        -- Always include running/boarding flights regardless of scheduled time
        status IN ('running', 'boarding')
        OR
        -- Include scheduled flights that haven't passed yet
        (status = 'scheduled' AND scheduled_departure >= NOW())
        OR
        -- Include cancelled flights within 2h grace period for restore
        (status = 'cancelled' AND scheduled_departure + INTERVAL '2 hours' >= NOW())
      )
      AND scheduled_departure <= NOW() + INTERVAL '${daysAhead} days'
    ORDER BY
      CASE
        WHEN status = 'running' THEN 0
        WHEN status = 'boarding' THEN 1
        WHEN status = 'scheduled' THEN 2
        WHEN status = 'cancelled' THEN 3
        ELSE 4
      END,
      scheduled_departure ASC
  `;
  const result = await pool.query(query, [serviceId]);
  return result.rows;
}

export async function updateFlightInstance(flightId, data) {
  const setClauses = [];
  const values = [flightId];
  let paramIndex = 2;

  const allowedFields = [
    'status', 'scheduled_departure', 'actual_departure', 'current_stop_index',
    'current_state', 'route_stops', 'auto_cancel_at',
    'discord_thread_id', 'completed_at'
  ];

  for (const field of allowedFields) {
    if (data[field] !== undefined) {
      setClauses.push(`${field} = $${paramIndex}`);
      values.push(field === 'route_stops' ? JSON.stringify(data[field]) : data[field]);
      paramIndex++;
    }
  }

  if (setClauses.length === 0) return null;

  setClauses.push(`updated_at = CURRENT_TIMESTAMP`);

  const query = `UPDATE service_flight_instances SET ${setClauses.join(', ')} WHERE id = $1 RETURNING *`;
  const result = await pool.query(query, values);
  return result.rows[0];
}

export async function logFlightStateChange(flightId, previousState, newState, stopIndex = null) {
  const query = `
    INSERT INTO service_flight_state_log (flight_id, previous_state, new_state, stop_index)
    VALUES ($1, $2, $3, $4)
    RETURNING *
  `;
  const result = await pool.query(query, [flightId, previousState, newState, stopIndex]);
  return result.rows[0];
}

export async function getFlightStateLog(flightId) {
  const query = `
    SELECT * FROM service_flight_state_log
    WHERE flight_id = $1
    ORDER BY changed_at DESC
  `;
  const result = await pool.query(query, [flightId]);
  return result.rows;
}

export async function undoFlightStateChange(logId) {
  const query = `
    UPDATE service_flight_state_log
    SET undone = true
    WHERE id = $1 AND can_undo = true AND undone = false
    RETURNING *
  `;
  const result = await pool.query(query, [logId]);
  return result.rows[0];
}

// =============================================
// CHECK-INS
// =============================================

export async function createCheckin(checkinData) {
  const query = `
    INSERT INTO service_checkins (
      flight_id, request_id, ticket_id, user_id,
      join_location, join_planet_id, exit_location, exit_planet_id, status
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending')
    RETURNING *
  `;
  const values = [
    checkinData.flight_id || null,
    checkinData.request_id || null,
    checkinData.ticket_id,
    checkinData.user_id,
    checkinData.join_location || null,
    checkinData.join_planet_id || null,
    checkinData.exit_location || null,
    checkinData.exit_planet_id || null
  ];
  const result = await pool.query(query, values);
  return result.rows[0];
}

export async function getExistingCheckin(flightId, userId) {
  const query = `
    SELECT * FROM service_checkins
    WHERE flight_id = $1 AND user_id = $2 AND status NOT IN ('denied', 'cancelled')
  `;
  const result = await pool.query(query, [flightId, userId]);
  return result.rows[0];
}

// Transactional check-in creation - reserves ticket use and creates check-in atomically
export async function createCheckinWithTransaction(ticketId, checkinData) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    // Reserve ticket use
    const reserveQuery = `
      UPDATE service_tickets
      SET uses_remaining = uses_remaining - 1
      WHERE id = $1 AND uses_remaining > 0
      RETURNING *
    `;
    const reserveResult = await client.query(reserveQuery, [ticketId]);
    if (reserveResult.rows.length === 0) {
      throw new Error('Failed to reserve ticket use - no uses remaining');
    }
    const updatedTicket = reserveResult.rows[0];

    // Create check-in
    const checkinQuery = `
      INSERT INTO service_checkins (
        flight_id, request_id, ticket_id, user_id,
        join_location, join_planet_id, exit_location, exit_planet_id, status
      )
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending')
      RETURNING *
    `;
    const checkinValues = [
      checkinData.flight_id || null,
      checkinData.request_id || null,
      ticketId,
      checkinData.user_id,
      checkinData.join_location || null,
      checkinData.join_planet_id || null,
      checkinData.exit_location || null,
      checkinData.exit_planet_id || null
    ];
    const checkinResult = await client.query(checkinQuery, checkinValues);

    await client.query('COMMIT');
    return {
      checkin: checkinResult.rows[0],
      ticket: updatedTicket
    };
  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  } finally {
    client.release();
  }
}

export async function reserveTicketUse(ticketId) {
  const query = `
    UPDATE service_tickets
    SET uses_remaining = uses_remaining - 1
    WHERE id = $1 AND uses_remaining > 0
    RETURNING *
  `;
  const result = await pool.query(query, [ticketId]);
  return result.rows[0];
}

export async function restoreTicketUse(ticketId) {
  const query = `
    UPDATE service_tickets
    SET uses_remaining = uses_remaining + 1,
        status = CASE WHEN status = 'used' THEN 'active' ELSE status END
    WHERE id = $1
    RETURNING *
  `;
  const result = await pool.query(query, [ticketId]);
  return result.rows[0];
}

export async function getFlightCheckins(flightId) {
  const query = `
    SELECT c.*, u.username as user_name, st.status as ticket_status,
           sto.name as offer_name,
           pj."Name" as join_planet_name,
           pe."Name" as exit_planet_name
    FROM service_checkins c
    JOIN users u ON c.user_id = u.id
    JOIN service_tickets st ON c.ticket_id = st.id
    JOIN service_ticket_offers sto ON st.offer_id = sto.id
    LEFT JOIN "Planets" pj ON c.join_planet_id = pj."Id"
    LEFT JOIN "Planets" pe ON c.exit_planet_id = pe."Id"
    WHERE c.flight_id = $1
    ORDER BY c.checked_in_at ASC
  `;
  const result = await pool.query(query, [flightId]);
  return result.rows;
}

export async function getUserCheckinForFlight(userId, flightId) {
  const query = `
    SELECT c.*, st.id as ticket_id, st.uses_remaining
    FROM service_checkins c
    JOIN service_tickets st ON c.ticket_id = st.id
    WHERE c.user_id = $1 AND c.flight_id = $2 AND c.status != 'cancelled'
    ORDER BY c.checked_in_at DESC
    LIMIT 1
  `;
  const result = await pool.query(query, [userId, flightId]);
  return result.rows[0] || null;
}

export async function cancelCheckin(checkinId) {
  const query = `
    UPDATE service_checkins
    SET status = 'cancelled'
    WHERE id = $1
    RETURNING *
  `;
  const result = await pool.query(query, [checkinId]);
  return result.rows[0];
}

// Restore a ticket use for a cancelled check-in
export async function restoreTicketUseForCheckin(checkinId) {
  const query = `
    UPDATE service_tickets st
    SET uses_remaining = uses_remaining + 1,
        status = CASE
          WHEN status = 'used' AND uses_remaining + 1 < uses_total THEN 'active'
          WHEN status = 'used' AND uses_remaining + 1 = uses_total THEN 'active'
          ELSE status
        END
    FROM service_checkins c
    WHERE c.id = $1
      AND c.ticket_id = st.id
      AND c.status = 'accepted'
    RETURNING st.*
  `;
  const result = await pool.query(query, [checkinId]);
  return result.rows[0] || null;
}

export async function updateCheckin(checkinId, data) {
  const setClauses = [];
  const values = [checkinId];
  let paramIndex = 2;

  const allowedFields = ['status', 'accepted_at', 'denial_reason', 'exit_location', 'exit_planet_id'];

  for (const field of allowedFields) {
    if (data[field] !== undefined) {
      setClauses.push(`${field} = $${paramIndex}`);
      values.push(data[field]);
      paramIndex++;
    }
  }

  if (setClauses.length === 0) return null;

  const query = `UPDATE service_checkins SET ${setClauses.join(', ')} WHERE id = $1 RETURNING *`;
  const result = await pool.query(query, values);
  return result.rows[0];
}

export async function refundCheckin(checkinId) {
  const query = `
    UPDATE service_checkins
    SET status = 'refunded'
    WHERE id = $1
    RETURNING *
  `;
  const result = await pool.query(query, [checkinId]);
  return result.rows[0];
}

export async function getRequestCheckins(requestId) {
  const query = `
    SELECT c.*, u.username as user_name, st.status as ticket_status,
           sto.name as offer_name
    FROM service_checkins c
    JOIN users u ON c.user_id = u.id
    JOIN service_tickets st ON c.ticket_id = st.id
    JOIN service_ticket_offers sto ON st.offer_id = sto.id
    WHERE c.request_id = $1
    ORDER BY c.checked_in_at ASC
  `;
  const result = await pool.query(query, [requestId]);
  return result.rows;
}

export async function updateCheckinStatus(checkinId, status) {
  const query = `
    UPDATE service_checkins SET
      status = $2,
      accepted_at = CASE WHEN $2 = 'accepted' THEN CURRENT_TIMESTAMP ELSE accepted_at END
    WHERE id = $1
    RETURNING *
  `;
  const result = await pool.query(query, [checkinId, status]);
  return result.rows[0];
}

export async function getCheckinById(checkinId) {
  const query = `
    SELECT c.*, u.username as user_name
    FROM service_checkins c
    JOIN users u ON c.user_id = u.id
    WHERE c.id = $1
  `;
  const result = await pool.query(query, [checkinId]);
  return result.rows[0] || null;
}

// Cancel all check-ins for a flight and return the affected user IDs
export async function cancelAllFlightCheckins(flightId) {
  const query = `
    UPDATE service_checkins
    SET status = 'cancelled'
    WHERE flight_id = $1 AND status IN ('pending', 'accepted')
    RETURNING user_id
  `;
  const result = await pool.query(query, [flightId]);
  return result.rows.map(row => row.user_id);
}

// Create a flight reschedule notification
export async function createRescheduleNotification(userId, flightId, oldDeparture, newDeparture, serviceTitle) {
  const query = `
    INSERT INTO flight_reschedule_notifications
    (user_id, flight_id, old_departure, new_departure, service_title)
    VALUES ($1, $2, $3, $4, $5)
    RETURNING *
  `;
  const result = await pool.query(query, [userId, flightId, oldDeparture, newDeparture, serviceTitle]);
  return result.rows[0];
}

// Get active flights for a service (excluding cancelled/completed)
export async function getActiveServiceFlights(serviceId, excludeFlightId = null) {
  let query = `
    SELECT * FROM service_flight_instances
    WHERE service_id = $1 AND status NOT IN ('completed', 'cancelled')
    ORDER BY scheduled_departure ASC
  `;
  const params = [serviceId];

  if (excludeFlightId) {
    query = `
      SELECT * FROM service_flight_instances
      WHERE service_id = $1 AND status NOT IN ('completed', 'cancelled') AND id != $2
      ORDER BY scheduled_departure ASC
    `;
    params.push(excludeFlightId);
  }

  const result = await pool.query(query, params);
  return result.rows;
}

// Restore ticket uses for cancelled check-ins
export async function restoreTicketUsesForFlight(flightId) {
  const query = `
    UPDATE service_tickets st
    SET uses_remaining = uses_remaining + 1,
        status = CASE
          WHEN st.status = 'used' AND uses_remaining + 1 < uses_total THEN 'active'
          WHEN st.status = 'used' AND uses_remaining + 1 = uses_total THEN 'active'
          ELSE st.status
        END
    FROM service_checkins c
    WHERE c.flight_id = $1
      AND c.ticket_id = st.id
      AND c.status IN ('accepted', 'pending')
    RETURNING st.*
  `;
  const result = await pool.query(query, [flightId]);
  return result.rows;
}

// Update current planet location for a transportation service
export async function updateServiceCurrentLocation(serviceId, planetId) {
  const query = `
    UPDATE service_transportation_details
    SET current_planet_id = $2
    WHERE service_id = $1
    RETURNING *
  `;
  const result = await pool.query(query, [serviceId, planetId]);
  return result.rows[0];
}

/* ==========================================
 * SERVICE PILOTS
 * ========================================== */

// Get all pilots for a service
export async function getServicePilots(serviceId) {
  const query = `
    SELECT
      sp.id,
      sp.service_id,
      sp.user_id,
      sp.added_by,
      sp.created_at,
      u.username,
      u.eu_name,
      adder.username as added_by_name
    FROM service_pilots sp
    JOIN users u ON sp.user_id = u.id
    LEFT JOIN users adder ON sp.added_by = adder.id
    WHERE sp.service_id = $1
    ORDER BY sp.created_at ASC
  `;
  const result = await pool.query(query, [serviceId]);
  return result.rows;
}

// Check if a user is a pilot for a service
export async function isServicePilot(serviceId, userId) {
  const query = `
    SELECT id FROM service_pilots
    WHERE service_id = $1 AND user_id = $2
  `;
  const result = await pool.query(query, [serviceId, userId]);
  return result.rows.length > 0;
}

// Check if a user can manage a service (owner or pilot)
export async function canManageService(serviceId, userId, isAdmin = false) {
  // Admins can manage everything
  if (isAdmin) return true;

  // Check if owner
  const service = await getServiceById(serviceId);
  if (service && service.user_id === userId) return true;

  // Check if pilot
  return await isServicePilot(serviceId, userId);
}

// Add a pilot to a service
export async function addServicePilot(serviceId, userId, addedBy) {
  const query = `
    INSERT INTO service_pilots (service_id, user_id, added_by)
    VALUES ($1, $2, $3)
    RETURNING *
  `;
  const result = await pool.query(query, [serviceId, userId, addedBy]);
  return result.rows[0];
}

// Remove a pilot from a service
export async function removeServicePilot(serviceId, userId) {
  const query = `
    DELETE FROM service_pilots
    WHERE service_id = $1 AND user_id = $2
    RETURNING *
  `;
  const result = await pool.query(query, [serviceId, userId]);
  return result.rows[0];
}

// Get all services a user is pilot for
export async function getUserPilotServices(userId) {
  const query = `
    SELECT
      sp.id as pilot_id,
      s.*,
      u.username as owner_name
    FROM service_pilots sp
    JOIN services s ON sp.service_id = s.id
    LEFT JOIN users u ON s.user_id = u.id
    WHERE sp.user_id = $1
    ORDER BY s.title ASC
  `;
  const result = await pool.query(query, [userId]);
  return result.rows;
}

// =============================================
// ADMIN USER MANAGEMENT
// =============================================

// Search users by username, global_name, or eu_name
export async function searchUsers(searchQuery, limit = 10) {
  const query = `
    SELECT id, username, global_name, eu_name, avatar, verified, administrator
    FROM users
    WHERE
      LOWER(username) LIKE LOWER($1)
      OR LOWER(global_name) LIKE LOWER($1)
      OR LOWER(eu_name) LIKE LOWER($1)
    ORDER BY
      CASE
        WHEN LOWER(eu_name) LIKE LOWER($1) THEN 1
        WHEN LOWER(global_name) LIKE LOWER($1) THEN 2
        ELSE 3
      END,
      global_name ASC
    LIMIT $2
  `;
  const searchPattern = `%${searchQuery}%`;
  const result = await pool.query(query, [searchPattern, limit]);
  return result.rows;
}

// List all users with pagination
export async function listUsers(page = 1, limit = 20, sortBy = 'global_name', sortOrder = 'ASC') {
  const offset = (page - 1) * limit;

  // Whitelist allowed sort columns
  const allowedSortColumns = ['global_name', 'username', 'eu_name', 'id', 'verified'];
  const sortColumn = allowedSortColumns.includes(sortBy) ? sortBy : 'global_name';
  const order = sortOrder.toUpperCase() === 'DESC' ? 'DESC' : 'ASC';

  const query = `
    SELECT id, username, global_name, eu_name, avatar, verified, administrator
    FROM users
    ORDER BY ${sortColumn} ${order} NULLS LAST
    LIMIT $1 OFFSET $2
  `;

  const countQuery = `SELECT COUNT(*) as total FROM users`;

  const [result, countResult] = await Promise.all([
    pool.query(query, [limit, offset]),
    pool.query(countQuery)
  ]);

  return {
    users: result.rows,
    total: parseInt(countResult.rows[0].total),
    page,
    limit,
    totalPages: Math.ceil(parseInt(countResult.rows[0].total) / limit)
  };
}

// Get full user details including lock/ban status
export async function getUserFullDetails(userId) {
  // Try full query with lock/ban columns first
  try {
    const query = `
      SELECT id, username, global_name, eu_name, avatar, verified, administrator,
             locked, locked_at, locked_reason, locked_by,
             banned, banned_at, banned_until, banned_reason, banned_by
      FROM users
      WHERE id = $1
    `;
    const result = await pool.query(query, [userId]);
    return result.rows[0] || null;
  } catch (err) {
    // Fallback if lock/ban columns don't exist yet (migration not run)
    if (err.code === '42703') { // undefined_column error
      const fallbackQuery = `
        SELECT id, username, global_name, eu_name, avatar, verified, administrator,
               false as locked, NULL as locked_at, NULL as locked_reason, NULL as locked_by,
               false as banned, NULL as banned_at, NULL as banned_until, NULL as banned_reason, NULL as banned_by
        FROM users
        WHERE id = $1
      `;
      const result = await pool.query(fallbackQuery, [userId]);
      return result.rows[0] || null;
    }
    throw err;
  }
}

// Lock a user
export async function lockUser(userId, adminId, reason) {
  const query = `
    UPDATE users
    SET locked = true, locked_at = NOW(), locked_reason = $2, locked_by = $3
    WHERE id = $1
    RETURNING *
  `;
  const result = await pool.query(query, [userId, reason, adminId]);

  // Log the action
  await logAdminAction(adminId, 'lock', 'user', String(userId), reason);

  return result.rows[0];
}

// Unlock a user
export async function unlockUser(userId, adminId) {
  const query = `
    UPDATE users
    SET locked = false, locked_at = NULL, locked_reason = NULL, locked_by = NULL
    WHERE id = $1
    RETURNING *
  `;
  const result = await pool.query(query, [userId]);

  // Log the action
  await logAdminAction(adminId, 'unlock', 'user', String(userId));

  return result.rows[0];
}

// Ban a user
export async function banUser(userId, adminId, reason, durationDays = null) {
  const bannedUntil = durationDays ? `NOW() + INTERVAL '${parseInt(durationDays)} days'` : 'NULL';

  const query = `
    UPDATE users
    SET banned = true, banned_at = NOW(), banned_until = ${bannedUntil},
        banned_reason = $2, banned_by = $3
    WHERE id = $1
    RETURNING *
  `;
  const result = await pool.query(query, [userId, reason, adminId]);

  // Log the action
  await logAdminAction(adminId, 'ban', 'user', String(userId), reason, { durationDays });

  return result.rows[0];
}

// Unban a user
export async function unbanUser(userId, adminId) {
  const query = `
    UPDATE users
    SET banned = false, banned_at = NULL, banned_until = NULL,
        banned_reason = NULL, banned_by = NULL
    WHERE id = $1
    RETURNING *
  `;
  const result = await pool.query(query, [userId]);

  // Log the action
  await logAdminAction(adminId, 'unban', 'user', String(userId));

  return result.rows[0];
}

// Expire all sessions for a user (used when banning)
export async function expireUserSessions(userId) {
  const query = `DELETE FROM sessions WHERE user_id = $1`;
  await pool.query(query, [userId]);
}

// Log admin action
export async function logAdminAction(adminId, actionType, targetType, targetId, reason = null, metadata = null) {
  const query = `
    INSERT INTO admin_actions (admin_id, action_type, target_type, target_id, reason, metadata)
    VALUES ($1, $2, $3, $4, $5, $6)
    RETURNING id
  `;
  const result = await pool.query(query, [adminId, actionType, targetType, targetId, reason, metadata ? JSON.stringify(metadata) : null]);
  return result.rows[0];
}

// Get admin action log
export async function getAdminActions(filters = {}, page = 1, limit = 50) {
  const offset = (page - 1) * limit;
  let whereConditions = [];
  let params = [];
  let paramIndex = 1;

  if (filters.adminId) {
    whereConditions.push(`admin_id = $${paramIndex++}`);
    params.push(filters.adminId);
  }
  if (filters.actionType) {
    whereConditions.push(`action_type = $${paramIndex++}`);
    params.push(filters.actionType);
  }
  if (filters.targetType) {
    whereConditions.push(`target_type = $${paramIndex++}`);
    params.push(filters.targetType);
  }
  if (filters.targetId) {
    whereConditions.push(`target_id = $${paramIndex++}`);
    params.push(filters.targetId);
  }

  const whereClause = whereConditions.length > 0 ? `WHERE ${whereConditions.join(' AND ')}` : '';

  const query = `
    SELECT aa.*, u.global_name as admin_name
    FROM admin_actions aa
    LEFT JOIN users u ON aa.admin_id = u.id
    ${whereClause}
    ORDER BY aa.created_at DESC
    LIMIT $${paramIndex++} OFFSET $${paramIndex}
  `;
  params.push(limit, offset);

  const countQuery = `SELECT COUNT(*) as total FROM admin_actions ${whereClause}`;
  const countParams = params.slice(0, -2);

  const [result, countResult] = await Promise.all([
    pool.query(query, params),
    pool.query(countQuery, countParams)
  ]);

  return {
    actions: result.rows,
    total: parseInt(countResult.rows[0].total),
    page,
    limit,
    totalPages: Math.ceil(parseInt(countResult.rows[0].total) / limit)
  };
}

// =============================================
// ADMIN CHANGE MANAGEMENT
// =============================================

// Get changes with filters and pagination
export async function getChangesFiltered(filters = {}, page = 1, limit = 20) {
  const offset = (page - 1) * limit;
  let whereConditions = [];
  let params = [];
  let paramIndex = 1;

  if (filters.state) {
    if (Array.isArray(filters.state)) {
      whereConditions.push(`c.state = ANY($${paramIndex++}::change_state[])`);
      params.push(filters.state);
    } else {
      whereConditions.push(`c.state = $${paramIndex++}`);
      params.push(filters.state);
    }
  }
  if (filters.entity) {
    if (Array.isArray(filters.entity)) {
      whereConditions.push(`c.entity = ANY($${paramIndex++}::change_entity[])`);
      params.push(filters.entity);
    } else {
      whereConditions.push(`c.entity = $${paramIndex++}`);
      params.push(filters.entity);
    }
  }
  if (filters.type) {
    if (Array.isArray(filters.type)) {
      whereConditions.push(`c.type = ANY($${paramIndex++}::change_type[])`);
      params.push(filters.type);
    } else {
      whereConditions.push(`c.type = $${paramIndex++}`);
      params.push(filters.type);
    }
  }
  if (filters.authorId) {
    whereConditions.push(`c.author_id = $${paramIndex++}`);
    params.push(filters.authorId);
  }
  if (filters.reviewedBy) {
    whereConditions.push(`c.reviewed_by = $${paramIndex++}`);
    params.push(filters.reviewedBy);
  }
  if (filters.fromDate) {
    whereConditions.push(`c.created_at >= $${paramIndex++}`);
    params.push(filters.fromDate);
  }
  if (filters.toDate) {
    whereConditions.push(`c.created_at <= $${paramIndex++}`);
    params.push(filters.toDate);
  }
  if (filters.search) {
    whereConditions.push(`c.data->>'Name' ILIKE $${paramIndex++}`);
    params.push(`%${filters.search}%`);
  }

  const whereClause = whereConditions.length > 0 ? `WHERE ${whereConditions.join(' AND ')}` : '';

  const query = `
    SELECT c.*,
           u.global_name as author_name, u.eu_name as author_eu_name,
           r.global_name as reviewer_name
    FROM changes c
    LEFT JOIN users u ON c.author_id = u.id
    LEFT JOIN users r ON c.reviewed_by = r.id
    ${whereClause}
    ORDER BY c.created_at DESC NULLS LAST, c.last_update DESC
    LIMIT $${paramIndex++} OFFSET $${paramIndex}
  `;
  params.push(limit, offset);

  const countQuery = `SELECT COUNT(*) as total FROM changes c ${whereClause}`;
  const countParams = params.slice(0, -2);

  const [result, countResult] = await Promise.all([
    pool.query(query, params),
    pool.query(countQuery, countParams)
  ]);

  return {
    changes: result.rows,
    total: parseInt(countResult.rows[0].total),
    page,
    limit,
    totalPages: Math.ceil(parseInt(countResult.rows[0].total) / limit)
  };
}

// Get single change with full details
export async function getChangeFullDetails(changeId) {
  const query = `
    SELECT c.*,
           u.global_name as author_name, u.eu_name as author_eu_name, u.avatar as author_avatar,
           r.global_name as reviewer_name
    FROM changes c
    LEFT JOIN users u ON c.author_id = u.id
    LEFT JOIN users r ON c.reviewed_by = r.id
    WHERE c.id = $1
  `;
  const result = await pool.query(query, [changeId]);
  return result.rows[0] || null;
}

// Get change history (versions)
export async function getChangeHistory(changeId) {
  const query = `
    SELECT ch.*, u.global_name as author_name
    FROM change_history ch
    LEFT JOIN users u ON ch.created_by = u.id
    WHERE ch.change_id = $1
    ORDER BY ch.created_at DESC
  `;
  const result = await pool.query(query, [changeId]);
  return result.rows;
}

// Get other approved changes for the same entity (for comparison)
// Returns approved changes with the same entity type and entity ID, excluding the current change
export async function getRelatedApprovedChanges(changeId, entityType, entityId) {
  if (!entityType || !entityId) {
    return [];
  }

  const query = `
    SELECT c.id, c.data, c.last_update, c.type, u.global_name as author_name
    FROM changes c
    LEFT JOIN users u ON c.author_id = u.id
    WHERE c.entity = $1
      AND c.data->>'Id' = $2
      AND c.state = 'Approved'
      AND c.id != $3
    ORDER BY c.last_update DESC
    LIMIT 10
  `;
  const result = await pool.query(query, [entityType, String(entityId), changeId]);
  return result.rows;
}

// Add change history entry (call when change is updated)
export async function addChangeHistory(changeId, data, userId) {
  const query = `
    INSERT INTO change_history (change_id, data, created_by)
    VALUES ($1, $2, $3)
    RETURNING id
  `;
  const result = await pool.query(query, [changeId, JSON.stringify(data), userId]);
  return result.rows[0];
}

// Build initial history from change data if no history exists
// This creates a baseline entry so users can see the original state
export async function buildInitialHistoryIfNeeded(changeId) {
  // Check if history exists
  const checkQuery = 'SELECT COUNT(*) as count FROM change_history WHERE change_id = $1';
  const checkResult = await pool.query(checkQuery, [changeId]);

  if (parseInt(checkResult.rows[0].count) > 0) {
    return false; // History already exists
  }

  // Get the change data
  const changeQuery = 'SELECT data, author_id, created_at FROM changes WHERE id = $1';
  const changeResult = await pool.query(changeQuery, [changeId]);

  if (!changeResult.rows[0]) {
    return false; // Change not found
  }

  const change = changeResult.rows[0];

  // Create initial history entry with the original created_at timestamp
  const insertQuery = `
    INSERT INTO change_history (change_id, data, created_by, created_at)
    VALUES ($1, $2, $3, $4)
    RETURNING id
  `;
  await pool.query(insertQuery, [changeId, JSON.stringify(change.data), change.author_id, change.created_at]);

  return true; // History was built
}

// Update change review status (called by bot or admin)
export async function setChangeReviewed(changeId, reviewerId, state) {
  const query = `
    UPDATE changes
    SET state = $2, reviewed_at = NOW(), reviewed_by = $3
    WHERE id = $1
    RETURNING *
  `;
  const result = await pool.query(query, [changeId, state, reviewerId]);

  // Log the action
  const actionType = state === 'Approved' ? 'approve_change' : 'deny_change';
  await logAdminAction(reviewerId, actionType, 'change', String(changeId));

  return result.rows[0];
}

// Get change statistics
export async function getChangeStats() {
  const query = `
    SELECT
      state,
      entity,
      COUNT(*) as count
    FROM changes
    GROUP BY state, entity
    ORDER BY state, entity
  `;
  const result = await pool.query(query);
  return result.rows;
}

// =============================================
// USER METRICS
// =============================================

// Get user activity metrics
export async function getUserMetrics(userId) {
  // Get change counts by state
  const changesQuery = `
    SELECT
      state,
      COUNT(*) as count
    FROM changes
    WHERE author_id = $1
    GROUP BY state
  `;

  // Get service count
  const servicesQuery = `
    SELECT COUNT(*) as count FROM services WHERE user_id = $1 AND deleted_at IS NULL
  `;

  // Get service requests made
  const requestsMadeQuery = `
    SELECT COUNT(*) as count FROM service_requests WHERE requester_id = $1
  `;

  // Get flights taken (as passenger)
  const flightsTakenQuery = `
    SELECT COUNT(*) as count FROM service_checkins WHERE user_id = $1 AND status = 'completed'
  `;

  // Get recent changes
  const recentChangesQuery = `
    SELECT id, entity, type, state, data->>'Name' as name, created_at, last_update
    FROM changes
    WHERE author_id = $1
    ORDER BY COALESCE(created_at, last_update) DESC
    LIMIT 10
  `;

  const [changesResult, servicesResult, requestsResult, flightsResult, recentResult] = await Promise.all([
    pool.query(changesQuery, [userId]),
    pool.query(servicesQuery, [userId]),
    pool.query(requestsMadeQuery, [userId]),
    pool.query(flightsTakenQuery, [userId]),
    pool.query(recentChangesQuery, [userId])
  ]);

  // Aggregate change counts
  const changeCounts = {
    total: 0,
    draft: 0,
    pending: 0,
    approved: 0,
    denied: 0,
    deleted: 0
  };

  changesResult.rows.forEach(row => {
    const state = row.state.toLowerCase();
    changeCounts[state] = parseInt(row.count);
    changeCounts.total += parseInt(row.count);
  });

  return {
    changes: changeCounts,
    services: parseInt(servicesResult.rows[0]?.count || 0),
    requestsMade: parseInt(requestsResult.rows[0]?.count || 0),
    flightsTaken: parseInt(flightsResult.rows[0]?.count || 0),
    recentChanges: recentResult.rows
  };
}

// Get users with most contributions
export async function getTopContributors(limit = 10) {
  const query = `
    SELECT
      u.id, u.global_name, u.eu_name, u.avatar,
      COUNT(c.id) FILTER (WHERE c.state = 'Approved') as approved_count,
      COUNT(c.id) as total_count
    FROM users u
    LEFT JOIN changes c ON u.id = c.author_id
    GROUP BY u.id
    HAVING COUNT(c.id) > 0
    ORDER BY approved_count DESC, total_count DESC
    LIMIT $1
  `;
  const result = await pool.query(query, [limit]);
  return result.rows;
}
export async function countUserLoadouts(userId) {
  const query = 'SELECT COUNT(*)::int AS count FROM loadouts WHERE user_id = $1';
  const values = [userId];
  const { rows } = await pool.query(query, values);
  return rows[0]?.count ?? 0;
}

export async function getUserLoadouts(userId) {
  const query = 'SELECT id, name, data, public, share_code, created_at, last_update FROM loadouts WHERE user_id = $1 ORDER BY last_update DESC';
  const values = [userId];
  const { rows } = await pool.query(query, values);
  return rows;
}

export async function getUserLoadoutById(userId, id) {
  const query = 'SELECT id, name, data, public, share_code, created_at, last_update FROM loadouts WHERE user_id = $1 AND id = $2';
  const values = [userId, id];
  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function createUserLoadout(userId, name, data, isPublic, shareCode) {
  const query = `INSERT INTO loadouts (user_id, name, data, public, share_code)
    VALUES ($1, $2, $3, $4, $5)
    RETURNING id, name, data, public, share_code, created_at, last_update`;
  const values = [userId, name, data, !!isPublic, shareCode];
  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function updateUserLoadout(userId, id, name, data, isPublic, shareCode) {
  const query = `UPDATE loadouts
    SET name = $3,
        data = $4,
        public = $5,
        share_code = $6,
        last_update = CURRENT_TIMESTAMP
    WHERE user_id = $1 AND id = $2
    RETURNING id, name, data, public, share_code, created_at, last_update`;
  const values = [userId, id, name, data, !!isPublic, shareCode];
  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function deleteUserLoadout(userId, id) {
  const query = 'DELETE FROM loadouts WHERE user_id = $1 AND id = $2';
  const values = [userId, id];
  await pool.query(query, values);
}

export async function getLoadoutByShareCode(shareCode) {
  const query = 'SELECT id, name, data, public, share_code, created_at, last_update, user_id FROM loadouts WHERE share_code = $1 AND public = true';
  const values = [shareCode];
  const { rows } = await pool.query(query, values);
  return rows[0];
}
