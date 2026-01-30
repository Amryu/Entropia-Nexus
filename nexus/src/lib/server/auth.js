// @ts-nocheck
import { error, redirect } from '@sveltejs/kit';

/**
 * Authorization helper functions for server-side access control
 */

/**
 * Check if user is logged in, throw 401 if not
 * @param {Object} locals - Request locals containing session
 * @param {string} [returnUrl] - Optional URL to redirect to after login
 * @throws {Redirect} Redirects to login page
 */
export function requireLogin(locals, returnUrl = null) {
  const user = locals.session?.user;
  if (!user) {
    const loginUrl = returnUrl
      ? `/login?redirect=${encodeURIComponent(returnUrl)}`
      : '/login';
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

/**
 * Check if user is an administrator
 * @param {Object} locals - Request locals containing session
 * @throws {HttpError} 401 if not logged in, 403 if not admin
 */
export function requireAdmin(locals) {
  const user = requireLogin(locals);

  if (!user.administrator) {
    throw error(403, 'This page is restricted to administrators.');
  }

  return user;
}

/**
 * Check if user owns a resource or is an admin
 * @param {Object} locals - Request locals containing session
 * @param {string|bigint} ownerId - Owner ID of the resource
 * @throws {HttpError} 401 if not logged in, 403 if not owner/admin
 */
export function requireOwnerOrAdmin(locals, ownerId) {
  const user = requireLogin(locals);

  const userIdStr = String(user.id);
  const ownerIdStr = String(ownerId);

  if (userIdStr !== ownerIdStr && !user.administrator) {
    throw error(403, 'You do not have permission to access this resource.');
  }

  return user;
}

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
  return !!user?.administrator;
}
