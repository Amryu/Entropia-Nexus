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
  return (await poolUsers.query('SELECT * FROM changes WHERE state IN (\'Draft\', \'Pending\') AND last_update > $1', [date.toISOString()])).rows;
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