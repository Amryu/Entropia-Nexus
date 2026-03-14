/**
 * Global Setup for Playwright Tests
 *
 * This script runs before any tests start and:
 * 1. Kills any existing test servers on ports 3100 (API) and 3101 (frontend)
 * 2. Creates a full clone of nexus -> nexus_test (schema + all data)
 * 3. Creates a full clone of nexus_users -> nexus_users_test (schema + all data)
 * 4. Seeds required mock-login test users in nexus_users_test
 *
 * This approach uses real production data for realistic testing.
 * Requires pg_dump and psql to be available in PATH.
 */

import { spawnSync, execSync } from 'child_process';
import { unlinkSync, existsSync } from 'fs';
import { join, resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import pg from 'pg';
import dotenv from 'dotenv';

// Load .env.test so we have the correct database credentials
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
dotenv.config({ path: resolve(__dirname, '..', '.env.test') });

// Parse database credentials from connection string or environment
function parseDbConfig() {
  const connStr = process.env.POSTGRES_CONNECTION_STRING;
  if (connStr) {
    try {
      const url = new URL(connStr);
      return {
        host: url.hostname || 'localhost',
        port: url.port || '5432',
        user: decodeURIComponent(url.username) || 'postgres',
        password: decodeURIComponent(url.password) || '',
      };
    } catch { /* fall through to defaults */ }
  }
  return {
    host: process.env.PGHOST || 'localhost',
    port: process.env.PGPORT || '5432',
    user: process.env.PGUSER || 'postgres',
    password: process.env.PGPASSWORD || '',
  };
}

const { host: DB_HOST, port: DB_PORT, user: DB_USER, password: DB_PASSWORD } = parseDbConfig();

// Database pairs to clone
const DATABASE_PAIRS = [
  { source: 'nexus', target: 'nexus_test' },
  { source: 'nexus_users', target: 'nexus_users_test' },
];

// Tables with massive data that should be cloned with only a small subset.
// Schema is always cloned; only data is excluded from the full dump,
// then a limited sample is inserted afterwards.
const LARGE_TABLE_SAMPLES: Record<string, { table: string; sampleQuery: string }[]> = {
  nexus_users: [
    { table: 'ingested_globals',            sampleQuery: 'SELECT * FROM ingested_globals ORDER BY event_timestamp DESC LIMIT 500' },
    { table: 'ingested_global_submissions', sampleQuery: 'SELECT * FROM ingested_global_submissions ORDER BY event_timestamp DESC LIMIT 500' },
    { table: 'globals_rollup_player',       sampleQuery: 'SELECT * FROM globals_rollup_player ORDER BY period_start DESC LIMIT 500' },
    { table: 'globals_rollup_target',       sampleQuery: 'SELECT * FROM globals_rollup_target ORDER BY period_start DESC LIMIT 500' },
    { table: 'globals_ath_leaderboard',     sampleQuery: 'SELECT * FROM globals_ath_leaderboard LIMIT 200' },
    { table: 'exchange_price_snapshots',    sampleQuery: 'SELECT * FROM exchange_price_snapshots ORDER BY recorded_at DESC LIMIT 500' },
    { table: 'exchange_price_summaries',    sampleQuery: 'SELECT * FROM exchange_price_summaries ORDER BY period_start DESC LIMIT 200' },
    { table: 'globals_player_agg',          sampleQuery: 'SELECT * FROM globals_player_agg LIMIT 200' },
    { table: 'globals_target_agg',          sampleQuery: 'SELECT * FROM globals_target_agg LIMIT 200' },
    { table: 'ingested_trade_messages',     sampleQuery: 'SELECT * FROM ingested_trade_messages ORDER BY event_timestamp DESC LIMIT 200' },
    { table: 'ingested_trade_submissions',  sampleQuery: 'SELECT s.* FROM ingested_trade_submissions s INNER JOIN (SELECT id FROM ingested_trade_messages ORDER BY event_timestamp DESC LIMIT 200) m ON s.trade_message_id = m.id' },
  ]
};

// Test server ports to kill before setup
const TEST_PORTS = [3100, 3101]; // API and frontend

const MOCK_TEST_USERS = [
  {
    id: '900000000000000001',
    username: 'verified1',
    globalName: 'Verified User 1',
    euName: 'Verified User 1',
    verified: true,
    administrator: false,
    roleName: 'user'
  },
  {
    id: '900000000000000002',
    username: 'verified2',
    globalName: 'Verified User 2',
    euName: 'Verified User 2',
    verified: true,
    administrator: false,
    roleName: 'user'
  },
  {
    id: '900000000000000003',
    username: 'verified3',
    globalName: 'Verified User 3',
    euName: 'Verified User 3',
    verified: true,
    administrator: false,
    roleName: 'user'
  },
  {
    id: '900000000000000004',
    username: 'unverified1',
    globalName: 'Unverified User 1',
    euName: null,
    verified: false,
    administrator: false,
    roleName: 'user'
  },
  {
    id: '900000000000000005',
    username: 'unverified2',
    globalName: 'Unverified User 2',
    euName: null,
    verified: false,
    administrator: false,
    roleName: 'user'
  },
  {
    id: '900000000000000006',
    username: 'unverified3',
    globalName: 'Unverified User 3',
    euName: null,
    verified: false,
    administrator: false,
    roleName: 'user'
  },
  {
    id: '900000000000000007',
    username: 'admin',
    globalName: 'Admin User',
    euName: 'Admin User',
    verified: true,
    administrator: true,
    roleName: 'admin'
  }
];

async function createPool(database: string) {
  return new pg.Pool({
    host: DB_HOST,
    port: parseInt(DB_PORT),
    user: DB_USER,
    password: DB_PASSWORD,
    database,
  });
}

/**
 * Terminate all connections to a database and drop/recreate it
 */
async function recreateDatabase(targetDb: string) {
  console.log(`   Dropping ${targetDb}...`);
  const pool = await createPool('postgres');

  // Terminate connections to target db
  await pool.query(`
    SELECT pg_terminate_backend(pg_stat_activity.pid)
    FROM pg_stat_activity
    WHERE pg_stat_activity.datname = $1
      AND pid <> pg_backend_pid()
  `, [targetDb]);

  // Drop and recreate
  await pool.query(`DROP DATABASE IF EXISTS "${targetDb}"`);
  await pool.query(`CREATE DATABASE "${targetDb}"`);
  await pool.end();
}

/**
 * Clone a database completely (schema + all data) using pg_dump/psql
 */
async function cloneDatabase(sourceDb: string, targetDb: string) {
  console.log(`\n📦 Cloning ${sourceDb} -> ${targetDb}...`);

  const connectionEnv = {
    ...process.env,
    PGHOST: DB_HOST,
    PGPORT: DB_PORT,
    PGUSER: DB_USER,
    PGPASSWORD: DB_PASSWORD,
  };

  const samples = LARGE_TABLE_SAMPLES[sourceDb] || [];

  // Step 1: Recreate target database
  await recreateDatabase(targetDb);

  // Step 2: Dump source database (schema + data) to temp file
  // For large tables, exclude their data from the dump (schema is still included)
  const tempDir = resolve(__dirname, '..');
  const tempDumpFile = join(tempDir, `dump-${sourceDb}-${Date.now()}.sql`);
  console.log(`   Dumping ${sourceDb}${samples.length ? ` (excluding data for ${samples.length} large tables)` : ''}...`);

  try {
    const pgDumpArgs = [
      '--no-owner',
      '--no-acl',
      '--encoding=UTF8',
      '-f', tempDumpFile,
    ];
    for (const { table } of samples) {
      pgDumpArgs.push('--exclude-table-data', table);
    }
    pgDumpArgs.push(sourceDb);

    const dumpResult = spawnSync('pg_dump', pgDumpArgs, {
      env: connectionEnv,
      stdio: ['pipe', 'pipe', 'pipe'],
      encoding: 'utf-8'
    });

    if (dumpResult.error) throw dumpResult.error;
    if (dumpResult.status !== 0) {
      console.error('   pg_dump stderr:', dumpResult.stderr);
      throw new Error(`pg_dump failed with exit code ${dumpResult.status}`);
    }

    // Step 3: Restore to target database
    console.log(`   Restoring to ${targetDb}...`);
    const psqlResult = spawnSync('psql', [
      '-q',
      '-f', tempDumpFile,
      targetDb
    ], {
      env: connectionEnv,
      stdio: ['pipe', 'pipe', 'pipe'],
      encoding: 'utf-8'
    });

    if (psqlResult.error) throw psqlResult.error;
    // psql often returns non-zero for harmless warnings (missing roles, extensions)
    // during restore — only log, don't fail
    if (psqlResult.status !== 0 && psqlResult.stderr) {
      const serious = psqlResult.stderr.split('\n').filter((l: string) => /ERROR/i.test(l) && !/role|extension|schema "public"/i.test(l));
      if (serious.length > 0) {
        console.warn(`   psql warnings:\n${serious.join('\n')}`);
      }
    }

    // Step 4: Seed small sample of large tables (copy from source to target)
    if (samples.length > 0) {
      await seedLargeTableSamples(sourceDb, targetDb, samples);
    }

    console.log(`✅ ${targetDb} ready!`);
  } finally {
    // Clean up temp file
    if (existsSync(tempDumpFile)) {
      unlinkSync(tempDumpFile);
    }
  }
}

/**
 * Copy a small sample of rows from large source tables into the target database.
 * Uses a direct connection to each DB — reads from source, inserts into target.
 */
async function seedLargeTableSamples(
  sourceDb: string,
  targetDb: string,
  samples: { table: string; sampleQuery: string }[]
) {
  console.log(`   Seeding ${samples.length} large table samples...`);
  const sourcePool = await createPool(sourceDb);
  const targetPool = await createPool(targetDb);

  try {
    for (const { table, sampleQuery } of samples) {
      const { rows } = await sourcePool.query(sampleQuery);
      if (rows.length === 0) continue;

      // Build a bulk INSERT from the sample rows
      const columns = Object.keys(rows[0]);
      const quotedCols = columns.map(c => `"${c}"`).join(', ');
      const valuePlaceholders: string[] = [];
      const allValues: any[] = [];
      let paramIdx = 1;

      for (const row of rows) {
        const rowPlaceholders: string[] = [];
        for (const col of columns) {
          rowPlaceholders.push(`$${paramIdx++}`);
          allValues.push(row[col]);
        }
        valuePlaceholders.push(`(${rowPlaceholders.join(', ')})`);
      }

      await targetPool.query(
        `INSERT INTO "${table}" (${quotedCols}) VALUES ${valuePlaceholders.join(', ')} ON CONFLICT DO NOTHING`,
        allValues
      );
      console.log(`   ${table}: ${rows.length} rows`);
    }
  } finally {
    await sourcePool.end();
    await targetPool.end();
  }
}

async function seedMockTestUsers(targetDb: string) {
  console.log(`\n👥 Seeding mock test users in ${targetDb}...`);
  const pool = await createPool(targetDb);

  try {
    await pool.query('BEGIN');

    const { rows: roleRows } = await pool.query(
      `SELECT id, name FROM roles WHERE name = ANY($1::text[])`,
      [['admin', 'user']]
    );

    const roleByName = new Map<string, number>(roleRows.map((r: any) => [r.name, r.id]));
    const adminRoleId = roleByName.get('admin');
    const userRoleId = roleByName.get('user');

    if (!adminRoleId || !userRoleId) {
      throw new Error('Required roles (admin/user) not found in test database');
    }

    for (const user of MOCK_TEST_USERS) {
      await pool.query(
        `
          INSERT INTO users (
            id, username, global_name, discriminator, avatar, eu_name, verified, administrator, locked, banned
          )
          VALUES ($1, $2, $3, $4, $5, $6, $7, $8, false, false)
          ON CONFLICT (id) DO UPDATE
          SET
            username = EXCLUDED.username,
            global_name = EXCLUDED.global_name,
            discriminator = EXCLUDED.discriminator,
            avatar = EXCLUDED.avatar,
            eu_name = EXCLUDED.eu_name,
            verified = EXCLUDED.verified,
            administrator = EXCLUDED.administrator,
            locked = false,
            locked_reason = NULL,
            locked_at = NULL,
            locked_by = NULL,
            banned = false,
            banned_reason = NULL,
            banned_at = NULL,
            banned_until = NULL,
            banned_by = NULL
        `,
        [
          user.id,
          user.username,
          user.globalName,
          '0000',
          null,
          user.euName,
          user.verified,
          user.administrator
        ]
      );
    }

    const seededIds = MOCK_TEST_USERS.map((u) => u.id);
    await pool.query(`DELETE FROM user_roles WHERE user_id = ANY($1::bigint[])`, [seededIds]);
    await pool.query(`DELETE FROM user_grants WHERE user_id = ANY($1::bigint[])`, [seededIds]);

    for (const user of MOCK_TEST_USERS) {
      const roleId = user.roleName === 'admin' ? adminRoleId : userRoleId;
      await pool.query(
        `INSERT INTO user_roles (user_id, role_id) VALUES ($1, $2) ON CONFLICT DO NOTHING`,
        [user.id, roleId]
      );
    }

    await pool.query('COMMIT');
    console.log(`✅ Seeded ${MOCK_TEST_USERS.length} mock test users`);
  } catch (error) {
    await pool.query('ROLLBACK');
    throw error;
  } finally {
    await pool.end();
  }
}

/**
 * Kill any processes listening on the test ports (Windows-specific)
 */
function killTestServers() {
  console.log('\n🔪 Killing existing test servers...');

  for (const port of TEST_PORTS) {
    try {
      // Find PIDs listening on the port using netstat
      const result = spawnSync('netstat', ['-ano'], {
        encoding: 'utf-8',
        shell: true,
      });

      if (result.stdout) {
        const lines = result.stdout.split('\n');
        const pidsToKill = new Set<string>();

        for (const line of lines) {
          // Match lines like "TCP    127.0.0.1:3100    ...    LISTENING    12345"
          if (line.includes(`:${port}`) && line.includes('LISTENING')) {
            const parts = line.trim().split(/\s+/);
            const pid = parts[parts.length - 1];
            if (pid && /^\d+$/.test(pid)) {
              pidsToKill.add(pid);
            }
          }
        }

        for (const pid of pidsToKill) {
          try {
            execSync(`taskkill /F /PID ${pid}`, { stdio: 'pipe' });
            console.log(`   Killed process ${pid} on port ${port}`);
          } catch {
            // Process may have already exited
          }
        }

        if (pidsToKill.size === 0) {
          console.log(`   No process found on port ${port}`);
        }
      }
    } catch (err) {
      console.log(`   Could not check port ${port}:`, err);
    }
  }

  // Give processes time to fully terminate
  spawnSync('timeout', ['/t', '2', '/nobreak'], { shell: true, stdio: 'pipe' });
}

async function globalSetup() {
  console.log('\n🔧 Starting test database setup...');

  try {
    // Step 0: Kill any existing test servers to prevent connection issues
    killTestServers();

    // Clone each database pair (full tear down + clone from local DBs)
    for (const { source, target } of DATABASE_PAIRS) {
      await cloneDatabase(source, target);
    }

    await seedMockTestUsers('nexus_users_test');

    console.log('\n🎉 All test databases ready!\n');
  } catch (error: any) {
    console.error('\n❌ Failed to setup test databases:', error.message);
    if (error.stderr) {
      console.error('   stderr:', error.stderr.toString());
    }
    throw error;
  }
}

export default globalSetup;

// Allow running directly via `npx tsx tests/global-setup.ts`
const isDirectRun = process.argv[1]?.includes('global-setup');
if (isDirectRun) {
  globalSetup()
    .then(() => process.exit(0))
    .catch(() => process.exit(1));
}
