/**
 * Global Setup for Playwright Tests
 *
 * This script runs before any tests start and:
 * 1. Kills any existing test servers on ports 3100 (API) and 3101 (frontend)
 * 2. Creates a full clone of nexus -> nexus-test (schema + all data)
 * 3. Creates a full clone of nexus-users -> nexus-users-test (schema + all data)
 *
 * This approach uses real production data for realistic testing.
 * Requires pg_dump and psql to be available in PATH.
 */

import { spawnSync, execSync } from 'child_process';
import { unlinkSync, existsSync } from 'fs';
import { tmpdir } from 'os';
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
  { source: 'nexus', target: 'nexus-test' },
  { source: 'nexus-users', target: 'nexus-users-test' },
];

// Test server ports to kill before setup
const TEST_PORTS = [3100, 3101]; // API and frontend

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

  // Step 1: Recreate target database
  await recreateDatabase(targetDb);

  // Step 2: Dump entire source database (schema + data) to temp file
  const tempDumpFile = join(tmpdir(), `dump-${sourceDb}-${Date.now()}.sql`);
  console.log(`   Dumping ${sourceDb}...`);

  try {
    const dumpResult = spawnSync('pg_dump', [
      '--no-owner',
      '--no-acl',
      '--encoding=UTF8',
      '-f', tempDumpFile,
      sourceDb
    ], {
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
    if (psqlResult.status !== 0) {
      console.error('   psql stderr:', psqlResult.stderr);
      throw new Error(`psql failed with exit code ${psqlResult.status}`);
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

    // Clone each database pair
    for (const { source, target } of DATABASE_PAIRS) {
      await cloneDatabase(source, target);
    }

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
