// @ts-nocheck
import { json } from '@sveltejs/kit';
import { dev } from '$app/environment';
import { createSession, getUserById } from '$lib/server/db';
import crypto from 'crypto';

// Test user IDs for mock authentication (prefixed with _ for SvelteKit compatibility)
const TEST_USERS = {
  verified1: 900000000000000001n,
  verified2: 900000000000000002n,
  verified3: 900000000000000003n,
  unverified1: 900000000000000004n,
  unverified2: 900000000000000005n,
  unverified3: 900000000000000006n,
  admin: 900000000000000007n
};

/**
 * Mock login endpoint for testing purposes.
 * Only available in development/test mode.
 *
 * POST /api/test/login
 * Body: { userId: "verified1" | "verified2" | ... | "admin" }
 */
export async function POST({ request, cookies }) {
  // Only allow mock login in development or test mode
  if (!dev && process.env.NODE_ENV !== 'test') {
    return json({ error: 'Mock login is only available in development/test mode' }, { status: 403 });
  }

  try {
    const body = await request.json();
    const { userId } = body;

    if (!userId || !TEST_USERS[userId]) {
      return json({
        error: 'Invalid user ID. Valid options: ' + Object.keys(TEST_USERS).join(', ')
      }, { status: 400 });
    }

    const testUserId = TEST_USERS[userId];

    // Check if user exists in database
    const user = await getUserById(testUserId);
    if (!user) {
      return json({
        error: `Test user ${userId} not found in database. Please run the migration: sql/nexus_users/migrations/005_add_test_users.sql`
      }, { status: 404 });
    }

    // Generate a random session ID
    const sessionId = crypto.randomBytes(32).toString('hex');

    // Create session with mock tokens (expires in 7 days)
    const expires = Math.floor(Date.now() / 1000) + (60 * 60 * 24 * 7);
    await createSession(testUserId, sessionId, 'mock_access_token', 'mock_refresh_token', expires);

    // Set the session cookie
    const cookieName = import.meta.env.VITE_SESSION_COOKIE_NAME;

    cookies.set(cookieName, sessionId, {
      path: '/',
      httpOnly: true,
      sameSite: 'lax',
      maxAge: 60 * 60 * 24 * 7,
      secure: !dev,
      domain: import.meta.env.VITE_DOMAIN
    });

    return json({
      success: true,
      user: {
        id: user.id.toString(),
        username: user.username,
        global_name: user.global_name,
        verified: user.verified,
        administrator: user.administrator
      }
    });
  } catch (err) {
    console.error('Test login error:', err);
    return json({ error: err.message || 'Unknown error during test login' }, { status: 500 });
  }
}

/**
 * Logout endpoint - clears the session
 * DELETE /api/test/login
 */
export async function DELETE({ cookies }) {
  if (!dev && process.env.NODE_ENV !== 'test') {
    return json({ error: 'Mock logout is only available in development/test mode' }, { status: 403 });
  }

  const cookieName = import.meta.env.VITE_SESSION_COOKIE_NAME;
  cookies.delete(cookieName, { path: '/' });

  return json({ success: true });
}
