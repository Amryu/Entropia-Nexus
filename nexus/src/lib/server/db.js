//@ts-nocheck
import pg from 'pg';

const Pool = pg.Pool;

export const pool = new Pool({
  connectionString: process.env.POSTGRES_CONNECTION_STRING,
});

// Optional read-only pool for the nexus entity database (MUST ONLY BE USED for image cleanup scanning)
export const nexusPool = process.env.POSTGRES_NEXUS_CONNECTION_STRING
  ? new Pool({ connectionString: process.env.POSTGRES_NEXUS_CONNECTION_STRING })
  : null;

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

export async function getUserProfileById(userId) {
  const query = `
    SELECT
      id,
      username,
      global_name,
      discriminator,
      avatar,
      eu_name,
      verified,
      administrator,
      society_id,
      biography_html,
      default_profile_tab,
      showcase_loadout_code,
      reward_score
    FROM users
    WHERE id = $1
  `;
  const { rows } = await pool.query(query, [userId]);
  return rows[0];
}

export async function getUserProfileByEntropiaName(entropiaName) {
  const query = `
    SELECT
      id,
      username,
      global_name,
      discriminator,
      avatar,
      eu_name,
      verified,
      administrator,
      society_id,
      biography_html,
      default_profile_tab,
      showcase_loadout_code,
      reward_score
    FROM users
    WHERE LOWER(eu_name) = LOWER($1)
  `;
  const { rows } = await pool.query(query, [entropiaName]);
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
  const query = 'SELECT * FROM changes WHERE data->>\'Id\' = $1 AND state IN (\'Draft\', \'Pending\', \'DirectApply\', \'ApplyFailed\')';
  const values = [id];

  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function getOpenChangeByEntityId(entity, id, type = null) {
  const conditions = [
    `c.entity = $1`,
    `c.state IN ('Draft', 'Pending', 'DirectApply', 'ApplyFailed')`,
    `c.data->>'Id' = $2`
  ];
  const values = [entity, String(id)];
  if (type) {
    conditions.push(`c.type = $3`);
    values.push(type);
  }
  const query = `SELECT * FROM changes c WHERE ${conditions.join(' AND ')} ORDER BY c.created_at DESC NULLS LAST LIMIT 1`;
  const { rows } = await pool.query(query, values);
  return rows[0] || null;
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

export async function updateUserProfile(userId, updates = {}) {
  const query = `
    UPDATE users
    SET biography_html = $2,
        default_profile_tab = $3,
        showcase_loadout_code = $4
    WHERE id = $1
    RETURNING
      id,
      username,
      global_name,
      discriminator,
      avatar,
      eu_name,
      verified,
      administrator,
      society_id,
      biography_html,
      default_profile_tab,
      showcase_loadout_code
  `;
  const values = [
    userId,
    updates.biography_html ?? null,
    updates.default_profile_tab ?? 'General',
    updates.showcase_loadout_code ?? null
  ];
  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function updateUserSociety(userId, societyId = null) {
  const query = `
    UPDATE users
    SET society_id = $2
    WHERE id = $1
    RETURNING id, society_id
  `;
  const { rows } = await pool.query(query, [userId, societyId]);
  return rows[0];
}

export async function getSocietyById(societyId) {
  const query = `
      SELECT id, name, abbreviation, description, discord_code, discord_public, leader_id
      FROM societies
      WHERE id = $1
    `;
  const { rows } = await pool.query(query, [societyId]);
  return rows[0];
}

export async function getSocietyByName(name) {
  const query = `
      SELECT id, name, abbreviation, description, discord_code, discord_public, leader_id
      FROM societies
      WHERE LOWER(name) = LOWER($1)
    `;
  const { rows } = await pool.query(query, [name]);
  return rows[0];
}

export async function searchSocieties(queryText = '') {
  const query = `
      SELECT id, name, abbreviation, description, discord_code, leader_id
      FROM societies
      WHERE ($1 = '' OR LOWER(name) LIKE LOWER($2) OR LOWER(abbreviation) LIKE LOWER($2))
      ORDER BY name
      LIMIT 50
    `;
  const value = String(queryText || '');
  const { rows } = await pool.query(query, [value, `%${value}%`]);
  return rows;
}

export async function createSociety({ name, abbreviation = null, description = null, discordCode = null, leaderId }) {
  const query = `
      INSERT INTO societies (name, abbreviation, description, discord_code, leader_id)
      VALUES ($1, $2, $3, $4, $5)
      RETURNING id, name, abbreviation, description, discord_code, leader_id
    `;
  const values = [name, abbreviation, description, discordCode, leaderId];
  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function createSocietyJoinRequest(userId, societyId) {
  const query = `
    INSERT INTO society_join_requests (user_id, society_id, status)
    VALUES ($1, $2, 'Pending')
    RETURNING id, user_id, society_id, status, created_at, updated_at
  `;
  const { rows } = await pool.query(query, [userId, societyId]);
  return rows[0];
}

export async function getPendingSocietyJoinRequest(userId) {
  const query = `
    SELECT id, user_id, society_id, status, created_at, updated_at
    FROM society_join_requests
    WHERE user_id = $1 AND status = 'Pending'
    ORDER BY created_at DESC
    LIMIT 1
  `;
  const { rows } = await pool.query(query, [userId]);
  return rows[0];
}

export async function updateSocietyJoinRequestStatus(requestId, status) {
  const query = `
    UPDATE society_join_requests
    SET status = $2,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = $1
    RETURNING id, user_id, society_id, status
  `;
  const { rows } = await pool.query(query, [requestId, status]);
  return rows[0];
}

export async function getSocietyJoinRequestById(requestId) {
  const query = `
    SELECT id, user_id, society_id, status, created_at, updated_at
    FROM society_join_requests
    WHERE id = $1
  `;
  const { rows } = await pool.query(query, [requestId]);
  return rows[0];
}

export async function getSocietyMembers(societyId) {
  const query = `
    SELECT id, eu_name, global_name, username, discriminator
    FROM users
    WHERE society_id = $1
    ORDER BY eu_name NULLS LAST, global_name NULLS LAST
  `;
  const { rows } = await pool.query(query, [societyId]);
  return rows;
}

export async function getSocietyJoinRequests(societyId, status = 'Pending', limit = 50, offset = 0) {
  const query = `
    SELECT
      r.id,
      r.user_id,
      r.status,
      r.created_at,
      u.eu_name,
      u.global_name,
      u.username,
      u.discriminator
    FROM society_join_requests r
    JOIN users u ON u.id = r.user_id
    WHERE r.society_id = $1 AND r.status = $2
    ORDER BY r.created_at DESC
    LIMIT $3 OFFSET $4
  `;
  const { rows } = await pool.query(query, [societyId, status, limit, offset]);
  return rows;
}

export async function countSocietyJoinRequests(societyId, status = 'Pending') {
  const query = `
      SELECT COUNT(*)::int AS count
    FROM society_join_requests
    WHERE society_id = $1 AND status = $2
  `;
  const { rows } = await pool.query(query, [societyId, status]);
  return rows[0]?.count ?? 0;
}

export async function updateSocietyDetails(societyId, description = null, discordCode = null, discordPublic = false) {
  const query = `
    UPDATE societies
    SET description = $2,
        discord_code = $3,
        discord_public = $4
    WHERE id = $1
    RETURNING id, name, abbreviation, description, discord_code, discord_public, leader_id
  `;
  const { rows } = await pool.query(query, [societyId, description, discordCode, discordPublic]);
  return rows[0];
}

export async function getAdminSocieties(limit = 50, offset = 0, queryText = '') {
  const query = `
    SELECT
      s.id,
      s.name,
      s.abbreviation,
      s.leader_id,
      u.eu_name as leader_eu_name,
      u.global_name as leader_global_name,
      u.username as leader_username,
      COUNT(m.id)::int as member_count
    FROM societies s
    LEFT JOIN users u ON u.id = s.leader_id
    LEFT JOIN users m ON m.society_id = s.id
    WHERE ($3 = '' OR LOWER(s.name) LIKE LOWER($4) OR LOWER(s.abbreviation) LIKE LOWER($4))
    GROUP BY s.id, u.eu_name, u.global_name, u.username
    ORDER BY s.name
    LIMIT $1 OFFSET $2
  `;
  const value = String(queryText || '');
  const { rows } = await pool.query(query, [limit, offset, value, `%${value}%`]);
  return rows;
}

export async function countAdminSocieties(queryText = '') {
  const query = `
    SELECT COUNT(*)::int AS count
    FROM societies s
    WHERE ($1 = '' OR LOWER(s.name) LIKE LOWER($2) OR LOWER(s.abbreviation) LIKE LOWER($2))
  `;
  const value = String(queryText || '');
  const { rows } = await pool.query(query, [value, `%${value}%`]);
  return rows[0]?.count ?? 0;
}

export async function disbandSociety(societyId) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const memberResult = await client.query(
      'SELECT id FROM users WHERE society_id = $1',
      [societyId]
    );
    const pendingResult = await client.query(
      "SELECT user_id FROM society_join_requests WHERE society_id = $1 AND status = 'Pending'",
      [societyId]
    );
    await client.query('UPDATE users SET society_id = NULL WHERE society_id = $1', [societyId]);
    await client.query(
      "UPDATE society_join_requests SET status = 'Rejected', updated_at = CURRENT_TIMESTAMP WHERE society_id = $1 AND status = 'Pending'",
      [societyId]
    );
    await client.query('DELETE FROM societies WHERE id = $1', [societyId]);
    await client.query('COMMIT');
    return {
      members: memberResult.rows.map(row => row.id),
      pending: pendingResult.rows.map(row => row.user_id)
    };
  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  } finally {
    client.release();
  }
}

export async function createNotification(userId, type, message) {
  const query = `
    INSERT INTO notifications (user_id, type, message)
    VALUES ($1, $2, $3)
    RETURNING *
  `;
  const { rows } = await pool.query(query, [userId, type, message]);
  return rows[0];
}

export async function notifyAdmins(message) {
  const { rows: admins } = await pool.query(
    `SELECT id FROM ONLY users WHERE administrator = true`
  );
  for (const admin of admins) {
    await pool.query(
      `INSERT INTO notifications (user_id, type, message) VALUES ($1, 'Admin', $2)`,
      [admin.id, message]
    );
  }
}

export async function getNotifications(userId, limit = 10, offset = 0) {
  const query = `
    SELECT id, user_id, type, message, date, read
    FROM notifications
    WHERE user_id = $1
    ORDER BY date DESC
    LIMIT $2 OFFSET $3
  `;
  const { rows } = await pool.query(query, [userId, limit, offset]);
  return rows;
}

export async function countNotifications(userId) {
  const query = `
    SELECT COUNT(*)::int AS count
    FROM notifications
    WHERE user_id = $1
  `;
  const { rows } = await pool.query(query, [userId]);
  return rows[0]?.count ?? 0;
}

export async function countUnreadNotifications(userId) {
  const query = `
    SELECT COUNT(*)::int AS count
    FROM notifications
    WHERE user_id = $1 AND read = false
  `;
  const { rows } = await pool.query(query, [userId]);
  return rows[0]?.count ?? 0;
}

export async function markNotificationRead(userId, notificationId) {
  const query = `
    UPDATE notifications
    SET read = true
    WHERE id = $1 AND user_id = $2
    RETURNING id, read
  `;
  const { rows } = await pool.query(query, [notificationId, userId]);
  return rows[0];
}

export async function markAllNotificationsRead(userId) {
  const query = `
    UPDATE notifications
    SET read = true
    WHERE user_id = $1 AND read = false
  `;
  await pool.query(query, [userId]);
}

export async function getUserContributionStats(userId) {
  const totalQuery = `
    SELECT COUNT(*)::int AS total
    FROM changes
    WHERE author_id = $1 AND state = 'Approved'
  `;
  const monthlyQuery = `
    SELECT COUNT(*)::int AS monthly
    FROM changes
    WHERE author_id = $1
      AND state = 'Approved'
      AND last_update >= date_trunc('month', now())
      AND last_update < (date_trunc('month', now()) + interval '1 month')
  `;

  const [totalResult, monthlyResult] = await Promise.all([
    pool.query(totalQuery, [userId]),
    pool.query(monthlyQuery, [userId])
  ]);

  return {
    total: totalResult.rows[0]?.total ?? 0,
    monthly: monthlyResult.rows[0]?.monthly ?? 0
  };
}

export async function getUserPublicLoadouts(userId) {
  const query = `
    SELECT id, name, share_code, last_update
    FROM loadouts
    WHERE user_id = $1 AND public = true
    ORDER BY last_update DESC
  `;
  const { rows } = await pool.query(query, [userId]);
  return rows;
}

export async function getUserShops(userId) {
  const query = `
    SELECT
      s.id,
      s.name,
      s.planet_id,
      p."Name" as planet_name
    FROM shops s
    LEFT JOIN "Planets" p ON s.planet_id = p."Id"
    WHERE s.owner_id = $1
    ORDER BY s.name
  `;
  const { rows } = await pool.query(query, [userId]);
  return rows;
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
      u.eu_name as manager_name,
      u.id as manager_id,
      COALESCE(s.owner_display_name, owner_u.eu_name, u.eu_name) as owner_name,
      COALESCE(s.owner_user_id, s.user_id) as owner_id,
      ticket_prices.min_price,
      ticket_prices.max_price
    FROM services s
    JOIN users u ON s.user_id = u.id
    LEFT JOIN users owner_u ON s.owner_user_id = owner_u.id
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
  const query = `
    SELECT
      s.*,
      u.eu_name as manager_name,
      u.id as manager_id,
      COALESCE(s.owner_display_name, owner_u.eu_name, u.eu_name) as owner_name,
      COALESCE(s.owner_user_id, s.user_id) as owner_id
    FROM services s
    JOIN users u ON s.user_id = u.id
    LEFT JOIN users owner_u ON s.owner_user_id = owner_u.id
    WHERE s.id = $1
  `;
  const { rows } = await pool.query(query, [serviceId]);
  return rows[0];
}

export async function getServiceByIdOrTitle(identifier) {
  let query, values;

  if (!isNaN(identifier)) {
    query = `
      SELECT
        s.*,
        u.eu_name as manager_name,
        u.id as manager_id,
        COALESCE(s.owner_display_name, owner_u.eu_name, u.eu_name) as owner_name,
        COALESCE(s.owner_user_id, s.user_id) as owner_id
      FROM services s
      JOIN users u ON s.user_id = u.id
      LEFT JOIN users owner_u ON s.owner_user_id = owner_u.id
      WHERE s.id = $1
    `;
    values = [parseInt(identifier)];
  } else {
    query = `
      SELECT
        s.*,
        u.eu_name as manager_name,
        u.id as manager_id,
        COALESCE(s.owner_display_name, owner_u.eu_name, u.eu_name) as owner_name,
        COALESCE(s.owner_user_id, s.user_id) as owner_id
      FROM services s
      JOIN users u ON s.user_id = u.id
      LEFT JOIN users owner_u ON s.owner_user_id = owner_u.id
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
      is_active, is_busy, owner_user_id, owner_display_name
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
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
    false,
    serviceData.owner_user_id != null ? serviceData.owner_user_id : null,
    serviceData.owner_display_name || null
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
      owner_user_id = $10,
      owner_display_name = $11,
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
    serviceData.is_active !== false,
    serviceData.owner_user_id !== undefined ? serviceData.owner_user_id : null,
    serviceData.owner_display_name !== undefined ? serviceData.owner_display_name : null
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
      u.eu_name as manager_name,
      u.id as manager_id,
      COALESCE(s.owner_display_name, owner_u.eu_name, u.eu_name) as owner_name,
      COALESCE(s.owner_user_id, s.user_id) as owner_id
    FROM services s
    JOIN users u ON s.user_id = u.id
    LEFT JOIN users owner_u ON s.owner_user_id = owner_u.id
    WHERE s.user_id = $1 OR s.owner_user_id = $1
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
      transportation_type, ship_name, service_mode, current_planet_id, discord_code
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
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
      current_planet_id = $15,
      discord_code = $16
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
    details.current_planet_id || null,
    details.discord_code || null
  ];
  const { rows } = await pool.query(query, values);
  return rows[0];
}

// Service equipment (bulk)
export async function getServicesEquipmentBulk(serviceIds) {
  if (!serviceIds.length) return {};
  const query = `
    SELECT * FROM service_equipment
    WHERE service_id = ANY($1)
    ORDER BY service_id, is_primary DESC, sort_order ASC
  `;
  const { rows } = await pool.query(query, [serviceIds]);
  const map = {};
  for (const row of rows) {
    if (!map[row.service_id]) map[row.service_id] = [];
    map[row.service_id].push(row);
  }
  return map;
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

// Check if a user can manage a service (manager, owner, or pilot)
export async function canManageService(serviceId, userId, isAdmin = false) {
  // Admins can manage everything
  if (isAdmin) return true;

  // Check if manager
  const service = await getServiceById(serviceId);
  if (service && service.user_id === userId) return true;

  // Check if owner
  if (service && service.owner_user_id && service.owner_user_id === userId) return true;

  // Check if pilot
  return await isServicePilot(serviceId, userId);
}

// Transfer the manager role to another user (pilot or owner)
export async function transferManager(serviceId, newManagerUserId, oldManagerUserId) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    // Update manager (user_id) to new user
    await client.query(
      `UPDATE services SET user_id = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2`,
      [newManagerUserId, serviceId]
    );

    // Remove new manager from pilots if they were a pilot
    await client.query(
      `DELETE FROM service_pilots WHERE service_id = $1 AND user_id = $2`,
      [serviceId, newManagerUserId]
    );

    // Add old manager as pilot (unless they are the owner)
    const service = await client.query(
      `SELECT owner_user_id FROM services WHERE id = $1`,
      [serviceId]
    );
    const isOldManagerOwner = service.rows[0]?.owner_user_id === oldManagerUserId;

    if (!isOldManagerOwner) {
      await client.query(
        `INSERT INTO service_pilots (service_id, user_id, added_by)
         VALUES ($1, $2, $3)
         ON CONFLICT (service_id, user_id) DO NOTHING`,
        [serviceId, oldManagerUserId, newManagerUserId]
      );
    }

    await client.query('COMMIT');
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
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
      u.eu_name as manager_name,
      COALESCE(s.owner_display_name, owner_u.eu_name, u.eu_name) as owner_name
    FROM service_pilots sp
    JOIN services s ON sp.service_id = s.id
    LEFT JOIN users u ON s.user_id = u.id
    LEFT JOIN users owner_u ON s.owner_user_id = owner_u.id
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
      SELECT u.id, u.username, u.global_name, u.eu_name, u.avatar, u.verified, u.administrator,
             u.society_id, s.name AS society_name, s.abbreviation AS society_abbreviation
      FROM users u
      LEFT JOIN societies s ON s.id = u.society_id
      WHERE
        LOWER(u.username) LIKE LOWER($1)
        OR LOWER(u.global_name) LIKE LOWER($1)
        OR LOWER(u.eu_name) LIKE LOWER($1)
      ORDER BY
        CASE
          WHEN LOWER(u.eu_name) LIKE LOWER($1) THEN 1
          WHEN LOWER(u.global_name) LIKE LOWER($1) THEN 2
          ELSE 3
        END,
        u.global_name ASC
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
      SELECT u.id, u.username, u.global_name, u.eu_name, u.avatar, u.verified, u.administrator,
             u.society_id, s.name AS society_name, s.abbreviation AS society_abbreviation
      FROM users u
      LEFT JOIN societies s ON s.id = u.society_id
      ORDER BY u.${sortColumn} ${order} NULLS LAST
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
  if (filters.entityId) {
    whereConditions.push(`(c.data->>'Id' = $${paramIndex} OR c.data->>'ItemId' = $${paramIndex})`);
    params.push(String(filters.entityId));
    paramIndex++;
  }
  if (filters.planet) {
    whereConditions.push(`c.data->'Planet'->>'Name' = $${paramIndex++}`);
    params.push(filters.planet);
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
    FROM ONLY users u
    LEFT JOIN ONLY changes c ON u.id = c.author_id
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
  const query = `SELECT l.id, l.name, l.data, l.public, l.share_code, l.created_at, l.last_update,
    (SELECT s.name FROM item_sets s WHERE s.loadout_id = l.id LIMIT 1) AS linked_item_set
    FROM loadouts l WHERE l.user_id = $1 ORDER BY l.last_update DESC`;
  const values = [userId];
  const { rows } = await pool.query(query, values);
  return rows;
}

export async function getUserLoadoutById(userId, id) {
  const query = `SELECT l.id, l.name, l.data, l.public, l.share_code, l.created_at, l.last_update,
    (SELECT s.name FROM item_sets s WHERE s.loadout_id = l.id LIMIT 1) AS linked_item_set
    FROM loadouts l WHERE l.user_id = $1 AND l.id = $2`;
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

// Crafting Plans
export async function getUserCraftingPlans(userId) {
  const query = 'SELECT id, name, data, created_at, last_update FROM crafting_plans WHERE user_id = $1 ORDER BY last_update DESC';
  const { rows } = await pool.query(query, [userId]);
  return rows;
}

export async function getUserCraftingPlanById(userId, id) {
  const query = 'SELECT id, name, data, created_at, last_update FROM crafting_plans WHERE user_id = $1 AND id = $2';
  const { rows } = await pool.query(query, [userId, id]);
  return rows[0];
}

export async function createUserCraftingPlan(userId, name, data) {
  const query = `INSERT INTO crafting_plans (user_id, name, data)
    VALUES ($1, $2, $3)
    RETURNING id, name, data, created_at, last_update`;
  const { rows } = await pool.query(query, [userId, name, data]);
  return rows[0];
}

export async function updateUserCraftingPlan(userId, id, name, data) {
  const query = `UPDATE crafting_plans
    SET name = $3,
        data = $4,
        last_update = CURRENT_TIMESTAMP
    WHERE user_id = $1 AND id = $2
    RETURNING id, name, data, created_at, last_update`;
  const { rows } = await pool.query(query, [userId, id, name, data]);
  return rows[0];
}

export async function deleteUserCraftingPlan(userId, id) {
  const query = 'DELETE FROM crafting_plans WHERE user_id = $1 AND id = $2';
  await pool.query(query, [userId, id]);
}

// Item Sets
export async function countUserItemSets(userId) {
  const query = 'SELECT COUNT(*)::int AS count FROM item_sets WHERE user_id = $1';
  const { rows } = await pool.query(query, [userId]);
  return rows[0]?.count ?? 0;
}

export async function getUserItemSets(userId) {
  const query = `SELECT s.id, s.name, s.loadout_id, s.created_at, s.last_update,
    (SELECT r.title FROM rental_offers r WHERE r.item_set_id = s.id AND r.status != 'deleted' LIMIT 1) AS linked_rental_offer
    FROM item_sets s WHERE s.user_id = $1 ORDER BY s.last_update DESC`;
  const { rows } = await pool.query(query, [userId]);
  return rows;
}

export async function getUserItemSetsWithData(userId) {
  const query = `SELECT s.id, s.name, s.data, s.loadout_id, s.created_at, s.last_update,
    (SELECT r.title FROM rental_offers r WHERE r.item_set_id = s.id AND r.status != 'deleted' LIMIT 1) AS linked_rental_offer
    FROM item_sets s WHERE s.user_id = $1 ORDER BY s.last_update DESC`;
  const { rows } = await pool.query(query, [userId]);
  return rows;
}

export async function getUserItemSetById(userId, id) {
  const query = 'SELECT id, name, data, customized, loadout_id, created_at, last_update FROM item_sets WHERE user_id = $1 AND id = $2';
  const { rows } = await pool.query(query, [userId, id]);
  return rows[0];
}

export async function createUserItemSet(userId, name, data, loadoutId = null) {
  const query = `INSERT INTO item_sets (user_id, name, data, loadout_id)
    VALUES ($1, $2, $3, $4)
    RETURNING id, name, data, loadout_id, created_at, last_update`;
  const { rows } = await pool.query(query, [userId, name, data, loadoutId]);
  return rows[0];
}

export async function updateUserItemSet(userId, id, name, data, customized) {
  const query = `UPDATE item_sets
    SET name = $3,
        data = $4,
        customized = $5,
        last_update = CURRENT_TIMESTAMP
    WHERE user_id = $1 AND id = $2
    RETURNING id, name, data, customized, loadout_id, created_at, last_update`;
  const { rows } = await pool.query(query, [userId, id, name, data, customized]);
  return rows[0];
}

export async function deleteUserItemSet(userId, id) {
  const query = 'DELETE FROM item_sets WHERE user_id = $1 AND id = $2';
  await pool.query(query, [userId, id]);
}

export async function getItemSetsByLoadoutId(userId, loadoutId) {
  const query = 'SELECT id, name FROM item_sets WHERE user_id = $1 AND loadout_id = $2';
  const { rows } = await pool.query(query, [userId, loadoutId]);
  return rows;
}

// ============================================
// RENTAL FUNCTIONS
// ============================================

// --- Rental Offers ---

export async function getRentalOffers(filters = {}) {
  let query = `
    SELECT ro.id, ro.title, ro.description, ro.planet_id, ro.location,
           ro.price_per_day, ro.discounts, ro.deposit, ro.status,
           ro.item_set_id, ro.created_at, ro.updated_at,
           u.eu_name AS owner_name, u.id AS owner_id,
           s.data AS item_set_data,
           (SELECT COUNT(*)::int FROM jsonb_array_elements(s.data->'items')) AS item_count
    FROM rental_offers ro
    JOIN users u ON ro.user_id = u.id
    LEFT JOIN item_sets s ON ro.item_set_id = s.id
    WHERE ro.status = 'available'
  `;
  const values = [];
  let paramIndex = 1;

  if (filters.planet_id) {
    query += ` AND ro.planet_id = $${paramIndex}`;
    values.push(filters.planet_id);
    paramIndex++;
  }

  query += ' ORDER BY ro.updated_at DESC';

  if (filters.limit) {
    query += ` LIMIT $${paramIndex}`;
    values.push(filters.limit);
    paramIndex++;
  }
  if (filters.offset) {
    query += ` OFFSET $${paramIndex}`;
    values.push(filters.offset);
    paramIndex++;
  }

  const { rows } = await pool.query(query, values);
  return rows;
}

export async function getRentalOfferById(id) {
  const query = `
    SELECT ro.*,
           u.eu_name AS owner_name, u.id AS owner_id,
           s.name AS item_set_name, s.data AS item_set_data
    FROM rental_offers ro
    JOIN users u ON ro.user_id = u.id
    LEFT JOIN item_sets s ON ro.item_set_id = s.id
    WHERE ro.id = $1 AND ro.status != 'deleted'
  `;
  const { rows } = await pool.query(query, [id]);
  return rows[0];
}

export async function getUserRentalOffers(userId) {
  const query = `
    SELECT ro.id, ro.title, ro.planet_id, ro.location,
           ro.price_per_day, ro.discounts, ro.deposit, ro.status,
           ro.item_set_id, ro.created_at, ro.updated_at,
           (SELECT COUNT(*)::int FROM jsonb_array_elements(s.data->'items')) AS item_count
    FROM rental_offers ro
    LEFT JOIN item_sets s ON ro.item_set_id = s.id
    WHERE ro.user_id = $1 AND ro.status != 'deleted'
    ORDER BY ro.updated_at DESC
  `;
  const { rows } = await pool.query(query, [userId]);
  return rows;
}

export async function getUserPublicRentalOffers(userId) {
  const query = `
    SELECT ro.id, ro.title, ro.planet_id, ro.location,
           ro.price_per_day, ro.discounts, ro.status,
           ro.item_set_id, ro.created_at,
           (SELECT COUNT(*)::int FROM jsonb_array_elements(s.data->'items')) AS item_count,
           (SELECT rr.end_date FROM rental_requests rr
            WHERE rr.offer_id = ro.id AND rr.status IN ('accepted', 'in_progress')
            ORDER BY rr.end_date DESC LIMIT 1
           ) AS rented_until
    FROM rental_offers ro
    LEFT JOIN item_sets s ON ro.item_set_id = s.id
    WHERE ro.user_id = $1 AND ro.status IN ('available', 'rented')
    ORDER BY ro.status ASC, ro.updated_at DESC
  `;
  const { rows } = await pool.query(query, [userId]);
  return rows;
}

export async function countUserRentalOffers(userId) {
  const query = "SELECT COUNT(*)::int AS count FROM rental_offers WHERE user_id = $1 AND status != 'deleted'";
  const { rows } = await pool.query(query, [userId]);
  return rows[0]?.count ?? 0;
}

export async function createRentalOffer(data) {
  const query = `
    INSERT INTO rental_offers (user_id, item_set_id, title, description, planet_id, location, price_per_day, discounts, deposit)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
    RETURNING *
  `;
  const { rows } = await pool.query(query, [
    data.user_id, data.item_set_id, data.title, data.description || null,
    data.planet_id || null, data.location || null,
    data.price_per_day, JSON.stringify(data.discounts || []), data.deposit || 0
  ]);
  return rows[0];
}

export async function updateRentalOffer(id, userId, data, expectedStatus = null) {
  const sets = [];
  const values = [];
  let paramIndex = 1;

  const fields = ['title', 'description', 'planet_id', 'location', 'price_per_day', 'deposit', 'status'];
  for (const field of fields) {
    if (data[field] !== undefined) {
      sets.push(`${field} = $${paramIndex}`);
      values.push(data[field]);
      paramIndex++;
    }
  }

  if (data.discounts !== undefined) {
    sets.push(`discounts = $${paramIndex}`);
    values.push(JSON.stringify(data.discounts));
    paramIndex++;
  }

  if (sets.length === 0) return null;

  sets.push(`updated_at = CURRENT_TIMESTAMP`);

  if (data.status === 'deleted') {
    sets.push(`deleted_at = CURRENT_TIMESTAMP`);
  }

  values.push(id, userId);
  let whereClause = `WHERE id = $${paramIndex} AND user_id = $${paramIndex + 1} AND status != 'deleted'`;

  // If expectedStatus is provided, add optimistic locking to prevent race conditions
  if (expectedStatus) {
    paramIndex += 2;
    whereClause += ` AND status = $${paramIndex}`;
    values.push(expectedStatus);
  }

  const query = `
    UPDATE rental_offers SET ${sets.join(', ')}
    ${whereClause}
    RETURNING *
  `;
  const { rows } = await pool.query(query, values);
  return rows[0];
}

export async function softDeleteRentalOffer(id, userId) {
  const query = `
    UPDATE rental_offers SET status = 'deleted', deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
    WHERE id = $1 AND user_id = $2 AND status != 'deleted'
    RETURNING id
  `;
  const { rows } = await pool.query(query, [id, userId]);
  return rows[0];
}

// --- Rental Blocked Dates ---

export async function getRentalBlockedDates(offerId) {
  const query = 'SELECT id, start_date, end_date, reason FROM rental_blocked_dates WHERE offer_id = $1 ORDER BY start_date';
  const { rows } = await pool.query(query, [offerId]);
  return rows;
}

export async function addRentalBlockedDate(offerId, startDate, endDate, reason = null) {
  const query = `
    INSERT INTO rental_blocked_dates (offer_id, start_date, end_date, reason)
    VALUES ($1, $2, $3, $4)
    RETURNING *
  `;
  const { rows } = await pool.query(query, [offerId, startDate, endDate, reason]);
  return rows[0];
}

export async function deleteRentalBlockedDate(id, offerId) {
  const query = 'DELETE FROM rental_blocked_dates WHERE id = $1 AND offer_id = $2 RETURNING id';
  const { rows } = await pool.query(query, [id, offerId]);
  return rows[0];
}

export async function countRentalBlockedDates(offerId) {
  const query = 'SELECT COUNT(*)::int AS count FROM rental_blocked_dates WHERE offer_id = $1';
  const { rows } = await pool.query(query, [offerId]);
  return rows[0]?.count ?? 0;
}

// --- Rental Requests ---

export async function getRentalRequests(offerId, status = null) {
  let query = `
    SELECT rr.*, u.eu_name AS requester_name
    FROM rental_requests rr
    JOIN users u ON rr.requester_id = u.id
    WHERE rr.offer_id = $1
  `;
  const values = [offerId];

  if (status) {
    query += ' AND rr.status = $2';
    values.push(status);
  }

  query += ' ORDER BY rr.created_at DESC';
  const { rows } = await pool.query(query, values);
  return rows;
}

export async function getRentalRequestById(id) {
  const query = `
    SELECT rr.*,
           u.eu_name AS requester_name, u.username AS requester_username,
           ro.title AS offer_title, ro.user_id AS offer_owner_id,
           ro.price_per_day AS offer_price_per_day, ro.discounts AS offer_discounts,
           ro.deposit AS offer_deposit, ro.status AS offer_status,
           ow.eu_name AS owner_name, ow.username AS owner_username
    FROM rental_requests rr
    JOIN users u ON rr.requester_id = u.id
    JOIN rental_offers ro ON rr.offer_id = ro.id
    JOIN users ow ON ro.user_id = ow.id
    WHERE rr.id = $1
  `;
  const { rows } = await pool.query(query, [id]);
  return rows[0];
}

export async function getUserRentalRequests(userId) {
  const query = `
    SELECT rr.*, ro.title AS offer_title,
           ow.eu_name AS owner_name
    FROM rental_requests rr
    JOIN rental_offers ro ON rr.offer_id = ro.id
    JOIN users ow ON ro.user_id = ow.id
    WHERE rr.requester_id = $1
    ORDER BY rr.created_at DESC
  `;
  const { rows } = await pool.query(query, [userId]);
  return rows;
}

export async function createRentalRequest(data) {
  // Atomic conflict check + insert to prevent TOCTOU race conditions
  const query = `
    WITH conflict_check AS (
      SELECT 1 FROM rental_blocked_dates
      WHERE offer_id = $1 AND start_date <= $4 AND end_date >= $3
      UNION ALL
      SELECT 1 FROM rental_requests
      WHERE offer_id = $1 AND status IN ('accepted', 'in_progress')
        AND start_date <= $4 AND end_date >= $3
      LIMIT 1
    )
    INSERT INTO rental_requests (offer_id, requester_id, start_date, end_date, total_days, price_per_day, discount_pct, total_price, deposit, requester_note)
    SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9, $10
    WHERE NOT EXISTS (SELECT 1 FROM conflict_check)
    RETURNING *
  `;
  const { rows } = await pool.query(query, [
    data.offer_id, data.requester_id, data.start_date, data.end_date,
    data.total_days, data.price_per_day, data.discount_pct, data.total_price,
    data.deposit, data.requester_note || null
  ]);
  return rows[0]; // null if conflict was found
}

export async function updateRentalRequest(id, data) {
  const sets = [];
  const values = [];
  let paramIndex = 1;

  const fields = ['status', 'owner_note', 'actual_return_date', 'end_date', 'total_days', 'price_per_day', 'discount_pct', 'total_price'];
  for (const field of fields) {
    if (data[field] !== undefined) {
      sets.push(`${field} = $${paramIndex}`);
      values.push(data[field]);
      paramIndex++;
    }
  }

  if (sets.length === 0) return null;

  sets.push('updated_at = CURRENT_TIMESTAMP');
  values.push(id);

  const query = `UPDATE rental_requests SET ${sets.join(', ')} WHERE id = $${paramIndex} RETURNING *`;
  const { rows } = await pool.query(query, values);
  return rows[0];
}

// --- Rental Extensions ---

export async function getRentalExtensions(requestId) {
  const query = 'SELECT * FROM rental_extensions WHERE request_id = $1 ORDER BY created_at';
  const { rows } = await pool.query(query, [requestId]);
  return rows;
}

export async function createRentalExtension(data) {
  const query = `
    INSERT INTO rental_extensions (request_id, previous_end, new_end, extra_days, retroactive, price_per_day, discount_pct, extra_price, new_total_price, note)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
    RETURNING *
  `;
  const { rows } = await pool.query(query, [
    data.request_id, data.previous_end, data.new_end, data.extra_days,
    data.retroactive, data.price_per_day, data.discount_pct,
    data.extra_price, data.new_total_price, data.note || null
  ]);
  return rows[0];
}

// --- Availability ---

export async function getRentalAvailability(offerId, startDate, endDate) {
  // Get blocked dates within range (reason excluded from public availability)
  // Alias start_date/end_date to start/end for frontend consumption
  const blockedQuery = `
    SELECT id, start_date AS start, end_date AS end
    FROM rental_blocked_dates
    WHERE offer_id = $1 AND end_date >= $2 AND start_date <= $3
    ORDER BY start_date
  `;
  const blocked = await pool.query(blockedQuery, [offerId, startDate, endDate]);

  // Get booked dates (accepted or in_progress requests) within range
  const bookedQuery = `
    SELECT id AS request_id, start_date AS start, end_date AS end, status
    FROM rental_requests
    WHERE offer_id = $1 AND status IN ('accepted', 'in_progress')
      AND end_date >= $2 AND start_date <= $3
    ORDER BY start_date
  `;
  const booked = await pool.query(bookedQuery, [offerId, startDate, endDate]);

  return {
    blockedDates: blocked.rows,
    bookedDates: booked.rows
  };
}

export async function checkRentalDateConflict(offerId, startDate, endDate, excludeRequestId = null) {
  // Check blocked dates
  const blockedQuery = `
    SELECT 1 FROM rental_blocked_dates
    WHERE offer_id = $1 AND start_date <= $3 AND end_date >= $2
    LIMIT 1
  `;
  const blocked = await pool.query(blockedQuery, [offerId, startDate, endDate]);
  if (blocked.rows.length > 0) return true;

  // Check existing bookings
  let bookedQuery = `
    SELECT 1 FROM rental_requests
    WHERE offer_id = $1 AND status IN ('accepted', 'in_progress')
      AND start_date <= $3 AND end_date >= $2
  `;
  const bookedValues = [offerId, startDate, endDate];

  if (excludeRequestId) {
    bookedQuery += ' AND id != $4';
    bookedValues.push(excludeRequestId);
  }

  bookedQuery += ' LIMIT 1';
  const booked = await pool.query(bookedQuery, bookedValues);
  return booked.rows.length > 0;
}

/**
 * Atomically update a rental request status and (optionally) the linked offer status.
 * Handles the 'completed' case by checking for other active requests before reverting offer to 'available'.
 */
export async function updateRentalRequestWithOfferStatus(requestId, requestData, offerId, offerOwnerId, newOfferStatus) {
  const client = await startTransaction();
  try {
    // 1. Update the request
    const reqSets = [];
    const reqValues = [];
    let p = 1;
    const reqFields = ['status', 'owner_note', 'actual_return_date', 'end_date', 'total_days', 'price_per_day', 'discount_pct', 'total_price'];
    for (const field of reqFields) {
      if (requestData[field] !== undefined) {
        reqSets.push(`${field} = $${p}`);
        reqValues.push(requestData[field]);
        p++;
      }
    }
    reqSets.push('updated_at = CURRENT_TIMESTAMP');
    reqValues.push(requestId);
    const reqQuery = `UPDATE rental_requests SET ${reqSets.join(', ')} WHERE id = $${p} RETURNING *`;
    const reqResult = await client.query(reqQuery, reqValues);
    const updatedRequest = reqResult.rows[0];

    // 2. Update the offer status if requested
    if (newOfferStatus && offerId && offerOwnerId) {
      let effectiveOfferStatus = newOfferStatus;

      // If completing, check for other active requests before reverting to 'available'
      if (newOfferStatus === 'available') {
        const otherActive = await client.query(
          `SELECT 1 FROM rental_requests WHERE offer_id = $1 AND id != $2 AND status IN ('accepted', 'in_progress') LIMIT 1`,
          [offerId, requestId]
        );
        if (otherActive.rows.length > 0) {
          effectiveOfferStatus = 'rented'; // Keep as rented if other bookings exist
        }
      }

      await client.query(
        `UPDATE rental_offers SET status = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2 AND user_id = $3 AND status != 'deleted'`,
        [effectiveOfferStatus, offerId, offerOwnerId]
      );
    }

    await commitTransaction(client);
    return updatedRequest;
  } catch (err) {
    await rollbackTransaction(client);
    throw err;
  }
}

// --- Item Set Rental Protection ---

export async function getItemSetRentalOffers(itemSetId) {
  const query = "SELECT id, title FROM rental_offers WHERE item_set_id = $1 AND status != 'deleted'";
  const { rows } = await pool.query(query, [itemSetId]);
  return rows;
}

// --- Rental DM Notifications ---

export async function createRentalDmNotification(data) {
  const query = `
    INSERT INTO rental_dm_notifications
      (owner_id, offer_id, offer_title, requester_name, start_date, end_date, total_days, total_price, deposit)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
  `;
  await pool.query(query, [
    data.owner_id, data.offer_id, data.offer_title, data.requester_name,
    data.start_date, data.end_date, data.total_days, data.total_price, data.deposit
  ]);
}

// Blueprint Ownership
export async function getUserBlueprintOwnership(userId) {
  const query = 'SELECT data, last_update FROM blueprint_ownership WHERE user_id = $1';
  const { rows } = await pool.query(query, [userId]);
  return rows[0]?.data || {};
}

export async function updateUserBlueprintOwnership(userId, data) {
  const query = `INSERT INTO blueprint_ownership (user_id, data, last_update)
    VALUES ($1, $2, CURRENT_TIMESTAMP)
    ON CONFLICT (user_id) DO UPDATE SET
      data = $2,
      last_update = CURRENT_TIMESTAMP
    RETURNING data, last_update`;
  const { rows } = await pool.query(query, [userId, data]);
  return rows[0];
}

// =============================================
// (item_prices tables removed — see migration 098)
// =============================================


// =============================================
// ROLE & GRANT MANAGEMENT
// =============================================

export async function getAllRoles() {
  const { rows } = await pool.query(`
    SELECT r.*, p.name AS parent_name,
      (SELECT COUNT(*)::int FROM user_roles ur WHERE ur.role_id = r.id) AS user_count,
      (SELECT COUNT(*)::int FROM role_grants rg WHERE rg.role_id = r.id) AS grant_count
    FROM roles r
    LEFT JOIN roles p ON p.id = r.parent_id
    ORDER BY r.name
  `);
  return rows;
}

export async function getRoleById(id) {
  const { rows } = await pool.query('SELECT * FROM roles WHERE id = $1', [id]);
  return rows[0];
}

export async function createRole({ name, description, parent_id }) {
  const { rows } = await pool.query(
    'INSERT INTO roles (name, description, parent_id) VALUES ($1, $2, $3) RETURNING *',
    [name, description || null, parent_id || null]
  );
  return rows[0];
}

export async function updateRole(id, { name, description, parent_id }) {
  const { rows } = await pool.query(
    'UPDATE roles SET name = $2, description = $3, parent_id = $4 WHERE id = $1 RETURNING *',
    [id, name, description || null, parent_id || null]
  );
  return rows[0];
}

export async function deleteRole(id) {
  await pool.query('DELETE FROM roles WHERE id = $1', [id]);
}

export async function getAllGrants() {
  const { rows } = await pool.query('SELECT * FROM grants ORDER BY key');
  return rows;
}

export async function getRoleGrants(roleId) {
  const { rows } = await pool.query(`
    SELECT g.id, g.key, g.description, rg.granted
    FROM role_grants rg
    JOIN grants g ON g.id = rg.grant_id
    WHERE rg.role_id = $1
    ORDER BY g.key
  `, [roleId]);
  return rows;
}

export async function setRoleGrants(roleId, grantEntries) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await client.query('DELETE FROM role_grants WHERE role_id = $1', [roleId]);
    for (const entry of grantEntries) {
      await client.query(
        'INSERT INTO role_grants (role_id, grant_id, granted) VALUES ($1, (SELECT id FROM grants WHERE key = $2), $3)',
        [roleId, entry.key, entry.granted !== false]
      );
    }
    await client.query('COMMIT');
  } catch (e) {
    await client.query('ROLLBACK');
    throw e;
  } finally {
    client.release();
  }
}

export async function getUserRoles(userId) {
  const { rows } = await pool.query(`
    SELECT r.id, r.name, r.description, ur.assigned_at
    FROM user_roles ur
    JOIN roles r ON r.id = ur.role_id
    WHERE ur.user_id = $1
    ORDER BY r.name
  `, [userId]);
  return rows;
}

export async function setUserRoles(userId, roleIds, assignedBy = null) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await client.query('DELETE FROM user_roles WHERE user_id = $1', [userId]);
    for (const roleId of roleIds) {
      await client.query(
        'INSERT INTO user_roles (user_id, role_id, assigned_by) VALUES ($1, $2, $3)',
        [userId, roleId, assignedBy]
      );
    }
    await client.query('COMMIT');
  } catch (e) {
    await client.query('ROLLBACK');
    throw e;
  } finally {
    client.release();
  }
}

export async function getUserGrantOverrides(userId) {
  const { rows } = await pool.query(`
    SELECT g.id, g.key, g.description, ug.granted
    FROM user_grants ug
    JOIN grants g ON g.id = ug.grant_id
    WHERE ug.user_id = $1
    ORDER BY g.key
  `, [userId]);
  return rows;
}

export async function setUserGrantOverrides(userId, grantEntries, assignedBy = null) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await client.query('DELETE FROM user_grants WHERE user_id = $1', [userId]);
    for (const entry of grantEntries) {
      await client.query(
        'INSERT INTO user_grants (user_id, grant_id, granted, assigned_by) VALUES ($1, (SELECT id FROM grants WHERE key = $2), $3, $4)',
        [userId, entry.key, entry.granted, assignedBy]
      );
    }
    await client.query('COMMIT');
  } catch (e) {
    await client.query('ROLLBACK');
    throw e;
  } finally {
    client.release();
  }
}

// =============================================
// GUIDE CONTENT
// =============================================

// --- Categories ---

export async function getGuideCategories() {
  const { rows } = await pool.query('SELECT * FROM guide_categories ORDER BY sort_order, id');
  return rows;
}

export async function getGuideCategoryById(id) {
  const { rows } = await pool.query('SELECT * FROM guide_categories WHERE id = $1', [id]);
  return rows[0];
}

export async function createGuideCategory({ title, description, sort_order, created_by }) {
  const { rows } = await pool.query(
    `INSERT INTO guide_categories (title, description, sort_order, created_by)
     VALUES ($1, $2, $3, $4) RETURNING *`,
    [title, description || null, sort_order || 0, created_by]
  );
  return rows[0];
}

export async function updateGuideCategory(id, { title, description, sort_order }) {
  const { rows } = await pool.query(
    `UPDATE guide_categories SET title = $2, description = $3,
     sort_order = $4, updated_at = now() WHERE id = $1 RETURNING *`,
    [id, title, description || null, sort_order]
  );
  return rows[0];
}

export async function deleteGuideCategory(id) {
  await pool.query('DELETE FROM guide_categories WHERE id = $1', [id]);
}

// --- Chapters ---

export async function getGuideChaptersByCategory(categoryId) {
  const { rows } = await pool.query(
    'SELECT * FROM guide_chapters WHERE category_id = $1 ORDER BY sort_order, id',
    [categoryId]
  );
  return rows;
}

export async function getGuideChapterById(id) {
  const { rows } = await pool.query('SELECT * FROM guide_chapters WHERE id = $1', [id]);
  return rows[0];
}

export async function createGuideChapter({ category_id, title, description, sort_order, created_by }) {
  const { rows } = await pool.query(
    `INSERT INTO guide_chapters (category_id, title, description, sort_order, created_by)
     VALUES ($1, $2, $3, $4, $5) RETURNING *`,
    [category_id, title, description || null, sort_order || 0, created_by]
  );
  return rows[0];
}

export async function updateGuideChapter(id, { title, description, sort_order }) {
  const { rows } = await pool.query(
    `UPDATE guide_chapters SET title = $2, description = $3,
     sort_order = $4, updated_at = now() WHERE id = $1 RETURNING *`,
    [id, title, description || null, sort_order]
  );
  return rows[0];
}

export async function deleteGuideChapter(id) {
  await pool.query('DELETE FROM guide_chapters WHERE id = $1', [id]);
}

// --- Lessons ---

export async function getGuideLessonsByChapter(chapterId) {
  const { rows } = await pool.query(
    'SELECT * FROM guide_lessons WHERE chapter_id = $1 ORDER BY sort_order, id',
    [chapterId]
  );
  return rows;
}

export async function getGuideLessonBySlug(slug) {
  const { rows } = await pool.query(
    `SELECT l.*, c.id AS chapter_id, c.title AS chapter_title, c.category_id,
            cat.title AS category_title
     FROM guide_lessons l
     JOIN guide_chapters c ON c.id = l.chapter_id
     JOIN guide_categories cat ON cat.id = c.category_id
     WHERE l.slug = $1`,
    [slug]
  );
  return rows[0];
}

export async function getGuideLessonById(id) {
  const { rows } = await pool.query('SELECT * FROM guide_lessons WHERE id = $1', [id]);
  return rows[0];
}

export async function createGuideLesson({ chapter_id, title, slug, sort_order, created_by }) {
  const { rows } = await pool.query(
    `INSERT INTO guide_lessons (chapter_id, title, slug, sort_order, created_by)
     VALUES ($1, $2, $3, $4, $5) RETURNING *`,
    [chapter_id, title, slug, sort_order || 0, created_by]
  );
  return rows[0];
}

export async function updateGuideLesson(id, { title, slug, sort_order }) {
  const { rows } = await pool.query(
    `UPDATE guide_lessons SET title = $2, slug = $3,
     sort_order = $4, updated_at = now() WHERE id = $1 RETURNING *`,
    [id, title, slug, sort_order]
  );
  return rows[0];
}

export async function deleteGuideLesson(id) {
  await pool.query('DELETE FROM guide_lessons WHERE id = $1', [id]);
}

// --- Paragraphs ---

export async function getGuideParagraphsByLesson(lessonId) {
  const { rows } = await pool.query(
    'SELECT * FROM guide_paragraphs WHERE lesson_id = $1 ORDER BY sort_order, id',
    [lessonId]
  );
  return rows;
}

export async function createGuideParagraph({ lesson_id, content_html, sort_order, created_by }) {
  const { rows } = await pool.query(
    `INSERT INTO guide_paragraphs (lesson_id, content_html, sort_order, created_by)
     VALUES ($1, $2, $3, $4) RETURNING *`,
    [lesson_id, content_html || '', sort_order || 0, created_by]
  );
  return rows[0];
}

export async function updateGuideParagraph(id, { content_html, sort_order }) {
  const { rows } = await pool.query(
    `UPDATE guide_paragraphs SET content_html = $2,
     sort_order = $3, updated_at = now() WHERE id = $1 RETURNING *`,
    [id, content_html, sort_order]
  );
  return rows[0];
}

export async function deleteGuideParagraph(id) {
  await pool.query('DELETE FROM guide_paragraphs WHERE id = $1', [id]);
}

export async function reorderGuideParagraphs(lessonId, orderedIds) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    for (let i = 0; i < orderedIds.length; i++) {
      await client.query(
        'UPDATE guide_paragraphs SET sort_order = $1, updated_at = now() WHERE id = $2 AND lesson_id = $3',
        [i, orderedIds[i], lessonId]
      );
    }
    await client.query('COMMIT');
  } catch (e) {
    await client.query('ROLLBACK');
    throw e;
  } finally {
    client.release();
  }
}

// --- Full guide tree ---

export async function getGuideTree() {
  const [cats, chaps, lessons] = await Promise.all([
    pool.query('SELECT * FROM guide_categories ORDER BY sort_order, id'),
    pool.query('SELECT * FROM guide_chapters ORDER BY sort_order, id'),
    pool.query('SELECT id, chapter_id, title, slug, sort_order FROM guide_lessons ORDER BY sort_order, id')
  ]);

  return cats.rows.map(cat => ({
    ...cat,
    chapters: chaps.rows
      .filter(ch => ch.category_id === cat.id)
      .map(ch => ({
        ...ch,
        lessons: lessons.rows.filter(l => l.chapter_id === ch.id)
      }))
  }));
}

// =============================================================================
// Announcements
// =============================================================================

export async function getPublishedAnnouncements(limit = 10) {
  const result = await pool.query(
    `SELECT id, title, summary, link, image_url, pinned, author_id, created_at, source,
            content_html IS NOT NULL AND content_html != '' AS has_content
     FROM announcements
     WHERE published = true
     ORDER BY pinned DESC, created_at DESC
     LIMIT $1`,
    [limit]
  );
  return result.rows;
}

export async function getSteamNewsCount() {
  const result = await pool.query(
    `SELECT COUNT(*)::int AS count FROM announcements WHERE source = 'steam'`
  );
  return result.rows[0].count;
}

export async function upsertSteamNews({ title, summary, link, content_html, source_id, created_at }) {
  const result = await pool.query(
    `INSERT INTO announcements (title, summary, link, content_html, source, source_id, published, created_at)
     VALUES ($1, $2, $3, $4, 'steam', $5, true, $6)
     ON CONFLICT (source, source_id) WHERE source_id IS NOT NULL
     DO UPDATE SET title = EXCLUDED.title, summary = EXCLUDED.summary,
       content_html = EXCLUDED.content_html, link = EXCLUDED.link
     RETURNING id`,
    [title, summary, link, content_html, source_id, created_at]
  );
  return result.rows[0];
}

export async function getAnnouncementsAdmin(page = 1, limit = 20) {
  const offset = (page - 1) * limit;
  const [dataResult, countResult] = await Promise.all([
    pool.query(
      `SELECT a.*, u.global_name AS author_name
       FROM announcements a
       LEFT JOIN users u ON u.id = a.author_id
       ORDER BY a.source ASC, a.created_at DESC
       LIMIT $1 OFFSET $2`,
      [limit, offset]
    ),
    pool.query('SELECT COUNT(*)::int AS total FROM announcements')
  ]);
  return { announcements: dataResult.rows, total: countResult.rows[0].total, page, limit };
}

export async function getAnnouncementById(id) {
  const result = await pool.query('SELECT * FROM announcements WHERE id = $1', [id]);
  return result.rows[0] || null;
}

export async function getPublishedAnnouncementById(id) {
  const result = await pool.query(
    `SELECT a.*, u.global_name AS author_name
     FROM announcements a
     LEFT JOIN users u ON u.id = a.author_id
     WHERE a.id = $1 AND a.published = true`,
    [id]
  );
  return result.rows[0] || null;
}

export async function createAnnouncement({ title, summary, link, image_url, pinned, published, author_id, content_html }) {
  const result = await pool.query(
    `INSERT INTO announcements (title, summary, link, image_url, pinned, published, author_id, content_html)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING *`,
    [title, summary || null, link || null, image_url || null, pinned || false, published || false, author_id, content_html || null]
  );
  return result.rows[0];
}

export async function updateAnnouncement(id, fields) {
  const allowedFields = ['title', 'summary', 'link', 'image_url', 'pinned', 'published', 'content_html'];
  const sets = [];
  const values = [];
  let paramIndex = 1;

  for (const key of allowedFields) {
    if (key in fields) {
      sets.push(`${key} = $${paramIndex++}`);
      values.push(fields[key]);
    }
  }
  if (sets.length === 0) return null;
  sets.push('updated_at = CURRENT_TIMESTAMP');
  values.push(id);

  const result = await pool.query(
    `UPDATE announcements SET ${sets.join(', ')} WHERE id = $${paramIndex} RETURNING *`,
    values
  );
  return result.rows[0] || null;
}

export async function deleteAnnouncement(id) {
  const result = await pool.query('DELETE FROM announcements WHERE id = $1 RETURNING id', [id]);
  return result.rowCount > 0;
}

// =============================================================================
// Events
// =============================================================================

export async function getUpcomingEvents(limit = 5) {
  const result = await pool.query(
    `SELECT e.id, e.title, e.description, e.start_date, e.end_date,
            e.location, e.type, e.link, e.image_url,
            u.global_name AS submitted_by_name
     FROM events e
     LEFT JOIN users u ON u.id = e.submitted_by
     WHERE e.state = 'approved'
       AND (e.start_date >= NOW() - INTERVAL '1 day'
            OR (e.end_date IS NOT NULL AND e.end_date >= NOW()))
     ORDER BY e.start_date ASC
     LIMIT $1`,
    [limit]
  );
  return result.rows;
}

export async function getPastEvents(limit = 50) {
  const result = await pool.query(
    `SELECT e.id, e.title, e.description, e.start_date, e.end_date,
            e.location, e.type, e.link, e.image_url,
            u.global_name AS submitted_by_name
     FROM events e
     LEFT JOIN users u ON u.id = e.submitted_by
     WHERE e.state = 'approved'
       AND (
         (e.end_date IS NOT NULL AND e.end_date < NOW())
         OR (e.end_date IS NULL AND e.start_date < NOW() - INTERVAL '1 day')
       )
     ORDER BY e.start_date DESC
     LIMIT $1`,
    [limit]
  );
  return result.rows;
}

export async function getEventsAdmin(page = 1, limit = 20, state = null) {
  const offset = (page - 1) * limit;
  const params = [limit, offset];
  let where = '';
  if (state) {
    where = 'WHERE e.state = $3';
    params.push(state);
  }
  const countWhere = state ? 'WHERE state = $1' : '';
  const countParams = state ? [state] : [];

  const [dataResult, countResult] = await Promise.all([
    pool.query(
      `SELECT e.*, u.global_name AS submitted_by_name, a.global_name AS approved_by_name
       FROM events e
       LEFT JOIN users u ON u.id = e.submitted_by
       LEFT JOIN users a ON a.id = e.approved_by
       ${where}
       ORDER BY e.created_at DESC
       LIMIT $1 OFFSET $2`,
      params
    ),
    pool.query(`SELECT COUNT(*)::int AS total FROM events ${countWhere}`, countParams)
  ]);
  return { events: dataResult.rows, total: countResult.rows[0].total, page, limit };
}

export async function getEventById(id) {
  const result = await pool.query(
    `SELECT e.*, u.global_name AS submitted_by_name, a.global_name AS approved_by_name
     FROM events e
     LEFT JOIN users u ON u.id = e.submitted_by
     LEFT JOIN users a ON a.id = e.approved_by
     WHERE e.id = $1`,
    [id]
  );
  return result.rows[0] || null;
}

export async function createEvent({ title, description, start_date, end_date, location, type, link, image_url, submitted_by }) {
  const result = await pool.query(
    `INSERT INTO events (title, description, start_date, end_date, location, type, link, image_url, submitted_by)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING *`,
    [title, description || null, start_date, end_date || null, location || null, type || 'player_run', link || null, image_url || null, submitted_by]
  );
  return result.rows[0];
}

export async function updateEventState(id, state, approved_by, admin_note = null) {
  const result = await pool.query(
    `UPDATE events SET state = $1, approved_by = $2, admin_note = $3, updated_at = CURRENT_TIMESTAMP
     WHERE id = $4 RETURNING *`,
    [state, approved_by, admin_note, id]
  );
  return result.rows[0] || null;
}

export async function updateEvent(id, fields) {
  const allowedFields = ['title', 'description', 'start_date', 'end_date', 'location', 'type', 'link', 'image_url'];
  const sets = [];
  const values = [];
  let paramIndex = 1;

  for (const key of allowedFields) {
    if (key in fields) {
      sets.push(`${key} = $${paramIndex++}`);
      values.push(fields[key]);
    }
  }
  if (sets.length === 0) return null;
  sets.push('updated_at = CURRENT_TIMESTAMP');
  values.push(id);

  const result = await pool.query(
    `UPDATE events SET ${sets.join(', ')} WHERE id = $${paramIndex} RETURNING *`,
    values
  );
  return result.rows[0] || null;
}

export async function deleteEvent(id) {
  const result = await pool.query('DELETE FROM events WHERE id = $1 RETURNING id', [id]);
  return result.rowCount > 0;
}

export async function countPendingEventsByUser(userId) {
  const result = await pool.query(
    "SELECT COUNT(*)::int AS count FROM events WHERE submitted_by = $1 AND state = 'pending'",
    [userId]
  );
  return result.rows[0].count;
}

// =============================================================================
// Content Creators
// =============================================================================

export async function getActiveCreators() {
  const result = await pool.query(
    `SELECT id, name, platform, channel_id, channel_url, description,
            avatar_url, display_order, cached_data, cached_at
     FROM content_creators
     WHERE active = true
     ORDER BY display_order ASC, name ASC`
  );
  return result.rows;
}

export async function getCreatorsAdmin() {
  const result = await pool.query(
    `SELECT cc.*, u.global_name AS added_by_name
     FROM content_creators cc
     LEFT JOIN users u ON u.id = cc.added_by
     ORDER BY cc.display_order ASC, cc.name ASC`
  );
  return result.rows;
}

export async function getCreatorById(id) {
  const result = await pool.query('SELECT * FROM content_creators WHERE id = $1', [id]);
  return result.rows[0] || null;
}

export async function createCreator({ name, platform, channel_id, channel_url, description, avatar_url, active, display_order, added_by, youtube_playlist_id }) {
  const result = await pool.query(
    `INSERT INTO content_creators (name, platform, channel_id, channel_url, description, avatar_url, active, display_order, added_by, youtube_playlist_id)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) RETURNING *`,
    [name, platform, channel_id || null, channel_url, description || null, avatar_url || null, active !== false, display_order || 0, added_by, youtube_playlist_id || null]
  );
  return result.rows[0];
}

export async function updateCreator(id, fields) {
  const allowedFields = ['name', 'platform', 'channel_id', 'channel_url', 'description', 'avatar_url', 'active', 'display_order', 'cached_data', 'cached_at', 'youtube_playlist_id'];
  const sets = [];
  const values = [];
  let paramIndex = 1;

  for (const key of allowedFields) {
    if (key in fields) {
      sets.push(`${key} = $${paramIndex++}`);
      values.push(key === 'cached_data' ? JSON.stringify(fields[key]) : fields[key]);
    }
  }
  if (sets.length === 0) return null;
  sets.push('updated_at = CURRENT_TIMESTAMP');
  values.push(id);

  const result = await pool.query(
    `UPDATE content_creators SET ${sets.join(', ')} WHERE id = $${paramIndex} RETURNING *`,
    values
  );
  return result.rows[0] || null;
}

export async function deleteCreator(id) {
  const result = await pool.query('DELETE FROM content_creators WHERE id = $1 RETURNING id', [id]);
  return result.rowCount > 0;
}

export async function getCreatorsForRefresh() {
  const result = await pool.query(
    `SELECT * FROM content_creators
     WHERE active = true
       AND platform != 'kick'
       AND (cached_at IS NULL OR cached_at < NOW() - INTERVAL '3 minutes')
     ORDER BY cached_at ASC NULLS FIRST
     LIMIT 10`
  );
  return result.rows;
}

// ─── Contributor Rewards ────────────────────────────────────────────

export async function getRewardRules() {
  const result = await pool.query(
    'SELECT * FROM reward_rules ORDER BY sort_order, id'
  );
  return result.rows;
}

export async function getActiveRewardRules() {
  const result = await pool.query(
    'SELECT * FROM reward_rules WHERE active = true ORDER BY sort_order, id'
  );
  return result.rows;
}

export async function createRewardRule({ name, description, category, entities, change_type, data_fields, min_amount, max_amount, contribution_score, sort_order }) {
  const result = await pool.query(
    `INSERT INTO reward_rules (name, description, category, entities, change_type, data_fields, min_amount, max_amount, contribution_score, sort_order)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
     RETURNING *`,
    [name, description || null, category || null, entities || null, change_type || null, data_fields || null, min_amount, max_amount, contribution_score || null, sort_order || 0]
  );
  return result.rows[0];
}

export async function updateRewardRule(id, fields) {
  const sets = [];
  const values = [];
  let paramIndex = 1;

  const allowed = ['name', 'description', 'category', 'entities', 'change_type', 'data_fields', 'min_amount', 'max_amount', 'contribution_score', 'active', 'sort_order'];
  for (const key of allowed) {
    if (key in fields) {
      sets.push(`${key} = $${paramIndex++}`);
      values.push(fields[key]);
    }
  }

  if (sets.length === 0) return null;
  values.push(id);

  const result = await pool.query(
    `UPDATE reward_rules SET ${sets.join(', ')} WHERE id = $${paramIndex} RETURNING *`,
    values
  );
  return result.rows[0] || null;
}

export async function deleteRewardRule(id) {
  const result = await pool.query('DELETE FROM reward_rules WHERE id = $1 RETURNING id', [id]);
  return result.rowCount > 0;
}

export async function getMatchingRules(entity, changeType, dataKeys, subType) {
  const result = await pool.query(
    'SELECT * FROM reward_rules WHERE active = true ORDER BY sort_order, id'
  );
  return result.rows.filter(rule => {
    if (rule.entities) {
      const matchesEntity = rule.entities.includes(entity) || (subType && rule.entities.includes(subType));
      if (!matchesEntity) return false;
    }
    if (rule.change_type && rule.change_type !== changeType) return false;
    if (rule.data_fields?.length) {
      if (!Array.isArray(dataKeys) || !rule.data_fields.some(f => dataKeys.includes(f))) return false;
    }
    return true;
  });
}

export async function getChangeRewards(changeId) {
  const result = await pool.query(
    `SELECT cr.*, rr.name as rule_name, u.global_name as assigned_by_name
     FROM contributor_rewards cr
     LEFT JOIN reward_rules rr ON cr.rule_id = rr.id
     LEFT JOIN users u ON cr.assigned_by = u.id
     WHERE cr.change_id = $1
     ORDER BY cr.created_at DESC, cr.id DESC`,
    [changeId]
  );
  return result.rows;
}

export async function getChangeReward(changeId) {
  const rewards = await getChangeRewards(changeId);
  return rewards[0] || null;
}

export async function assignReward({ change_id, user_id, rule_id, amount, contribution_score, note, assigned_by }) {
  const result = await pool.query(
    `INSERT INTO contributor_rewards (change_id, user_id, rule_id, amount, contribution_score, note, assigned_by)
     VALUES ($1, $2, $3, $4, $5, $6, $7)
     RETURNING *`,
    [change_id, user_id, rule_id || null, amount, contribution_score || null, note || null, assigned_by]
  );
  // Update pre-calculated reward_score on user
  const score = parseFloat(contribution_score) || 0;
  if (score > 0) {
    await pool.query('UPDATE ONLY users SET reward_score = reward_score + $1 WHERE id = $2', [score, user_id]);
  }
  return result.rows[0];
}

export async function removeReward(rewardId) {
  // Read the reward's contribution_score before deleting to decrement user's reward_score
  const reward = await pool.query('SELECT user_id, contribution_score FROM contributor_rewards WHERE id = $1', [rewardId]);
  const result = await pool.query('DELETE FROM contributor_rewards WHERE id = $1 RETURNING id', [rewardId]);
  if (result.rowCount > 0 && reward.rows[0]) {
    const score = parseFloat(reward.rows[0].contribution_score) || 0;
    if (score > 0) {
      await pool.query('UPDATE ONLY users SET reward_score = GREATEST(reward_score - $1, 0) WHERE id = $2', [score, reward.rows[0].user_id]);
    }
  }
  return result.rowCount > 0;
}

export async function getContributorBalances(page = 1, limit = 50, search = null) {
  const offset = (page - 1) * limit;
  const params = [limit, offset];
  let searchClause = '';
  if (search) {
    params.push(`%${search}%`);
    searchClause = `AND (u.global_name ILIKE $3 OR u.eu_name ILIKE $3)`;
  }

  const query = `
    SELECT
      u.id, u.global_name, u.eu_name, u.avatar,
      COALESCE((SELECT COUNT(*) FROM changes c WHERE c.author_id = u.id AND c.state = 'Approved'), 0) as approved_count,
      COALESCE((SELECT COUNT(*) FROM contributor_rewards cr WHERE cr.user_id = u.id), 0) as rewarded_count,
      COALESCE((SELECT SUM(cr.amount) FROM contributor_rewards cr WHERE cr.user_id = u.id), 0) as total_earned,
      COALESCE((SELECT SUM(cr.contribution_score) FROM contributor_rewards cr WHERE cr.user_id = u.id), 0) as total_score,
      COALESCE((SELECT SUM(cp.amount) FROM contributor_payouts cp WHERE cp.user_id = u.id), 0) as total_paid
    FROM users u
    WHERE (
      EXISTS (SELECT 1 FROM changes c3 WHERE c3.author_id = u.id AND c3.state = 'Approved')
      OR
      EXISTS (SELECT 1 FROM contributor_rewards cr2 WHERE cr2.user_id = u.id)
      OR EXISTS (SELECT 1 FROM contributor_payouts cp2 WHERE cp2.user_id = u.id)
    )
    ${searchClause}
    ORDER BY total_earned DESC, approved_count DESC
    LIMIT $1 OFFSET $2
  `;

  const countQuery = `
    SELECT COUNT(DISTINCT u.id) as total
    FROM users u
    WHERE (
      EXISTS (SELECT 1 FROM changes c3 WHERE c3.author_id = u.id AND c3.state = 'Approved')
      OR
      EXISTS (SELECT 1 FROM contributor_rewards cr2 WHERE cr2.user_id = u.id)
      OR EXISTS (SELECT 1 FROM contributor_payouts cp2 WHERE cp2.user_id = u.id)
    )
    ${search ? `AND (u.global_name ILIKE $1 OR u.eu_name ILIKE $1)` : ''}
  `;

  const [dataResult, countResult] = await Promise.all([
    pool.query(query, params),
    pool.query(countQuery, search ? [`%${search}%`] : [])
  ]);

  return {
    contributors: dataResult.rows,
    total: parseInt(countResult.rows[0]?.total || 0),
    page,
    totalPages: Math.ceil(parseInt(countResult.rows[0]?.total || 0) / limit)
  };
}

export async function getContributorDetail(userId) {
  const [rewardsResult, payoutsResult, userResult, eligibleChangesResult] = await Promise.all([
    pool.query(
      `SELECT cr.*, rr.name as rule_name, c.entity, c.type, c.data->>'Name' as entity_name,
              ua.global_name as assigned_by_name
       FROM contributor_rewards cr
       LEFT JOIN reward_rules rr ON cr.rule_id = rr.id
       LEFT JOIN changes c ON cr.change_id = c.id
       LEFT JOIN users ua ON cr.assigned_by = ua.id
       WHERE cr.user_id = $1
       ORDER BY cr.created_at DESC`,
      [userId]
    ),
    pool.query(
      `SELECT cp.*, ua.global_name as created_by_name
       FROM contributor_payouts cp
       LEFT JOIN users ua ON cp.created_by = ua.id
       WHERE cp.user_id = $1
       ORDER BY cp.created_at DESC`,
      [userId]
    ),
    pool.query(
      'SELECT id, global_name, eu_name, avatar FROM users WHERE id = $1',
      [userId]
    ),
    pool.query(
      `SELECT
         c.id,
         c.entity,
         c.type,
         c.data->>'Name' as entity_name,
         c.data->>'Id' as entity_id,
         c.created_at,
         c.last_update
       FROM changes c
       WHERE c.author_id = $1
         AND c.state = 'Approved'
         AND NOT EXISTS (
           SELECT 1
           FROM contributor_rewards cr
           WHERE cr.change_id = c.id
         )
       ORDER BY c.last_update DESC NULLS LAST, c.created_at DESC
       LIMIT 250`,
      [userId]
    )
  ]);

  return {
    user: userResult.rows[0] || null,
    rewards: rewardsResult.rows,
    payouts: payoutsResult.rows,
    eligible_changes: eligibleChangesResult.rows
  };
}

export async function getPayouts(page = 1, limit = 50, filters = {}) {
  const offset = (page - 1) * limit;
  const params = [limit, offset];
  const conditions = [];
  let paramIndex = 3;

  if (filters.status) {
    conditions.push(`cp.status = $${paramIndex++}`);
    params.push(filters.status);
  }
  if (filters.user_id) {
    conditions.push(`cp.user_id = $${paramIndex++}`);
    params.push(filters.user_id);
  }

  const whereClause = conditions.length ? `WHERE ${conditions.join(' AND ')}` : '';

  const query = `
    SELECT cp.*, u.global_name, u.eu_name, u.avatar, ua.global_name as created_by_name
    FROM contributor_payouts cp
    LEFT JOIN users u ON cp.user_id = u.id
    LEFT JOIN users ua ON cp.created_by = ua.id
    ${whereClause}
    ORDER BY cp.created_at DESC
    LIMIT $1 OFFSET $2
  `;

  const countQuery = `
    SELECT COUNT(*) as total FROM contributor_payouts cp ${whereClause}
  `;

  const countParams = params.slice(2);
  const [dataResult, countResult] = await Promise.all([
    pool.query(query, params),
    pool.query(countQuery, countParams)
  ]);

  return {
    payouts: dataResult.rows,
    total: parseInt(countResult.rows[0]?.total || 0),
    page,
    totalPages: Math.ceil(parseInt(countResult.rows[0]?.total || 0) / limit)
  };
}

export async function createPayout({ user_id, amount, is_bonus, note, created_by }) {
  const result = await pool.query(
    `INSERT INTO contributor_payouts (user_id, amount, is_bonus, note, created_by)
     VALUES ($1, $2, $3, $4, $5)
     RETURNING *`,
    [user_id, amount, is_bonus || false, note || null, created_by]
  );
  return result.rows[0];
}

export async function completePayout(id) {
  const result = await pool.query(
    `UPDATE contributor_payouts SET status = 'completed', completed_at = CURRENT_TIMESTAMP
     WHERE id = $1 AND status = 'pending'
     RETURNING *`,
    [id]
  );
  return result.rows[0] || null;
}

// =============================================
// MARKET PRICE SNAPSHOTS
// =============================================

// In-memory cache for market price queries.
// Confirmed (finalized, older than 2h) entries: 1 hour TTL.
// Pending (recent/unfinalized) entries: 1 minute TTL — can still change.
const MPS_CACHE_TTL_CONFIRMED = 60 * 60 * 1000; // 1 hour
const MPS_CACHE_TTL_PENDING = 60 * 1000;          // 1 minute
const MPS_CACHE_MAX = 500;
const MPS_PENDING_THRESHOLD_MS = 2 * 60 * 60 * 1000; // 2 hours
const mpsCache = new Map();

function mpsCacheGet(key) {
  const entry = mpsCache.get(key);
  if (!entry) return undefined;
  if (Date.now() - entry.ts > entry.ttl) {
    mpsCache.delete(key);
    return undefined;
  }
  return entry.data;
}

/**
 * Check whether any row in the result set is still pending confirmation.
 * A row is pending if its recorded_at is within the last 2 hours (it may
 * still receive new submissions or be re-finalized).
 */
function mpsHasPendingRows(data) {
  const cutoff = Date.now() - MPS_PENDING_THRESHOLD_MS;
  const rows = Array.isArray(data) ? data : (data ? [data] : []);
  return rows.some(r => {
    const recAt = r.recorded_at ? new Date(r.recorded_at).getTime() : 0;
    return recAt > cutoff;
  });
}

function mpsCacheSet(key, data) {
  if (mpsCache.size >= MPS_CACHE_MAX) {
    const keys = [...mpsCache.keys()];
    for (let i = 0; i < keys.length / 2; i++) mpsCache.delete(keys[i]);
  }
  const ttl = mpsHasPendingRows(data) ? MPS_CACHE_TTL_PENDING : MPS_CACHE_TTL_CONFIRMED;
  mpsCache.set(key, { data, ts: Date.now(), ttl });
}

/** Invalidate cache entries for a specific item (called after finalization). */
export function invalidateMarketPriceCache(itemId) {
  for (const key of mpsCache.keys()) {
    if (key.startsWith(`mps:${itemId}:`) || key.startsWith('mps-latest:') || key.startsWith('mps-name:') || key === 'mps-all') {
      mpsCache.delete(key);
    }
  }
}

export async function getMarketPriceSnapshots(itemId, { from, to, limit = 100 } = {}) {
  const cacheKey = `mps:${itemId}:${from || ''}:${to || ''}:${limit}`;
  const cached = mpsCacheGet(cacheKey);
  if (cached) return cached;

  const conditions = ['item_id = $1'];
  const values = [itemId];
  let idx = 2;

  if (from) {
    conditions.push(`recorded_at >= $${idx}`);
    values.push(from);
    idx++;
  }
  if (to) {
    conditions.push(`recorded_at <= $${idx}`);
    values.push(to);
    idx++;
  }

  const { rows } = await pool.query(
    `SELECT * FROM ONLY market_price_snapshots
     WHERE ${conditions.join(' AND ')}
     ORDER BY recorded_at DESC
     LIMIT $${idx}`,
    [...values, Math.min(limit, 1000)]
  );
  mpsCacheSet(cacheKey, rows);
  return rows;
}

export async function getLatestMarketPrices(itemIds) {
  if (!itemIds.length) return [];
  const sorted = [...itemIds].sort((a, b) => a - b);
  const cacheKey = `mps-latest:${sorted.join(',')}`;
  const cached = mpsCacheGet(cacheKey);
  if (cached) return cached;

  const { rows } = await pool.query(
    `SELECT DISTINCT ON (item_id)
       id, item_name, item_id, tier,
       markup_1d, sales_1d, markup_7d, sales_7d,
       markup_30d, sales_30d, markup_365d, sales_365d,
       markup_3650d, sales_3650d, recorded_at,
       confidence, finalized_at, submission_count, manually_reviewed
     FROM ONLY market_price_snapshots
     WHERE item_id = ANY($1)
     ORDER BY item_id, recorded_at DESC`,
    [sorted]
  );
  mpsCacheSet(cacheKey, rows);
  return rows;
}

/**
 * Find latest snapshot by name (unresolved entries) or item_id (resolved).
 * Pass itemId when the caller can resolve name→id from the item cache.
 */
export async function getLatestMarketPriceByName(name, itemId = null) {
  const cacheKey = `mps-name:${name.toLowerCase()}:${itemId || ''}`;
  const cached = mpsCacheGet(cacheKey);
  if (cached !== undefined) return cached;

  const { rows } = await pool.query(
    `SELECT * FROM ONLY market_price_snapshots
     WHERE (
       ($2::int IS NOT NULL AND item_id = $2)
       OR (item_id IS NULL AND LOWER(item_name) = LOWER($1))
     )
     ORDER BY recorded_at DESC
     LIMIT 1`,
    [name, itemId]
  );
  const result = rows[0] || null;
  mpsCacheSet(cacheKey, result);
  return result;
}

/**
 * Get latest snapshot per item, combining resolved (by item_id) and
 * unresolved (by item_name) entries.
 */
export async function getAllLatestMarketPrices() {
  const cached = mpsCacheGet('mps-all');
  if (cached) return cached;

  const { rows } = await pool.query(
    `SELECT * FROM (
       (SELECT DISTINCT ON (item_id)
          id, item_name, item_id, tier,
          markup_1d, sales_1d, markup_7d, sales_7d,
          markup_30d, sales_30d, markup_365d, sales_365d,
          markup_3650d, sales_3650d, recorded_at,
          confidence, finalized_at, submission_count, manually_reviewed
        FROM ONLY market_price_snapshots
        WHERE item_id IS NOT NULL
        ORDER BY item_id, recorded_at DESC)
       UNION ALL
       (SELECT DISTINCT ON (LOWER(item_name))
          id, item_name, item_id, tier,
          markup_1d, sales_1d, markup_7d, sales_7d,
          markup_30d, sales_30d, markup_365d, sales_365d,
          markup_3650d, sales_3650d, recorded_at,
          confidence, finalized_at, submission_count, manually_reviewed
        FROM ONLY market_price_snapshots
        WHERE item_id IS NULL AND item_name IS NOT NULL
        ORDER BY LOWER(item_name), recorded_at DESC)
     ) combined
     ORDER BY recorded_at DESC
     LIMIT 10000`
  );
  mpsCacheSet('mps-all', rows);
  return rows;
}

export async function getRewardsSummary() {
  const result = await pool.query(`
    SELECT
      COALESCE((SELECT SUM(amount) FROM contributor_rewards), 0) as total_earned,
      COALESCE((SELECT SUM(amount) FROM contributor_payouts), 0) as total_paid,
      COALESCE((SELECT SUM(amount) FROM contributor_payouts WHERE status = 'pending'), 0) as total_pending,
      COALESCE((SELECT COUNT(*) FROM contributor_rewards), 0) as reward_count,
      COALESCE((SELECT COUNT(*) FROM contributor_payouts WHERE status = 'pending'), 0) as pending_payout_count,
      COALESCE((SELECT SUM(contribution_score) FROM contributor_rewards), 0) as total_score
  `);
  return result.rows[0];
}
