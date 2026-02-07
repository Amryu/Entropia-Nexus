// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getAdminSocieties, countAdminSocieties } from '$lib/server/db';

/**
 * List societies (admin only)
 * GET /api/admin/societies?q=search&page=1&limit=20
 */
export async function GET({ url, locals }) {
  const realUser = locals.session?.realUser || locals.session?.user;

  if (!realUser) {
    return json({ error: 'Not authenticated' }, { status: 401 });
  }

  if (!realUser?.grants?.includes('admin.panel')) {
    return json({ error: 'Only administrators can access this endpoint' }, { status: 403 });
  }

  const searchQuery = url.searchParams.get('q') || '';
  const page = parseInt(url.searchParams.get('page') || '1');
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '20'), 100);
  const offset = Math.max(page - 1, 0) * limit;

  try {
    const [societies, total] = await Promise.all([
      getAdminSocieties(limit, offset, searchQuery),
      countAdminSocieties(searchQuery)
    ]);

    return json({
      societies: societies.map(society => ({
        ...society,
        id: String(society.id),
        leader_id: society.leader_id != null ? String(society.leader_id) : null
      })),
      total,
      page,
      limit,
      totalPages: Math.max(1, Math.ceil(total / limit))
    });
  } catch (error) {
    console.error('Error fetching societies:', error);
    return json({ error: 'Failed to fetch societies' }, { status: 500 });
  }
}
