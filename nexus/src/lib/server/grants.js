// @ts-nocheck
import { pool } from './db.js';

/**
 * Resolve all effective grants for a user.
 * Priority: user_grants > child role grants > parent role grants.
 *
 * The 'admin' role is treated as a superrole: users with the admin role
 * (directly or via inheritance) automatically receive all grants, unless
 * a user-level override explicitly denies a specific grant.
 *
 * Uses a single recursive CTE query that:
 * 1. Walks role parent chains from user's directly assigned roles
 * 2. Detects if any role in the hierarchy is the 'admin' role
 * 3. If admin: grants all permissions from the grants table
 * 4. Otherwise: collects role grants with depth (child overrides parent)
 * 5. Merges with user-level grant overrides (highest priority)
 *
 * @param {bigint} userId
 * @returns {Promise<Set<string>>} Set of granted permission keys
 */
export async function resolveUserGrants(userId) {
  const query = `
    WITH RECURSIVE role_hierarchy AS (
      -- Start from user's directly assigned roles (depth 1)
      SELECT r.id AS role_id, r.name AS role_name, r.parent_id, 1 AS depth
      FROM user_roles ur
      JOIN roles r ON r.id = ur.role_id
      WHERE ur.user_id = $1

      UNION ALL

      -- Walk up the parent chain (increasing depth)
      SELECT r.id AS role_id, r.name AS role_name, r.parent_id, rh.depth + 1
      FROM role_hierarchy rh
      JOIN roles r ON r.id = rh.parent_id
      WHERE rh.depth < 10  -- prevent infinite loops
    ),
    -- Check if the user has the admin role anywhere in hierarchy
    is_admin AS (
      SELECT EXISTS (
        SELECT 1 FROM role_hierarchy WHERE role_name = 'admin'
      ) AS val
    ),
    -- Non-admin path: resolve role grants with depth priority
    non_admin_grants AS (
      SELECT DISTINCT ON (g.key) g.key, rg.granted
      FROM role_hierarchy rh
      JOIN role_grants rg ON rg.role_id = rh.role_id
      JOIN grants g ON g.id = rg.grant_id
      ORDER BY g.key, rh.depth ASC
    ),
    -- Effective role grants: all grants if admin, otherwise role-specific
    role_grant_resolved AS (
      SELECT g.key, true AS granted
      FROM grants g
      WHERE (SELECT val FROM is_admin)

      UNION ALL

      SELECT key, granted
      FROM non_admin_grants
      WHERE NOT (SELECT val FROM is_admin)
    ),
    -- Get user-level grant overrides
    user_grant_overrides AS (
      SELECT g.key, ug.granted
      FROM user_grants ug
      JOIN grants g ON g.id = ug.grant_id
      WHERE ug.user_id = $1
    )
    -- Final resolution: user overrides take highest priority
    SELECT
      COALESCE(ugo.key, rgr.key) AS key,
      CASE
        WHEN ugo.key IS NOT NULL THEN ugo.granted
        ELSE rgr.granted
      END AS granted
    FROM role_grant_resolved rgr
    FULL OUTER JOIN user_grant_overrides ugo ON ugo.key = rgr.key;
  `;

  const { rows } = await pool.query(query, [userId]);

  const grants = new Set();
  for (const row of rows) {
    if (row.granted) {
      grants.add(row.key);
    }
  }
  return grants;
}

/**
 * Check if a resolved grants set contains a specific grant.
 * @param {Set<string>} grants
 * @param {string} key
 * @returns {boolean}
 */
export function hasGrant(grants, key) {
  return grants.has(key);
}

/**
 * Check if a resolved grants set contains any of the specified grants.
 * @param {Set<string>} grants
 * @param {...string} keys
 * @returns {boolean}
 */
export function hasAnyGrant(grants, ...keys) {
  return keys.some(key => grants.has(key));
}
