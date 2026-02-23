// @ts-nocheck
import { error, redirect } from '@sveltejs/kit';

/**
 * Authorization helper functions for server-side access control.
 * Uses the role-based grant system (user.grants array) with backward
 * compatibility fallback to user.administrator during migration.
 */

// --- Helper to check grants on a user object ---

function userHasGrant(user, grantKey) {
  return user?.grants?.includes(grantKey) || false;
}

function userHasAnyGrant(user, ...grantKeys) {
  if (!user?.grants) return false;
  return grantKeys.some(key => user.grants.includes(key));
}

// --- Login / verification ---

/**
 * Check if user is logged in, throw redirect if not
 * @param {Object} locals - Request locals containing session
 * @param {string} [returnUrl] - Optional URL to redirect to after login
 * @throws {Redirect} Redirects to login page
 */
export function requireLogin(locals, returnUrl = null) {
  const user = locals.session?.user;
  if (!user) {
    const loginUrl = returnUrl
      ? `/discord/login?redirect=${encodeURIComponent(returnUrl)}`
      : '/discord/login';
    throw redirect(302, loginUrl);
  }
  return user;
}

/**
 * Check if user is logged in and verified, throw error if not
 * @param {Object} locals - Request locals containing session
 * @param {string} [returnUrl] - Optional URL for return redirect
 * @throws {HttpError} 401 if not logged in, 403 if not verified
 */
export function requireVerified(locals, returnUrl = null) {
  const user = requireLogin(locals, returnUrl);

  if (!user.verified) {
    throw error(403, 'You must be a verified user to access this page. Please verify your Entropia Universe character.');
  }

  return user;
}

// --- Grant-based authorization ---

/**
 * Require a specific grant, throw 403 if not present
 * @param {Object} locals - Request locals containing session
 * @param {string} grantKey - Grant key to check (e.g. 'admin.panel')
 * @throws {HttpError} 403 if user lacks the grant
 */
export function requireGrant(locals, grantKey) {
  const user = requireLogin(locals);
  if (!userHasGrant(user, grantKey)) {
    throw error(403, 'You do not have the required permission.');
  }
  return user;
}

/**
 * Require any of the specified grants, throw 403 if none are present
 * @param {Object} locals - Request locals containing session
 * @param {...string} grantKeys - Grant keys to check
 * @throws {HttpError} 403 if user lacks all specified grants
 */
export function requireAnyGrant(locals, ...grantKeys) {
  const user = requireLogin(locals);
  if (!userHasAnyGrant(user, ...grantKeys)) {
    throw error(403, 'You do not have the required permissions.');
  }
  return user;
}

/**
 * Check if user has a specific grant (returns boolean, doesn't throw)
 * @param {Object} locals - Request locals containing session
 * @param {string} grantKey - Grant key to check
 * @returns {boolean}
 */
export function hasGrant(locals, grantKey) {
  const user = locals.session?.user;
  return userHasGrant(user, grantKey);
}

// --- API-specific login check (returns 401 instead of redirect) ---

/**
 * Check if user is logged in, throw 401 error if not.
 * Use this in API endpoints (+server.js) instead of requireLogin,
 * which throws a redirect unsuitable for JSON API responses.
 * @param {Object} locals - Request locals containing session
 * @throws {HttpError} 401 if not logged in
 */
export function requireLoginAPI(locals) {
  const user = locals.session?.user;
  if (!user) {
    throw error(401, 'Authentication required.');
  }
  return user;
}

/**
 * Check if user is logged in and verified (API version).
 * Use in +server.js endpoints instead of requireVerified.
 * @param {Object} locals - Request locals containing session
 * @throws {HttpError} 401 if not logged in, 403 if not verified
 */
export function requireVerifiedAPI(locals) {
  const user = requireLoginAPI(locals);
  if (!user.verified) {
    throw error(403, 'Verified account required.');
  }
  return user;
}

/**
 * Require a specific grant (API version — throws 401/403, not redirect).
 * Use in +server.js API endpoints.
 * @param {Object} locals - Request locals containing session
 * @param {string} grantKey - Grant key to check (e.g. 'inventory.manage')
 * @throws {HttpError} 401 if not logged in, 403 if not verified or lacks grant
 */
export function requireGrantAPI(locals, grantKey) {
  const user = requireVerifiedAPI(locals);
  if (!userHasGrant(user, grantKey)) {
    throw error(403, 'Permission denied.');
  }
  return user;
}

// --- Admin helpers (use grants with backward compat) ---

/**
 * Check if user is an administrator (has admin.panel grant)
 * @param {Object} locals - Request locals containing session
 * @throws {HttpError} 401 if not logged in, 403 if not admin
 */
export function requireAdmin(locals) {
  const user = requireLogin(locals);

  if (!userHasGrant(user, 'admin.panel') && !user.administrator) {
    throw error(403, 'This page is restricted to administrators.');
  }

  return user;
}

/**
 * Check if user is an administrator (API version - returns 401 instead of redirect)
 * @param {Object} locals - Request locals containing session
 * @throws {HttpError} 401 if not logged in, 403 if not admin
 */
export function requireAdminAPI(locals) {
  const user = requireLoginAPI(locals);

  if (!userHasGrant(user, 'admin.panel') && !user.administrator) {
    throw error(403, 'This endpoint is restricted to administrators.');
  }

  return user;
}

/**
 * Check if user owns a resource or has admin.panel grant
 * @param {Object} locals - Request locals containing session
 * @param {string|bigint} ownerId - Owner ID of the resource
 * @throws {HttpError} 401 if not logged in, 403 if not owner/admin
 */
export function requireOwnerOrAdmin(locals, ownerId) {
  const user = requireLogin(locals);

  const userIdStr = String(user.id);
  const ownerIdStr = String(ownerId);

  if (userIdStr !== ownerIdStr && !userHasGrant(user, 'admin.panel') && !user.administrator) {
    throw error(403, 'You do not have permission to access this resource.');
  }

  return user;
}

// --- OAuth helpers ---

/**
 * Check if the current request is authenticated via OAuth Bearer token.
 * @param {Object} locals - Request locals
 * @returns {boolean}
 */
export function isOAuthRequest(locals) {
  return locals.isOAuth === true;
}

// --- Boolean check helpers ---

/**
 * Get the current user if logged in, or null
 * @param {Object} locals - Request locals containing session
 * @returns {Object|null} User object or null
 */
export function getUser(locals) {
  return locals.session?.user || null;
}

/**
 * Check if user is logged in (returns boolean, doesn't throw)
 * @param {Object} locals - Request locals containing session
 * @returns {boolean}
 */
export function isLoggedIn(locals) {
  return !!locals.session?.user;
}

/**
 * Check if user is verified (returns boolean, doesn't throw)
 * @param {Object} locals - Request locals containing session
 * @returns {boolean}
 */
export function isVerified(locals) {
  const user = locals.session?.user;
  return !!user?.verified;
}

/**
 * Check if user is an administrator (returns boolean, doesn't throw)
 * @param {Object} locals - Request locals containing session
 * @returns {boolean}
 */
export function isAdmin(locals) {
  const user = locals.session?.user;
  return userHasGrant(user, 'admin.panel') || !!user?.administrator;
}
