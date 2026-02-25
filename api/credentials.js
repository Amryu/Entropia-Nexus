// credentials.js
// Load DB credentials from environment variables. Use .env for local development.
require('dotenv').config();

function env(name, def) {
  if (process.env[name] !== undefined) return process.env[name];
  return def;
}

function envInt(name, def) {
  const v = env(name, String(def));
  const n = parseInt(v, 10);
  return Number.isNaN(n) ? def : n;
}

const credentials = {
  nexus: {
    user: env('NEXUS_DB_USER', 'nexus'),
    host: env('NEXUS_DB_HOST', 'localhost'),
    database: env('NEXUS_DB_NAME', 'nexus'),
    password: env('NEXUS_DB_PASS', 'nexus'),
    port: envInt('NEXUS_DB_PORT', 5432),
    // Optional pool tuning values (used when creating Pool)
    max: envInt('NEXUS_DB_MAX', 10),
    idleTimeoutMillis: envInt('NEXUS_DB_IDLE_MS', 30000),
    keepAlive: env('NEXUS_DB_KEEPALIVE', 'true') === 'true'
  },
  nexus_users: {
    user: env('NEXUS_USERS_DB_USER', 'nexus'),
    host: env('NEXUS_USERS_DB_HOST', 'localhost'),
    database: env('NEXUS_USERS_DB_NAME', 'nexus_users'),
    password: env('NEXUS_USERS_DB_PASS', 'nexus'),
    port: envInt('NEXUS_USERS_DB_PORT', 5432),
    max: envInt('NEXUS_USERS_DB_MAX', 10),
    idleTimeoutMillis: envInt('NEXUS_USERS_DB_IDLE_MS', 30000),
    keepAlive: env('NEXUS_USERS_DB_KEEPALIVE', 'true') === 'true'
  }
};

module.exports = credentials;