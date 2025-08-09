const { Pool } = require('pg');
const credentials = require('../credentials');

// Single shared pools for the whole API
const pool = new Pool(credentials.nexus);
const usersPool = new Pool(credentials['nexus-users']);

module.exports = { pool, usersPool };
