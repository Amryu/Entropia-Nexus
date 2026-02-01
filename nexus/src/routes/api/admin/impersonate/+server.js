// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getUserById } from '$lib/server/db';

const IMPERSONATE_COOKIE = 'nexus_impersonate';

/**
 * Start impersonating a user (admin only)
 * POST /api/admin/impersonate
 * Body: { userId: bigint }
 */
export async function POST({ request, cookies, locals }) {
  const realUser = locals.session?.realUser || locals.session?.user;

  // Must be logged in and be an admin
  if (!realUser) {
    return json({ error: 'Not authenticated' }, { status: 401 });
  }

  if (!realUser.administrator) {
    return json({ error: 'Only administrators can impersonate users' }, { status: 403 });
  }

  const body = await request.json();
  const { userId } = body;

  if (!userId) {
    return json({ error: 'userId is required' }, { status: 400 });
  }

  // Look up the user to impersonate
  const targetUser = await getUserById(BigInt(userId));

  if (!targetUser) {
    return json({ error: 'User not found' }, { status: 404 });
  }

  // Don't allow impersonating yourself
  if (String(targetUser.id) === String(realUser.id)) {
    return json({ error: 'Cannot impersonate yourself' }, { status: 400 });
  }

  // Set impersonation cookie
  cookies.set(IMPERSONATE_COOKIE, String(targetUser.id), {
    path: '/',
    httpOnly: true,
    sameSite: 'lax',
    maxAge: 60 * 60 * 4, // 4 hours max
    secure: import.meta.env.MODE !== 'development',
    domain: import.meta.env.VITE_DOMAIN
  });

  return json({
    success: true,
    impersonating: {
      id: String(targetUser.id),
      username: targetUser.username,
      global_name: targetUser.global_name,
      verified: targetUser.verified,
      administrator: targetUser.administrator
    }
  });
}

/**
 * Stop impersonating
 * DELETE /api/admin/impersonate
 */
export async function DELETE({ cookies, locals }) {
  const realUser = locals.session?.realUser || locals.session?.user;

  if (!realUser || !realUser.administrator) {
    return json({ error: 'Not authorized' }, { status: 403 });
  }

  // Must match the same options used when setting the cookie
  cookies.delete(IMPERSONATE_COOKIE, {
    path: '/',
    secure: import.meta.env.MODE !== 'development',
    domain: import.meta.env.VITE_DOMAIN
  });

  return json({ success: true });
}

/**
 * Get current impersonation status
 * GET /api/admin/impersonate
 */
export async function GET({ locals }) {
  const session = locals.session;

  if (!session?.user) {
    return json({ impersonating: false });
  }

  const isImpersonating = !!session.realUser;

  return json({
    impersonating: isImpersonating,
    realUser: isImpersonating ? {
      id: String(session.realUser.id),
      username: session.realUser.username,
      global_name: session.realUser.global_name
    } : null,
    currentUser: {
      id: String(session.user.id),
      username: session.user.username,
      global_name: session.user.global_name
    }
  });
}
