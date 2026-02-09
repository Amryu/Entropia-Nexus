import dotenv from 'dotenv';
import pg from 'pg';

dotenv.config();

const Pool = pg.Pool;

const poolUsers = new Pool({
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
  await (await poolUsers.query(query, values)).rows[0];
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
export async function assignEditorRole(userId) {
  await poolUsers.query(
    `INSERT INTO user_roles (user_id, role_id)
     SELECT $1, r.id FROM roles r WHERE r.name = 'editor'
     ON CONFLICT DO NOTHING`,
    [userId]
  );
}
export async function getChanges() {
  return (await poolUsers.query('SELECT * FROM changes')).rows;
}
export async function getOpenChanges(date) {
  // Use content_updated_at to only pick up changes where actual content was modified
  // This prevents duplicate notifications when only admin fields (thread_id, etc.) change
  return (await poolUsers.query('SELECT * FROM changes WHERE state IN (\'Draft\', \'Pending\') AND content_updated_at > $1', [date.toISOString()])).rows;
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
    SELECT fi.*, s.title as service_title, s.user_id as provider_user_id,
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
    WHERE fi.status IN ('boarding', 'running')
      AND fi.discord_thread_id IS NULL
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

// ---- Item Price Functions ----

export async function insertItemPrices(prices) {
  if (!prices.length) return;

  const valueClauses = [];
  const values = [];
  let idx = 1;

  for (const p of prices) {
    valueClauses.push(`($${idx}, $${idx + 1}, $${idx + 2}, $${idx + 3}, $${idx + 4})`);
    values.push(p.item_id, p.price_value, p.quantity || 1, p.source || null, p.recorded_at || new Date());
    idx += 5;
  }

  const query = `
    INSERT INTO item_prices (item_id, price_value, quantity, source, recorded_at)
    VALUES ${valueClauses.join(', ')}
  `;

  await poolUsers.query(query, values);
}

const VALID_PERIOD_TYPES = ['hour', 'day', 'week'];

function periodTruncSql(periodType) {
  switch (periodType) {
    case 'hour': return `date_trunc('hour', recorded_at)`;
    case 'day': return `date_trunc('day', recorded_at)`;
    case 'week': return `date_trunc('week', recorded_at)`;
    default: throw new Error(`Unknown period type: ${periodType}`);
  }
}

function currentBoundarySql(periodType) {
  switch (periodType) {
    case 'hour': return `date_trunc('hour', now())`;
    case 'day': return `date_trunc('day', now())`;
    case 'week': return `date_trunc('week', now())`;
    default: throw new Error(`Unknown period type: ${periodType}`);
  }
}

/**
 * Compute price summaries for a single period type.
 * Uses watermarks for incremental processing. Idempotent.
 * @param {string} periodType - 'hour', 'day', or 'week'
 * @returns {{ period_type: string, processed: number }}
 */
export async function computePriceSummaries(periodType) {
  if (!VALID_PERIOD_TYPES.includes(periodType)) {
    throw new Error(`Invalid period type: ${periodType}`);
  }

  const wmResult = await poolUsers.query(
    'SELECT last_computed_until FROM item_price_summary_watermarks WHERE period_type = $1',
    [periodType]
  );
  const watermark = wmResult.rows[0]?.last_computed_until;

  const boundaryResult = await poolUsers.query(`SELECT ${currentBoundarySql(periodType)} AS boundary`);
  const boundary = boundaryResult.rows[0].boundary;

  if (!boundary) return { period_type: periodType, processed: 0 };

  if (watermark && new Date(watermark) >= new Date(boundary)) {
    return { period_type: periodType, processed: 0 };
  }

  const periodTrunc = periodTruncSql(periodType);
  const conditions = ['recorded_at < $1'];
  const values = [boundary];
  let idx = 2;

  if (watermark) {
    conditions.push(`recorded_at >= $${idx}`);
    values.push(watermark);
    idx++;
  }

  const query = `
    INSERT INTO item_price_summaries (
      item_id, source, period_type, period_start,
      price_min, price_max, price_avg,
      price_p5, price_median, price_p95,
      price_wap, volume, sample_count, computed_at
    )
    SELECT
      item_id,
      source,
      '${periodType}'::price_period_type,
      ${periodTrunc} AS period_start,
      MIN(price_value),
      MAX(price_value),
      AVG(price_value),
      PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY price_value),
      PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_value),
      PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY price_value),
      SUM(price_value * quantity) / NULLIF(SUM(quantity), 0),
      SUM(quantity),
      COUNT(*),
      now()
    FROM item_prices
    WHERE ${conditions.join(' AND ')}
    GROUP BY item_id, source, ${periodTrunc}
    ON CONFLICT (item_id, COALESCE(source, ''), period_type, period_start)
    DO UPDATE SET
      price_min = EXCLUDED.price_min,
      price_max = EXCLUDED.price_max,
      price_avg = EXCLUDED.price_avg,
      price_p5 = EXCLUDED.price_p5,
      price_median = EXCLUDED.price_median,
      price_p95 = EXCLUDED.price_p95,
      price_wap = EXCLUDED.price_wap,
      volume = EXCLUDED.volume,
      sample_count = EXCLUDED.sample_count,
      computed_at = EXCLUDED.computed_at
  `;

  const result = await poolUsers.query(query, values);

  await poolUsers.query(
    `UPDATE item_price_summary_watermarks
     SET last_computed_until = $1, last_run_at = now()
     WHERE period_type = $2`,
    [boundary, periodType]
  );

  return { period_type: periodType, processed: result.rowCount };
}

/**
 * Compute summaries for all period types.
 * @returns {Array<{ period_type: string, processed: number }>}
 */
export async function computeAllPriceSummaries() {
  const results = [];
  for (const pt of VALID_PERIOD_TYPES) {
    results.push(await computePriceSummaries(pt));
  }
  return results;
}
