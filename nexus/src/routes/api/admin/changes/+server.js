// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getChangesFiltered, getChangeStats } from '$lib/server/db';

/**
 * Get changes with filters (admin only)
 * GET /api/admin/changes?state=Pending&entity=Weapon&page=1&limit=20
 */
export async function GET({ url, locals }) {
  const realUser = locals.session?.realUser || locals.session?.user;

  if (!realUser) {
    return json({ error: 'Not authenticated' }, { status: 401 });
  }

  if (!realUser?.grants?.includes('wiki.approve')) {
    return json({ error: 'Only administrators can access this endpoint' }, { status: 403 });
  }

  // Parse filters
  const filters = {};

  const state = url.searchParams.get('state');
  if (state) {
    filters.state = state.includes(',') ? state.split(',') : state;
  }

  const entity = url.searchParams.get('entity');
  if (entity) {
    filters.entity = entity.includes(',') ? entity.split(',') : entity;
  }

  const authorId = url.searchParams.get('authorId');
  if (authorId) {
    filters.authorId = BigInt(authorId);
  }

  const reviewedBy = url.searchParams.get('reviewedBy');
  if (reviewedBy) {
    filters.reviewedBy = BigInt(reviewedBy);
  }

  const fromDate = url.searchParams.get('fromDate');
  if (fromDate) {
    filters.fromDate = new Date(fromDate);
  }

  const toDate = url.searchParams.get('toDate');
  if (toDate) {
    filters.toDate = new Date(toDate);
  }

  const search = url.searchParams.get('search');
  if (search) {
    filters.search = search;
  }

  const page = parseInt(url.searchParams.get('page') || '1');
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '20'), 100);

  try {
    const result = await getChangesFiltered(filters, page, limit);

    // Convert BigInts to strings for JSON serialization
    const changes = result.changes.map(c => ({
      ...c,
      id: c.id,
      author_id: String(c.author_id),
      reviewed_by: c.reviewed_by ? String(c.reviewed_by) : null,
      entityName: c.data?.Name || 'Unknown'
    }));

    return json({
      changes,
      total: result.total,
      page: result.page,
      limit: result.limit,
      totalPages: result.totalPages
    });
  } catch (error) {
    console.error('Error fetching changes:', error);
    return json({ error: 'Failed to fetch changes' }, { status: 500 });
  }
}
