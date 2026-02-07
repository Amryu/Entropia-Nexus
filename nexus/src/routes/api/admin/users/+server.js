// @ts-nocheck
import { json } from '@sveltejs/kit';
import { searchUsers, listUsers } from '$lib/server/db';

/**
 * Search or list users (admin only)
 * GET /api/admin/users?q=search&page=1&limit=20
 */
export async function GET({ url, locals }) {
  const realUser = locals.session?.realUser || locals.session?.user;

  // Must be logged in and be an admin
  if (!realUser) {
    return json({ error: 'Not authenticated' }, { status: 401 });
  }

  if (!realUser?.grants?.includes('admin.users')) {
    return json({ error: 'Only administrators can access this endpoint' }, { status: 403 });
  }

  const searchQuery = url.searchParams.get('q');
  const page = parseInt(url.searchParams.get('page') || '1');
  const limit = parseInt(url.searchParams.get('limit') || '20');
  const sortBy = url.searchParams.get('sortBy') || 'global_name';
  const sortOrder = url.searchParams.get('sortOrder') || 'ASC';

  try {
    if (searchQuery && searchQuery.trim().length > 0) {
      // Search mode
      const users = await searchUsers(searchQuery.trim(), Math.min(limit, 50));

      // Annotate each result with what matched
      const annotatedUsers = users.map(user => {
        const matches = [];
        const lowerQuery = searchQuery.toLowerCase();

        if (user.eu_name && user.eu_name.toLowerCase().includes(lowerQuery)) {
          matches.push({ field: 'eu_name', label: 'EU Name' });
        }
        if (user.global_name && user.global_name.toLowerCase().includes(lowerQuery)) {
          matches.push({ field: 'global_name', label: 'Discord Name' });
        }
        if (user.username && user.username.toLowerCase().includes(lowerQuery)) {
          matches.push({ field: 'username', label: 'Discord Username' });
        }

        return {
          ...user,
          id: String(user.id),
          matches
        };
      });

      return json({ users: annotatedUsers, mode: 'search' });
    } else {
      // List mode with pagination
      const result = await listUsers(page, Math.min(limit, 100), sortBy, sortOrder);

      return json({
        users: result.users.map(u => ({ ...u, id: String(u.id) })),
        total: result.total,
        page: result.page,
        limit: result.limit,
        totalPages: result.totalPages,
        mode: 'list'
      });
    }
  } catch (error) {
    console.error('Error fetching users:', error);
    return json({ error: 'Failed to fetch users' }, { status: 500 });
  }
}
