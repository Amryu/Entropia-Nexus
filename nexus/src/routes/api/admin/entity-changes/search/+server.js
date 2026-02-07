// @ts-nocheck
import { pool } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';

export async function GET({ locals, url }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'Authentication required' }, 401);
  }

  if (!user?.grants?.includes('wiki.approve')) {
    return getResponse({ error: 'Admin access required' }, 403);
  }

  const q = url.searchParams.get('q') || '';
  const type = url.searchParams.get('type') || '';
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '50'), 100);
  const offset = parseInt(url.searchParams.get('offset') || '0');

  try {
    // Build query to find unique entities with their change counts
    // Group by entity type and entity ID (or name for creates without ID)
    let whereConditions = ["state IN ('Draft', 'Pending', 'Approved', 'Denied')"];
    let params = [];
    let paramIndex = 1;

    if (q) {
      whereConditions.push(`data->>'Name' ILIKE $${paramIndex}`);
      params.push(`%${q}%`);
      paramIndex++;
    }

    if (type) {
      whereConditions.push(`entity = $${paramIndex}`);
      params.push(type);
      paramIndex++;
    }

    const whereClause = whereConditions.length > 0
      ? 'WHERE ' + whereConditions.join(' AND ')
      : '';

    // Count total unique entities
    const countQuery = `
      SELECT COUNT(DISTINCT COALESCE(
        (data->>'Id')::text,
        entity || ':' || (data->>'Name')
      )) as total
      FROM changes
      ${whereClause}
    `;

    const countResult = await pool.query(countQuery, params);
    const total = parseInt(countResult.rows[0]?.total || 0);

    // Get paginated results grouped by entity
    const searchQuery = `
      SELECT
        entity as "entityType",
        (data->>'Id')::bigint as "entityId",
        data->>'Name' as "entityName",
        COUNT(*) as "changeCount",
        MIN(created_at) as "firstChange",
        MAX(last_update) as "lastChange"
      FROM changes
      ${whereClause}
      GROUP BY entity, (data->>'Id')::bigint, data->>'Name'
      ORDER BY MAX(last_update) DESC
      LIMIT $${paramIndex} OFFSET $${paramIndex + 1}
    `;

    const searchResult = await pool.query(searchQuery, [...params, limit, offset]);

    return new Response(JSON.stringify({
      results: searchResult.rows.map(r => ({
        entityType: r.entityType,
        entityId: r.entityId,
        entityName: r.entityName,
        changeCount: parseInt(r.changeCount),
        firstChange: r.firstChange,
        lastChange: r.lastChange
      })),
      total,
      limit,
      offset
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    console.error('Failed to search entity changes:', error);
    return getResponse({ error: 'Failed to search entity changes' }, 500);
  }
}
