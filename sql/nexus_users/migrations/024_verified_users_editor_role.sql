-- Migration: Assign editor role to all existing verified users
-- Database: nexus_users

BEGIN;

-- Assign the 'editor' role to all verified users who don't already have it
INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u
CROSS JOIN roles r
WHERE u.verified = true
  AND r.name = 'editor'
  AND NOT EXISTS (
    SELECT 1 FROM user_roles ur
    WHERE ur.user_id = u.id AND ur.role_id = r.id
  );

COMMIT;
