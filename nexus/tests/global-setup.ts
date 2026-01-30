/**
 * Global Setup for Playwright Tests
 *
 * This script runs before any tests start and:
 * 1. Clones the database schema from nexus-users to nexus-users-test
 * 2. Inserts test users for E2E testing
 *
 * Requires pg_dump and psql to be available in PATH
 */

import { execSync, spawnSync } from 'child_process';
import { writeFileSync, unlinkSync, existsSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import pg from 'pg';

const SOURCE_DB = 'nexus-users';
const TARGET_DB = 'nexus-users-test';
const DB_HOST = 'localhost';
const DB_PORT = '5432';
const DB_USER = 'postgres';
const DB_PASSWORD = '***REMOVED***';

// Test users SQL (from 005_add_test_users.sql)
const TEST_USERS_SQL = `
-- Test verified users
INSERT INTO users (id, username, global_name, discriminator, avatar, eu_name, verified, administrator, locked, banned)
VALUES
  (900000000000000001, 'testuser1', 'Test User 1', '0', NULL, 'Test Avatar One', true, false, false, false),
  (900000000000000002, 'testuser2', 'Test User 2', '0', NULL, 'Test Avatar Two', true, false, false, false),
  (900000000000000003, 'testuser3', 'Test User 3', '0', NULL, 'Test Avatar Three', true, false, false, false)
ON CONFLICT (id) DO UPDATE SET
  username = EXCLUDED.username,
  global_name = EXCLUDED.global_name,
  eu_name = EXCLUDED.eu_name,
  verified = EXCLUDED.verified,
  administrator = EXCLUDED.administrator,
  locked = EXCLUDED.locked,
  banned = EXCLUDED.banned;

-- Test unverified users
INSERT INTO users (id, username, global_name, discriminator, avatar, eu_name, verified, administrator, locked, banned)
VALUES
  (900000000000000004, 'unverified1', 'Unverified User 1', '0', NULL, NULL, false, false, false, false),
  (900000000000000005, 'unverified2', 'Unverified User 2', '0', NULL, NULL, false, false, false, false),
  (900000000000000006, 'unverified3', 'Unverified User 3', '0', NULL, NULL, false, false, false, false)
ON CONFLICT (id) DO UPDATE SET
  username = EXCLUDED.username,
  global_name = EXCLUDED.global_name,
  eu_name = EXCLUDED.eu_name,
  verified = EXCLUDED.verified,
  administrator = EXCLUDED.administrator,
  locked = EXCLUDED.locked,
  banned = EXCLUDED.banned;

-- Test admin user (verified + admin)
INSERT INTO users (id, username, global_name, discriminator, avatar, eu_name, verified, administrator, locked, banned)
VALUES
  (900000000000000007, 'testadmin', 'Test Admin', '0', NULL, 'Test Admin Avatar', true, true, false, false)
ON CONFLICT (id) DO UPDATE SET
  username = EXCLUDED.username,
  global_name = EXCLUDED.global_name,
  eu_name = EXCLUDED.eu_name,
  verified = EXCLUDED.verified,
  administrator = EXCLUDED.administrator,
  locked = EXCLUDED.locked,
  banned = EXCLUDED.banned;
`;

async function globalSetup() {
  console.log('\n🔧 Setting up test database...');

  const connectionEnv = {
    ...process.env,
    PGHOST: DB_HOST,
    PGPORT: DB_PORT,
    PGUSER: DB_USER,
    PGPASSWORD: DB_PASSWORD,
  };

  try {
    // Step 1: Check if target database exists, create if not
    console.log(`   Checking if ${TARGET_DB} exists...`);
    const adminPool = new pg.Pool({
      host: DB_HOST,
      port: parseInt(DB_PORT),
      user: DB_USER,
      password: DB_PASSWORD,
      database: 'postgres',
    });

    const dbCheck = await adminPool.query(
      `SELECT 1 FROM pg_database WHERE datname = $1`,
      [TARGET_DB]
    );

    if (dbCheck.rows.length === 0) {
      console.log(`   Creating database ${TARGET_DB}...`);
      await adminPool.query(`CREATE DATABASE "${TARGET_DB}"`);
    }
    await adminPool.end();

    // Step 2: Drop and recreate the database for a clean slate
    // This is more reliable than trying to drop individual objects
    console.log(`   Recreating ${TARGET_DB} from scratch...`);

    // Connect to postgres db to drop/create target
    const recreatePool = new pg.Pool({
      host: DB_HOST,
      port: parseInt(DB_PORT),
      user: DB_USER,
      password: DB_PASSWORD,
      database: 'postgres',
    });

    // Terminate connections to target db
    await recreatePool.query(`
      SELECT pg_terminate_backend(pg_stat_activity.pid)
      FROM pg_stat_activity
      WHERE pg_stat_activity.datname = $1
        AND pid <> pg_backend_pid()
    `, [TARGET_DB]);

    // Drop and recreate
    await recreatePool.query(`DROP DATABASE IF EXISTS "${TARGET_DB}"`);
    await recreatePool.query(`CREATE DATABASE "${TARGET_DB}"`);
    await recreatePool.end();

    // Step 3: Clone schema using pg_dump to file, then psql from file
    // This avoids Windows piping issues with dollar-quoted strings
    console.log(`   Cloning schema from ${SOURCE_DB} to ${TARGET_DB}...`);

    const tempSchemaFile = join(tmpdir(), `nexus-schema-${Date.now()}.sql`);

    try {
      // Step 3a: Dump schema to file
      console.log('   Running pg_dump...');
      const dumpResult = spawnSync('pg_dump', [
        '--schema-only',
        '--no-owner',
        '--no-acl',
        '--encoding=UTF8',
        '-f', tempSchemaFile,
        SOURCE_DB
      ], {
        env: connectionEnv,
        stdio: ['pipe', 'pipe', 'pipe'],
        encoding: 'utf-8'
      });

      if (dumpResult.error) {
        throw dumpResult.error;
      }
      if (dumpResult.status !== 0) {
        console.log('   pg_dump stdout:', dumpResult.stdout);
        console.log('   pg_dump stderr:', dumpResult.stderr);
        throw new Error(`pg_dump failed with exit code ${dumpResult.status}`);
      }

      // Step 3b: Apply schema from file
      console.log('   Running psql to apply schema...');
      const psqlResult = spawnSync('psql', [
        '-q',
        '-f', tempSchemaFile,
        TARGET_DB
      ], {
        env: connectionEnv,
        stdio: ['pipe', 'pipe', 'pipe'],
        encoding: 'utf-8'
      });

      if (psqlResult.error) {
        throw psqlResult.error;
      }
      if (psqlResult.status !== 0) {
        console.log('   psql stdout:', psqlResult.stdout);
        console.log('   psql stderr:', psqlResult.stderr);
        throw new Error(`psql failed with exit code ${psqlResult.status}`);
      }
    } finally {
      // Clean up temp file
      if (existsSync(tempSchemaFile)) {
        unlinkSync(tempSchemaFile);
      }
    }

    // Step 4: Insert test users
    console.log('   Inserting test users...');
    const finalPool = new pg.Pool({
      host: DB_HOST,
      port: parseInt(DB_PORT),
      user: DB_USER,
      password: DB_PASSWORD,
      database: TARGET_DB,
    });

    await finalPool.query(TEST_USERS_SQL);
    await finalPool.end();

    console.log('✅ Test database setup complete!\n');
  } catch (error: any) {
    console.error('❌ Failed to setup test database:', error.message);
    if (error.stderr) {
      console.error('   stderr:', error.stderr.toString());
    }
    if (error.stdout) {
      console.error('   stdout:', error.stdout.toString());
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
