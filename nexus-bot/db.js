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