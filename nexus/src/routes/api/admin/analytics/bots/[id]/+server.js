// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth.js';
import { pool } from '$lib/server/db.js';
import { reloadBotPatterns } from '$lib/server/route-analytics.js';

/**
 * PATCH /api/admin/analytics/bots/[id]
 * Update a bot pattern (enable/disable, change description).
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
  if (typeof body.pattern === 'string' && body.pattern.trim()) {
    updates.push(`pattern = $${idx++}`);
    values.push(body.pattern.trim());
  }

  if (updates.length === 0) {
    return json({ error: 'No updates provided' }, { status: 400 });
  }

  values.push(id);

  try {
    const { rowCount, rows } = await pool.query(
      `UPDATE bot_patterns SET ${updates.join(', ')} WHERE id = $${idx} RETURNING id, pattern, description, enabled, created_at`,
      values
    );

    if (rowCount === 0) return json({ error: 'Pattern not found' }, { status: 404 });

    await reloadBotPatterns();
    return json({ pattern: rows[0] });
  } catch (e) {
    if (e.code === '23505') {
      return json({ error: 'Pattern already exists' }, { status: 409 });
    }
    console.error('[analytics] Update bot pattern error:', e);
    return json({ error: 'Failed to update pattern' }, { status: 500 });
  }
}

/**
 * DELETE /api/admin/analytics/bots/[id]
 * Delete a bot pattern.
 */
export async function DELETE({ locals, params }) {
  requireAdminAPI(locals);

  const id = parseInt(params.id, 10);
  if (isNaN(id)) return json({ error: 'Invalid ID' }, { status: 400 });

  try {
    const { rowCount } = await pool.query(
      `DELETE FROM bot_patterns WHERE id = $1`, [id]
    );

    if (rowCount === 0) return json({ error: 'Pattern not found' }, { status: 404 });

    await reloadBotPatterns();
    return json({ success: true });
  } catch (e) {
    console.error('[analytics] Delete bot pattern error:', e);
    return json({ error: 'Failed to delete pattern' }, { status: 500 });
  }
}
