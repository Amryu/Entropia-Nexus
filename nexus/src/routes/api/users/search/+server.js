// @ts-nocheck
import { json } from '@sveltejs/kit';
import { searchUsers } from '$lib/server/db';

/**
 * Search users (for verified users to find estate owners, etc.)
 * GET /api/users/search?q=search&limit=10
 *
 * Returns limited user info (id, name, eu_name) - not full user details
 */
export async function GET({ url, locals }) {
  const user = locals.session?.user;

  // Must be logged in and verified
  if (!user) {
    return json({ error: 'Not authenticated' }, { status: 401 });
  }

  if (!user.verified && !user.isAdmin) {
    return json({ error: 'Only verified users can search' }, { status: 403 });
  }

  const searchQuery = url.searchParams.get('q');
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '10'), 20);

  if (!searchQuery || searchQuery.trim().length < 2) {
    return json({ users: [] });
  }

  try {
    const users = await searchUsers(searchQuery.trim(), limit);

    // Return only essential fields for privacy
    const sanitizedUsers = users.map(u => ({
      id: String(u.id),
      global_name: u.global_name,
      username: u.username,
      eu_name: u.eu_name,
      verified: u.verified
    }));

    return json({ users: sanitizedUsers });
  } catch (error) {
    console.error('Error searching users:', error);
    return json({ error: 'Failed to search users' }, { status: 500 });
  }
}
