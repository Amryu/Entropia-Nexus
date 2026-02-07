// @ts-nocheck
import { json } from '@sveltejs/kit';
import {
  getUserFullDetails,
  getUserMetrics,
  lockUser,
  unlockUser,
  banUser,
  unbanUser,
  expireUserSessions,
  getAdminActions
} from '$lib/server/db';

/**
 * Get user full details with metrics (admin only)
 * GET /api/admin/users/[id]
 */
export async function GET({ params, url, locals }) {
  const realUser = locals.session?.realUser || locals.session?.user;

  if (!realUser) {
    return json({ error: 'Not authenticated' }, { status: 401 });
  }

  if (!realUser?.grants?.includes('admin.users')) {
    return json({ error: 'Only administrators can access this endpoint' }, { status: 403 });
  }

  try {
    const userId = BigInt(params.id);
    const user = await getUserFullDetails(userId);

    if (!user) {
      return json({ error: 'User not found' }, { status: 404 });
    }

    // Get metrics if requested
    let metrics = null;
    if (url.searchParams.get('includeMetrics') === 'true') {
      metrics = await getUserMetrics(userId);
    }

    // Get admin actions for this user if requested
    let actions = null;
    if (url.searchParams.get('includeActions') === 'true') {
      const actionsResult = await getAdminActions({ targetType: 'user', targetId: String(userId) }, 1, 20);
      actions = actionsResult.actions;
    }

    return json({
      user: {
        ...user,
        id: String(user.id),
        locked_by: user.locked_by ? String(user.locked_by) : null,
        banned_by: user.banned_by ? String(user.banned_by) : null
      },
      metrics,
      actions
    });
  } catch (error) {
    console.error('Error fetching user:', error);
    return json({ error: 'Failed to fetch user' }, { status: 500 });
  }
}

/**
 * Update user lock/ban status (admin only)
 * PATCH /api/admin/users/[id]
 * Body: { action: 'lock'|'unlock'|'ban'|'unban', reason?: string, durationDays?: number }
 */
export async function PATCH({ params, request, locals }) {
  const realUser = locals.session?.realUser || locals.session?.user;

  if (!realUser) {
    return json({ error: 'Not authenticated' }, { status: 401 });
  }

  if (!realUser?.grants?.includes('admin.users')) {
    return json({ error: 'Only administrators can access this endpoint' }, { status: 403 });
  }

  try {
    const userId = BigInt(params.id);
    const body = await request.json();
    const { action, reason, durationDays } = body;

    // Prevent self-ban/lock
    if (String(userId) === String(realUser.id)) {
      return json({ error: 'Cannot modify your own account' }, { status: 400 });
    }

    let result;

    switch (action) {
      case 'lock':
        if (!reason) {
          return json({ error: 'Reason is required for locking' }, { status: 400 });
        }
        result = await lockUser(userId, realUser.id, reason);
        break;

      case 'unlock':
        result = await unlockUser(userId, realUser.id);
        break;

      case 'ban':
        if (!reason) {
          return json({ error: 'Reason is required for banning' }, { status: 400 });
        }
        result = await banUser(userId, realUser.id, reason, durationDays || null);
        // Expire all sessions immediately
        await expireUserSessions(userId);
        break;

      case 'unban':
        result = await unbanUser(userId, realUser.id);
        break;

      default:
        return json({ error: 'Invalid action. Must be lock, unlock, ban, or unban' }, { status: 400 });
    }

    if (!result) {
      return json({ error: 'User not found' }, { status: 404 });
    }

    return json({
      success: true,
      user: {
        ...result,
        id: String(result.id),
        locked_by: result.locked_by ? String(result.locked_by) : null,
        banned_by: result.banned_by ? String(result.banned_by) : null
      }
    });
  } catch (error) {
    console.error('Error updating user:', error);
    return json({ error: 'Failed to update user' }, { status: 500 });
  }
}
