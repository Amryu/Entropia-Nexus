// @ts-nocheck
import { pool } from '$lib/server/db.js';
import { getResponse } from '$lib/util.js';

export async function GET({ locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'Authentication required' }, 401);
  }

  if (!user.administrator) {
    return getResponse({ error: 'Admin access required' }, 403);
  }

  try {
    // Get unique entity types with counts from changes table
    const result = await pool.query(`
      SELECT
        entity as "entityType",
        COUNT(*) as count
      FROM changes
      WHERE state IN ('Draft', 'Pending', 'Approved', 'Denied')
      GROUP BY entity
      ORDER BY entity
    `);

    return new Response(JSON.stringify({
      types: result.rows.map(r => ({
        entityType: r.entityType,
        count: parseInt(r.count)
      }))
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    console.error('Failed to get entity types:', error);
    return getResponse({ error: 'Failed to get entity types' }, 500);
  }
}
