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

// =============================================
// ON-DEMAND SERVICE REQUESTS
// =============================================

// Get service requests needing thread creation (all types)
// Note: Planet names are not fetched here as the planets table is in a different database
export async function getOnDemandRequestsNeedingThread() {
  const query = `
    SELECT sr.*, s.title as service_title, s.type as service_type,
           s.user_id as provider_user_id, u.id as requester_discord_id,
           u.username as requester_username, u.eu_name as requester_eu_name,
           sr.requested_start, sr.requested_duration_minutes, sr.is_open_ended,
           sr.service_notes,
           std.current_planet_id as provider_planet_id,
           trd.customer_planet_id, trd.pickup_requested, trd.pickup_location,
           trd.dropoff_location, trd.ticket_id,
           st.waives_pickup_fee as ticket_waives_fee,
           s.planet_id as service_planet_id,
           hd.rate_per_hour as healing_rate,
           dd.rate_per_hour as dps_rate
    FROM service_requests sr
    JOIN services s ON sr.service_id = s.id
    JOIN users u ON sr.requester_id = u.id
    LEFT JOIN service_transportation_details std ON s.id = std.service_id
    LEFT JOIN service_transport_request_details trd ON sr.id = trd.request_id
    LEFT JOIN service_tickets st_ticket ON trd.ticket_id = st_ticket.id
    LEFT JOIN service_ticket_offers st ON st_ticket.offer_id = st.id
    LEFT JOIN service_healing_details hd ON s.id = hd.service_id
    LEFT JOIN service_dps_details dd ON s.id = dd.service_id
    WHERE sr.status IN ('pending', 'accepted', 'negotiating', 'in_progress')
      AND sr.discord_thread_id IS NULL
      AND (
        (s.type = 'transportation' AND (std.service_mode = 'on_demand' OR std.service_mode IS NULL))
        OR s.type IN ('healing', 'dps', 'custom')
      )
  `;
  return (await poolUsers.query(query)).rows;
}

// Set request thread ID
export async function setRequestThreadId(requestId, threadId) {
  const query = 'UPDATE service_requests SET discord_thread_id = $2 WHERE id = $1';
  await poolUsers.query(query, [requestId, threadId]);
}

// Get request by thread ID
export async function getRequestByThreadId(threadId) {
  const query = `
    SELECT sr.*, s.title as service_title, s.id as service_id,
           s.type as service_type, s.user_id as provider_user_id,
           u.id as requester_discord_id, u.username as requester_username,
           trd.ticket_id, trd.dropoff_location as destination_planet_id
    FROM service_requests sr
    JOIN services s ON sr.service_id = s.id
    JOIN users u ON sr.requester_id = u.id
    LEFT JOIN service_transport_request_details trd ON sr.id = trd.request_id
    WHERE sr.discord_thread_id = $1
  `;
  const result = await poolUsers.query(query, [threadId]);
  return result.rows[0] || null;
}

// Get request by ID with full context
export async function getRequestById(requestId) {
  const query = `
    SELECT sr.*, s.title as service_title, s.id as service_id,
           s.type as service_type, s.user_id as provider_user_id,
           u.id as requester_discord_id, u.username as requester_username,
           trd.ticket_id, trd.dropoff_location as destination_planet_id,
           hd.rate_per_hour as healing_rate, hd.accepts_decay_billing as healing_accepts_decay,
           dd.rate_per_hour as dps_rate, dd.accepts_decay_billing as dps_accepts_decay
    FROM service_requests sr
    JOIN services s ON sr.service_id = s.id
    JOIN users u ON sr.requester_id = u.id
    LEFT JOIN service_transport_request_details trd ON sr.id = trd.request_id
    LEFT JOIN service_healing_details hd ON s.id = hd.service_id
    LEFT JOIN service_dps_details dd ON s.id = dd.service_id
    WHERE sr.id = $1
  `;
  const result = await poolUsers.query(query, [requestId]);
  return result.rows[0] || null;
}

// Update request status
export async function updateRequestStatus(requestId, status) {
  const query = `
    UPDATE service_requests
    SET status = $2, updated_at = NOW()
    WHERE id = $1
    RETURNING *
  `;
  const result = await poolUsers.query(query, [requestId, status]);
  return result.rows[0];
}

// Update service request with multiple fields
export async function updateServiceRequest(requestId, data) {
  const setClauses = [];
  const values = [requestId];
  let paramIndex = 2;

  const allowedFields = [
    'status', 'requested_start', 'requested_duration_minutes', 'is_open_ended',
    'final_start', 'final_duration_minutes', 'final_price',
    'actual_start', 'actual_end', 'actual_decay_ped', 'break_minutes',
    'actual_payment', 'service_notes', 'discord_thread_id'
  ];

  for (const field of allowedFields) {
    if (data[field] !== undefined) {
      setClauses.push(`${field} = $${paramIndex}`);
      values.push(data[field]);
      paramIndex++;
    }
  }

  if (setClauses.length === 0) return null;

  setClauses.push('updated_at = NOW()');

  const query = `UPDATE service_requests SET ${setClauses.join(', ')} WHERE id = $1 RETURNING *`;
  const result = await poolUsers.query(query, values);
  return result.rows[0];
}

// Get ticket by ID
export async function getTicketById(ticketId) {
  const query = `
    SELECT st.*, sto.waives_pickup_fee
    FROM service_tickets st
    JOIN service_ticket_offers sto ON st.offer_id = sto.id
    WHERE st.id = $1
  `;
  const result = await poolUsers.query(query, [ticketId]);
  return result.rows[0] || null;
}

// Decrement ticket use (for completing on-demand request)
export async function useTicket(ticketId) {
  const query = `
    UPDATE service_tickets
    SET uses_remaining = uses_remaining - 1,
        status = CASE
          WHEN uses_remaining - 1 <= 0 THEN 'used'
          ELSE status
        END
    WHERE id = $1 AND uses_remaining > 0
    RETURNING *
  `;
  const result = await poolUsers.query(query, [ticketId]);
  return result.rows[0];
}

// Restore ticket use (for aborted/declined requests)
export async function restoreTicketUse(ticketId) {
  const query = `
    UPDATE service_tickets
    SET uses_remaining = uses_remaining + 1,
        status = CASE WHEN status = 'used' THEN 'active' ELSE status END
    WHERE id = $1
    RETURNING *
  `;
  const result = await poolUsers.query(query, [ticketId]);
  return result.rows[0];
}

// Delete pending ticket (for declined/aborted if pending)
export async function deletePendingTicket(ticketId) {
  const query = `
    DELETE FROM service_tickets
    WHERE id = $1 AND status = 'pending'
    RETURNING *
  `;
  const result = await poolUsers.query(query, [ticketId]);
  return result.rows[0];
}

// Activate pending ticket
export async function activateTicket(ticketId) {
  const query = `
    UPDATE service_tickets
    SET status = 'active', activated_at = NOW()
    WHERE id = $1 AND status = 'pending'
    RETURNING *
  `;
  const result = await poolUsers.query(query, [ticketId]);
  return result.rows[0];
}

// Update provider location
export async function updateProviderLocation(serviceId, planetId) {
  const query = `
    UPDATE service_transportation_details
    SET current_planet_id = $2
    WHERE service_id = $1
    RETURNING *
  `;
  const result = await poolUsers.query(query, [serviceId, planetId]);
  return result.rows[0];
}

// Get requests ready for archive (completed/aborted/declined/cancelled with thread)
export async function getRequestsReadyForArchive() {
  const query = `
    SELECT sr.*, s.title as service_title
    FROM service_requests sr
    JOIN services s ON sr.service_id = s.id
    WHERE sr.status IN ('completed', 'aborted', 'declined', 'cancelled')
      AND sr.discord_thread_id IS NOT NULL
      AND sr.updated_at < NOW() - INTERVAL '5 minutes'
  `;
  return (await poolUsers.query(query)).rows;
}

// Clear request thread ID (after archiving)
export async function clearRequestThreadId(requestId) {
  const query = 'UPDATE service_requests SET discord_thread_id = NULL WHERE id = $1';
  await poolUsers.query(query, [requestId]);
}