-- Migration: Add Test Users
-- These users are used for E2E testing with mock authentication
-- User IDs start with 9000... to avoid conflicts with real Discord IDs

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

-- Note: Run this on the TEST database (nexus_users_test), not production!
