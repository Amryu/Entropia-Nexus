// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth';
import { getMatchingRules } from '$lib/server/db';
import { pool } from '$lib/server/db';

export async function GET({ params, locals }) {
  requireAdminAPI(locals);

  const changeResult = await pool.query(
    'SELECT entity, type, data FROM changes WHERE id = $1',
    [parseInt(params.changeId)]
  );

  const change = changeResult.rows[0];
  if (!change) {
    return json({ error: 'Change not found' }, { status: 404 });
  }

  const dataKeys = change.data ? Object.keys(change.data) : [];
  const rules = await getMatchingRules(change.entity, change.type, dataKeys);

  return json({ rules });
}
