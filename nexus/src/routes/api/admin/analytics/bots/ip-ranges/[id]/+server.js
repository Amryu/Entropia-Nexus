// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth.js';
import { pool } from '$lib/server/db.js';
import { reloadBotIpRanges } from '$lib/server/route-analytics.js';

/**
 * PATCH /api/admin/analytics/bots/ip-ranges/[id]
 */
export async function PATCH({ locals, params, request }) {
  requireAdminAPI(locals);
  const id = parseInt(params.id, 10);
  if (isNaN(id)) return json({ error: 'Invalid ID' }, { status: 400 });

  const body = await request.json();
  const updates = [];
  const values = [];
  let idx = 1;

  if (typeof body.enabled === 'boolean') {
    updates.push(`enabled = $${idx++}`);
    values.push(body.enabled);
  }
  if (typeof body.description === 'string') {
    updates.push(`description = $${idx++}`);
    values.push(body.description.trim() || null);
  }
  if (updates.length === 0) return json({ error: 'No updates' }, { status: 400 });

  values.push(id);
  try {
    const { rowCount, rows } = await pool.query(
      `UPDATE bot_ip_ranges SET ${updates.join(', ')} WHERE id = $${idx}
       RETURNING id, cidr::text, description, enabled, created_at`,
      values
    );
    if (rowCount === 0) return json({ error: 'Range not found' }, { status: 404 });
    await reloadBotIpRanges();
    return json({ range: rows[0] });
  } catch (e) {
    console.error('[analytics] Update IP range error:', e);
    return json({ error: 'Failed to update range' }, { status: 500 });
  }
}

/**
 * DELETE /api/admin/analytics/bots/ip-ranges/[id]
 */
export async function DELETE({ locals, params }) {
  requireAdminAPI(locals);
  const id = parseInt(params.id, 10);
  if (isNaN(id)) return json({ error: 'Invalid ID' }, { status: 400 });

  try {
    const { rowCount } = await pool.query(`DELETE FROM bot_ip_ranges WHERE id = $1`, [id]);
    if (rowCount === 0) return json({ error: 'Range not found' }, { status: 404 });
    await reloadBotIpRanges();
    return json({ success: true });
  } catch (e) {
    console.error('[analytics] Delete IP range error:', e);
    return json({ error: 'Failed to delete range' }, { status: 500 });
  }
}
