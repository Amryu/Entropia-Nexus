// @ts-nocheck
import { json } from '@sveltejs/kit';
import { requireAdminAPI } from '$lib/server/auth.js';
import { pool } from '$lib/server/db.js';
import { reloadBotPatterns } from '$lib/server/route-analytics.js';

/**
 * GET /api/admin/analytics/bots
 * List all bot patterns.
 */
export async function GET({ locals }) {
  requireAdminAPI(locals);

  try {
    const { rows } = await pool.query(
      `SELECT id, pattern, description, enabled, created_at
       FROM bot_patterns
       ORDER BY id`
    );
    return json({ patterns: rows });
  } catch (e) {
    console.error('[analytics] Bot patterns error:', e);
    return json({ error: 'Failed to fetch bot patterns' }, { status: 500 });
  }
}

/**
 * POST /api/admin/analytics/bots
 * Add a new bot pattern.
 */
export async function POST({ locals, request }) {
  requireAdminAPI(locals);

  const body = await request.json();
  const { pattern, description } = body;

  if (!pattern || typeof pattern !== 'string' || pattern.trim().length === 0) {
    return json({ error: 'Pattern is required' }, { status: 400 });
  }

  // Validate that the pattern can be used in a regex
  try {
    new RegExp(pattern.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  } catch {
    return json({ error: 'Invalid pattern' }, { status: 400 });
  }

  try {
    const { rows } = await pool.query(
      `INSERT INTO bot_patterns (pattern, description) VALUES ($1, $2) RETURNING id, pattern, description, enabled, created_at`,
      [pattern.trim(), description?.trim() || null]
    );

    // Reload bot regex in memory
    await reloadBotPatterns();

    return json({ pattern: rows[0] }, { status: 201 });
  } catch (e) {
    if (e.code === '23505') {
      return json({ error: 'Pattern already exists' }, { status: 409 });
    }
    console.error('[analytics] Add bot pattern error:', e);
    return json({ error: 'Failed to add bot pattern' }, { status: 500 });
  }
}
