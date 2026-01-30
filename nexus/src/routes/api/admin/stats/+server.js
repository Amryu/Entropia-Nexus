// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getChangeStats, getTopContributors } from '$lib/server/db';

/**
 * Get admin dashboard statistics
 * GET /api/admin/stats
 */
export async function GET({ locals }) {
  const realUser = locals.session?.realUser || locals.session?.user;

  if (!realUser) {
    return json({ error: 'Not authenticated' }, { status: 401 });
  }

  if (!realUser.administrator) {
    return json({ error: 'Only administrators can access this endpoint' }, { status: 403 });
  }

  try {
    const [changeStats, topContributors] = await Promise.all([
      getChangeStats(),
      getTopContributors(10)
    ]);

    // Aggregate change stats
    const statsByState = {};
    const statsByEntity = {};

    changeStats.forEach(row => {
      // By state
      if (!statsByState[row.state]) {
        statsByState[row.state] = 0;
      }
      statsByState[row.state] += parseInt(row.count);

      // By entity
      if (!statsByEntity[row.entity]) {
        statsByEntity[row.entity] = { total: 0, byState: {} };
      }
      statsByEntity[row.entity].total += parseInt(row.count);
      statsByEntity[row.entity].byState[row.state] = parseInt(row.count);
    });

    return json({
      changes: {
        byState: statsByState,
        byEntity: statsByEntity
      },
      topContributors: topContributors.map(c => ({
        ...c,
        id: String(c.id)
      }))
    });
  } catch (error) {
    console.error('Error fetching stats:', error);
    return json({ error: 'Failed to fetch stats' }, { status: 500 });
  }
}
