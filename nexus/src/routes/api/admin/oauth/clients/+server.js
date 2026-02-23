// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getAllClientsWithMetrics } from '$lib/server/oauth.js';

/**
 * GET /api/admin/oauth/clients — List all OAuth clients with usage metrics.
 */
export async function GET({ locals }) {
  const realUser = locals.session?.realUser || locals.session?.user;

  if (!realUser) {
    return json({ error: 'Not authenticated' }, { status: 401 });
  }

  if (!realUser?.grants?.includes('admin.panel')) {
    return json({ error: 'Only administrators can access this endpoint' }, { status: 403 });
  }

  try {
    const clients = await getAllClientsWithMetrics();
    return json({ clients });
  } catch (error) {
    console.error('Error fetching OAuth clients:', error);
    return json({ error: 'Failed to fetch OAuth clients' }, { status: 500 });
  }
}
