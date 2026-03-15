import dotenv from 'dotenv';
import pg from 'pg';

dotenv.config();

const Pool = pg.Pool;

export const poolUsers = new Pool({
  connectionString: process.env.POSTGRES_USERS_CONNECTION_STRING,
});

const poolNexus = new Pool({
  connectionString: process.env.POSTGRES_NEXUS_CONNECTION_STRING,
});

export async function startUsersTransaction() {
  const client = await poolUsers.connect();
  await client.query('BEGIN');
  return client;
}
export async function startNexusTransaction() {
  const client = await poolNexus.connect();
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
export async function createUser(user) {
  const query = 'INSERT INTO users (id, username, global_name, discriminator, avatar) VALUES ($1, $2, $3, $4, $5) RETURNING *';
  const values = [user.id, user.username, user.global_name, user.discriminator, user.avatar];
  return (await poolUsers.query(query, values)).rows[0];
}
export async function getUsers() {
  return (await poolUsers.query('SELECT * FROM users')).rows;
}
export async function getUserById(id) {
  const query = 'SELECT * FROM users WHERE id = $1';
  const values = [id];
  return (await poolUsers.query(query, values)).rows[0];
}
export async function getUserByUsername(username) {
  const query = 'SELECT * FROM users WHERE username = $1';
  const values = [username];
  return (await poolUsers.query(query, values)).rows[0];
}
export async function setUserEuName(id, euName) {
  const query = 'UPDATE users SET eu_name = $2 WHERE id = $1';
  const values = [id, euName];
  await poolUsers.query(query, values);
}
export async function setUserVerified(id, verified) {
  const query = 'UPDATE users SET verified = $2 WHERE id = $1';
  const values = [id, verified];
  await poolUsers.query(query, values);
}
export async function assignUserRole(userId) {
  await poolUsers.query(
    `INSERT INTO user_roles (user_id, role_id)
     SELECT $1, r.id FROM roles r WHERE r.name = 'user'
     ON CONFLICT DO NOTHING`,
    [userId]
  );
}
export async function getUsersWithGrant(grantKey) {
  const query = `
    WITH RECURSIVE role_hierarchy AS (
      SELECT ur.user_id, r.id AS role_id, r.name AS role_name, r.parent_id, 1 AS depth
      FROM user_roles ur
      JOIN roles r ON r.id = ur.role_id

      UNION ALL

      SELECT rh.user_id, r.id, r.name, r.parent_id, rh.depth + 1
      FROM role_hierarchy rh
      JOIN roles r ON r.id = rh.parent_id
      WHERE rh.depth < 10
    ),
    admin_users AS (
      SELECT DISTINCT user_id FROM role_hierarchy WHERE role_name = 'admin'
    ),
    role_grant_users AS (
      SELECT DISTINCT rh.user_id
      FROM role_hierarchy rh
      JOIN role_grants rg ON rg.role_id = rh.role_id
      JOIN grants g ON g.id = rg.grant_id
      WHERE g.key = $1 AND rg.granted = true
    ),
    direct_grant_users AS (
      SELECT ug.user_id, ug.granted
      FROM user_grants ug
      JOIN grants g ON g.id = ug.grant_id
      WHERE g.key = $1
    )
    SELECT DISTINCT u.id
    FROM users u
    WHERE (
      u.id IN (SELECT user_id FROM admin_users)
      OR u.id IN (SELECT user_id FROM role_grant_users)
      OR u.id IN (SELECT user_id FROM direct_grant_users WHERE granted = true)
    )
    AND u.id NOT IN (
      SELECT user_id FROM direct_grant_users WHERE granted = false
    )
  `;
  return (await poolUsers.query(query, [grantKey])).rows.map(r => r.id);
}
export async function getChanges() {
  return (await poolUsers.query('SELECT * FROM changes')).rows;
}
export async function getOpenChanges(date) {
  // Use content_updated_at to only pick up changes where actual content was modified
  // This prevents duplicate notifications when only admin fields (thread_id, etc.) change
  // DirectApply: admin pass-through changes that skip review and get applied immediately
  return (await poolUsers.query('SELECT * FROM changes WHERE state IN (\'Draft\', \'Pending\', \'DirectApply\') AND content_updated_at > $1', [date.toISOString()])).rows;
}
export async function getDeletedChanges() {
  return (await poolUsers.query('SELECT * FROM changes WHERE state = \'Deleted\'')).rows;
}
export async function deleteChange(id) {
  await poolUsers.query('DELETE FROM changes WHERE id = $1', [id]);
}
export async function deleteChanges(ids) {
  await poolUsers.query('DELETE FROM changes WHERE id = ANY($1)', [ids]);
}
export async function getChangeById(id) {
  return (await poolUsers.query('SELECT * FROM changes WHERE id = $1', [id])).rows[0];
}
export async function getChangeByThreadId(threadId) {
  const query = 'SELECT * FROM changes WHERE thread_id = $1';
  const values = [threadId];
  return (await poolUsers.query(query, values)).rows[0];
}
export async function setChangeThreadId(id, threadId) {
  const query = 'UPDATE changes SET thread_id = $2 WHERE id = $1';
  const values = [id, threadId];
  await poolUsers.query(query, values);
}
export async function setChangeState(id, state) {
  const query = 'UPDATE changes SET state = $2 WHERE id = $1';
  const values = [id, state];
  await poolUsers.query(query, values);
}

export async function setChangeDenied(id, reason = null) {
  await poolUsers.query(
    `UPDATE changes SET state = 'Denied', denial_reason = $2 WHERE id = $1`,
    [id, reason]
  );
}

// Reward functions
export async function getMatchingRewardRules(entity, changeType, dataKeys, subType) {
  const { rows } = await poolUsers.query(
    'SELECT * FROM reward_rules WHERE active = true ORDER BY sort_order, id'
  );
  return rows.filter(rule => {
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

export async function assignChangeReward({ change_id, user_id, rule_id, amount, contribution_score, assigned_by, note = null }) {
  // Auto-calculate contribution score: 2x PED amount, minimum 1, probabilistic rounding
  let score = contribution_score;
  if (score == null || score === 0) {
    const raw = Math.max(1, amount * 2);
    const base = Math.floor(raw);
    const decimal = raw - base;
    score = decimal > 0 && Math.random() < decimal ? base + 1 : base;
  }

  const { rows } = await poolUsers.query(
    `INSERT INTO contributor_rewards (change_id, user_id, rule_id, amount, contribution_score, note, assigned_by)
     VALUES ($1, $2, $3, $4, $5, $6, $7)
     ON CONFLICT (change_id, rule_id) DO NOTHING
     RETURNING *`,
    [change_id, user_id, rule_id, amount, score, note || 'Auto-assigned on approval', assigned_by]
  );
  if (!rows[0]) return null;
  if (score > 0) {
    await poolUsers.query(
      'UPDATE users SET reward_score = reward_score + $1 WHERE id = $2',
      [score, user_id]
    );
  }
  return rows[0];
}

export async function getContributorBalance(userId) {
  const [rewardsResult, payoutsResult] = await Promise.all([
    poolUsers.query(
      `SELECT COALESCE(SUM(amount), 0) as total_earned,
              COALESCE(SUM(contribution_score), 0) as total_score
       FROM contributor_rewards WHERE user_id = $1`,
      [userId]
    ),
    poolUsers.query(
      `SELECT COALESCE(SUM(amount), 0) as total_paid
       FROM contributor_payouts WHERE user_id = $1`,
      [userId]
    ),
  ]);
  const totalEarned = parseFloat(rewardsResult.rows[0].total_earned);
  const totalScore = parseFloat(rewardsResult.rows[0].total_score);
  const totalPaid = parseFloat(payoutsResult.rows[0].total_paid);
  return {
    total_earned: totalEarned,
    total_score: totalScore,
    total_paid: totalPaid,
    balance: totalEarned - totalPaid,
  };
}

export async function getRewardDmEnabled(userId) {
  const { rows } = await poolUsers.query(
    `SELECT data FROM user_preferences WHERE user_id = $1 AND key = 'rewards.dm_enabled'`,
    [userId]
  );
  if (!rows[0]) return true; // default: enabled
  return rows[0].data === true;
}

export async function setRewardDmEnabled(userId, enabled) {
  await poolUsers.query(
    `INSERT INTO user_preferences (user_id, key, data, updated_at)
     VALUES ($1, 'rewards.dm_enabled', $2::jsonb, NOW())
     ON CONFLICT (user_id, key) DO UPDATE SET data = $2::jsonb, updated_at = NOW()`,
    [userId, JSON.stringify(enabled)]
  );
}

// Shop functions
export async function getShopById(id) {
  const query = `
    SELECT 
      e."Id" as id,
      e."Name" as name,
      e."Description" as description,
      e."PlanetId" as planet_id,
      e."Longitude" as longitude,
      e."Latitude" as latitude,
      e."Altitude" as altitude,
      e."OwnerId" as owner_id,
      p."Name" as planet_name
    FROM "Estates" e
    LEFT JOIN "Planets" p ON e."PlanetId" = p."Id"
    WHERE e."Id" = $1 AND e."Type" = 'Shop'`;
  const values = [id];
  return (await poolNexus.query(query, values)).rows[0];
}

export async function getShopByName(name) {
  const query = `
    SELECT 
      e."Id" as id,
      e."Name" as name,
      e."Description" as description,
      e."PlanetId" as planet_id,
      e."Longitude" as longitude,
      e."Latitude" as latitude,
      e."Altitude" as altitude,
      e."OwnerId" as owner_id,
      p."Name" as planet_name
    FROM "Estates" e
    LEFT JOIN "Planets" p ON e."PlanetId" = p."Id"
    WHERE e."Name" ILIKE $1 AND e."Type" = 'Shop'
  `;
  const values = [name];
  const result = await poolNexus.query(query, values);
  return result.rows[0];
}

export async function updateShopOwner(shopId, ownerId) {
  const query = 'UPDATE "Estates" SET "OwnerId" = $2 WHERE "Id" = $1';
  const values = [shopId, ownerId];
  await poolNexus.query(query, values);
}

export async function addShopManager(shopId, userId) {
  const query = 'INSERT INTO shop_managers (shop_id, user_id) VALUES ($1, $2) ON CONFLICT DO NOTHING';
  const values = [shopId, userId];
  await poolNexus.query(query, values);
}

export async function removeShopManager(shopId, userId) {
  const query = 'DELETE FROM shop_managers WHERE shop_id = $1 AND user_id = $2';
  const values = [shopId, userId];
  await poolNexus.query(query, values);
}

export async function getShopManagers(shopId) {
  const query = `
    SELECT sm.*, u."Name" as username
    FROM shop_managers sm
    LEFT JOIN users u ON sm.user_id = u.id
    WHERE sm.shop_id = $1
  `;
  const values = [shopId];
  const result = await poolNexus.query(query, values);
  return result.rows;
}

export async function getUserShops(userId) {
  const query = `
    SELECT 
      e."Id" as id,
      e."Name" as name,
      e."Description" as description,
      e."PlanetId" as planet_id,
      e."Longitude" as longitude,
      e."Latitude" as latitude,
      e."Altitude" as altitude,
      e."OwnerId" as owner_id,
      p."Name" as planet_name
    FROM "Estates" e
    LEFT JOIN "Planets" p ON e."PlanetId" = p."Id"
    WHERE e."Type" = 'Shop' AND (e."OwnerId" = $1 OR e."Id" IN (
      SELECT shop_id FROM shop_managers WHERE user_id = $1
    ))
    ORDER BY e."Name"
  `;
  const values = [userId];
  const result = await poolNexus.query(query, values);
  return result.rows;
}
export async function getShops() {
  return (await poolNexus.query('SELECT e."Id" as id, e."Name" as name, e."Description" as description, e."PlanetId" as planet_id, e."Longitude" as longitude, e."Latitude" as latitude, e."Altitude" as altitude, e."OwnerId" as owner_id, p."Name" as planet_name FROM "Estates" e LEFT JOIN "Planets" p ON e."PlanetId" = p."Id" WHERE e."Type" = \'Shop\' ORDER BY e."Name"')).rows;
}

// ---- Flight Discord Integration ----

// Get flights that entered boarding/running state but don't have a Discord thread yet
export async function getFlightsNeedingThread() {
  const query = `
    SELECT fi.*, s.title as service_title, s.user_id as provider_user_id, s.owner_user_id,
           u.username as provider_username,
           COALESCE(
             (SELECT json_agg(json_build_object('user_id', sp.user_id, 'username', pu.username))
              FROM service_pilots sp
              JOIN users pu ON sp.user_id = pu.id
              WHERE sp.service_id = s.id),
             '[]'::json
           ) as pilots
    FROM service_flight_instances fi
    JOIN services s ON fi.service_id = s.id
    JOIN users u ON s.user_id = u.id
    LEFT JOIN service_transportation_details std ON std.service_id = s.id
    WHERE fi.status IN ('boarding', 'running')
      AND fi.discord_thread_id IS NULL
      AND (std.discord_code IS NULL OR std.discord_code = '')
  `;
  return (await poolUsers.query(query)).rows;
}

// Set the Discord thread ID for a flight
export async function setFlightThreadId(flightId, threadId) {
  const query = 'UPDATE service_flight_instances SET discord_thread_id = $2 WHERE id = $1';
  await poolUsers.query(query, [flightId, threadId]);
}

// Get accepted check-ins that haven't been added to Discord thread yet
export async function getCheckinsPendingThreadAdd() {
  const query = `
    SELECT c.*, fi.discord_thread_id, u.id as discord_user_id, u.username,
           fi.id as flight_id, fi.status as flight_status
    FROM service_checkins c
    JOIN service_flight_instances fi ON c.flight_id = fi.id
    JOIN users u ON c.user_id = u.id
    WHERE c.status = 'accepted'
      AND c.added_to_thread = false
      AND fi.discord_thread_id IS NOT NULL
  `;
  return (await poolUsers.query(query)).rows;
}

// Mark a check-in as added to the Discord thread
export async function markCheckinAddedToThread(checkinId) {
  const query = 'UPDATE service_checkins SET added_to_thread = true WHERE id = $1';
  await poolUsers.query(query, [checkinId]);
}

// Get recent flight state changes that haven't been notified yet
// We use a "notified" approach: state log entries newer than what we last checked
export async function getUnnotifiedFlightStateChanges(since) {
  const query = `
    SELECT fsl.*, fi.discord_thread_id, fi.route_stops, fi.service_id,
           fi.current_state, fi.current_stop_index, fi.route_type,
           s.title as service_title
    FROM service_flight_state_log fsl
    JOIN service_flight_instances fi ON fsl.flight_id = fi.id
    JOIN services s ON fi.service_id = s.id
    WHERE fsl.changed_at > $1
      AND fi.discord_thread_id IS NOT NULL
      AND fsl.undone = false
    ORDER BY fsl.changed_at ASC
  `;
  return (await poolUsers.query(query, [since])).rows;
}

// Get flights that completed or were cancelled and still have an active thread
export async function getFlightsNeedingArchive() {
  const query = `
    SELECT fi.*, s.title as service_title
    FROM service_flight_instances fi
    JOIN services s ON fi.service_id = s.id
    WHERE fi.status IN ('completed', 'cancelled')
      AND fi.discord_thread_id IS NOT NULL
  `;
  return (await poolUsers.query(query)).rows;
}

// Clear the Discord thread ID after archiving (so we don't re-process)
export async function clearFlightThreadId(flightId) {
  const query = 'UPDATE service_flight_instances SET discord_thread_id = NULL WHERE id = $1';
  await poolUsers.query(query, [flightId]);
}

// Get pending flight reschedule notifications
export async function getPendingRescheduleNotifications() {
  const query = `
    SELECT frn.*, u.username, u.id as discord_user_id
    FROM flight_reschedule_notifications frn
    JOIN users u ON frn.user_id = u.id
    WHERE frn.sent = false
    ORDER BY frn.created_at ASC
  `;
  return (await poolUsers.query(query)).rows;
}

// Mark a reschedule notification as sent
export async function markRescheduleNotificationSent(notificationId) {
  const query = 'UPDATE flight_reschedule_notifications SET sent = true WHERE id = $1';
  await poolUsers.query(query, [notificationId]);
}

// Get pending rental DM notifications
export async function getPendingRentalDmNotifications() {
  const query = `
    SELECT rdn.*, u.id AS discord_user_id
    FROM rental_dm_notifications rdn
    JOIN users u ON rdn.owner_id = u.id
    WHERE rdn.sent = false
    ORDER BY rdn.created_at ASC
  `;
  return (await poolUsers.query(query)).rows;
}

// Mark a rental DM notification as sent
export async function markRentalDmNotificationSent(notificationId) {
  const query = 'UPDATE rental_dm_notifications SET sent = true WHERE id = $1';
  await poolUsers.query(query, [notificationId]);
}

// Get pilots for a service
export async function getServicePilots(serviceId) {
  const query = `
    SELECT sp.user_id, u.username
    FROM service_pilots sp
    JOIN users u ON sp.user_id = u.id
    WHERE sp.service_id = $1
  `;
  return (await poolUsers.query(query, [serviceId])).rows;
}

// Get accepted check-ins for a flight (to kick customers later)
export async function getFlightAcceptedCheckins(flightId) {
  const query = `
    SELECT c.user_id, u.id as discord_user_id, u.username
    FROM service_checkins c
    JOIN users u ON c.user_id = u.id
    WHERE c.flight_id = $1 AND c.status IN ('accepted', 'completed')
  `;
  return (await poolUsers.query(query, [flightId])).rows;
}

// Get flights ready for customer kick (completed/cancelled 5+ minutes ago)
export async function getFlightsReadyForCustomerKick() {
  const query = `
    SELECT fi.*, s.title as service_title, s.user_id as provider_user_id
    FROM service_flight_instances fi
    JOIN services s ON fi.service_id = s.id
    WHERE fi.status IN ('completed', 'cancelled')
      AND fi.discord_thread_id IS NOT NULL
      AND fi.completed_at IS NOT NULL
      AND fi.completed_at < NOW() - INTERVAL '5 minutes'
  `;
  return (await poolUsers.query(query)).rows;
}

// Update flight completed_at timestamp
export async function setFlightCompletedAt(flightId) {
  const query = 'UPDATE service_flight_instances SET completed_at = NOW() WHERE id = $1 AND completed_at IS NULL';
  await poolUsers.query(query, [flightId]);
}

// Track route changes - get flights where route_stops changed recently
export async function getFlightsWithRouteChanges(since) {
  const query = `
    SELECT fi.*, s.title as service_title,
           fi.updated_at as route_changed_at
    FROM service_flight_instances fi
    JOIN services s ON fi.service_id = s.id
    WHERE fi.status = 'running'
      AND fi.route_type = 'flexible'
      AND fi.discord_thread_id IS NOT NULL
      AND fi.updated_at > $1
  `;
  return (await poolUsers.query(query, [since])).rows;
}

// Expire tickets past their valid_until date (run daily)
export async function expireTickets() {
  const query = `
    UPDATE service_tickets SET status = 'expired'
    WHERE status = 'active' AND valid_until IS NOT NULL AND valid_until < CURRENT_DATE
    RETURNING id
  `;
  const result = await poolUsers.query(query);
  return result.rows.length;
}

// Get config value
export async function getBotConfig(key) {
  const query = 'SELECT value FROM bot_config WHERE key = $1';
  const result = await poolUsers.query(query, [key]);
  return result.rows[0]?.value;
}

// Set config value
export async function setBotConfig(key, value) {
  const query = `
    INSERT INTO bot_config (key, value) VALUES ($1, $2)
    ON CONFLICT (key) DO UPDATE SET value = $2
  `;
  await poolUsers.query(query, [key, value]);
}

// ---- Content Creator Functions ----

export async function getActiveContentCreators() {
  const result = await poolUsers.query(
    `SELECT id, name, platform, channel_id, channel_url, cached_data
     FROM content_creators
     WHERE active = true`
  );
  return result.rows;
}

// ---- Trade Request Functions ----

export async function getPendingTradeRequests() {
  const query = `
    SELECT tr.*,
           ru.eu_name AS requester_name, ru.username AS requester_username,
           tu.eu_name AS target_name, tu.username AS target_username
    FROM trade_requests tr
    LEFT JOIN users ru ON ru.id = tr.requester_id
    LEFT JOIN users tu ON tu.id = tr.target_id
    WHERE tr.status = 'pending'
    ORDER BY tr.created_at ASC
  `;
  return (await poolUsers.query(query)).rows;
}

export async function getTradeRequestItems(requestId) {
  const query = `
    SELECT * FROM trade_request_items
    WHERE trade_request_id = $1
    ORDER BY added_at ASC
  `;
  return (await poolUsers.query(query, [requestId])).rows;
}

export async function getNewTradeRequestItems(requestId, since) {
  const query = `
    SELECT * FROM trade_request_items
    WHERE trade_request_id = $1 AND added_at > $2
    ORDER BY added_at ASC
  `;
  return (await poolUsers.query(query, [requestId, since])).rows;
}

export async function setTradeRequestThread(requestId, threadId) {
  const query = `
    UPDATE trade_requests
    SET discord_thread_id = $2, status = 'active'
    WHERE id = $1
  `;
  await poolUsers.query(query, [requestId, threadId]);
}

export async function getWarnableTradeRequests() {
  const query = `
    SELECT tr.*,
           ru.eu_name AS requester_name,
           tu.eu_name AS target_name
    FROM trade_requests tr
    LEFT JOIN users ru ON ru.id = tr.requester_id
    LEFT JOIN users tu ON tu.id = tr.target_id
    WHERE tr.status = 'active'
      AND tr.warning_sent = false
      AND tr.last_activity_at < NOW() - INTERVAL '18 hours'
  `;
  return (await poolUsers.query(query)).rows;
}

export async function markWarningSent(requestId) {
  await poolUsers.query(
    'UPDATE trade_requests SET warning_sent = true WHERE id = $1',
    [requestId]
  );
}

export async function getExpirableTradeRequests() {
  const query = `
    SELECT tr.*, ru.eu_name AS requester_name, tu.eu_name AS target_name
    FROM trade_requests tr
    LEFT JOIN users ru ON ru.id = tr.requester_id
    LEFT JOIN users tu ON tu.id = tr.target_id
    WHERE tr.status = 'active'
      AND tr.last_activity_at < NOW() - INTERVAL '24 hours'
  `;
  return (await poolUsers.query(query)).rows;
}

export async function updateTradeRequestStatus(requestId, status) {
  const closedAt = ['completed', 'cancelled', 'expired'].includes(status) ? 'NOW()' : 'NULL';
  await poolUsers.query(
    `UPDATE trade_requests SET status = $2, closed_at = ${closedAt} WHERE id = $1`,
    [requestId, status]
  );
}

export async function findTradeRequestByThread(threadId) {
  const query = 'SELECT * FROM trade_requests WHERE discord_thread_id = $1';
  return (await poolUsers.query(query, [threadId])).rows[0];
}

export async function updateLastActivity(requestId) {
  await poolUsers.query(
    'UPDATE trade_requests SET last_activity_at = NOW(), warning_sent = false WHERE id = $1',
    [requestId]
  );
}

export async function getActiveTradeRequestsWithNewItems(since) {
  const query = `
    SELECT DISTINCT tr.id, tr.discord_thread_id
    FROM trade_requests tr
    JOIN trade_request_items tri ON tri.trade_request_id = tr.id
    WHERE tr.status = 'active'
      AND tr.discord_thread_id IS NOT NULL
      AND tri.added_at > $1
  `;
  return (await poolUsers.query(query, [since])).rows;
}

/**
 * Adjust offer quantities after a completed trade.
 * Reduces each offer's quantity by the traded amount. Closes offers that reach 0.
 * Returns a summary of adjustments made.
 */
export async function adjustOfferQuantities(tradeRequestId) {
  const itemsResult = await poolUsers.query(
    'SELECT offer_id, quantity FROM trade_request_items WHERE trade_request_id = $1 AND offer_id IS NOT NULL',
    [tradeRequestId]
  );

  const results = [];
  for (const item of itemsResult.rows) {
    // Reduce quantity, minimum 0
    const updateResult = await poolUsers.query(
      `UPDATE trade_offers
       SET quantity = GREATEST(quantity - $2, 0),
           bumped_at = NOW()
       WHERE id = $1
         AND state NOT IN ('closed', 'terminated')
       RETURNING id, quantity, state`,
      [item.offer_id, item.quantity]
    );

    if (updateResult.rows.length > 0) {
      const updated = updateResult.rows[0];
      // Close the offer if quantity hit 0
      if (updated.quantity <= 0) {
        await poolUsers.query(
          `UPDATE trade_offers SET state = 'closed' WHERE id = $1`,
          [item.offer_id]
        );
        results.push({ offerId: item.offer_id, closed: true });
      } else {
        results.push({ offerId: item.offer_id, remaining: updated.quantity });
      }
    }
  }

  return results;
}

// ---- Service Requests (Questions & On-Demand Flight Requests) ----

export async function getPendingServiceRequests() {
  const query = `
    SELECT sr.*, s.title as service_title, s.user_id as manager_id, s.owner_user_id,
           s.type as service_type,
           req_u.username as requester_username, req_u.eu_name as requester_name,
           mgr_u.username as manager_username,
           std.discord_code,
           COALESCE(
             (SELECT json_agg(json_build_object('user_id', sp.user_id, 'username', pu.username))
              FROM service_pilots sp
              JOIN users pu ON sp.user_id = pu.id
              WHERE sp.service_id = s.id),
             '[]'::json
           ) as pilots
    FROM service_requests sr
    JOIN services s ON sr.service_id = s.id
    JOIN users req_u ON sr.requester_id = req_u.id
    JOIN users mgr_u ON s.user_id = mgr_u.id
    LEFT JOIN service_transportation_details std ON std.service_id = s.id
    WHERE sr.status = 'pending'
      AND sr.discord_thread_id IS NULL
    ORDER BY sr.created_at ASC
  `;
  return (await poolUsers.query(query)).rows;
}

export async function setServiceRequestThread(requestId, threadId) {
  const query = 'UPDATE service_requests SET discord_thread_id = $2, status = \'negotiating\' WHERE id = $1';
  await poolUsers.query(query, [requestId, threadId]);
}

// Mark a service request as notified via DM (no thread created)
export async function markServiceRequestNotified(requestId) {
  const query = "UPDATE service_requests SET status = 'negotiating' WHERE id = $1";
  await poolUsers.query(query, [requestId]);
}

// Accept a service request (flight request) — only if still negotiating/pending
export async function acceptServiceRequest(requestId) {
  const query = `
    UPDATE service_requests SET status = 'accepted', updated_at = CURRENT_TIMESTAMP
    WHERE id = $1 AND status IN ('pending', 'negotiating')
    RETURNING *
  `;
  const result = await poolUsers.query(query, [requestId]);
  return result.rows[0] || null;
}

// Decline a service request (flight request) — only if still negotiating/pending
export async function declineServiceRequest(requestId) {
  const query = `
    UPDATE service_requests SET status = 'declined', updated_at = CURRENT_TIMESTAMP
    WHERE id = $1 AND status IN ('pending', 'negotiating')
    RETURNING *
  `;
  const result = await poolUsers.query(query, [requestId]);
  return result.rows[0] || null;
}

// Get a service request by ID (for button interaction validation)
export async function getServiceRequestById(requestId) {
  const query = `
    SELECT sr.*, s.user_id as manager_id, s.owner_user_id, s.title as service_title
    FROM service_requests sr
    JOIN services s ON sr.service_id = s.id
    WHERE sr.id = $1
  `;
  const result = await poolUsers.query(query, [requestId]);
  return result.rows[0] || null;
}

// Accept a flight check-in — only if still pending
export async function acceptCheckin(checkinId) {
  const query = `
    UPDATE service_checkins SET status = 'accepted', accepted_at = CURRENT_TIMESTAMP
    WHERE id = $1 AND status = 'pending'
    RETURNING *
  `;
  const result = await poolUsers.query(query, [checkinId]);
  return result.rows[0] || null;
}

// Deny a flight check-in — only if still pending
export async function denyCheckin(checkinId) {
  const query = `
    UPDATE service_checkins SET status = 'denied'
    WHERE id = $1 AND status = 'pending'
    RETURNING *
  `;
  const result = await poolUsers.query(query, [checkinId]);
  return result.rows[0] || null;
}

// Get a check-in by ID with flight and service info (for button validation)
export async function getCheckinWithContext(checkinId) {
  const query = `
    SELECT c.*, fi.service_id, fi.id as flight_id, fi.status as flight_status,
           s.user_id as manager_id, s.owner_user_id, s.title as service_title,
           u.username as passenger_username, u.eu_name as passenger_name
    FROM service_checkins c
    JOIN service_flight_instances fi ON c.flight_id = fi.id
    JOIN services s ON fi.service_id = s.id
    JOIN users u ON c.user_id = u.id
    WHERE c.id = $1
  `;
  const result = await poolUsers.query(query, [checkinId]);
  return result.rows[0] || null;
}

// Activate a ticket (first accepted check-in)
export async function activateTicketByCheckin(ticketId) {
  const query = `
    UPDATE service_tickets SET status = 'active', activated_at = CURRENT_TIMESTAMP
    WHERE id = $1 AND status = 'purchased'
    RETURNING *
  `;
  const result = await poolUsers.query(query, [ticketId]);
  return result.rows[0] || null;
}

// Get pending check-ins for flights on services with discord_code (for DM notifications)
// Uses added_to_thread = false as the "not yet notified" marker (thread-based check-ins
// are handled separately and require discord_thread_id IS NOT NULL)
export async function getPendingCheckinsDmNotify() {
  const query = `
    SELECT c.*, fi.id as flight_id,
           s.title as service_title, s.user_id as manager_id, s.owner_user_id,
           u.username as passenger_username, u.eu_name as passenger_name,
           COALESCE(
             (SELECT json_agg(json_build_object('user_id', sp.user_id))
              FROM service_pilots sp WHERE sp.service_id = s.id),
             '[]'::json
           ) as pilots
    FROM service_checkins c
    JOIN service_flight_instances fi ON c.flight_id = fi.id
    JOIN services s ON fi.service_id = s.id
    JOIN users u ON c.user_id = u.id
    JOIN service_transportation_details std ON std.service_id = s.id
    WHERE c.status = 'pending'
      AND c.added_to_thread = false
      AND fi.discord_thread_id IS NULL
      AND std.discord_code IS NOT NULL AND std.discord_code != ''
    ORDER BY c.checked_in_at ASC
  `;
  return (await poolUsers.query(query)).rows;
}

// ── Unverified account cleanup ──────────────────────────────────────────────

/** Mark an unverified user as having left the Discord server. Only sets if not already set. */
export async function setUserLeftServer(userId) {
  await poolUsers.query(
    'UPDATE users SET left_server_at = NOW() WHERE id = $1 AND left_server_at IS NULL',
    [userId]
  );
}

/** Clear the left_server_at timestamp (user rejoined the server). */
export async function clearUserLeftServer(userId) {
  await poolUsers.query(
    'UPDATE users SET left_server_at = NULL WHERE id = $1',
    [userId]
  );
}

/** Get unverified users who left the server 7+ days ago. */
export async function getStaleUnverifiedUsers() {
  const query = `
    SELECT id, username, left_server_at FROM users
    WHERE verified = false
      AND left_server_at IS NOT NULL
      AND left_server_at < NOW() - INTERVAL '7 days'
  `;
  return (await poolUsers.query(query)).rows;
}

/**
 * Delete a single unverified user and all their data within a transaction.
 * Returns the deleted user row, or null if safety checks prevent deletion.
 *
 * Safety: triple-checks verified=false (query filter, FOR UPDATE lock, final DELETE WHERE).
 * Aborts if any NO ACTION FK tables have rows (should never happen for unverified users).
 */
export async function deleteUnverifiedUser(userId, txClient) {
  // Safety gate: re-check verified status with row lock
  const userCheck = await txClient.query(
    'SELECT id, username, verified FROM users WHERE id = $1 FOR UPDATE',
    [userId]
  );

  if (!userCheck.rows[0]) return null;
  if (userCheck.rows[0].verified === true) {
    console.error(`[CLEANUP] SAFETY ABORT: User ${userId} is verified! Skipping.`);
    return null;
  }

  // Step A: Clean tables with no FK constraint (won't block deletion)
  await txClient.query('DELETE FROM sessions WHERE user_id = $1', [userId]);
  await txClient.query('DELETE FROM notifications WHERE user_id = $1', [userId]);
  await txClient.query('DELETE FROM bot_config WHERE key = $1', [`verify_reminder:${userId}`]);
  await txClient.query('DELETE FROM shop_managers WHERE user_id = $1', [userId]);
  await txClient.query('DELETE FROM trade_offers WHERE user_id = $1', [userId]);
  await txClient.query('DELETE FROM user_items WHERE user_id = $1', [userId]);
  await txClient.query('DELETE FROM trade_requests WHERE requester_id = $1', [userId]);
  await txClient.query('DELETE FROM society_join_requests WHERE user_id = $1', [userId]);

  // Step B: Safety-check ALL NO ACTION FK tables
  // These should always be empty for unverified users. If any have rows, abort.
  const blockCheck = await txClient.query(`
    SELECT
      (SELECT COUNT(*) FROM service_tickets WHERE user_id = $1) +
      (SELECT COUNT(*) FROM service_checkins WHERE user_id = $1) +
      (SELECT COUNT(*) FROM service_requests WHERE requester_id = $1) +
      (SELECT COUNT(*) FROM service_pilots WHERE added_by = $1) +
      (SELECT COUNT(*) FROM services WHERE owner_user_id = $1) +
      (SELECT COUNT(*) FROM flight_reschedule_notifications WHERE user_id = $1) +
      (SELECT COUNT(*) FROM rental_requests WHERE requester_id = $1) +
      (SELECT COUNT(*) FROM rental_dm_notifications WHERE owner_id = $1) +
      (SELECT COUNT(*) FROM auctions WHERE seller_id = $1) +
      (SELECT COUNT(*) FROM auctions WHERE current_bidder = $1) +
      (SELECT COUNT(*) FROM auction_bids WHERE bidder_id = $1) +
      (SELECT COUNT(*) FROM auction_disclaimers WHERE user_id = $1) +
      (SELECT COUNT(*) FROM auction_audit_log WHERE user_id = $1) +
      (SELECT COUNT(*) FROM admin_actions WHERE admin_id = $1) +
      (SELECT COUNT(*) FROM announcements WHERE author_id = $1) +
      (SELECT COUNT(*) FROM events WHERE submitted_by = $1) +
      (SELECT COUNT(*) FROM events WHERE approved_by = $1) +
      (SELECT COUNT(*) FROM content_creators WHERE added_by = $1) +
      (SELECT COUNT(*) FROM change_history WHERE created_by = $1) +
      (SELECT COUNT(*) FROM changes WHERE reviewed_by = $1) +
      (SELECT COUNT(*) FROM users WHERE locked_by = $1) +
      (SELECT COUNT(*) FROM users WHERE banned_by = $1)
    AS blocking_refs
  `, [userId]);

  const blockingRefs = parseInt(blockCheck.rows[0].blocking_refs);
  if (blockingRefs > 0) {
    console.error(`[CLEANUP] ABORT: User ${userId} (${userCheck.rows[0].username}) has ${blockingRefs} blocking FK reference(s). Manual review needed.`);
    return null;
  }

  // Step C: Delete user row (CASCADE handles loadouts, services, user_roles, etc.)
  const result = await txClient.query(
    'DELETE FROM users WHERE id = $1 AND verified = false RETURNING *',
    [userId]
  );

  return result.rows[0] || null;
}

// =============================================
// MARKET PRICE SNAPSHOTS
// =============================================

/**
 * Get the latest market price snapshot for an item by name or item_id.
 * When querying by name, searches unresolved entries AND resolves name→id
 * via the Item table to also find resolved entries (item_name IS NULL).
 */
export async function getLatestMarketPrice(itemNameOrId) {
  if (typeof itemNameOrId === 'number') {
    const { rows } = await poolUsers.query(
      `SELECT * FROM market_price_snapshots
       WHERE item_id = $1
       ORDER BY recorded_at DESC LIMIT 1`,
      [itemNameOrId]
    );
    return rows[0] || null;
  }
  // Try to resolve name → item_id from the entity DB
  const { rows: itemRows } = await poolNexus.query(
    `SELECT "Id" FROM ONLY "Item" WHERE LOWER("Name") = LOWER($1) LIMIT 1`,
    [itemNameOrId]
  );
  const itemId = itemRows.length > 0 ? itemRows[0].Id : null;

  // Search by item_id (resolved entries) OR by name (unresolved entries)
  const { rows } = await poolUsers.query(
    `SELECT * FROM market_price_snapshots
     WHERE (
       ($1::int IS NOT NULL AND item_id = $1)
       OR (item_id IS NULL AND LOWER(item_name) = LOWER($2))
     )
     ORDER BY recorded_at DESC LIMIT 1`,
    [itemId, itemNameOrId]
  );
  return rows[0] || null;
}

/**
 * Get market price history for an item.
 */
export async function getMarketPriceHistory(itemId, { days = 30 } = {}) {
  const { rows } = await poolUsers.query(
    `SELECT * FROM market_price_snapshots
     WHERE item_id = $1 AND recorded_at > now() - make_interval(days => $2)
     ORDER BY recorded_at DESC`,
    [itemId, days]
  );
  return rows;
}

/**
 * Resolve unresolved item names in market_price_snapshots.
 * Cross-references the nexus entity database Item table.
 * Returns the number of rows updated.
 */
export async function resolveMarketPriceItemIds() {
  // Get unresolved item names from users DB
  const { rows: unresolved } = await poolUsers.query(
    `SELECT DISTINCT item_name FROM market_price_snapshots
     WHERE item_id IS NULL
     LIMIT 500`
  );

  if (unresolved.length === 0) return 0;

  let resolved = 0;
  for (const { item_name } of unresolved) {
    // Try exact match in nexus entity DB
    const { rows: exact } = await poolNexus.query(
      `SELECT "Id" FROM ONLY "Item" WHERE "Name" = $1 LIMIT 1`,
      [item_name]
    );

    let itemId = exact.length > 0 ? exact[0].Id : null;

    // Fallback: case-insensitive match
    if (!itemId) {
      const { rows: ilike } = await poolNexus.query(
        `SELECT "Id" FROM ONLY "Item" WHERE LOWER("Name") = LOWER($1) LIMIT 1`,
        [item_name]
      );
      itemId = ilike.length > 0 ? ilike[0].Id : null;
    }

    // Fallback: prefix match (for truncated OCR names)
    if (!itemId && item_name.length >= 4) {
      const { rows: prefixRows } = await poolNexus.query(
        `SELECT "Id" FROM ONLY "Item"
         WHERE LOWER("Name") LIKE LOWER($1) || '%'
         LIMIT 2`,
        [item_name]
      );
      // Only use prefix match if exactly one result (unambiguous)
      if (prefixRows.length === 1) {
        itemId = prefixRows[0].Id;
      }
    }

    if (itemId) {
      // Set item_id and clear item_name (name is looked up from the Item table).
      // Use LOWER() because OCR may store ALL CAPS names from the game UI.
      await poolUsers.query(
        `UPDATE ONLY market_price_snapshots SET item_id = $1, item_name = NULL
         WHERE LOWER(item_name) = LOWER($2) AND item_id IS NULL`,
        [itemId, item_name]
      );
      resolved++;
    }
  }

  return resolved;
}
