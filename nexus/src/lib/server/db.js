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
  const values = [user.id, user.username, user.global_name, user.discriminator, user.avatar];

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