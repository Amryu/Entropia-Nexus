// @ts-nocheck
import { pool } from './db.js';

// ---------------------------------------------------------------------------
// In-memory grants cache
// ---------------------------------------------------------------------------

/** How long a per-user cache entry is trusted (ms). */
const GRANTS_CACHE_TTL = 30_000; // 30 seconds

/** How often the poller checks for role/grant changes (ms). */
const GRANTS_POLL_INTERVAL = 30_000; // 30 seconds

/** @type {Map<string, { grants: Set<string>, cachedAt: number }>} userId (string) -> cached entry */
const grantsCache = new Map();

/**
 * Watermark: the most recent assigned_at across user_roles and user_grants
 * observed by the poller.  When a newer value appears the whole cache is
 * flushed because we can't tell which users were affected (and the data is
 * small enough that a full flush is fine).
 * @type {string|null}
 */
let lastKnownWatermark = null;

/** @type {ReturnType<typeof setInterval>|null} */
let pollTimer = null;

/**
 * Clear the entire grants cache.  Call after admin role/grant mutations.
 */
export function clearGrantsCache() {
  grantsCache.clear();
}

/**
 * Start the background poller that watches for role/grant table changes.
 * Safe to call multiple times; only one poller will run.
 */
export function startGrantsPoller() {
  if (pollTimer) return;

  // Run an initial poll immediately so the watermark is seeded
  _pollForChanges().catch(err => console.error('[grants] Initial poll error:', err));

  pollTimer = setInterval(() => {
    _pollForChanges().catch(err => console.error('[grants] Poll error:', err));
  }, GRANTS_POLL_INTERVAL);
  pollTimer.unref();
}

/**
 * Internal: build a fingerprint from all grant-related tables and flush the
 * cache when anything changes.  Covers:
 *  - user_roles / user_grants  (have assigned_at)
 *  - role_grants               (no timestamp → use count + checksum)
 *  - roles                     (parent_id changes affect hierarchy)
 */
async function _pollForChanges() {
  const { rows } = await pool.query(`
    SELECT concat_ws('|',
      (SELECT MAX(assigned_at)::text FROM user_roles),
      (SELECT MAX(assigned_at)::text FROM user_grants),
      (SELECT COUNT(*)::text || ':' || COALESCE(SUM(grant_id * role_id * (CASE WHEN granted THEN 1 ELSE -1 END))::text, '0') FROM role_grants),
      (SELECT COUNT(*)::text || ':' || COALESCE(SUM(COALESCE(parent_id, 0))::text, '0') FROM roles)
    ) AS watermark
  `);
  const watermark = rows[0]?.watermark ?? null;

  if (lastKnownWatermark === null) {
    // First poll — just seed the watermark, don't flush
    lastKnownWatermark = watermark;
    return;
  }

  if (watermark !== lastKnownWatermark) {
    grantsCache.clear();
    lastKnownWatermark = watermark;
  }
}

// ---------------------------------------------------------------------------
// Core query
// ---------------------------------------------------------------------------

const RESOLVE_QUERY = `
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

/**
 * Resolve all effective grants for a user.
 * Priority: user_grants > child role grants > parent role grants.
 *
 * The 'admin' role is treated as a superrole: users with the admin role
 * (directly or via inheritance) automatically receive all grants, unless
 * a user-level override explicitly denies a specific grant.
 *
 * Results are cached in-memory per userId for up to GRANTS_CACHE_TTL.
 * A background poller clears the cache when role/grant data changes.
 *
 * @param {bigint} userId
 * @returns {Promise<Set<string>>} Set of granted permission keys
 */
export async function resolveUserGrants(userId) {
  const key = userId.toString();
  const now = Date.now();

  const cached = grantsCache.get(key);
  if (cached && now - cached.cachedAt < GRANTS_CACHE_TTL) {
    return cached.grants;
  }

  const { rows } = await pool.query(RESOLVE_QUERY, [userId]);

  const grants = new Set();
  for (const row of rows) {
    if (row.granted) {
      grants.add(row.key);
    }
  }

  grantsCache.set(key, { grants, cachedAt: now });
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
